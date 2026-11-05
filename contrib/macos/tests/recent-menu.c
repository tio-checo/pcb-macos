/* Test-only GTK module: inspect and activate the real Open Recent submenu. */
#include <gtk/gtk.h>
#include <dlfcn.h>
#include <limits.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

extern int hid_actionl (const char *, ...);
extern void SetChangedFlag (bool);
extern bool ChangeLayoutName (char *);
static char directory[PATH_MAX];
static GtkRecentChooser *chooser;
static const char *menu_label;
static int response, dialogs;

static void find_chooser (GtkWidget *widget)
{
  GList *children, *p;
  if (GTK_IS_MENU_ITEM (widget))
    {
      GtkWidget *submenu = gtk_menu_item_get_submenu (GTK_MENU_ITEM (widget));
      if (submenu && GTK_IS_RECENT_CHOOSER (submenu))
        {
          chooser = GTK_RECENT_CHOOSER (submenu);
          menu_label = gtk_menu_item_get_label (GTK_MENU_ITEM (widget));
        }
      else if (submenu)
        find_chooser (submenu);
    }
  if (!GTK_IS_CONTAINER (widget)) return;
  children = gtk_container_get_children (GTK_CONTAINER (widget));
  for (p = children; p; p = p->next) find_chooser (p->data);
  g_list_free (children);
}

static gboolean answer_dialog (gpointer unused)
{
  GList *windows = gtk_window_list_toplevels (), *p;
  (void) unused;
  for (p = windows; p; p = p->next)
    if (GTK_IS_MESSAGE_DIALOG (p->data) && gtk_widget_get_visible (p->data))
      {
        dialogs++;
        gtk_dialog_response (GTK_DIALOG (p->data), response);
        g_list_free (windows);
        return FALSE;
      }
  g_list_free (windows);
  return TRUE;
}

static gboolean poll_request (gpointer unused)
{
  gchar *request = g_build_filename (directory, "request.ini", NULL);
  GKeyFile *input = g_key_file_new (), *output;
  GList *windows, *p, *items;
  gchar *operation, *path, *tag, *filename, *data;
  guint responder = 0;
  gsize length;
  (void) unused;
  if (!g_key_file_load_from_file (input, request, G_KEY_FILE_NONE, NULL))
    { g_key_file_free (input); g_free (request); return TRUE; }
  unlink (request);
  g_free (request);
  operation = g_key_file_get_string (input, "request", "operation", NULL);
  path = g_key_file_get_string (input, "request", "path", NULL);
  tag = g_key_file_get_string (input, "request", "tag", NULL);
  if (!tag || strspn (tag, "abcdefghijklmnopqrstuvwxyz-0123456789") != strlen (tag))
    g_error ("Invalid recent-menu test request");
  chooser = NULL;
  windows = gtk_window_list_toplevels ();
  for (p = windows; p; p = p->next) find_chooser (p->data);
  g_list_free (windows);
  if (!chooser) { g_error ("Open Recent chooser not found"); }
  dialogs = 0;
  output = g_key_file_new ();
  if (strcmp (operation, "activate") == 0)
    {
      gchar *uri = g_filename_to_uri (path, NULL, NULL);
      response = g_key_file_get_integer (input, "request", "response", NULL);
      if (response) responder = g_timeout_add (10, answer_dialog, NULL);
      /* An unmapped GTK2 menu's set_current_uri() leaves its active widget
       * unchanged. Select and activate the real item, as a pointer click does. */
      GList *children = gtk_container_get_children (GTK_CONTAINER (chooser)), *child;
      gboolean activated = FALSE;
      int position = 0;
      for (child = children; child; child = child->next, position++)
        {
          GtkRecentInfo *info = g_object_get_data (G_OBJECT (child->data), "gtk-recent-info");
          if (info && strcmp (gtk_recent_info_get_uri (info), uri) == 0)
            {
              gtk_menu_set_active (GTK_MENU (chooser), position);
              gtk_menu_item_activate (GTK_MENU_ITEM (child->data));
              activated = TRUE;
              break;
            }
        }
      g_list_free (children);
      g_key_file_set_boolean (output, "menu", "activated", activated);
      if (responder && !dialogs) g_source_remove (responder);
      g_free (uri);
    }
  else if (strcmp (operation, "load") == 0)
    hid_actionl ("LoadFrom", "Layout", path, NULL);
  else if (strcmp (operation, "buffer") == 0)
    hid_actionl ("LoadFrom", "LayoutToBuffer", path, NULL);
  else if (strcmp (operation, "save") == 0)
    { hid_actionl ("SaveTo", "LayoutAs", path, NULL); hid_actionl ("PCBChanged", NULL); }
  else if (strcmp (operation, "dirty") == 0)
    {
      ChangeLayoutName (g_strdup ("Edited board"));
      SetChangedFlag (true);
      hid_actionl ("PCBChanged", NULL);
    }
  else if (strcmp (operation, "inspect") != 0)
    g_error ("Unknown operation %s", operation);
  g_key_file_set_string (output, "menu", "label", menu_label);
  g_key_file_set_integer (output, "menu", "limit", gtk_recent_chooser_get_limit (chooser));
  g_key_file_set_integer (output, "menu", "sort", gtk_recent_chooser_get_sort_type (chooser));
  g_key_file_set_boolean (output, "menu", "tips", gtk_recent_chooser_get_show_tips (chooser));
  g_key_file_set_boolean (output, "menu", "numbers",
                         gtk_recent_chooser_menu_get_show_numbers (GTK_RECENT_CHOOSER_MENU (chooser)));
  g_key_file_set_integer (output, "menu", "dialogs", dialogs);
  items = gtk_recent_chooser_get_items (chooser);
  int i = 0;
  for (p = items; p; p = p->next)
    {
      gchar *key = g_strdup_printf ("uri%d", i++);
      g_key_file_set_string (output, "items", key, gtk_recent_info_get_uri (p->data));
      g_free (key);
      gtk_recent_info_unref (p->data);
    }
  g_key_file_set_integer (output, "menu", "count", i);
  g_list_free (items);
  windows = gtk_window_list_toplevels ();
  for (p = windows; p; p = p->next)
    if (GTK_IS_WINDOW (p->data) && !GTK_IS_DIALOG (p->data))
      {
        const char *title = gtk_window_get_title (GTK_WINDOW (p->data));
        if (title && (g_str_has_suffix (title, " - PCB") ||
                      g_str_has_suffix (title, " - PCB OpenGL (experimental)")))
          g_key_file_set_string (output, "menu", "title", title);
      }
  g_list_free (windows);
  data = g_key_file_to_data (output, &length, NULL);
  filename = g_strdup_printf ("%s/%s.ini", directory, tag);
  if (!g_file_set_contents (filename, data, length, NULL)) g_error ("Cannot write test report");
  g_free (filename); g_free (data); g_free (operation); g_free (path); g_free (tag);
  g_key_file_free (input); g_key_file_free (output);
  return TRUE;
}

G_MODULE_EXPORT void gtk_module_init (gint *argc, gchar ***argv)
{
  Dl_info info;
  (void) argc; (void) argv;
  if (!dladdr ((const void *) gtk_module_init, &info)) g_error ("Cannot locate module");
  g_strlcpy (directory, info.dli_fname, sizeof directory);
  char *slash = strrchr (directory, '/');
  if (!slash) g_error ("Absolute module path required");
  *slash = '\0';
  g_timeout_add (25, poll_request, NULL);
}
