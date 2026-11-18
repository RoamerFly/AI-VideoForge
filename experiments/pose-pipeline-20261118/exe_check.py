import hashlib,json,subprocess,time,sys
from pathlib import Path
import psutil,requests
from PyInstaller.archive.readers import CArchiveReader
ROOT=Path(__file__).resolve().parents[2]
exe=ROOT/'app/dist/H3影栈.exe'
archive=CArchiveReader(str(exe));pyz=archive.open_embedded_archive(next(k for k in archive.toc if k.endswith('.pyz')))
assert 'pose_pipeline' in pyz.toc
for suffix in ['ui/app.js','templates/05p.json','templates/05m.json']:
 key=next(k for k in archive.toc if k.replace('\\','/').endswith(suffix))
 assert archive.extract(key)==(ROOT/'app'/suffix).read_bytes(),suffix
log=(Path(__file__).parent/'exe-server.log').open('wb')
proc=subprocess.Popen([str(exe),'--server'],cwd=str(exe.parent),stdout=log,stderr=log,creationflags=0x08000000)
session=requests.Session();session.trust_env=False
try:
 end=time.monotonic()+45;base=None
 while time.monotonic()<end:
  own=psutil.Process(proc.pid);ids={proc.pid}|{p.pid for p in own.children(recursive=True)}
  for conn in psutil.net_connections(kind='tcp'):
   if conn.pid in ids and conn.status=='LISTEN' and conn.laddr.ip=='127.0.0.1':
    base=f'http://127.0.0.1:{conn.laddr.port}'
    break
  if base:break
  if proc.poll() is not None:raise RuntimeError('EXE exited before opening server')
  time.sleep(.3)
 assert base,'EXE server not ready'
 res=session.get(base+'/api/pose/runs',timeout=20);res.raise_for_status();assert 'runs' in res.json()
 js=session.get(base+'/ui/app.js',timeout=10);assert 'H3 · 固定流程' in js.text and 'pipeline_audio' in js.text
 data={'status':'pass','exe':str(exe),'bytes':exe.stat().st_size,'sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),
       'url':base,'pose_pipeline_module_included':True,'templates_match_source':True,'endpoint_imports_cv2_numpy_and_pillow':True}
 (Path(__file__).parent/'exe-check.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(data,ensure_ascii=False),flush=True)
finally:
 try:
  children=psutil.Process(proc.pid).children(recursive=True)
  for child in children:child.terminate()
  proc.terminate();proc.wait(timeout=10)
 except (psutil.Error,subprocess.TimeoutExpired):pass
 log.close()
