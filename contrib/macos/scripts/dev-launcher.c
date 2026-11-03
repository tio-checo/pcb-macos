/* Development bundle: start PCB with a deterministic, isolated environment. */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#ifndef PROJECT_ROOT
#error PROJECT_ROOT is required
#endif
int main(int argc, char **argv) {
  const char *engine = PROJECT_ROOT "/build/PCBDev.app/Contents/MacOS/PCBEngine";
  char *env[] = {
    "HOME=" PROJECT_ROOT "/build/runtime-home",
    "TMPDIR=" PROJECT_ROOT "/build/runtime-home/tmp/",
    "XDG_CONFIG_HOME=" PROJECT_ROOT "/build/runtime-home/config",
    "XDG_CACHE_HOME=" PROJECT_ROOT "/build/runtime-home/cache",
    "XDG_DATA_HOME=" PROJECT_ROOT "/build/runtime-home/data",
    "PATH=" PROJECT_ROOT "/install/gtk2/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
    "GTK_PATH=/opt/homebrew/lib/gtk-2.0",
    "LC_ALL=C", NULL
  };
  char **args = calloc((size_t)argc + 2, sizeof(*args));
  if (!args) return 1;
  args[0] = (char *)engine;
  if (argc == 1) args[1] = PROJECT_ROOT "/build/gui/LED.pcb";
  else for (int i = 1; i < argc; ++i) args[i] = argv[i];
  if (chdir(PROJECT_ROOT "/build/gui") != 0) { perror("chdir"); return 1; }
  if (!freopen(PROJECT_ROOT "/docs/logs/gui-dev-app.log", "a", stdout)) return 1;
  if (!freopen(PROJECT_ROOT "/docs/logs/gui-dev-app.log", "a", stderr)) return 1;
  execve(engine, args, env);
  perror("execve PCB");
  return 1;
}
