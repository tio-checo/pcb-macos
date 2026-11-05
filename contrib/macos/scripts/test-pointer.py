#!/usr/bin/env python3
"""Check Quartz pointer coordinates and modifier keys in GDK or OpenGL PCB."""
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--app', required=True, type=Path)
parser.add_argument('--run-parent', type=Path, default=Path('/private/tmp'))
parser.add_argument('--module-source', type=Path,
                    default=Path(__file__).resolve().parent.parent / 'tests/pointer-events.m')
args = parser.parse_args()
app = args.app.resolve()
run = Path(tempfile.mkdtemp(prefix='pcb-pointer-', dir=args.run_parent))
print('Artifacts: ' + str(run), flush=True)
flags = shlex.split(subprocess.check_output(
    ['/opt/homebrew/bin/pkg-config', '--cflags', 'gtk+-2.0'], text=True))
module = run / 'pointer-events.so'
subprocess.run(['clang', '-Wall', '-Wextra', '-Werror', '-Wno-deprecated-declarations',
                '-bundle', '-undefined', 'dynamic_lookup', *flags, str(args.module_source),
                '-framework', 'AppKit', '-o', str(module)], check=True)
subprocess.run(['codesign', '--force', '--sign', '-', str(module)], check=True,
               capture_output=True)
board = run / 'input.pcb'
shutil.copy2(app / 'Contents/Resources/examples/LED.pcb', board)
original = hashlib.sha256(board.read_bytes()).hexdigest()
(run / 'home').mkdir()
environment = dict(os.environ, HOME=str(run / 'home'), PCB_BUNDLE_PROFILE=str(run / 'profile'))
checks = []
process = None

def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)
    print('PASS ' + name, flush=True)

def request(mode, tag, x=0, y=0):
    (run / 'pointer-request').write_text(f'{mode} {tag} {x} {y}\n')
    deadline = time.monotonic() + 20
    while not (run / (tag + '.done')).exists():
        if process.poll() is not None:
            raise RuntimeError('PCB exited: ' + str(process.returncode))
        if time.monotonic() > deadline:
            raise TimeoutError(tag)
        time.sleep(.03)
    report = configparser.ConfigParser()
    report.read(run / (tag + '.ini'))
    return report

try:
    with (run / 'pcb.log').open('w') as log:
        process = subprocess.Popen([str(app / 'Contents/MacOS/PCB'),
                                    '--gtk-module=' + str(module), '--listen',
                                    '--backup-interval', '0', str(board)], env=environment,
                                   cwd=run, stdin=subprocess.PIPE, stdout=log,
                                   stderr=subprocess.STDOUT, text=True)
        for tag, x, y in [('initial', 210, 140), ('resized', 270, 190), ('moved', 310, 160)]:
            if tag == 'resized':
                request('resize', 'resize', 1300, 850)
            if tag == 'moved':
                request('move', 'move', 180, 160)
            time.sleep(.3)
            request('warp', 'warp-' + tag, x, y)
            time.sleep(.3)
            report = request('check', tag)
            check(tag + ': pointer query matches native drawing-area position',
                  all(report.getint('pointer', 'expected-' + axis) ==
                      report.getint('pointer', 'queried-' + axis) for axis in ('x', 'y')))
            before = report['pcb']['motion']
            check(tag + ': motion establishes valid board coordinates',
                  '-9223372036854775808' not in before)
            for key in ('control-left', 'control-right', 'shift-left', 'shift-right'):
                for phase in ('press', 'hold', 'release'):
                    check(f'{tag}: {key} {phase} preserves pointer board coordinates',
                          report[key][phase] == before)
            check(tag + ': pointer refresh agrees with the motion event',
                  report['pcb']['pointer-query'] == before)
        process.stdin.write('Quit()\n')
        process.stdin.flush()
        process.wait(timeout=15)
        check('PCB quits normally', process.returncode == 0)
        process = None
    text = (run / 'pcb.log').read_text()
    check('No GTK critical or module errors',
          not any(token in text for token in ('-CRITICAL', '-ERROR', 'Failed to load module')))
    check('Input board remains unchanged', hashlib.sha256(board.read_bytes()).hexdigest() == original)
    (run / 'result.json').write_text(json.dumps(dict(app=str(app), passed=len(checks), checks=checks), indent=2) + '\n')
    print(str(len(checks)) + ' checks passed', flush=True)
finally:
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
