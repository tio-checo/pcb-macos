/* Test-only GTK module for the real PCB OpenGL renderer and Quartz previews. */
#include <gtk/gtk.h>
#include <gtk/gtkgl.h>
#include <OpenGL/gl.h>
#include <OpenGL/glext.h>
#include <OpenGL/OpenGL.h>
#include <dlfcn.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
extern GdkPixmap *ghid_render_pixmap(int,int,double,int,int,int);
/* Public HID action ABI; this arm64 build configures Coord as long. */
typedef struct {
  char *name; const char *need_coord_msg;
  int (*trigger_cb)(int,char **,long,long);
  const char *description,*syntax;
} TestAction;
extern TestAction *hid_find_action(const char *);
extern void check_quartz_layout(GtkWidget *,GKeyFile *,const char *,const char *);
static char directory[PATH_MAX];
static GtkWidget *drawing;
static void find_drawing(GtkWidget *w,gpointer unused) {
  (void)unused;
  if(GTK_IS_DRAWING_AREA(w) && gtk_widget_is_gl_capable(w) && w->allocation.width>400 && w->allocation.height>200)
    drawing=w;
  if(GTK_IS_CONTAINER(w))gtk_container_foreach(GTK_CONTAINER(w),find_drawing,NULL);
}
static void save_pixels(GdkPixbuf *pixels,const char *tag) {
  char path[PATH_MAX];GError *error=NULL;
  if(!pixels)g_error("No preview pixels");
  snprintf(path,sizeof path,"%s/%s.png",directory,tag);
  if(!gdk_pixbuf_save(pixels,path,"png",&error,NULL))g_error("Save PNG: %s",error->message);
  snprintf(path,sizeof path,"%s/%s.rgb",directory,tag);
  FILE *f=fopen(path,"wb");if(!f)g_error("Cannot save RGB");
  for(int y=0;y<gdk_pixbuf_get_height(pixels);y++)
    for(int x=0;x<gdk_pixbuf_get_width(pixels);x++)
      fwrite(gdk_pixbuf_get_pixels(pixels)+y*gdk_pixbuf_get_rowstride(pixels)+x*gdk_pixbuf_get_n_channels(pixels),1,3,f);
  fclose(f);
}
static gboolean poll_request(gpointer unused) {
  char path[PATH_MAX],mode[32],tag[64];int width,height;
  (void)unused;
  snprintf(path,sizeof path,"%s/gl-request",directory);
  FILE *request=fopen(path,"r");if(!request)return TRUE;
  int n=fscanf(request,"%31s %63s %d %d",mode,tag,&width,&height);fclose(request);
  if(n!=4 || strspn(tag,"abcdefghijklmnopqrstuvwxyz-0123456789")!=strlen(tag))g_error("Bad GL request");
  if(!drawing) {
    GList *tops=gtk_window_list_toplevels();for(GList *p=tops;p;p=p->next)find_drawing(p->data,NULL);g_list_free(tops);
    if(!drawing)return TRUE;
  }
  GKeyFile *report=g_key_file_new();
  GdkGLDrawable *drawable=gtk_widget_get_gl_drawable(drawing);
  GdkGLContext *context=gtk_widget_get_gl_context(drawing);
  if(!strcmp(mode,"resize"))gtk_window_resize(GTK_WINDOW(gtk_widget_get_toplevel(drawing)),width,height);
  else if(!strcmp(mode,"zoom")) {
    TestAction *zoom=hid_find_action("Zoom");
    char factor[32];snprintf(factor,sizeof factor,"%g",width/100.0);char *args[]={factor};
    if(!zoom || zoom->trigger_cb(width==0?0:1,args,10000000L,10000000L)!=0)g_error("Zoom action failed");
  } else if(!strcmp(mode,"preview")) {
    GdkPixmap *pm=ghid_render_pixmap(44450000,41910000,300000.0,width,height,gdk_visual_get_system()->depth);
    if(!pm)g_error("Preview returned NULL");
    GdkPixbuf *pb=gdk_pixbuf_get_from_drawable(NULL,pm,gdk_colormap_get_system(),0,0,0,0,width,height);
    save_pixels(pb,tag);g_object_unref(pb);g_object_unref(pm);
  } else {
    if(!gdk_gl_drawable_gl_begin(drawable,context))g_error("Cannot begin real PCB context");
    g_key_file_set_string(report,"context","vendor",(const char *)glGetString(GL_VENDOR));
    g_key_file_set_string(report,"context","renderer",(const char *)glGetString(GL_RENDERER));
    g_key_file_set_string(report,"context","version",(const char *)glGetString(GL_VERSION));
    GLint accelerated=0,stencil=0;glGetIntegerv(GL_STENCIL_BITS,&stencil);
    CGLDescribePixelFormat(CGLGetPixelFormat(CGLGetCurrentContext()),0,kCGLPFAAccelerated,&accelerated);
    g_key_file_set_integer(report,"context","accelerated",accelerated);
    g_key_file_set_integer(report,"context","stencil",stencil);
    g_key_file_set_integer(report,"context","width",drawing->allocation.width);
    g_key_file_set_integer(report,"context","height",drawing->allocation.height);
    if(!strcmp(mode,"window")) {
      check_quartz_layout(drawing,report,directory,tag);
      GLint old_read;glGetIntegerv(GL_READ_BUFFER,&old_read);
      glReadBuffer(GL_FRONT);glPushClientAttrib(GL_CLIENT_PIXEL_STORE_BIT);
      glPixelStorei(GL_PACK_ALIGNMENT,1);glPixelStorei(GL_PACK_ROW_LENGTH,0);
      glPixelStorei(GL_PACK_SKIP_ROWS,0);glPixelStorei(GL_PACK_SKIP_PIXELS,0);
      int w=drawing->allocation.width,h=drawing->allocation.height;
      GdkPixbuf *pb=gdk_pixbuf_new(GDK_COLORSPACE_RGB,FALSE,8,w,h);
      for(int y=0;y<h;y++)glReadPixels(0,y,w,1,GL_RGB,GL_UNSIGNED_BYTE,gdk_pixbuf_get_pixels(pb)+(h-y-1)*gdk_pixbuf_get_rowstride(pb));
      save_pixels(pb,tag);g_object_unref(pb);glPopClientAttrib();glReadBuffer(old_read);
    } else if(!strcmp(mode,"state")) {
      GLint old_mode;glGetIntegerv(GL_MATRIX_MODE,&old_mode);
      glPushAttrib(GL_ALL_ATTRIB_BITS);glPushClientAttrib(GL_CLIENT_ALL_ATTRIB_BITS);
      glMatrixMode(GL_PROJECTION);glPushMatrix();glLoadIdentity();glTranslated(2,3,4);
      glMatrixMode(GL_MODELVIEW);glPushMatrix();glLoadIdentity();glScaled(2,3,4);
      glMatrixMode(GL_PROJECTION);glViewport(7,11,123,157);
      glPixelStorei(GL_PACK_ALIGNMENT,8);glPixelStorei(GL_PACK_ROW_LENGTH,17);
      glPixelStorei(GL_PACK_SKIP_ROWS,2);glPixelStorei(GL_PACK_SKIP_PIXELS,3);
      GLfloat projection[16],modelview[16],p2[16],m2[16];
      glGetFloatv(GL_PROJECTION_MATRIX,projection);glGetFloatv(GL_MODELVIEW_MATRIX,modelview);
      CGLContextObj previous=CGLGetCurrentContext();
      GdkPixmap *pm=ghid_render_pixmap(44450000,41910000,300000.0,width,height,gdk_visual_get_system()->depth);
      g_key_file_set_boolean(report,"state","preview",pm!=NULL);
      if(pm) {
        GdkPixbuf *pb=gdk_pixbuf_get_from_drawable(NULL,pm,gdk_colormap_get_system(),0,0,0,0,width,height);
        save_pixels(pb,tag);g_object_unref(pb);g_object_unref(pm);
      }
      GLint viewport[4],alignment,row_length,skip_rows,skip_pixels,fb,rb,matrix_mode;
      glGetIntegerv(GL_VIEWPORT,viewport);glGetIntegerv(GL_PACK_ALIGNMENT,&alignment);
      glGetIntegerv(GL_PACK_ROW_LENGTH,&row_length);glGetIntegerv(GL_PACK_SKIP_ROWS,&skip_rows);
      glGetIntegerv(GL_PACK_SKIP_PIXELS,&skip_pixels);glGetIntegerv(GL_FRAMEBUFFER_BINDING_EXT,&fb);
      glGetIntegerv(GL_RENDERBUFFER_BINDING_EXT,&rb);glGetIntegerv(GL_MATRIX_MODE,&matrix_mode);
      glGetFloatv(GL_PROJECTION_MATRIX,p2);glGetFloatv(GL_MODELVIEW_MATRIX,m2);
      g_key_file_set_boolean(report,"state","context",CGLGetCurrentContext()==previous);
      g_key_file_set_boolean(report,"state","viewport",viewport[0]==7&&viewport[1]==11&&viewport[2]==123&&viewport[3]==157);
      g_key_file_set_boolean(report,"state","pixel-store",alignment==8&&row_length==17&&skip_rows==2&&skip_pixels==3);
      g_key_file_set_boolean(report,"state","matrices",memcmp(projection,p2,sizeof p2)==0&&memcmp(modelview,m2,sizeof m2)==0&&matrix_mode==GL_PROJECTION);
      g_key_file_set_boolean(report,"state","framebuffer",fb==0&&rb==0);
      g_key_file_set_boolean(report,"state","zero-width",ghid_render_pixmap(0,0,1,0,1,gdk_visual_get_system()->depth)==NULL);
      glMatrixMode(GL_MODELVIEW);glPopMatrix();glMatrixMode(GL_PROJECTION);glPopMatrix();glMatrixMode(old_mode);
      glPopClientAttrib();glPopAttrib();
    }
    g_key_file_set_integer(report,"context","error",glGetError());
    gdk_gl_drawable_gl_end(drawable);
  }
  gchar *text=g_key_file_to_data(report,NULL,NULL);g_key_file_unref(report);
  snprintf(path,sizeof path,"%s/%s.ini",directory,tag);g_file_set_contents(path,text,-1,NULL);g_free(text);
  snprintf(path,sizeof path,"%s/gl-request",directory);unlink(path);
  snprintf(path,sizeof path,"%s/%s.done",directory,tag);FILE *done=fopen(path,"w");if(done)fclose(done);
  return TRUE;
}
G_MODULE_EXPORT void gtk_module_init(gint *argc,gchar ***argv) {
  Dl_info info;(void)argc;(void)argv;
  if(!dladdr((const void *)gtk_module_init,&info))g_error("Cannot locate OpenGL test module");
  g_strlcpy(directory,info.dli_fname,sizeof directory);char *slash=strrchr(directory,'/');if(!slash)g_error("Absolute module path required");*slash=0;
  g_timeout_add(25,poll_request,NULL);
}
