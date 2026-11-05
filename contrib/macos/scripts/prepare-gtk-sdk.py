#!/usr/bin/env python3
"""Extract the known GTK2/Quartz Homebrew bottle into a private build prefix."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--bottle',required=True,type=Path)
ap.add_argument('--work',required=True,type=Path)
args=ap.parse_args()
expected='50bf4d48f706e87bc7bff60b97ea41bc0ca1d4616390be8fe2781360531244c2'
if hashlib.sha256(args.bottle.read_bytes()).hexdigest()!=expected:
    raise SystemExit('Unexpected GTK bottle checksum')
dest=args.work.resolve()
if dest.exists():
    raise SystemExit('Refusing to overwrite GTK SDK: '+str(dest))
dest.mkdir(parents=True)
with tarfile.open(args.bottle) as t:
    t.extractall(dest,filter='data')
prefix=dest/'gtk+/2.24.33_2'
replacements={'@@HOMEBREW_CELLAR@@/gtk+/2.24.33_2':str(prefix),
              '@@HOMEBREW_PREFIX@@/opt/gtk+':str(prefix),
              '/opt/homebrew/opt/gtk+':str(prefix),
              '/opt/homebrew/Cellar/gtk+/2.24.33_2':str(prefix),
              '@@HOMEBREW_CELLAR@@':'/opt/homebrew/Cellar',
              '@@HOMEBREW_PREFIX@@':'/opt/homebrew'}
images=[]
for p in prefix.rglob('*'):
    if not p.is_file() or p.is_symlink(): continue
    if p.suffix in ('.pc','.la') or p.name=='immodules.cache':
        text=p.read_text()
        for old,new in replacements.items(): text=text.replace(old,new)
        p.write_text(text)
    if p.suffix in ('.dylib','.so'):
        images.append(p)
for p in images:
    deps=subprocess.check_output(['otool','-L',str(p)],text=True).splitlines()[1:]
    cmd=['install_name_tool']
    for line in deps:
        dep=line.strip().split(' (compatibility')[0]
        target=dep
        for old,new in replacements.items(): target=target.replace(old,new)
        if target!=dep: cmd+=['-change',dep,target]
    identity=subprocess.run(['otool','-D',str(p)],capture_output=True,text=True).stdout.splitlines()
    if len(identity)>1:
        cmd+=['-id',str(p)]
    if len(cmd)>1:
        subprocess.run([*cmd,str(p)],check=True,capture_output=True)
    subprocess.run(['codesign','--force','--sign','-',str(p)],check=True,capture_output=True)
(dest/'sdk-manifest.json').write_text(json.dumps(dict(bottle_sha256=expected,architecture='arm64',
    gtk_version='2.24.33',backend='quartz',prefix=str(prefix),native_images=len(images)),indent=2)+'\n')
print(prefix)
