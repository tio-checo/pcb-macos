#!/usr/bin/env python3
"""Verify native-library closure, signatures, architecture and symlink containment."""
import json
from pathlib import Path
import subprocess
import sys
app = Path(sys.argv[1]).resolve()
assert app.is_dir()
images = []
for p in app.rglob('*'):
    if p.is_symlink():
        assert p.exists() and p.resolve().is_relative_to(app), f'Escaping/broken symlink: {p}'
        continue
    if not p.is_file():
        continue
    with p.open('rb') as f:
        magic = f.read(4)
    if magic not in (b'\xcf\xfa\xed\xfe', b'\xca\xfe\xba\xbe', b'\xfe\xed\xfa\xcf'):
        continue
    arch = subprocess.check_output(['/usr/bin/lipo', '-archs', str(p)], text=True).strip()
    assert arch == 'arm64', (p, arch)
    deps = subprocess.check_output(['/usr/bin/otool', '-L', str(p)], text=True).splitlines()[1:]
    for line in deps:
        dep = line.strip().split(' (compatibility')[0]
        if dep.startswith(('/usr/lib/', '/System/Library/')) or dep == '@rpath/' + p.name:
            continue
        assert dep.startswith('@loader_path/'), (p, dep)
        target = (p.parent / dep[len('@loader_path/'):]).resolve()
        assert target.is_relative_to(app) and target.is_file(), (p, dep, target)
    commands = subprocess.check_output(['/usr/bin/otool', '-l', str(p)], text=True)
    assert 'cmd LC_RPATH' not in commands, p
    images.append(str(p.relative_to(app)))
subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)], check=True)
for name in ('pixbuf-loaders.cache.in', 'gtk-immodules.cache.in', 'gtkrc.in'):
    text = (app / 'Contents/Resources' / name).read_text()
    assert '/opt/homebrew' not in text and '/opt/local' not in text, name
print(json.dumps(dict(result='PASS', bundle=str(app), arm64_images=len(images),
                     no_external_non_Apple_load_commands=True, no_external_rpaths=True,
                     all_symlinks_contained=True, ad_hoc_signature_valid=True), indent=2))
