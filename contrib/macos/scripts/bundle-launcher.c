/* Native, relocatable launcher. All runtime paths come from this app bundle. */
#include <mach-o/dyld.h>
#include <sys/stat.h>
#include <pwd.h>
#include <unistd.h>
#include <limits.h>
#include <stdint.h>
#include <errno.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
extern char **environ;
static char resources[PATH_MAX], profile[PATH_MAX];

static void join(char *out, const char *base, const char *suffix) {
  int n = snprintf(out, PATH_MAX, "%s/%s", base, suffix);
  if (n < 0 || n >= PATH_MAX) { fputs("PCB: path too long\n", stderr); exit(2); }
}
static void mkdirs(const char *path) {
  char copy[PATH_MAX];
  if (strlen(path) >= sizeof copy) exit(2);
  strcpy(copy, path);
  for (char *p = copy + 1; ; ++p) {
    if (*p == '/' || !*p) {
      char end = *p; *p = 0;
      if (mkdir(copy, 0700) && errno != EEXIST) { perror(copy); exit(2); }
      struct stat st;
      if (stat(copy, &st) || !S_ISDIR(st.st_mode)) exit(2);
      *p = end;
      if (!end) break;
    }
  }
}
static void envpath(const char *key, const char *base, const char *suffix) {
  char p[PATH_MAX]; join(p, base, suffix);
  if (setenv(key, p, 1)) exit(2);
}
static char *quoted(const char *s) {
  char *out = malloc(strlen(s) * 4 + 3), *p = out;
  if (!out) exit(2);
  *p++ = '\'';
  while (*s) {
    if (*s == '\'') { memcpy(p, "'\\''", 4); p += 4; }
    else *p++ = *s;
    ++s;
  }
  *p++ = '\''; *p = 0;
  return out;
}
static char *helper_command(const char *name, const char *args) {
  char path[PATH_MAX]; join(path, resources, name);
  char *q = quoted(path), *cmd = NULL;
  if (asprintf(&cmd, "/bin/sh %s %s", q, args) < 0) exit(2);
  free(q); return cmd;
}
/* Module caches contain GLib-quoted filenames. Keep the signed bundle read-only. */
static void cache(const char *name, const char *key, uint64_t hash) {
  char source[PATH_MAX], target[PATH_MAX], temporary[PATH_MAX], suffix[128];
  snprintf(suffix, sizeof suffix, "%s.in", name); join(source, resources, suffix);
  snprintf(suffix, sizeof suffix, "cache/%016llx-%s", (unsigned long long)hash, name);
  join(target, profile, suffix); join(temporary, profile, "cache/module-cache-XXXXXX");
  FILE *in = fopen(source, "r"); int fd = mkstemp(temporary);
  if (!in || fd < 0) { perror("PCB module cache"); exit(2); }
  FILE *out = fdopen(fd, "w"); if (!out) exit(2);
  char *line = NULL; size_t cap = 0;
  while (getline(&line, &cap, in) >= 0) {
    char *p = line, *m;
    while ((m = strstr(p, "@RESOURCES@"))) {
      fwrite(p, 1, (size_t)(m - p), out);
      for (const char *r = resources; *r; ++r) {
        if (*r == '"' || *r == '\\') fputc('\\', out);
        fputc(*r, out);
      }
      p = m + strlen("@RESOURCES@");
    }
    fputs(p, out);
  }
  free(line);
  if (ferror(in) || fclose(out) || fclose(in) || rename(temporary, target)) {
    perror("PCB module cache write"); exit(2);
  }
  setenv(key, target, 1);
}
int main(int argc, char **argv) {
  char executable[PATH_MAX], real[PATH_MAX], contents[PATH_MAX], engine[PATH_MAX];
  uint32_t size = sizeof executable;
  if (_NSGetExecutablePath(executable, &size) || !realpath(executable, real)) return 2;
  char *slash = strrchr(real, '/'); if (!slash) return 2; *slash = 0;
  slash = strrchr(real, '/'); if (!slash) return 2; *slash = 0;
  strcpy(contents, real); join(resources, contents, "Resources");
  join(engine, contents, "MacOS/PCBEngine");
  const char *override = getenv("PCB_BUNDLE_PROFILE");
  struct passwd *pw = getpwuid(getuid());
  if (override && override[0] == '/') {
    if (strlen(override) >= sizeof profile) return 2;
    strcpy(profile, override);
  } else if (pw) join(profile, pw->pw_dir, "Library/Application Support/PCB-Quartz");
  else return 2;
  char home[PATH_MAX];
  const char *requested_home = getenv("HOME");
  const char *real_home = (override && override[0] == '/' && requested_home && requested_home[0] == '/')
                         ? requested_home : (pw ? pw->pw_dir : NULL);
  if (!real_home || strlen(real_home) >= sizeof home) return 2;
  strcpy(home, real_home);
  char *lang = strdup(getenv("LANG") ? getenv("LANG") : "en_US.UTF-8");
  int trace = getenv("DYLD_PRINT_LIBRARIES") && !strcmp(getenv("DYLD_PRINT_LIBRARIES"), "1");
  mkdirs(profile);
  const char *dirs[] = {"cache", "config", "data", "tmp"};
  for (unsigned i = 0; i < 4; ++i) { char p[PATH_MAX]; join(p, profile, dirs[i]); mkdirs(p); }
  /* Do not inherit MacPorts, Homebrew, GTK, font or dynamic-loader overrides. */
  while (environ && environ[0]) {
    char *key = strdup(environ[0]); if (!key) return 2;
    char *equal = strchr(key, '='); if (equal) *equal = 0;
    if (unsetenv(key)) { free(key); return 2; }
    free(key);
  }
  setenv("HOME", home, 1); setenv("PCB_BUNDLE_PROFILE", profile, 1);
  setenv("PCB_BUNDLE_RESOURCES", resources, 1); setenv("LANG", lang, 1); free(lang);
  envpath("TMPDIR", profile, "tmp/");
  envpath("XDG_CONFIG_HOME", profile, "config"); envpath("XDG_CACHE_HOME", profile, "cache");
  envpath("XDG_DATA_HOME", profile, "data"); envpath("XDG_DATA_DIRS", resources, "share");
  envpath("XDG_CONFIG_DIRS", resources, "etc");
  envpath("PATH", resources, "bin:/usr/bin:/bin:/usr/sbin:/sbin");
  envpath("GTK_PATH", resources, "lib/gtk-2.0");
  setenv("GTK_DATA_PREFIX", resources, 1); setenv("GTK_EXE_PREFIX", resources, 1);
  envpath("GDK_PIXBUF_MODULEDIR", resources, "lib/gdk-pixbuf-2.0/2.10.0/loaders");
  envpath("GIO_MODULE_DIR", resources, "lib/gio/modules");
  envpath("FONTCONFIG_PATH", resources, "etc/fonts");
  envpath("FONTCONFIG_FILE", resources, "etc/fonts/fonts.conf");
  envpath("PCB_BUNDLE_LOCALE_DIR", resources, "share/locale");
  envpath("PCB_BUNDLE_M4", resources, "bin/m4");
  uint64_t hash = UINT64_C(14695981039346656037);
  for (const unsigned char *p = (const unsigned char *)resources; *p; ++p) hash = (hash ^ *p) * UINT64_C(1099511628211);
  cache("pixbuf-loaders.cache", "GDK_PIXBUF_MODULE_FILE", hash);
  cache("gtk-immodules.cache", "GTK_IM_MODULE_FILE", hash);
  cache("gtkrc", "GTK2_RC_FILES", hash);
  if (trace) setenv("DYLD_PRINT_LIBRARIES", "1", 1);
  if (argc == 1) {
    char log[PATH_MAX]; join(log, profile, "editor.log");
    if (!freopen(log, "a", stdout) || !freopen(log, "a", stderr)) return 2;
    if (chdir(profile)) return 2;
  }
  char **args = calloc((size_t)argc + 10, sizeof(*args)); if (!args) return 2;
  int count = 0, first = 1;
  char menu[PATH_MAX]; join(menu, resources, "share/pcb/gpcb-menu.res");
  args[count++] = engine;
  /* PCB requires -x <exporter> / -p to precede all other options. */
  if (argc > 2 && !strcmp(argv[1], "-x")) {
    args[count++] = argv[1]; args[count++] = argv[2]; first = 3;
  } else if (argc > 1 && !strcmp(argv[1], "-p")) { args[count++] = argv[1]; first = 2; }
  int early = argc > 1 && (!strcmp(argv[1], "-V") || !strcmp(argv[1], "--help") || !strcmp(argv[1], "-h"));
  if (!early) {
    args[count++] = "--pcb-menu"; args[count++] = menu;
    args[count++] = "--lib-command";
    args[count++] = helper_command("share/pcb/QueryLibrary.sh", "'%p' '%f' %a");
    args[count++] = "--lib-contents-command";
    args[count++] = helper_command("share/pcb/ListLibraryContents.sh", "'%p' '%f'");
  }
  for (int i = first; i < argc; ++i) if (strncmp(argv[i], "-psn_", 5)) args[count++] = argv[i];
  execve(engine, args, environ); perror("PCB engine"); return 2;
}
