#!/usr/bin/env python3
"""Package the installed GTK2 PCB without modifying installed dependencies."""
from collections import deque
import json
import hashlib
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import tempfile

SUPPORT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = SUPPORT.parent.parent
ROOT = SOURCE_ROOT.parent
VARIANT = os.environ.get('PCB_BUILD_VARIANT', 'gdk')
if VARIANT not in ('gdk', 'opengl'):
    raise SystemExit('PCB_BUILD_VARIANT must be gdk or opengl')
OPENGL = VARIANT == 'opengl'
GTK_PREFIX = Path(os.environ.get('PCB_GTK_PREFIX', '/opt/homebrew')).resolve()
PREFIX = ROOT / ('install/opengl' if OPENGL else 'install/gtk2')
SNAPSHOT = ROOT / ('build/source-opengl' if OPENGL else 'build/source')
NAME = 'PCB-OpenGL' if OPENGL else 'PCB'
OUT = ROOT / 'dist' / (NAME + '.app')
if OUT.exists():
    raise SystemExit(str(OUT) + ' already exists; move it aside before rebuilding')
if subprocess.check_output(['git', '-C', str(SOURCE_ROOT), 'status', '--porcelain']).strip():
    raise SystemExit('The source checkout must be clean')
commit = subprocess.check_output(['git', '-C', str(SOURCE_ROOT), 'rev-parse', 'HEAD'], text=True).strip()
if (SNAPSHOT / '.source-commit').read_text().strip() != commit:
    raise SystemExit('Build snapshot differs from checkout HEAD; rebuild from a fresh snapshot')
if b'PCB_BUNDLE_LOCALE_DIR' not in (PREFIX / 'bin/pcb').read_bytes():
    raise SystemExit('Build PCB with the relocatable-locale patch first')
WORK = Path(tempfile.mkdtemp(prefix='package-', dir=ROOT / 'build'))
APP = WORK / 'PCB.app'
CONT = APP / 'Contents'
RES = CONT / 'Resources'
FW = CONT / 'Frameworks'
for p in (RES, FW, CONT / 'MacOS', RES / 'bin', RES / 'lib/gio/modules'):
    p.mkdir(parents=True, exist_ok=True)

def run(*args):
    return subprocess.check_output([str(a) for a in args], text=True, stderr=subprocess.PIPE).strip()

def tree(src, dst):
    shutil.copytree(src, dst, symlinks=False, dirs_exist_ok=True)

def system(path):
    return path.startswith(('/usr/lib/', '/System/Library/'))

def dependencies(path):
    return [line.strip().split(' (compatibility')[0] for line in run('/usr/bin/otool', '-L', path).splitlines()[1:]]

def rpaths(path):
    lines = run('/usr/bin/otool', '-l', path).splitlines()
    return [lines[i + 2].strip().split('path ', 1)[1].split(' (offset')[0]
            for i, line in enumerate(lines) if 'cmd LC_RPATH' in line]

def resolve(dep, src):
    if dep.startswith('@loader_path/'):
        return (src.parent / dep[len('@loader_path/'):]).resolve()
    if dep.startswith('@rpath/'):
        name = dep[len('@rpath/'):]
        candidates = [Path(p.replace('@loader_path', str(src.parent))) / name for p in rpaths(src)]
        candidates += [src.parent / name, Path('/opt/homebrew/lib') / name]
        for p in candidates:
            if p.is_file():
                return p.resolve()
        raise RuntimeError(f'Unresolved dependency {dep} in {src}')
    if not dep.startswith('/'):
        raise RuntimeError(f'Unsupported dependency {dep} in {src}')
    return Path(dep).resolve()

tree(PREFIX / 'share', RES / 'share')
tree(SUPPORT / 'netlist', RES / 'share/pcb/netlist')
shutil.copy2(SUPPORT / 'scripts/gnetlist-bridge.sh', RES / 'bin/gnetlist')
(RES / 'bin/gnetlist').chmod(0o755)
(CONT / 'share').symlink_to('Resources/share', target_is_directory=True)
for name in ('Default', 'Raleigh', 'Mac'):
    tree(GTK_PREFIX / 'share/themes' / name, RES / 'share/themes' / name)
for name in ('Adwaita', 'hicolor'):
    tree(Path('/opt/homebrew/share/icons') / name, RES / 'share/icons' / name)
tree('/opt/homebrew/share/mime', RES / 'share/mime')
tree('/opt/homebrew/etc/fonts/conf.d', RES / 'etc/fonts/conf.d')
fonts = Path('/opt/homebrew/etc/fonts/fonts.conf').read_text()
fonts = re.sub(r'\s*<cachedir>/opt/homebrew/[^<]+</cachedir>', '', fonts)
(RES / 'etc/fonts/fonts.conf').write_text(fonts)
(RES / 'examples').mkdir()
shutil.copy2(SOURCE_ROOT / 'example/LED.pcb', RES / 'examples/LED.pcb')
# Use explicit module caches; never consult Homebrew at runtime.
modules = [(GTK_PREFIX / 'lib/gtk-2.0/2.10.0/immodules', 'lib/gtk-2.0/2.10.0/immodules'),
           (GTK_PREFIX / 'lib/gtk-2.0/2.10.0/printbackends', 'lib/gtk-2.0/2.10.0/printbackends'),
           ('/opt/homebrew/lib/gdk-pixbuf-2.0/2.10.0/loaders', 'lib/gdk-pixbuf-2.0/2.10.0/loaders')]
roots = [(PREFIX / 'bin/pcb', CONT / 'MacOS/PCBEngine'),
         (Path('/opt/homebrew/opt/m4/bin/m4'), RES / 'bin/m4')]
for directory, relative in modules:
    for p in sorted(Path(directory).glob('*.so')):
        roots.append((p, RES / relative / p.name))
for source, name, relative in [(GTK_PREFIX / 'lib/gtk-2.0/2.10.0/immodules.cache', 'gtk-immodules.cache', 'lib/gtk-2.0/2.10.0/immodules'),
                               ('/opt/homebrew/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache', 'pixbuf-loaders.cache', 'lib/gdk-pixbuf-2.0/2.10.0/loaders')]:
    text = '\n'.join(line for line in Path(source).read_text().splitlines() if not line.startswith('#')) + '\n'
    text = re.sub(r'"/[^"\n]+/([^/"\n]+\.(?:so|dylib))"',
                  lambda m: f'"@RESOURCES@/{relative}/{m.group(1)}"', text)
    text = re.sub(r'"/[^"\n]+/share/locale"', '"@RESOURCES@/share/locale"', text)
    if '/opt/homebrew/' in text or str(GTK_PREFIX) + '/' in text:
        raise RuntimeError('Unrelocated module cache: ' + name)
    (RES / (name + '.in')).write_text(text)
(RES / 'gtkrc.in').write_text('gtk-theme-name="Raleigh"\ngtk-icon-theme-name="Adwaita"\ngtk-font-name="Sans 10"\n')
# GTK catalogs are data, not library roots.
for p in (GTK_PREFIX / 'share/locale').glob('*/LC_MESSAGES/*.mo'):
    if p.name in ('gtk20.mo', 'gtk20-properties.mo', 'glib20.mo', 'atk10.mo', 'gdk-pixbuf.mo'):
        dst = RES / 'share/locale' / p.relative_to(GTK_PREFIX / 'share/locale')
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)
# The legacy m4 helpers must retain spaces in colon-separated library paths.
for name in ('QueryLibrary.sh', 'ListLibraryContents.sh'):
    p = RES / 'share/pcb' / name
    text = p.read_text()
    text = text.replace('SearchPath=`echo "$1" | tr \':\' \' \'`', 'SearchPath="$1"')
    text = text.replace('for dir in $SearchPath; do', 'old_IFS=$IFS\nIFS=:\nset -f\nfor dir in $SearchPath; do\n\tIFS=$old_IFS')
    text = text.replace('M4=/usr/bin/gm4', 'M4="${PCB_BUNDLE_M4:-/usr/bin/m4}"')
    text = text.replace('PATH=$PATH:`dirname $0`', 'PATH="$PATH:$(dirname "$0")"')
    text = text.replace('$M4 -R $name -', '"$M4" -R "$name" -')
    text = text.replace('[ -r $name ]', '[ -r "$name" ]').replace('cat $name', 'cat "$name"')
    p.write_text(text)
# Compile a launcher with no project path baked into it.
launcher = WORK / 'PCB-launcher'
subprocess.run(['/usr/bin/clang', '-std=c99', '-Wall', '-Wextra', '-Werror',
                '-Wl,-headerpad_max_install_names',
                *(['-DPCB_PROFILE_DIR="Library/Application Support/PCB-OpenGL-Quartz"'] if OPENGL else []), str(SUPPORT / 'scripts/bundle-launcher.c'), '-o', str(launcher)], check=True)
roots.append((launcher, CONT / 'MacOS/PCB'))
# Collect both static dependencies and dynamic modules. Real paths deduplicate aliases.
queue = deque(roots)
sources, destinations, formulas = {}, {}, set()
while queue:
    original, dst = queue.popleft()
    src = original.resolve()
    if src in sources:
        continue
    if dst in destinations and destinations[dst] != src:
        raise RuntimeError('Library filename collision: ' + str(dst))
    if not src.is_file():
        raise RuntimeError('Missing library: ' + str(src))
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    dst.chmod(0o755)
    sources[src], destinations[dst] = dst, src
    if src.parent.name == 'lib' and ((src.parent.parent / 'INSTALL_RECEIPT.json').exists() or (src.parent.parent / '.brew').is_dir()):
        formulas.add(src.parent.parent)
    if '/Cellar/' in str(src):
        formulas.add(Path(*src.parts[:src.parts.index('Cellar') + 3]))
    for dep in dependencies(src):
        if system(dep):
            continue
        target = resolve(dep, src)
        if target != src:
            queue.append((target, FW / target.name))
# Rewrite only bundle copies, including dynamic modules and their own install IDs.
for dst, src in destinations.items():
    changes = []
    for dep in dependencies(src):
        if system(dep):
            continue
        target = resolve(dep, src)
        if target == src:
            changes += ['-id', '@rpath/' + dst.name]
        else:
            relative = os.path.relpath(sources[target], dst.parent)
            changes += ['-change', dep, '@loader_path/' + relative]
    for value in rpaths(src):
        changes += ['-delete_rpath', value]
    if changes:
        subprocess.run(['/usr/bin/install_name_tool', *changes, str(dst)], check=True, capture_output=True)
# Include upstream artwork as an icns icon.
iconset = WORK / 'PCB.iconset'
iconset.mkdir()
base_icon = WORK / 'icon.png'
subprocess.run(['/opt/homebrew/bin/rsvg-convert', '-w', '1024', '-h', '1024', '-o', str(base_icon), str(SOURCE_ROOT / 'data/pcb.svg')], check=True)
for size in (16, 32, 128, 256, 512):
    for scale in (1, 2):
        name = f'icon_{size}x{size}' + ('@2x' if scale == 2 else '') + '.png'
        run('/usr/bin/sips', '-z', size * scale, size * scale, base_icon, '--out', iconset / name)
run('/usr/bin/iconutil', '-c', 'icns', iconset, '-o', RES / 'PCB.icns')
commit = run('git', '-C', SOURCE_ROOT, 'rev-parse', 'HEAD')
info = dict(CFBundleExecutable='PCB', CFBundleIdentifier=('local.geda-pcb.OpenGL.Quartz' if OPENGL else 'local.geda-pcb.Quartz'), CFBundleName=NAME,
            CFBundleDisplayName=NAME, CFBundlePackageType='APPL', CFBundleVersion='1',
            CFBundleShortVersionString='0.1', CFBundleIconFile='PCB.icns', NSHighResolutionCapable=True,
            LSMinimumSystemVersion='26.0', CFBundleGetInfoString='gEDA PCB ' + commit[:8] + (' (GTK2/Quartz/OpenGL experimental)' if OPENGL else ' (GTK2/Quartz)'))
with (CONT / 'Info.plist').open('wb') as f:
    plistlib.dump(info, f)
licenses = RES / 'licenses'
licenses.mkdir()
shutil.copy2(SOURCE_ROOT / 'COPYING', licenses / 'PCB-COPYING')
for formula in sorted(formulas):
    dest = licenses / (formula.parent.name + '-' + formula.name)
    dest.mkdir()
    for p in formula.iterdir():
        if p.is_file() and re.search(r'COPYING|LICENSE|COPYRIGHT|AUTHORS|NOTICE|INSTALL_RECEIPT|sbom', p.name, re.I):
            shutil.copy2(p, dest / p.name)
source = RES / 'source'
source.mkdir()
subprocess.run(['git', '-C', str(SOURCE_ROOT), 'archive', '--format=tar.gz', '-o', str(source / 'pcb-upstream.tar.gz'), 'HEAD'], check=True)
tree(SUPPORT / 'patches', source / 'patches')
tree(SUPPORT / 'netlist', source / 'netlist')
(source / 'packaging').mkdir()
for name in ('build-opengl.py', 'prepare-gtkglext.py', 'prepare-gtk-sdk.py', 'bundle-launcher.c', 'build-app.py', 'audit-app.py', 'build-env.sh', 'build-gtk2.sh', 'apply-source-patches.sh', 'preflight.sh', 'gnetlist-bridge.sh'):
    shutil.copy2(SUPPORT / 'scripts' / name, source / 'packaging' / name)
manifest = dict(pcb_commit=commit, architecture='arm64', gtk_backend='quartz', minimum_macos='26.0', renderer=('OpenGL' if OPENGL else 'GDK'),
                gtk_prefix=str(GTK_PREFIX), profile=('PCB-OpenGL-Quartz' if OPENGL else 'PCB-Quartz'),
                ad_hoc_signed=True, notarized=False,
                launcher_sha256=hashlib.sha256((SUPPORT / 'scripts/bundle-launcher.c').read_bytes()).hexdigest(),
                patches={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((SUPPORT / 'patches').glob('*.patch'))},
                libraries={str(dst.relative_to(CONT)): str(src) for dst, src in destinations.items()})
(RES / 'build-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
for dst in destinations:
    subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-', str(dst)], check=True, capture_output=True)
subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-', str(APP)], check=True, capture_output=True)
subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(APP)], check=True)
OUT.parent.mkdir(exist_ok=True)
APP.rename(OUT)
(ROOT / ('docs/opengl-bundle' if OPENGL else 'docs/bundle')).mkdir(exist_ok=True)
(ROOT / ('docs/opengl-bundle/build-manifest.json' if OPENGL else 'docs/bundle/build-manifest.json')).write_text(json.dumps(manifest, indent=2) + '\n')
print(OUT)
print(f'{len(destinations)} native images; {len(formulas)} dependency formulae')
