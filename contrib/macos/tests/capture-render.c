#include <gtk/gtk.h>
#include <dlfcn.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

/* Test-only GTK module. Read the actual GTK renderer's offscreen pixmap;
 * no screen recording or accessibility permissions are needed. */
extern GdkPixmap *ghid_render_pixmap(int, int, double, int, int, int);
static char directory[PATH_MAX];

static gboolean capture(gpointer unused)
{
  char request[PATH_MAX], output[PATH_MAX], tag[64];
  FILE *file;
  GdkPixmap *pixmap;
  GdkPixbuf *pixels;
  GError *error = NULL;
  (void) unused;
  snprintf(request, sizeof request, "%s/capture-request", directory);
  file = fopen(request, "r");
  if (!file) return TRUE;
  if (fscanf(file, "%63s", tag) != 1) { fclose(file); return TRUE; }
  fclose(file);
  if (strspn(tag, "abcdefghijklmnopqrstuvwxyz-0123456789") != strlen(tag))
    return TRUE;
  pixmap = ghid_render_pixmap(10000000, 10000000, 62500.0, 320, 320,
                              gdk_visual_get_system()->depth);
  pixels = gdk_pixbuf_get_from_drawable(NULL, pixmap, gdk_colormap_get_system(),
                                       0, 0, 0, 0, 320, 320);
  if (!pixels) g_error("Cannot capture GTK renderer pixmap");
  snprintf(output, sizeof output, "%s/%s.png", directory, tag);
  if (!gdk_pixbuf_save(pixels, output, "png", &error, NULL))
    g_error("Cannot save GTK render: %s", error->message);
  snprintf(output, sizeof output, "%s/%s.rgb", directory, tag);
  file = fopen(output, "wb");
  if (!file) g_error("Cannot write RGB pixels");
  int channels = gdk_pixbuf_get_n_channels(pixels);
  int stride = gdk_pixbuf_get_rowstride(pixels);
  guchar *data = gdk_pixbuf_get_pixels(pixels);
  for (int y = 0; y < 320; ++y)
    for (int x = 0; x < 320; ++x)
      fwrite(data + y * stride + x * channels, 1, 3, file);
  fclose(file);
  g_object_unref(pixels);
  g_object_unref(pixmap);
  unlink(request);
  snprintf(output, sizeof output, "%s/%s.done", directory, tag);
  file = fopen(output, "w");
  if (file) fclose(file);
  return TRUE;
}

G_MODULE_EXPORT void gtk_module_init(gint *argc, gchar ***argv)
{
  Dl_info info;
  (void) argc;
  (void) argv;
  if (!dladdr((const void *) gtk_module_init, &info)) g_error("Cannot locate test module");
  g_strlcpy(directory, info.dli_fname, sizeof directory);
  char *slash = strrchr(directory, '/');
  if (!slash) g_error("Test module path must be absolute");
  *slash = '\0';
  g_timeout_add(25, capture, NULL);
}
