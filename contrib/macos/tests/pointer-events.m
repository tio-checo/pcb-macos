/* Test-only GTK module: compare real pointer coordinates and modifier events. */
#import <AppKit/AppKit.h>
#include <gtk/gtk.h>
#include <gdk/gdkquartz.h>
#include <gdk/gdkkeysyms.h>
#include <dlfcn.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

extern void ghid_get_pointer (int *, int *);
extern void ghid_get_coords (const char *, long *, long *);
extern gboolean ghid_note_event_location (GdkEventButton *);
static GtkWidget *drawing;
static char directory[PATH_MAX];

static void find_drawing (GtkWidget *widget, gpointer unused)
{
  (void) unused;
  if (GTK_IS_DRAWING_AREA (widget) && widget->allocation.width > 400 &&
      widget->allocation.height > 200)
    drawing = widget;
  if (GTK_IS_CONTAINER (widget))
    gtk_container_foreach (GTK_CONTAINER (widget), find_drawing, NULL);
}

static void save_coords (GKeyFile *report, const char *group, const char *key)
{
  /* Coord is long in the arm64 build; no private GUI structure is duplicated. */
  long x = LONG_MIN, y = LONG_MIN;
  ghid_get_coords (NULL, &x, &y);
  gchar *text = g_strdup_printf ("%ld,%ld", x, y);
  g_key_file_set_string (report, group, key, text);
  g_free (text);
}

static gboolean poll_request (gpointer unused)
{
  char path[PATH_MAX], mode[32], tag[64];
  int x, y;
  (void) unused;
  snprintf (path, sizeof path, "%s/pointer-request", directory);
  FILE *request = fopen (path, "r");
  if (!request) return TRUE;
  int count = fscanf (request, "%31s %63s %d %d", mode, tag, &x, &y);
  fclose (request);
  if (count != 4 || strspn (tag, "abcdefghijklmnopqrstuvwxyz-0123456789") != strlen (tag))
    g_error ("Invalid pointer test request");
  if (!drawing)
    {
      GList *tops = gtk_window_list_toplevels ();
      for (GList *p = tops; p; p = p->next) find_drawing (p->data, NULL);
      g_list_free (tops);
      if (!drawing) return TRUE;
    }
  GtkWidget *top = gtk_widget_get_toplevel (drawing);
  GdkWindow *window = gtk_widget_get_window (drawing);
  GKeyFile *report = g_key_file_new ();
  if (!strcmp (mode, "warp"))
    {
      gint ox, oy, tx, ty;
      gdk_window_get_origin (gtk_widget_get_window (top), &ox, &oy);
      gtk_widget_translate_coordinates (drawing, top, x, y, &tx, &ty);
      gtk_window_present (GTK_WINDOW (top));
      gtk_widget_grab_focus (drawing);
      gdk_display_warp_pointer (gdk_display_get_default (), gdk_screen_get_default (), ox + tx, oy + ty);
    }
  else if (!strcmp (mode, "resize")) gtk_window_resize (GTK_WINDOW (top), x, y);
  else if (!strcmp (mode, "move")) gtk_window_move (GTK_WINDOW (top), x, y);
  else if (!strcmp (mode, "check"))
    {
      @autoreleasepool {
        /* Independent native reference, also valid for a non-native GDK canvas. */
        NSView *view = gdk_quartz_window_get_nsview (gtk_widget_get_window (top));
        NSPoint point = [view convertPoint:[[view window] mouseLocationOutsideOfEventStream] fromView:nil];
        gtk_widget_translate_coordinates (top, drawing, (gint) point.x, (gint) point.y, &x, &y);
      }
      int px, py;
      ghid_get_pointer (&px, &py);
      g_key_file_set_integer (report, "pointer", "expected-x", x);
      g_key_file_set_integer (report, "pointer", "expected-y", y);
      g_key_file_set_integer (report, "pointer", "queried-x", px);
      g_key_file_set_integer (report, "pointer", "queried-y", py);
      GdkModifierType mask;
      gdk_window_get_pointer (window, &px, &py, &mask);
      g_key_file_set_integer (report, "pointer", "raw-gdk-x", px);
      g_key_file_set_integer (report, "pointer", "raw-gdk-y", py);
      GdkEventCrossing enter = {0};
      enter.type = GDK_ENTER_NOTIFY; enter.window = window;
      enter.mode = GDK_CROSSING_NORMAL; enter.detail = GDK_NOTIFY_ANCESTOR;
      gboolean handled;
      g_signal_emit_by_name (drawing, "enter-notify-event", &enter, &handled);
      GdkEventMotion motion = {0};
      motion.type = GDK_MOTION_NOTIFY; motion.window = window;
      motion.x = x; motion.y = y;
      g_signal_emit_by_name (drawing, "motion-notify-event", &motion, &handled);
      save_coords (report, "pcb", "motion");
      const guint keys[] = {GDK_Control_L, GDK_Control_R, GDK_Shift_L, GDK_Shift_R};
      const char *names[] = {"control-left", "control-right", "shift-left", "shift-right"};
      for (unsigned i = 0; i < G_N_ELEMENTS (keys); i++)
        {
          GdkEventKey key = {0};
          key.type = GDK_KEY_PRESS; key.window = window;
          key.keyval = keys[i]; key.is_modifier = 1;
          gtk_widget_event (drawing, (GdkEvent *) &key);
          save_coords (report, names[i], "press");
          key.state = i < 2 ? GDK_CONTROL_MASK : GDK_SHIFT_MASK;
          for (int repeat = 0; repeat < 5; repeat++)
            gtk_widget_event (drawing, (GdkEvent *) &key);
          save_coords (report, names[i], "hold");
          key.type = GDK_KEY_RELEASE;
          gtk_widget_event (drawing, (GdkEvent *) &key);
          save_coords (report, names[i], "release");
        }
      ghid_note_event_location (NULL);
      save_coords (report, "pcb", "pointer-query");
    }
  else g_error ("Unknown pointer test mode");
  gchar *text = g_key_file_to_data (report, NULL, NULL);
  g_key_file_unref (report);
  snprintf (path, sizeof path, "%s/%s.ini", directory, tag);
  g_file_set_contents (path, text, -1, NULL); g_free (text);
  snprintf (path, sizeof path, "%s/pointer-request", directory); unlink (path);
  snprintf (path, sizeof path, "%s/%s.done", directory, tag);
  g_file_set_contents (path, "", 0, NULL);
  return TRUE;
}

G_MODULE_EXPORT void gtk_module_init (gint *argc, gchar ***argv)
{
  (void) argc; (void) argv;
  Dl_info info;
  if (!dladdr ((const void *) gtk_module_init, &info)) g_error ("Module location missing");
  g_strlcpy (directory, info.dli_fname, sizeof directory);
  char *slash = strrchr (directory, '/');
  if (!slash) g_error ("Absolute module path required");
  *slash = 0;
  g_timeout_add (25, poll_request, NULL);
}
