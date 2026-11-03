#!/usr/bin/env python3
"""Exercise PCB's supported --listen interface in a disposable GTK session."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

SUPPORT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = SUPPORT.parent.parent
ROOT = SOURCE_ROOT.parent
(ROOT / 'docs/logs').mkdir(parents=True, exist_ok=True)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--app', type=Path, help='Test a standalone app through its native launcher')
parser.add_argument('--run-parent', type=Path, help='Directory for disposable test sessions')
parser.add_argument('--sandbox', action='store_true', help='Deny runtime reads of Homebrew, MacPorts and the project')
options = parser.parse_args()
APP = options.app.resolve() if options.app else None
parent = options.run_parent.resolve() if options.run_parent else ROOT / 'build'
parent.mkdir(parents=True, exist_ok=True)
RUN = Path(tempfile.mkdtemp(prefix='session-', dir=parent))
PREFIX = []
if options.sandbox:
    if APP is None or APP.is_relative_to(ROOT) or RUN.is_relative_to(ROOT):
        raise SystemExit('--sandbox requires an app and run directory outside the project')
    policy = RUN / 'runtime.sb'
    policy.write_text('(version 1)\n(allow default)\n(deny file-read* '
                      '(subpath "/opt/homebrew") (subpath "/opt/local") '
                      '(subpath ' + json.dumps(str(ROOT)) + '))\n')
    # SIP removes DYLD_* variables when sandbox-exec itself starts. Restore
    # the diagnostic flag in an unprotected test helper, inside the same sandbox.
    helper_source = RUN / 'trace-exec.c'
    helper_source.write_text('#include <stdlib.h>\n#include <unistd.h>\n'
                             'int main(int argc, char **argv) {\n'
                             '  if (argc < 2 || setenv("DYLD_PRINT_LIBRARIES", "1", 1)) return 2;\n'
                             '  execv(argv[1], argv + 1); return 2;\n}\n')
    helper = RUN / 'trace-exec'
    subprocess.run(['/usr/bin/clang', '-Wall', '-Wextra', '-Werror', str(helper_source), '-o', str(helper)], check=True)
    PREFIX = ['/usr/bin/sandbox-exec', '-f', str(policy), str(helper)]
PROFILE = RUN / 'home'
for path in (PROFILE, PROFILE / 'tmp', PROFILE / 'config', PROFILE / 'cache', PROFILE / 'data'):
    path.mkdir(parents=True, exist_ok=True)
ENV = dict(HOME=str(PROFILE), TMPDIR=str(PROFILE / 'tmp') + '/',
           XDG_CONFIG_HOME=str(PROFILE / 'config'), XDG_CACHE_HOME=str(PROFILE / 'cache'),
           XDG_DATA_HOME=str(PROFILE / 'data'), GTK_PATH='/opt/homebrew/lib/gtk-2.0',
           LC_ALL='C', PATH='/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin')
if APP:
    real_home = RUN / 'user-home'
    real_home.mkdir()
    ENV['HOME'] = str(real_home)
    ENV['PCB_BUNDLE_PROFILE'] = str(PROFILE)
    ENV['DYLD_PRINT_LIBRARIES'] = '1'
SOURCE = APP / 'Contents/Resources/examples/LED.pcb' if APP else SOURCE_ROOT / 'example/LED.pcb'
source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
shutil.copyfile(SOURCE, RUN / 'input.pcb')
print(f'Artifacts: {RUN}', flush=True)
ENGINE = APP / 'Contents/MacOS/PCB' if APP else ROOT / 'build/PCBDev.app/Contents/MacOS/PCBEngine'
checks = []
process = None
sequence = 0

def check(name, condition, detail=None):
    if not condition:
        raise AssertionError(name + (': ' + str(detail) if detail else ''))
    checks.append(name)
    print('PASS: ' + name, flush=True)

def records(text, kind):
    return re.findall(r'^\s*' + kind + r'[\[(].*$', text, re.M)

def body(text):
    return '\n'.join(line for line in text.splitlines() if not line.startswith('#'))

def command(*actions):
    if process.poll() is not None:
        raise RuntimeError(f'PCB exited unexpectedly: {process.returncode}')
    for action in actions:
        process.stdin.write(action + '\n')
    process.stdin.flush()

def snapshot(name, *actions):
    # The second save is a barrier: the first file has been closed before the
    # marker is created. This avoids reading a PCB file while it is still written.
    global sequence
    sequence += 1
    output = RUN / (name + '.pcb')
    marker = RUN / f'ack-{sequence:02}.pcb'
    command(*actions, f'SaveTo(LayoutAs,{output})', f'SaveTo(LayoutAs,{marker})')
    deadline = time.monotonic() + 15
    while not marker.exists():
        if process.poll() is not None:
            raise RuntimeError(f'PCB exited during {name}: {process.returncode}')
        if time.monotonic() > deadline:
            raise TimeoutError('PCB did not complete ' + name)
        time.sleep(0.05)
    return output.read_text()

try:
    with (RUN / 'pcb.log').open('w') as log:
        process = subprocess.Popen([*PREFIX, str(ENGINE), '--listen', '--backup-interval', '0', str(RUN / 'input.pcb')],
                                   cwd=RUN, env=ENV, stdin=subprocess.PIPE, stdout=log,
                                   stderr=subprocess.STDOUT, text=True)
        baseline = snapshot('baseline', 'DumpLibrary()')
        n_elements, n_vias = len(records(baseline, 'Element')), len(records(baseline, 'Via'))
        check('GTK session accepts commands after widget initialization', n_elements > 0)
        library_log = (RUN / 'pcb.log').read_text()
        menus = re.search(r'MenuN\s*=\s*(\d+)', library_log)
        check('Installed library is indexed', menus is not None and int(menus.group(1)) > 0)
        check('Library includes RESC1608N and DIP8', all(x in library_log for x in ('RESC1608N', 'DIP8')))

        placed = snapshot('resistor', 'LoadFootprint(RESC1608N,R_TEST,10k)', 'PasteBuffer(ToLayout,20,20,mm)')
        check('Place resistor from library by name', len(records(placed, 'Element')) == n_elements + 1 and '"R_TEST" "10k"' in placed)
        undone = snapshot('undo', 'Undo()')
        check('Undo footprint placement', len(records(undone, 'Element')) == n_elements and '"R_TEST"' not in undone)
        redone = snapshot('redo', 'Redo()')
        check('Redo footprint placement', len(records(redone, 'Element')) == n_elements + 1 and '"R_TEST"' in redone)

        rotated = snapshot('rotated', 'LoadFootprint(DIP8,U_TEST,TEST)',
                           f'SaveTo(PasteBuffer,{RUN / "unrotated.fp"})', 'PasteBuffer(Rotate,1)',
                           f'SaveTo(PasteBuffer,{RUN / "rotated.fp"})', 'PasteBuffer(ToLayout,40,20,mm)')
        check('Rotate and place through-hole footprint', len(records(rotated, 'Element')) == n_elements + 2 and '"U_TEST"' in rotated)
        check('Save footprint from paste buffer', len(records((RUN / 'rotated.fp').read_text(), 'Element')) == 1)

        def pin_delta(path):
            pins = records(path.read_text(), 'Pin')[:2]
            xy = [[float(re.match(r'[-0-9.]+', v).group())
                   for v in pin.split('[', 1)[1].split()[:2]] for pin in pins]
            return (xy[1][0] - xy[0][0], xy[1][1] - xy[0][1])
        before = pin_delta(RUN / 'unrotated.fp')
        after = pin_delta(RUN / 'rotated.fp')
        check('Footprint pin geometry rotates by 90 degrees',
              math.isclose(after[0], before[1]) and math.isclose(after[1], -before[0]))

        removed = snapshot('removed', 'Unselect(All)', 'Select(ElementByName,^R_TEST$)', 'RemoveSelected()')
        check('Select and remove resistor', len(records(removed, 'Element')) == n_elements + 1 and '"R_TEST"' not in removed)
        restored = snapshot('restored', 'Undo()', 'Unselect(All)')
        check('Undo footprint removal', len(records(restored, 'Element')) == n_elements + 2 and '"R_TEST"' in restored)

        via = snapshot('via', 'CreateVia(60,20,mm)')
        check('Create via', len(records(via, 'Via')) == n_vias + 1)
        reopened = snapshot('reopened', f'LoadFrom(Layout,{RUN / "via.pcb"})')
        check('Save and reopen preserves board data', body(via) == body(reopened))
        external = snapshot('external-footprint', 'PasteBuffer(Clear)',
                            f'LoadFrom(ElementToBuffer,{RUN / "rotated.fp"})', 'PasteBuffer(ToLayout,40,40,mm)')
        check('Load saved footprint and place it again', len(records(external, 'Element')) == n_elements + 3)

        # Zoom/Scroll actions ask for pointer coordinates if the pointer has not
        # entered the canvas. Keep those in the manual GUI check.
        view = snapshot('view', 'Display(Redraw)')
        check('GTK redraw command completes', len(records(view, 'Element')) == n_elements + 3)
        library_view = snapshot('library-window', 'DoWindows(Library)')
        check('GTK library window initializes', len(records(library_view, 'Element')) == n_elements + 3)
        if APP:
            check('All bundled library groups are indexed', int(menus.group(1)) >= 53)
            legacy = snapshot('legacy', 'LoadFootprint("CONNECTOR 1 2",J_TEST,HEADER)',
                              'PasteBuffer(ToLayout,60,40,mm)')
            check('Generate and place a legacy m4 footprint',
                  len(records(legacy, 'Element')) == n_elements + 4 and '"J_TEST"' in legacy)
        if APP:
            snapshot('settings', 'SaveSettings()')
            check('PCB settings stay in its own profile, separate from HOME',
                  (PROFILE / '.pcb/settings').is_file() and not (real_home / '.pcb').exists())
        command('Quit()')
        process.wait(timeout=15)
        check('Clean GTK session shutdown', process.returncode == 0)

    render = subprocess.run([*PREFIX, str(ENGINE if APP else ROOT / 'install/gtk2/bin/pcb'), '-x', 'png', '--outfile', str(RUN / 'edited.png'),
                             str(RUN / ('legacy.pcb' if APP else 'view.pcb'))], cwd=RUN, env=ENV, capture_output=True, text=True, timeout=15)
    (RUN / 'export.log').write_text(render.stdout + render.stderr)
    check('Reopened edited board exports to PNG', render.returncode == 0 and (RUN / 'edited.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
    check('Public source board remains unchanged', hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash)
    log_text = (RUN / 'pcb.log').read_text()
    check('No GTK/GLib critical errors in session log', re.search(r'(?:Gtk|GLib|Gdk|Pango).*-(?:CRITICAL|ERROR)', log_text) is None)
    if APP:
        trace = log_text + render.stdout + render.stderr
        check('Runtime loader trace contains bundled GTK Quartz',
              'dyld[' in trace and 'libgtk-quartz-2.0.0.dylib' in trace)
        check('No Homebrew or MacPorts runtime paths in loader trace',
              '/opt/homebrew/' not in trace and '/opt/local/' not in trace)
    result = dict(passed=len(checks), checks=checks, run=str(RUN), library_menus=int(menus.group(1)),
                  original_elements=n_elements, original_vias=n_vias,
                  manual_checks=['zoom and pan', 'file chooser dialogs', 'export dialog'],
                  app=str(APP) if APP else None, runtime_sandbox=options.sandbox)
    (RUN / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    (ROOT / ('docs/logs/bundle-editor-session.json' if APP else 'docs/logs/editor-session.json')).write_text(json.dumps(result, indent=2) + '\n')
    print(f'{len(checks)} checks passed; artifacts: {RUN}', flush=True)
finally:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
