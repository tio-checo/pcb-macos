#!/usr/bin/env python3
"""Prepare a pinned arm64 Quartz GtkGLExt SDK without modifying Homebrew."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--bottle',type=Path,required=True)
ap.add_argument('--gtk-prefix',type=Path,required=True)
ap.add_argument('--work',type=Path,required=True)
a=ap.parse_args()
expected='764e97c887571389641f45ef171ca06af71ac4bc5fcaaff56e85c9d663cad92a'
if hashlib.sha256(a.bottle.read_bytes()).hexdigest()!=expected:raise SystemExit('Unexpected GtkGLExt bottle checksum')
work=a.work.resolve();gtk=a.gtk_prefix.resolve()
if work.exists():raise SystemExit('Refusing to overwrite '+str(work))
work.mkdir(parents=True)
with tarfile.open(a.bottle) as t:t.extractall(work,filter='data')
gl=work/'gtkglext/1.2.0_4'
replace={'@@HOMEBREW_CELLAR@@/gtkglext/1.2.0_4':str(gl),'@@HOMEBREW_PREFIX@@/opt/gtkglext':str(gl),
 '@@HOMEBREW_PREFIX@@/opt/gtk+':str(gtk),'@@HOMEBREW_CELLAR@@':'/opt/homebrew/Cellar','@@HOMEBREW_PREFIX@@':'/opt/homebrew'}
for p in gl.rglob('*'):
 if not p.is_file() or p.is_symlink():continue
 if p.suffix in ['.pc','.la']:
  s=p.read_text()
  for old,new in replace.items():s=s.replace(old,new)
  p.write_text(s)
 if p.suffix=='.dylib':
  deps=subprocess.check_output(['otool','-L',str(p)],text=True).splitlines()[1:]
  args=['install_name_tool','-id',str(p)]
  for line in deps:
   dep=line.strip().split(' (compatibility')[0];target=dep
   for old,new in replace.items():target=target.replace(old,new)
   if target!=dep:args+=['-change',dep,target]
  subprocess.run([*args,str(p)],check=True,capture_output=True)
  subprocess.run(['codesign','--force','--sign','-',str(p)],check=True,capture_output=True)
(work/'sdk-manifest.json').write_text(json.dumps(dict(gtkglext_version='1.2.0_4',backend='quartz',architecture='arm64',bottle_sha256=expected,gtk_prefix=str(gtk),prefix=str(gl)),indent=2)+'\n')
print(gl)
