#!/usr/bin/env python3
"""Exercise the Lepton bridge and PCB Import() using only public fixtures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

SUPPORT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--app', required=True, type=Path)
parser.add_argument('--lepton-app', type=Path, default=Path('/Applications/LeptonEDA.app'))
parser.add_argument('--run-parent', type=Path)
options = parser.parse_args()
APP = options.app.resolve()
LEPTON = options.lepton_app.resolve()
parent = options.run_parent.resolve() if options.run_parent else SUPPORT.parent.parent.parent / 'build'
parent.mkdir(parents=True, exist_ok=True)
RUN = Path(tempfile.mkdtemp(prefix='import-', dir=parent))
print('Artifacts:', RUN, flush=True)
profile, lepton_profile, home = RUN / 'profile', RUN / 'lepton-profile', RUN / 'user-home'
for path in (profile, lepton_profile, home):
    path.mkdir()
fixture = SUPPORT / 'tests/import.sch'
fixture_hash = hashlib.sha256(fixture.read_bytes()).hexdigest()
schematic_dir = RUN / 'Schematics with spaces'
schematic_dir.mkdir()
schematic = schematic_dir / 'import.sch'
shutil.copy2(fixture, schematic)
alias = RUN / 'Lepton with spaces.app'
alias.symlink_to(LEPTON, target_is_directory=True)
config = profile / 'lepton-app'
config.write_text(str(alias) + '\n')
ENV = dict(HOME=str(home), PCB_BUNDLE_PROFILE=str(profile),
           LEPTON_BUNDLE_PROFILE=str(lepton_profile),
           PATH='/usr/bin:/bin:/usr/sbin:/sbin', LANG='en_US.UTF-8')
BRIDGE = APP / 'Contents/Resources/bin/gnetlist'
checks = []

def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)
    print('PASS:', name, flush=True)

def bridge(label, *sources):
    output = RUN / (label + '.actions')
    result = subprocess.run([str(BRIDGE), '-g', 'pcbfwd', '-o', str(output), '--',
                             *(str(p) for p in sources)], cwd=RUN, env=ENV,
                            capture_output=True, text=True, timeout=30)
    (RUN / (label + '.log')).write_text(result.stdout + result.stderr)
    return result, output.read_text() if output.exists() else ''

result, actions = bridge('netlist', schematic)
check('Bridge finds configured Lepton app through a path with spaces', result.returncode == 0)
check('Backend emits footprint and value for both components',
      'ElementList("Need","D3","SOD123"' in actions and
      'ElementList("Need","R1","RESC1608N","10k")' in actions)
check('Backend quotes punctuation, quotes and backslashes',
      'TVS, \\"test\\"\\\\path' in actions and
      'ElementSetAttr("D3","manufacturer","Test, Inc.")' in actions)
expected = {'INPUT': {'D3-1'}, 'RETURN': {'R1-2'}, 'SIGNAL, (test)': {'D3-2', 'R1-1'}}
for net, pins in expected.items():
    for pin in pins:
        assert 'Netlist("Add",' + json.dumps(net) + ',' + json.dumps(pin) + ')' in actions
check('Backend emits the exact expected connectivity', True)
check('Backend emits all four pin labels', actions.count('ChangePinName(') == 4)
second = schematic_dir / 'second.sch'
second.write_text(schematic.read_text().replace('refdes=D3', 'refdes=D4').replace('refdes=R1', 'refdes=R2'))
result, multi = bridge('multiple-sources', schematic, second)
check('Import accepts multiple schematic files', result.returncode == 0 and multi.count('ElementList("Need",') == 4)
config.unlink()
result, default = bridge('automatic-discovery', schematic)
check('Bridge discovers an installed Lepton app without profile configuration',
      result.returncode == 0 and default == actions)
config.write_text(str(alias) + '\n')

def quoted(value):
    return json.dumps(str(value), ensure_ascii=False)

board = RUN / 'input.pcb'
board.write_text('PCB["Import bridge test" 800000 600000]\n'
                 'Grid[1000 0 0 0]\n'
                 'Attribute("import::src0" ' + quoted(schematic) + ')\n')
process = None
sequence = 0

def snapshot(name, *actions):
    global sequence
    sequence += 1
    target, marker = RUN / (name + '.pcb'), RUN / ('ack-%02d.pcb' % sequence)
    commands = [*actions, 'SaveTo(LayoutAs,' + quoted(target) + ')',
                'SaveTo(LayoutAs,' + quoted(marker) + ')']
    process.stdin.write('\n'.join(commands) + '\n')
    process.stdin.flush()
    deadline = time.monotonic() + 30
    while not marker.exists():
        if process.poll() is not None:
            raise RuntimeError('PCB exited: %s' % process.returncode)
        if time.monotonic() > deadline:
            raise TimeoutError(name)
        time.sleep(.05)
    return target.read_text()

def elements(text):
    result = {}
    for line in text.splitlines():
        if line.startswith('Element['):
            fields = [json.loads(token) for token in re.findall(r'"(?:\\.|[^"\\])*"', line)]
            result[fields[2]] = dict(footprint=fields[1], value=fields[3], header=line)
    return result

def nets(text):
    result = {}
    for match in re.finditer(r'\bNet\(("(?:\\.|[^"\\])*")[^\n]*\)\s*\(\s*(.*?)\n\s*\)', text, re.S):
        result[json.loads(match.group(1))] = set(json.loads(pin) for pin in
                                               re.findall(r'Connect\(("(?:\\.|[^"\\])*")\)', match.group(2)))
    return result

def body(text):
    return '\n'.join(line for line in text.splitlines() if not line.startswith('#'))

try:
    with (RUN / 'pcb.log').open('w') as log:
        process = subprocess.Popen([str(APP / 'Contents/MacOS/PCB'), '--listen',
                                    '--backup-interval', '0', str(board)], cwd=RUN,
                                   env=ENV, stdin=subprocess.PIPE, stdout=log,
                                   stderr=subprocess.STDOUT, text=True)
        initial = snapshot('initial')
        check('Test board starts without components', elements(initial) == {})
        imported = snapshot('imported', 'Import()')
        imported_elements = elements(imported)
        check('Menu Import() obtains the source from the board attribute', set(imported_elements) == {'D3', 'R1'})
        check('Import preserves footprint and escaped value',
              imported_elements['D3']['footprint'] == 'SOD123' and
              imported_elements['D3']['value'] == 'TVS, "test"\\path')
        check('Import transfers component attributes', 'Attribute("manufacturer" "Test, Inc.")' in imported)
        check('Import produces the exact expected PCB netlist', nets(imported) == expected)
        removed = snapshot('removed', 'Unselect(All)', 'Select(ElementByName,^D3$)', 'RemoveSelected()')
        check('D3 is removed from the test board', set(elements(removed)) == {'R1'})
        restored = snapshot('restored', 'Import()')
        check('Import restores deleted D3', set(elements(restored)) == {'D3', 'R1'})
        check('Import preserves existing R1 placement', elements(restored)['R1']['header'] == imported_elements['R1']['header'])
        check('Reimport preserves all expected connections', nets(restored) == expected)

        # A netlister that emits valid partial actions then fails must not alter PCB.
        fake = RUN / 'Failing Lepton.app/Contents/Resources/bin/lepton-netlist'
        fake.parent.mkdir(parents=True)
        fake.write_text('#!/bin/sh\noutput=\nwhile [ "$#" -gt 0 ]; do\n'
                        '  case "$1" in -o) output=$2; shift 2 ;; *) shift ;; esac\n'
                        'done\nprintf \'ElementList(Need,SHOULD_NOT_IMPORT,SOD123,bad)\\n\' > "$output"\nexit 23\n')
        fake.chmod(0o755)
        config.write_text(str(fake.parents[3]) + '\n')
        failed = snapshot('failed-netlister', 'Import()')
        check('Failed netlister cannot apply its partial action file', body(failed) == body(restored))

        config.write_text(str(RUN / 'Missing Lepton.app') + '\n')
        missing = snapshot('missing-lepton', 'Import()')
        check('Unavailable Lepton app leaves the board unchanged', body(missing) == body(restored))
        config.write_text(str(alias) + '\n')
        oversized = schematic_dir / 'oversized.sch'
        oversized.write_text(schematic.read_text().replace('value=10k', 'value=' + 'x' * 300))
        failed = snapshot('oversized-record', 'Import(gnetlist,' + quoted(oversized) + ')')
        check('Oversized backend record is rejected without partial import', body(failed) == body(restored))
        process.stdin.write('Quit()\n')
        process.stdin.flush()
        process.wait(timeout=15)
        check('Test editor shuts down cleanly', process.returncode == 0)
finally:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

log_text = (RUN / 'pcb.log').read_text()
check('Failures provide diagnostics without reading missing action files',
      'pcbfwd: action exceeds PCB' in log_text and
      'PCB import: LeptonEDA.app was not found.' in log_text and
      'Could not open actions file' not in log_text)
check('Import has no GTK or GLib critical errors',
      re.search(r'(?:Gtk|GLib|Gdk|Pango).*-(?:CRITICAL|ERROR)', log_text) is None)
check('Public schematic fixture is unchanged', hashlib.sha256(fixture.read_bytes()).hexdigest() == fixture_hash)
summary = dict(passed=len(checks), checks=checks, app=str(APP), lepton_app=str(LEPTON), run=str(RUN))
(RUN / 'result.json').write_text(json.dumps(summary, indent=2) + '\n')
print('%s import checks passed; artifacts: %s' % (len(checks), RUN), flush=True)
