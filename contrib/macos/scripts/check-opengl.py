#!/usr/bin/env python3
"""Exercise the real OpenGL window and FBO previews with an isolated PCB profile."""
import argparse,configparser,hashlib,json,os
from pathlib import Path
import shlex,shutil,subprocess,tempfile,time
support=Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--app',required=True,type=Path)
ap.add_argument('--run-parent',type=Path,default=Path('/private/tmp'))
a=ap.parse_args();app=a.app.resolve()
run=Path(tempfile.mkdtemp(prefix='pcb-opengl-check-',dir=a.run_parent));print('Artifacts: '+str(run),flush=True)
flags=shlex.split(subprocess.check_output(['/opt/homebrew/bin/pkg-config','--cflags','gtkglext-1.0'],text=True))
module=run/'check-opengl.so'
subprocess.run(['clang','-Wall','-Wextra','-Werror','-Wno-deprecated-declarations','-bundle','-undefined','dynamic_lookup',*flags,str(support/'tests/check-opengl.c'),str(support/'tests/check-quartz-layout.m'),'-framework','AppKit','-framework','OpenGL','-o',str(module)],check=True)
subprocess.run(['codesign','--force','--sign','-',str(module)],check=True,capture_output=True)
board=run/'input.pcb';shutil.copy2(app/'Contents/Resources/examples/LED.pcb',board)
original=hashlib.sha256(board.read_bytes()).hexdigest()
checks=[];p=None

def check(name,ok):
 if not ok:raise AssertionError(name)
 checks.append(name);print('PASS '+name,flush=True)
def wait(path):
 deadline=time.monotonic()+20
 while not path.exists():
  if p.poll() is not None:raise RuntimeError('PCB exited '+str(p.returncode))
  if time.monotonic()>deadline:raise TimeoutError(str(path))
  time.sleep(.03)
def capture(mode,tag,w=320,h=320):
 (run/'gl-request').write_text(f'{mode} {tag} {w} {h}\n');wait(run/(tag+'.done'))
 report=configparser.ConfigParser();report.read(run/(tag+'.ini'));return report
def action(*commands):
 for command in commands:p.stdin.write(command+'\n')
 marker=run/('ack-'+str(time.monotonic_ns())+'.pcb');p.stdin.write(f'SaveTo(LayoutAs,{marker})\n');p.stdin.flush();wait(marker)
def rgb(tag):return (run/(tag+'.rgb')).read_bytes()
def varied(data):return len(set(data[i:i+3] for i in range(0,len(data),3)))>2
try:
 env=dict(os.environ,HOME=str(run/'home'),PCB_BUNDLE_PROFILE=str(run/'profile'),DYLD_PRINT_LIBRARIES='1')
 (run/'home').mkdir()
 with (run/'pcb.log').open('w') as log:
  p=subprocess.Popen([str(app/'Contents/MacOS/PCB'),'--gtk-module='+str(module),'--listen','--backup-interval','0',str(board)],env=env,cwd=run,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,text=True)
  action()
  capture('zoom','fit',0,0)
  time.sleep(.3)
  first=capture('window','initial')
  for key in ['native-canvas','separate-view','gl-view','canvas-size','menu-visible','menu-hit']:
   check('OpenGL stays inside the drawing area: '+key,first.getboolean('layout',key))
  check('Real PCB window uses accelerated OpenGL',first.getint('context','accelerated')==1 and 'Apple' in first['context']['renderer'])
  check('Real PCB context has stencil and no GL errors',first.getint('context','stencil')>=8 and first.getint('context','error')==0)
  check('The presented window contains rendered board pixels',varied(rgb('initial')))
  capture('preview','preview')
  check('FBO board preview contains rendered pixels',varied(rgb('preview')))
  capture('preview','rectangle',320,238)
  expected=rgb('preview')[41*320*3:279*320*3]
  check('Non-square preview remains centered on the same board coordinates',rgb('rectangle')==expected)
  state=capture('state','state',319,237)
  for key in ['preview','context','viewport','pixel-store','matrices','framebuffer','zero-width']:
   check('Preview preserves GL state: '+key,state.getboolean('state',key))
  check('Preview leaves no OpenGL errors',state.getint('context','error')==0)
  check('Odd-width non-square preview produces all RGB rows',len(rgb('state'))==319*237*3 and varied(rgb('state')))
  for i in range(5):
   capture('preview','repeat-'+str(i))
   check('Repeated preview is stable '+str(i),rgb('repeat-'+str(i))==rgb('preview'))
  capture('zoom','refit',0,0);time.sleep(.25)
  after=capture('window','after-preview')
  check('Window still renders after previews',varied(rgb('after-preview')) and after.getint('context','error')==0)
  w=first.getint('context','width');h=first.getint('context','height')
  capture('resize','resize',1600,1000);time.sleep(.4)
  resized=capture('window','resized')
  for key in ['native-canvas','separate-view','gl-view','canvas-size','menu-visible','menu-hit']:
   check('Resize keeps the menu and native drawing area separate: '+key,resized.getboolean('layout',key))
  check('Real OpenGL window resizes',resized.getint('context','width')!=w or resized.getint('context','height')!=h)
  check('Window redraw after resize has pixels and no errors',varied(rgb('resized')) and resized.getint('context','error')==0)
  capture('zoom','zoom',50,0);time.sleep(.2);zoomed=capture('window','zoomed')
  check('Zoom changes rendered pixels without GL errors',rgb('zoomed')!=rgb('resized') and zoomed.getint('context','error')==0)
  action('DoWindows(Library)','DRC()','DoWindows(DRC)');time.sleep(.4)
  dialogs=capture('window','after-dialogs')
  check('Library and DRC windows leave renderer usable',varied(rgb('after-dialogs')) and dialogs.getint('context','error')==0)
  p.stdin.write('Quit()\n');p.stdin.flush();p.wait(timeout=15)
  check('PCB quits normally',p.returncode==0);p=None
  text=(run/'pcb.log').read_text()
  check('Runtime loads bundled GtkGLExt Quartz libraries','/Contents/Frameworks/libgtkglext-quartz' in text and '/Contents/Frameworks/libgdkglext-quartz' in text)
  loaded=[line for line in text.splitlines() if line.startswith('dyld[')]
  check('Runtime uses no Homebrew, MacPorts or build libraries',all('/opt/homebrew/' not in line and '/opt/local/' not in line and '/pcb-opengl-probe/' not in line for line in loaded))
  check('No GTK critical or OpenGL preview warnings',not any(token in text for token in ['-CRITICAL','-ERROR','Cannot read OpenGL preview','Cannot create OpenGL preview','Failed to load module']))
  check('Public input board remains unchanged',hashlib.sha256(board.read_bytes()).hexdigest()==original)
 (run/'result.json').write_text(json.dumps(dict(passed=len(checks),checks=checks,app=str(app),context=dict(first['context'])),indent=2)+'\n')
 print(str(len(checks))+' checks passed',flush=True)
finally:
 if p and p.poll() is None:
  p.terminate()
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait()
