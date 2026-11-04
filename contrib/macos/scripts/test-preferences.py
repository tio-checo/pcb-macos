#!/usr/bin/env python3
"""Check Preferences with optional library settings in disposable app profiles."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True, help='Standalone PCB.app to test')
    options = parser.parse_args()
    engine = options.app.resolve() / 'Contents/MacOS/PCB'
    if not engine.is_file():
        parser.error('App does not contain Contents/MacOS/PCB')
    run = Path(tempfile.mkdtemp(prefix='pcb-preferences-'))
    print(f'Artifacts: {run}', flush=True)
    library = run / 'custom footprints'
    library.mkdir()
    cases = {
        'fresh-profile': None,
        'unset-library': '# library-newlib = NULL\n',
        'empty-library': 'library-newlib =\n',
        'configured-library': f'library-newlib = {library}\n',
    }
    for name, preferences in cases.items():
        profile = run / name
        (profile / '.pcb').mkdir(parents=True)
        if preferences is not None:
            (profile / '.pcb/preferences').write_text(preferences)
        env = os.environ.copy()
        env['PCB_BUNDLE_PROFILE'] = str(profile)
        # Use the same action as File -> Preferences, including reopening it.
        result = subprocess.run(
            [str(engine), '--action-string',
             'DoWindows(Preferences);DoWindows(Preferences);Quit()'],
            cwd=profile, env=env, capture_output=True, text=True, timeout=30)
        log = result.stdout + result.stderr
        (run / (name + '.log')).write_text(log)
        if result.returncode != 0:
            raise RuntimeError(f'{name}: PCB exited {result.returncode}; see {run}')
        if re.search(r'(?:Gtk|GLib|Gdk|Pango).*-(?:CRITICAL|ERROR)', log):
            raise RuntimeError(f'{name}: GUI error; see {run}')
        print(f'PASS: {name}', flush=True)
    (run / 'result.json').write_text(json.dumps({'passed': list(cases)}, indent=2) + '\n')


if __name__ == '__main__':
    main()
