#!/usr/bin/env python3
"""Check normal Quit() saves GTK geometry and restores it on the next launch.

Uses the same Quit() action as File -> Quit, a disposable profile and a copy
of the public LED board. A deliberately short initial height forces GTK's
minimum-size allocation to generate a geometry change without accessibility.
Quartz window bounds verify the real window is the same size after restart.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--app', required=True, type=Path)
parser.add_argument('--run-parent', type=Path, default=Path('/private/tmp'))
args = parser.parse_args()
app = args.app.resolve()
args.run_parent.mkdir(parents=True, exist_ok=True)
run = Path(tempfile.mkdtemp(prefix='pcb-window-size-', dir=args.run_parent))
print('Artifacts: ' + str(run), flush=True)
profile = run / 'profile'
(profile / '.pcb').mkdir(parents=True)
preferences = profile / '.pcb/preferences'
preferences.write_text('top-window-width = 1200\ntop-window-height = 1\n')
board = run / 'input.pcb'
shutil.copyfile(app / 'Contents/Resources/examples/LED.pcb', board)
environment = dict(os.environ, PCB_BUNDLE_PROFILE=str(profile))
probe_source = run / 'window-bounds.c'
probe_source.write_text(r'''#include <ApplicationServices/ApplicationServices.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv) {
  if (argc != 2) return 2;
  int target = atoi(argv[1]);
  CFArrayRef windows = CGWindowListCopyWindowInfo(kCGWindowListOptionAll, kCGNullWindowID);
  if (!windows) return 2;
  for (CFIndex i = 0; i < CFArrayGetCount(windows); ++i) {
    CFDictionaryRef item = CFArrayGetValueAtIndex(windows, i);
    int pid = 0, layer = -1;
    CFNumberGetValue(CFDictionaryGetValue(item, kCGWindowOwnerPID), kCFNumberIntType, &pid);
    CFNumberGetValue(CFDictionaryGetValue(item, kCGWindowLayer), kCFNumberIntType, &layer);
    CGRect rect;
    if (pid == target && layer == 0 && CGRectMakeWithDictionaryRepresentation(
          CFDictionaryGetValue(item, kCGWindowBounds), &rect) && rect.size.width > 200) {
      printf("%.0f %.0f\n", rect.size.width, rect.size.height);
      CFRelease(windows); return 0;
    }
  }
  CFRelease(windows); return 1;
}
''')
probe = run / 'window-bounds'
subprocess.run(['/usr/bin/clang', '-Wall', '-Wextra', '-Werror', str(probe_source),
                '-framework', 'ApplicationServices', '-o', str(probe)], check=True)
process = None
checks = []

def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)
    print('PASS: ' + name, flush=True)

def geometry():
    values = dict(re.findall(r'^(top-window-(?:width|height))\s*=\s*(\d+)',
                             preferences.read_text(), re.M))
    return [int(values['top-window-width']), int(values['top-window-height'])]

def session(number):
    global process
    marker = run / ('ready-%d.pcb' % number)
    with (run / ('session-%d.log' % number)).open('w') as log:
        process = subprocess.Popen([str(app / 'Contents/MacOS/PCB'), '--listen',
                                    '--backup-interval', '0', str(board)], cwd=run,
                                   env=environment, stdin=subprocess.PIPE,
                                   stdout=log, stderr=subprocess.STDOUT, text=True)
        process.stdin.write('SaveTo(LayoutAs,%s)\n' % marker)
        process.stdin.flush()
        deadline = time.monotonic() + 20
        previous, stable_since = None, time.monotonic()
        while True:
            if process.poll() is not None:
                raise RuntimeError('Editor exited before readiness: ' + str(process.returncode))
            if time.monotonic() > deadline:
                raise TimeoutError('Editor did not finish startup')
            result = subprocess.run([str(probe), str(process.pid)], capture_output=True, text=True)
            bounds = [int(x) for x in result.stdout.split()] if result.returncode == 0 else None
            if bounds != previous:
                previous, stable_since = bounds, time.monotonic()
            if bounds and marker.exists() and time.monotonic() - stable_since > 0.7:
                break
            time.sleep(0.1)
        process.stdin.write('Quit()\n')
        process.stdin.flush()
        process.wait(timeout=15)
        check('Session %d exits normally through Quit()' % number, process.returncode == 0)
        process = None
    return bounds

try:
    first = session(1)
    saved = geometry()
    check('Quit() writes the GTK minimum-size geometry change', saved[0] > 1 and saved[1] > 1)
    check('Quit() writes the complete preferences file', 'route-styles =' in preferences.read_text())
    second = session(2)
    check('Restart restores the same actual Quartz window size', first == second)
    check('Second Quit() preserves saved GTK dimensions', saved == geometry())
    with (run / 'startup-quit.log').open('w') as log:
        process = subprocess.Popen([str(app / 'Contents/MacOS/PCB'), '--backup-interval', '0',
                                    '--action-string', 'Quit()', str(board)], cwd=run,
                                   env=environment, stdout=log, stderr=subprocess.STDOUT)
        process.wait(timeout=15)
        check('Startup Quit() exits before entering the GTK main loop', process.returncode == 0)
        process = None
    check('Startup Quit() has no GTK critical errors',
          re.search(r'(?:Gtk|GLib|Gdk|Pango).*-(?:CRITICAL|ERROR)',
                    (run / 'startup-quit.log').read_text()) is None)
    for log in run.glob('session-*.log'):
        check(log.name + ' has no GTK critical errors',
              re.search(r'(?:Gtk|GLib|Gdk|Pango).*-(?:CRITICAL|ERROR)', log.read_text()) is None)
    (run / 'result.json').write_text(json.dumps(dict(checks=checks, passed=len(checks),
        first_window=first, restarted_window=second, saved_geometry=saved, app=str(app)), indent=2) + '\n')
    print('%d checks passed; artifacts: %s' % (len(checks), run), flush=True)
finally:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
