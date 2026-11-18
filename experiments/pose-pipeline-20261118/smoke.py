import json,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'app'))
import core
BASE=ROOT/'experiments/pose-pipeline-20261118'
core.CFG=dict(core.CFG,out_dir=str(BASE/'outputs'))
core.boot()
print(core.start_comfy(block=True),flush=True)
params={'engine':'h3_pipeline','video_abs':str(ROOT.parent/'AI视频模板/申鹤站立扭身舞.mp4'),
 'images':[str(ROOT.parent/'freetime_AI_Draw/角色工坊库/角色库/宗师雏田/参考图/宗师雏田_参考01_全身_正面.png')],
 'char_count':1,'width':576,'height':1024,'pipeline_duration':3,
 'steps':4,'turbo':True,'seed':20261118,'swap_str':1.15,'ref_size':'match',
 'background_mode':'grey','upscale':True,'keep_audio':True,
 'prompt':'Keep her long black hair, blue hair ribbon, pale violet eyes, red asymmetric mandarin-collar costume, silver tiger belt buckle, cyan knots and tassels, red arm guards and burgundy mid-calf flat boots.'}
last=BASE/'task-current.json'
if last.exists():
 previous=json.loads(last.read_text(encoding='utf-8'))
 if previous.get('status')=='error' and previous.get('work_dir'):
  params=previous['params'];params['resume_work']=previous['work_dir']
t=core.new_task('05','固定流程真实3秒验证',params)
BASE.mkdir(exist_ok=True);(BASE/'task.json').write_text(json.dumps(t,ensure_ascii=False,indent=2),encoding='utf-8')
try:
 while True:
  t=core.task_get(t['id']);(BASE/'task-current.json').write_text(json.dumps(t,ensure_ascii=False,indent=2),encoding='utf-8')
  print(t['status'],t['progress'],t['stage'],t.get('error',''),flush=True)
  if t['status'] in ('done','error','canceled'):break
  time.sleep(15)
finally:
 if core.queue_info()=={'running':0,'pending':0}:core.stop_owned()
if t['status']!='done':raise RuntimeError(t.get('error') or t['status'])
