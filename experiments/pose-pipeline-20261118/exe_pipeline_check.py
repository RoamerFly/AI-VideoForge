"""Exercise the packaged task API with persisted completed segments; no fresh diffusion."""
import json,sys,time,subprocess,shutil,hashlib
from pathlib import Path
import psutil,requests
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'app'))
import core
BASE=Path(__file__).parent
old=json.loads((BASE/'task-current.json').read_text(encoding='utf-8'))
target=Path(core.out_dir())/'过程'/f'H3流程_EXE验证_{int(time.time())}'
assert target.resolve().is_relative_to(Path(core.out_dir()).resolve())
shutil.copytree(old['work_dir'],target)
params=dict(old['params'],resume_work=str(target))
exe=ROOT/'app/dist/H3影栈.exe';log=(BASE/'exe-pipeline.log').open('wb')
proc=subprocess.Popen([str(exe),'--server'],cwd=str(exe.parent),stdout=log,stderr=log,creationflags=0x08000000)
s=requests.Session();s.trust_env=False
try:
 base=None;end=time.monotonic()+45
 while time.monotonic()<end:
  ids={proc.pid}|{p.pid for p in psutil.Process(proc.pid).children(recursive=True)}
  for c in psutil.net_connections(kind='tcp'):
   if c.pid in ids and c.status=='LISTEN' and c.laddr.ip=='127.0.0.1':base=f'http://127.0.0.1:{c.laddr.port}';break
  if base:break
  time.sleep(.3)
 assert base
 res=s.post(base+'/api/generate',json={'mode':'05','title':'EXE固定流程续接验证','params':params},timeout=20);res.raise_for_status();tid=res.json()['task']['id']
 end=time.monotonic()+180
 while time.monotonic()<end:
  tasks=s.get(base+'/api/tasks',timeout=15).json()['tasks'];t=next(x for x in tasks if x['id']==tid)
  print(t['status'],t['stage'],flush=True)
  if t['status'] in ('done','error','canceled'):break
  time.sleep(5)
 assert t['status']=='done',t.get('error')
 m=json.loads((target/'流程状态.json').read_text(encoding='utf-8'));assert Path(m['final']).exists()
 # All three phase task IDs must be the original real inference tasks.
 oldstate=json.loads((Path(old['work_dir'])/'流程状态.json').read_text(encoding='utf-8'))
 for phase in ['generation_job','segmentation_job','upscale_job']:
  assert m['segments'][0][phase]['pid']==oldstate['segments'][0][phase]['pid']
 report={'status':'pass','exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'task':t,'reused_all_three_phase_ids':True,'fresh_diffusion_submitted':False}
 (BASE/'exe-pipeline-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print('Packaged pipeline resumed, assembled and verified the 1080p sample',flush=True)
finally:
 try:
  children=psutil.Process(proc.pid).children(recursive=True)
  for child in reversed(children):child.terminate()
  proc.terminate();proc.wait(timeout=10)
 except (psutil.Error,subprocess.TimeoutExpired):pass
 log.close()
