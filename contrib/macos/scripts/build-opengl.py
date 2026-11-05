#!/usr/bin/env python3
"""Build the experimental Quartz/OpenGL PCB in separate source/install directories."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tarfile

support=Path(__file__).resolve().parent.parent
src=support.parent.parent
root=src.parent
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--gtk-prefix',required=True,type=Path)
ap.add_argument('--gtkglext-prefix',required=True,type=Path)
ap.add_argument('--jobs',type=int,default=6)
a=ap.parse_args()
gtk=a.gtk_prefix.resolve();glext=a.gtkglext_prefix.resolve()
if subprocess.check_output(['git','-C',str(src),'status','--porcelain']).strip():
 raise SystemExit('Build from a clean source snapshot (including local experimental changes).')
commit=subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()
source=root/'build/source-opengl';build=root/'build/opengl';prefix=root/'install/opengl';logs=root/'docs/opengl-build'
if any(p.exists() for p in [source,build,prefix]):
 raise SystemExit('Use fresh build/source-opengl, build/opengl and install/opengl directories.')
for p in [source,build,logs,root/'build/tools/bin',root/'build/tools/share/aclocal']:
 p.mkdir(parents=True,exist_ok=True)
intl=Path(os.environ['INTLTOOL_PREFIX']) if os.environ.get('INTLTOOL_PREFIX') else (Path('/opt/homebrew') if Path('/opt/homebrew/bin/intltoolize').exists() else Path('/opt/local'))
for name in ['intltoolize','intltool-extract','intltool-merge','intltool-update']:
 tool=intl/'bin'/name
 if not tool.is_file():raise SystemExit('Missing build tool '+str(tool))
 (root/'build/tools/bin'/name).symlink_to(tool)
(root/'build/tools/share/aclocal/intltool.m4').symlink_to(intl/'share/aclocal/intltool.m4')
major=subprocess.check_output(['sw_vers','-productVersion'],text=True).strip().split('.')[0]
env=dict(HOME=os.environ['HOME'],TMPDIR=os.environ.get('TMPDIR','/tmp'),LC_ALL='C',
 PATH=f'{root}/build/tools/bin:/opt/homebrew/opt/bison/bin:/opt/homebrew/opt/texinfo/bin:/opt/homebrew/opt/flex/bin:/opt/homebrew/opt/gettext/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin',
 ACLOCAL_PATH=f'{root}/build/tools/share/aclocal:{gtk}/share/aclocal:{glext}/share/aclocal',
 CC='/usr/bin/clang',CXX='/usr/bin/clang++',CFLAGS='-g -O2 -std=gnu99 -Wno-deprecated-declarations',
 PKG_CONFIG='/opt/homebrew/bin/pkg-config',
 PKG_CONFIG_LIBDIR=f'{glext}/lib/pkgconfig:{gtk}/lib/pkgconfig:/opt/homebrew/lib/pkgconfig:/opt/homebrew/share/pkgconfig:/opt/homebrew/opt/libffi/lib/pkgconfig:/opt/homebrew/Library/Homebrew/os/mac/pkgconfig/{major}')
for package in ['gdk-2.0','gdkglext-1.0','gtkglext-1.0']:
 target=subprocess.check_output(['/opt/homebrew/bin/pkg-config','--variable=target',package],env=env,text=True).strip()
 if target!='quartz':raise SystemExit(package+' must target Quartz, found '+target)
archive=root/'build/opengl-source.tar'
subprocess.run(['git','-C',str(src),'archive','--format=tar','-o',str(archive),'HEAD'],check=True)
with tarfile.open(archive) as t:t.extractall(source,filter='data')
archive.unlink()
(source/'.source-commit').write_text(commit+'\n')
with (logs/'patches.log').open('w') as log:
 for patch in sorted((support/'patches').glob('*.patch')):
  subprocess.run(['/usr/bin/patch','-f','-p1','-i',str(patch)],cwd=source,stdout=log,stderr=subprocess.STDOUT,check=True)
def run(name,args,cwd,extra=None):
 print(name,flush=True)
 with (logs/(name+'.log')).open('w') as log:
  subprocess.run(list(map(str,args)),cwd=cwd,env=dict(env,**(extra or {})),stdout=log,stderr=subprocess.STDOUT,check=True)
run('bootstrap',['sh','./autogen.sh'],source,{'GIT_DIR':subprocess.check_output(['git','-C',str(src),'rev-parse','--absolute-git-dir'],text=True).strip()})
run('configure',[source/'configure','--with-libintl-prefix=/opt/homebrew/opt/gettext','--prefix='+str(prefix),
 '--with-gui=gtk','--enable-gl','--disable-dbus','--without-x','--disable-doc','--disable-update-desktop-database',
 '--disable-update-mime-database','--disable-xrender','--disable-xinerama'],build,{'WISH':'/usr/bin/true'})
run('build',['make','-j'+str(a.jobs)],build)
run('unit-tests',['make','-C','src','check'],build)
run('install',['make','install'],build)
meta=dict(pcb_commit=commit,renderer='OpenGL',backend='quartz',gtk_prefix=str(gtk),gtkglext_prefix=str(glext),
 environment=env,configure_summary=(logs/'configure.log').read_text()[-6000:])
(logs/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
print('Installed '+str(prefix),flush=True)
