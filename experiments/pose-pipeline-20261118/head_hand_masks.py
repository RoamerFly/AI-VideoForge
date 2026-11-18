import json,sys,time,uuid,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'app'))
import core,pose_pipeline as pp
HQ=ROOT.parent/'freetime_AI_Draw/角色工坊库/Temp/宗师雏田面部原生清晰度核验-20261118-身份主脸'
BASE=HQ/'局部人脸重建';r=json.loads((BASE/'head-result.json').read_text(encoding='utf-8'));mapping=json.loads((BASE/'head-crop-mapping.json').read_text(encoding='utf-8'))
core.CFG=dict(core.CFG,out_dir=str(BASE));core.boot();print(core.start_comfy(block=True),flush=True)
tid='hands-'+uuid.uuid4().hex[:6];core.TASKS[tid]={'id':tid,'status':'running'}
p=pp.Pipeline(core,tid,dict(r['params'],resume_work=r['work']),time.strftime('%m%d_%H%M%S'));seg=p.m['segments'][0]
sam=p.model('CheckpointLoaderSimple','ckpt_name','sam3')
for tag,path,count in [('body-hand',mapping['source'],72),('head-hand',r['file'],73)]:
 folder=BASE/'hand-masks'/tag;folder.mkdir(parents=True,exist_ok=True)
 if len(list(folder.glob('*.png')))==count:continue
 graph=core.load_template('05m');graph['1']['inputs']['file']=core.stage_asset(str(path),sub='h3studio/'+p.work.name)
 graph['4']['inputs']['ckpt_name']=sam;graph['5']['inputs']['text']='hand'
 graph['6']['inputs'].update(detection_threshold=.25,max_objects=2)
 graph['9']['inputs']['filename_prefix']=f'H3影栈/{p.work.name}/{tag}'
 result=p.execute(graph,seg,tag,0,1);paths=pp.outputs(core,result,'.png');assert len(paths)==count,(tag,len(paths))
 for i,source in enumerate(paths):shutil.copy2(source,folder/f'{i:05d}.png')
 print(tag,'complete',len(paths),flush=True)
