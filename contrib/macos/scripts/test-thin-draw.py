#!/usr/bin/env python3
"""Compare actual GTK polygon renders in normal and thin draw modes.

Requires GTK2 development headers and Apple's Command Line Tools. A test-only
GTK module captures ghid_render_pixmap() into private PNG/RGB files, without
screen recording or accessibility automation. All sessions use a generated
public fixture and disposable profiles.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--app', type=Path, required=True)
parser.add_argument('--run-parent', type=Path, default=Path('/private/tmp'))
parser.add_argument('--capture-source', type=Path,
                    default=Path(__file__).resolve().parent.parent / 'tests/capture-render.c')
args = parser.parse_args()
app = args.app.resolve()
manifest = app / 'Contents/Resources/build-manifest.json'
opengl = manifest.is_file() and json.loads(manifest.read_text()).get('renderer') == 'OpenGL'
run = Path(tempfile.mkdtemp(prefix='pcb-thin-draw-', dir=args.run_parent))
print('Artifacts: ' + str(run), flush=True)
flags = subprocess.check_output(['/opt/homebrew/bin/pkg-config', '--cflags', 'gtk+-2.0'], text=True)
module = run / 'capture-render.so'
subprocess.run(['/usr/bin/clang', '-std=gnu99', '-Wno-deprecated-declarations',
                '-bundle', '-undefined', 'dynamic_lookup', *shlex.split(flags),
                str(args.capture_source), '-o', str(module)], check=True)
subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-', str(module)], check=True,
               capture_output=True)
board = run / 'polygon.pcb'
board.write_text('''PCB["Thin polygon regression" 20mm 20mm]
Grid[1mm 0 0 0]
Flags("")
Groups("4,5,6,c:1,2,3,s:8:7")
Styles("Signal,10,40,20:Power,25,60,35:Fat,40,60,35:Skinny,8,36,20")
''' + ''.join('Layer(%d "%s")\n(\n%s)\n' % (n, name,
    '''Polygon("clearpoly")
(
  [2mm 2mm] [18mm 2mm] [18mm 18mm] [2mm 18mm]
)
Line[5mm 10mm 15mm 10mm 1mm 0.4mm "clearline"]
''' if n == 4 else '') for n, name in enumerate(
    ['solder', 'gnd-solder', 'vcc-solder', 'component', 'gnd-component',
     'vcc-component', 'unused', 'unused', 'silk', 'silk'], 1)))
initial_hash = hashlib.sha256(board.read_bytes()).hexdigest()
environment = dict(os.environ, PCB_BUNDLE_PROFILE=str(run / 'profile'))
checks = []
process = None

def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)
    print('PASS: ' + name, flush=True)

def wait_for(path):
    deadline = time.monotonic() + 15
    while not path.exists():
        if process.poll() is not None:
            raise RuntimeError('PCB exited: ' + str(process.returncode))
        if time.monotonic() > deadline:
            raise TimeoutError('Missing ' + str(path))
        time.sleep(0.03)

def snapshot(name, *actions):
    marker = run / (name + '.pcb')
    for action in (*actions, 'SaveTo(LayoutAs,%s)' % marker):
        process.stdin.write(action + '\n')
    process.stdin.flush()
    wait_for(marker)
    (run / 'capture-request').write_text(name + '\n')
    wait_for(run / (name + '.done'))
    return (run / (name + '.rgb')).read_bytes(), marker.read_text()

def pixel(data, x, y):
    offset = (y * 320 + x) * 3
    return data[offset:offset+3]

try:
    with (run / 'pcb.log').open('w') as log:
        process = subprocess.Popen([str(app / 'Contents/MacOS/PCB'),
                                    '--gtk-module=' + str(module), '--listen',
                                    '--backup-interval', '0', str(board)], cwd=run,
                                   env=environment, stdin=subprocess.PIPE,
                                   stdout=log, stderr=subprocess.STDOUT, text=True)
        normal, normal_board = snapshot('normal')
        background = pixel(normal, 10, 10)
        check('Normal rendering fills the polygon interior', pixel(normal, 80, 80) != background)
        thin, thin_board = snapshot('thin-poly', 'Display(ToggleThindrawPoly)')
        check('Thin Draw Poly action sets the board flag', 'thindrawpoly' in thin_board)
        if opengl:
            expected = [round(b + (n - b) * 0.25) for b, n in zip(background, pixel(normal, 80, 80))]
            check('OpenGL Thin Draw Poly reduces polygon opacity to one quarter',
                  all(abs(a - b) <= 2 for a, b in zip(pixel(thin, 80, 80), expected)))
        else:
            check('Thin Draw Poly removes the polygon interior fill', pixel(thin, 80, 80) == background)
        check('Thin Draw Poly changes actual GTK pixels', normal != thin)
        check('Thin Draw Poly retains the polygon outline',
              any(pixel(thin, x, 80) != background for x in (31, 32, 33)))
        check('Thin Draw Poly preserves the thick trace', pixel(thin, 160, 165) != background)
        restored, _ = snapshot('restored', 'Display(ToggleThindrawPoly)')
        check('Turning Thin Draw Poly off restores identical pixels', restored == normal)
        all_thin, _ = snapshot('thin-all', 'Display(ToggleThindraw)')
        if opengl:
            check('OpenGL Thin Draw retains quarter-opacity polygons', pixel(all_thin, 80, 80) == pixel(thin, 80, 80))
            check('Thin Draw reduces the trace to its center line', pixel(all_thin, 160, 165) == background)
        else:
            check('Thin Draw also removes the polygon interior fill', pixel(all_thin, 80, 80) == background)
            check('Thin Draw reduces the trace to its center line', pixel(all_thin, 160, 165) == background)
        again, again_board = snapshot('normal-again', 'Display(ToggleThindraw)')
        check('Turning Thin Draw off restores identical pixels', again == normal)
        check('Switching display modes preserves the saved board data', again_board == normal_board)
        process.stdin.write('Quit()\n')
        process.stdin.flush()
        process.wait(timeout=15)
        check('GTK test session exits normally', process.returncode == 0)
        process = None
    export = subprocess.run([str(app / 'Contents/MacOS/PCB'), '-x', 'gerber',
                             '--gerberfile', str(run / 'manufacturing'), str(run / 'thin-poly.pcb')],
                            cwd=run, env=environment, capture_output=True, text=True, timeout=20)
    (run / 'export.log').write_text(export.stdout + export.stderr)
    check('Gerber export from a thin-mode board succeeds', export.returncode == 0)
    check('Gerber export retains filled polygon regions',
          any('G36*' in p.read_text(errors='replace') for p in run.glob('manufacturing*') if p.is_file()))
    check('Input fixture remains unchanged', hashlib.sha256(board.read_bytes()).hexdigest() == initial_hash)
    check('No GTK critical errors or module load failures',
          re.search(r'(?:Gtk|GLib|Gdk|Pango).*-(?:CRITICAL|ERROR)|Failed to load module',
                    (run / 'pcb.log').read_text()) is None)
    (run / 'result.json').write_text(json.dumps(dict(passed=len(checks), checks=checks, app=str(app)), indent=2) + '\n')
    print('%d checks passed; artifacts: %s' % (len(checks), run), flush=True)
finally:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
