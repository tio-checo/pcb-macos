#import <AppKit/AppKit.h>
#include <gtk/gtk.h>
#include <gdk/gdkquartz.h>
#include <math.h>
static GtkWidget *menu_bar;
static void find_menu(GtkWidget *widget,gpointer unused) {
 (void)unused;
 if(GTK_IS_MENU_BAR(widget))menu_bar=widget;
 if(GTK_IS_CONTAINER(widget))gtk_container_foreach(GTK_CONTAINER(widget),find_menu,NULL);
}
void check_quartz_layout(GtkWidget *drawing,GKeyFile *report,const char *directory,const char *tag) {
 @autoreleasepool {
  GtkWidget *top=gtk_widget_get_toplevel(drawing);
  NSView *canvas=gdk_quartz_window_get_nsview(gtk_widget_get_window(drawing));
  NSView *root=gdk_quartz_window_get_nsview(gtk_widget_get_window(top));
  NSView *glview=[[NSOpenGLContext currentContext] view];
  g_key_file_set_boolean(report,"layout","native-canvas",gdk_window_has_native(gtk_widget_get_window(drawing)));
  g_key_file_set_boolean(report,"layout","separate-view",canvas!=root);
  g_key_file_set_boolean(report,"layout","gl-view",glview==canvas);
  menu_bar=NULL;find_menu(top,NULL);
  gboolean visible=menu_bar && gtk_widget_get_visible(menu_bar) && gtk_widget_get_mapped(menu_bar);
  g_key_file_set_boolean(report,"layout","menu-visible",visible);
  gboolean reachable=FALSE;
  if(visible) {
   gint x=0,y=0;gtk_widget_translate_coordinates(menu_bar,top,5,5,&x,&y);
   NSPoint point=[[root superview] convertPoint:NSMakePoint(x,y) fromView:root];
   NSView *hit=[root hitTest:point];
   reachable=hit!=nil && hit!=canvas;
  }
  g_key_file_set_boolean(report,"layout","menu-hit",reachable);
  NSRect rect=[canvas convertRect:[canvas bounds] toView:root];
  g_key_file_set_boolean(report,"layout","canvas-size",fabs(rect.size.width-drawing->allocation.width)<1&&fabs(rect.size.height-drawing->allocation.height)<1);
  g_key_file_set_double(report,"layout","native-width",rect.size.width);
  g_key_file_set_double(report,"layout","native-height",rect.size.height);
  g_key_file_set_double(report,"layout","native-y",rect.origin.y);
  NSBitmapImageRep *bitmap=[root bitmapImageRepForCachingDisplayInRect:[root bounds]];
  [root cacheDisplayInRect:[root bounds] toBitmapImageRep:bitmap];
  NSData *data=[bitmap representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
  NSString *path=[NSString stringWithFormat:@"%s/%s-layout.png",directory,tag];
  [data writeToFile:path atomically:YES];
 }
}
