#!/usr/bin/env python3
"""Exercise the actual GTK Open Recent menu with disposable profiles and boards.

Requires GTK2 development headers and Command Line Tools. A test-only GTK
module inspects the menu and activates entries without accessibility automation.
"""
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from urllib.parse import unquote

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--app', type=Path, required=True)
parser.add_argument('--run-parent', type=Path, default=Path('/private/tmp'))
parser.add_argument('--module-source', type=Path,
                    default=Path(__file__).resolve().parent.parent / 'tests/recent-menu.c')
args = parser.parse_args()
app = args.app.resolve()
run = Path(tempfile.mkdtemp(prefix='pcb-recent-', dir=args.run_parent))
print('Artifacts: ' + str(run), flush=True)
flags = shlex.split(subprocess.check_output(['/opt/homebrew/bin/pkg-config', '--cflags', 'gtk+-2.0'], text=True))
module = run / 'recent-menu.so'
subprocess.run(['/usr/bin/clang', '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                '-Wno-deprecated-declarations', '-bundle', '-undefined', 'dynamic_lookup',
                *flags, str(args.module_source), '-o', str(module)], check=True)
subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-', str(module)], check=True, capture_output=True)
def uri(path):
    return unquote(path.as_uri())

profile, home = run / 'profile', run / 'user-home'
(profile / 'data').mkdir(parents=True)
home.mkdir()
legacy = home / '.recently-used.xbel'
legacy.write_text('Unrelated user history: must not migrate or change\n')
source = app / 'Contents/Resources/examples/LED.pcb'
fixture_hash = hashlib.sha256(source.read_bytes()).hexdigest()
boards = [run / ('board-%02d.pcb' % n) for n in range(12)]
special = run / 'Příliš žluťoučká, "quoted" deska.pcb'
saved, buffer_board = run / 'saved-as.pcb', run / 'buffer-only.pcb'
for p in [*boards, special, buffer_board]:
    shutil.copy2(source, p)
schematic = run / 'unrelated.sch'
schematic.write_text('not a PCB')
# Seed an unrelated schematic to prove that the chooser filters by file type.
xbel = profile / 'data/recently-used.xbel'
xbel.write_text('''<?xml version="1.0"?>
<xbel version="1.0" xmlns:mime="http://www.freedesktop.org/standards/shared-mime-info"
 xmlns:bookmark="http://www.freedesktop.org/standards/desktop-bookmarks">
 <bookmark href="%s" added="2026-11-04T00:00:00Z" modified="2026-11-04T00:00:00Z" visited="2026-11-04T00:00:00Z">
 <info><metadata owner="http://freedesktop.org"><mime:mime-type type="application/x-lepton-schematic"/>
 <bookmark:applications><bookmark:application name="test" exec="test %%f" modified="2026-11-04T00:00:00Z" count="1"/></bookmark:applications>
 </metadata></info></bookmark>
</xbel>''' % uri(schematic))
env = dict(os.environ, PCB_BUNDLE_PROFILE=str(profile), HOME=str(home), LANG='en_US.UTF-8')
checks, process, sequence, logs = [], None, 0, []

def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)
    print('PASS: ' + name, flush=True)

def request(operation='inspect', path=None, response=0):
    global sequence
    sequence += 1
    tag = 'step-%04d' % sequence
    lines = ['[request]', 'tag=' + tag, 'operation=' + operation, 'response=' + str(response)]
    if path is not None:
        lines.append('path=' + str(path))
    temporary = run / 'request.tmp'
    temporary.write_text('\n'.join(lines) + '\n')
    temporary.rename(run / 'request.ini')
    output = run / (tag + '.ini')
    deadline = time.monotonic() + 15
    while not output.exists():
        if process.poll() is not None:
            raise RuntimeError('PCB exited: %s' % process.returncode)
        if time.monotonic() > deadline:
            raise TimeoutError('No menu report for ' + tag)
        time.sleep(0.03)
    report = configparser.ConfigParser(interpolation=None)
    report.read(output)
    return report

def items(report):
    return [unquote(value) for value in report['items'].values()] if report.has_section('items') else []

def settled(predicate):
    deadline = time.monotonic() + 8
    while True:
        report = request()
        if predicate(report):
            return report
        if time.monotonic() > deadline:
            raise AssertionError('Menu did not reach expected state: ' + str(dict(report['menu'])))
        time.sleep(0.06)

def activate(path, response=0):
    # GTK rebuilds menu widgets asynchronously after recent-manager changes.
    deadline = time.monotonic() + 8
    while True:
        report = request('activate', path, response=response)
        if report['menu'].getboolean('activated'):
            return report
        if time.monotonic() > deadline:
            raise AssertionError('Recent menu item not populated: ' + str(path))
        time.sleep(0.08)

def start(board=None, alternate_profile=None):
    global process
    log_path = run / ('session-%d.log' % len(logs))
    logs.append(log_path)
    environment = dict(env)
    if alternate_profile:
        environment['PCB_BUNDLE_PROFILE'] = str(alternate_profile)
    with log_path.open('w') as log:
        process = subprocess.Popen([str(app / 'Contents/MacOS/PCB'), '--gtk-module=' + str(module),
                                    '--listen', '--backup-interval', '0', *([str(board)] if board else [])],
                                   cwd=run, env=environment, stdin=subprocess.PIPE,
                                   stdout=log, stderr=subprocess.STDOUT, text=True)
    return request()

def stop():
    global process
    process.stdin.write('Quit()\n')
    process.stdin.flush()
    process.wait(timeout=15)
    check('GTK session exits normally', process.returncode == 0)
    process = None

try:
    first = start()
    check('File menu uses the same Open Recent label as Lepton', first['menu']['label'] == 'Open Recen_t')
    check('Recent menu starts empty and excludes unrelated schematics', items(first) == [])
    check('Menu matches Lepton: limit 10, MRU order, numbers and path tooltips',
          first['menu'].getint('limit') == 10 and first['menu'].getint('sort') == 1
          and first['menu'].getboolean('tips') and first['menu'].getboolean('numbers'))
    request('load', boards[0])
    check('Normal open adds a board to the actual recent chooser',
          uri(boards[0]) in items(settled(lambda r: uri(boards[0]) in items(r))))
    request('load', special)
    settled(lambda r: uri(special) in items(r))
    activated = activate(boards[0])
    check('Selecting a recent entry opens that board', str(boards[0]) in activated['menu']['title'])
    activated = activate(special)
    check('Menu opens paths with spaces, Unicode, quotes and commas literally', str(special) in activated['menu']['title'])
    request('dirty')
    cancelled = activate(boards[0], response=-6)  # GTK_RESPONSE_CANCEL
    check('Cancel on unsaved changes preserves the current modified board',
          cancelled['menu'].getint('dialogs') == 1 and str(special) in cancelled['menu']['title']
          and cancelled['menu']['title'].startswith('*Edited board'))
    accepted = activate(boards[0], response=-5)  # GTK_RESPONSE_OK
    check('Explicit confirmation permits replacing an unsaved board',
          accepted['menu'].getint('dialogs') == 1 and str(boards[0]) in accepted['menu']['title']
          and not accepted['menu']['title'].startswith('*'))
    request('buffer', buffer_board)
    check('Loading a board into the paste buffer does not add it to recent files',
          uri(buffer_board) not in items(request()))
    bad = run / 'invalid.pcb'
    bad.write_text('This is not a PCB layout\n')
    request('load', bad)
    check('A failed load neither replaces the board nor enters recent files',
          uri(bad) not in items(request()) and str(boards[0]) in request()['menu']['title'])
    for board in boards[1:]:
        request('load', board)
    report = settled(lambda r: len(items(r)) == 10)
    check('The menu displays at most ten boards', len(items(report)) == 10)
    time.sleep(1.1)  # GTK2 MRU timestamps have one-second precision.
    request('load', boards[0])
    report = settled(lambda r: items(r)[0] == uri(boards[0]))
    check('Reopening a board promotes it to the top without duplicates',
          items(report)[0] == uri(boards[0]) and items(report).count(uri(boards[0])) == 1)
    request('save', saved)
    settled(lambda r: uri(saved) in items(r))
    check('Successful Save As adds the new filename', uri(saved) in items(request()))
    stop()
    persisted = {unquote(node.attrib['href']) for node in ET.parse(xbel).getroot().findall('bookmark')}
    check('History is persisted in the isolated PCB profile', uri(boards[0]) in persisted and uri(saved) in persisted)
    check('Failed loads and paste-buffer files are absent from stored history', uri(bad) not in persisted and uri(buffer_board) not in persisted)
    start()
    report = settled(lambda r: uri(saved) in items(r))
    check('Restart restores the recent-file menu', uri(saved) in items(report) and len(items(report)) == 10)
    stale = boards[0]
    stale.unlink()
    report = request('activate', stale)
    check('A deleted recent file cannot replace the current layout or crash PCB',
          process.poll() is None and report['menu']['title'].startswith('Unnamed'))
    stop()
    start(alternate_profile=run / 'separate-profile')
    check('A separate PCB profile has a separate empty recent list', items(request()) == [])
    stop()
    start(board=boards[1], alternate_profile=run / 'command-line-profile')
    check('Opening a board on the command line adds it to recent files',
          uri(boards[1]) in items(settled(lambda r: uri(boards[1]) in items(r))))
    stop()
    # Startup Save As + immediate Quit must flush without entering gtk_main().
    rapid = run / 'rapid-save.pcb'
    quick = subprocess.run([str(app / 'Contents/MacOS/PCB'), '--action-string',
                            'SaveTo(LayoutAs,%s);Quit()' % rapid, str(boards[1])],
                           cwd=run, env=env, capture_output=True, text=True, timeout=20)
    (run / 'rapid.log').write_text(quick.stdout + quick.stderr)
    check('Immediate Save As and Quit persist history before the GTK loop',
          quick.returncode == 0 and uri(rapid) in {unquote(n.attrib['href']) for n in ET.parse(xbel).getroot().findall('bookmark')})
    check('Legacy history in the real HOME is untouched', legacy.read_text() == 'Unrelated user history: must not migrate or change\n')
    check('Bundled public fixture remains unchanged', hashlib.sha256(source.read_bytes()).hexdigest() == fixture_hash)
    all_logs = '\n'.join(p.read_text() for p in logs) + quick.stdout + quick.stderr
    check('No GTK critical errors or test-module load failures',
          re.search(r'(?:Gtk|GLib|Gdk|Pango).*-(?:CRITICAL|ERROR)|Failed to load module', all_logs) is None)
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
