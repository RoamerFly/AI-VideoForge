"""Native-resolution facial quality experiment after rejection of the SR example."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'app'))
import core
BASE=ROOT.parent/'freetime_AI_Draw/角色工坊库/Temp/宗师雏田面部原生清晰度核验-20261118-身份主脸'
BASE.mkdir(parents=True,exist_ok=True)
character=ROOT.parent/'freetime_AI_Draw/角色工坊库/角色库/宗师雏田/参考图/宗师雏田_参考01_全身_正面.png'
face=character.with_name('宗师雏田_参考05_头部_正面.png')
(BASE/'参考分工.json').write_text(json.dumps({'costume_and_proportions':str(character),'authoritative_face':str(face),'method':'使用角色参考图目录的现成主脸，未重新生成或修改面部'},ensure_ascii=False,indent=2),encoding='utf-8')
core.CFG=dict(core.CFG,out_dir=str(BASE));core.boot()
print(core.start_comfy(block=True),flush=True)
params={'engine':'h3_pipeline','video_abs':str(ROOT.parent/'AI视频模板/申鹤站立扭身舞.mp4'),
 'images':[str(character),str(face)],'char_count':2,'identity_ref_index':2,'width':768,'height':1376,'pipeline_duration':3,
 'steps':20,'turbo':False,'seed':20261118,'swap_str':1.15,'ref_size':'max','head_chunks':8,'ff_chunks':4,
 'background_mode':'grey','upscale':False,'keep_audio':True,
 'prompt':'Picture 1 and Picture 2 show the exact SAME adult woman. Picture 1 defines costume and full-body proportions. Picture 2 is the authoritative facial identity: preserve its natural eye size and eyelid shapes, pale violet irises, coherent pupils, nose, lips and face contour. Keep both eyes coherent and naturally focused. High fidelity photographic face with natural skin texture. Maintain her long black hair, blue ribbon, red asymmetric mandarin-collar costume, silver tiger belt, cyan tassels, red arm guards and burgundy flat boots. Match the source body movements and timing without inventing extra head turns. Avoid beauty-filter smoothing, oversharpened eyelashes, painted eyes and exaggerated eye enlargement.'}
last=BASE/'task-current.json'
if last.exists():
 previous=json.loads(last.read_text(encoding='utf-8'))
 if previous.get('status')=='error' and previous.get('work_dir'):
  params=dict(previous['params'],resume_work=previous['work_dir'])
t=core.new_task('05','768原生20步人脸核验（尚未验收）',params)
try:
 while True:
  t=core.task_get(t['id']);last.write_text(json.dumps(t,ensure_ascii=False,indent=2),encoding='utf-8')
  print(t['status'],t['progress'],t['stage'],t.get('error',''),flush=True)
  if t['status'] in ('done','error','canceled'):break
  time.sleep(25)
finally:
 if core.queue_info()=={'running':0,'pending':0}:core.stop_owned()
if t['status']!='done':raise RuntimeError(t.get('error') or t['status'])
