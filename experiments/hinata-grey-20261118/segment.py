"""Existing native SAM3 segmentation; no model downloads, no background hallucination."""
from pathlib import Path
import argparse,json,requests,shutil
from run_trial import HERE,OUT,STAGE,BASE,core,save

a=argparse.ArgumentParser();a.add_argument('action',choices=['image','video','status']);a.add_argument('name');args=a.parse_args()
record_tag=args.name+'-seg'
if args.action=='status':
    task=json.loads((HERE/f'{record_tag}-submit.json').read_text(encoding='utf-8'))['prompt_id']
    entry=requests.get(BASE+'/history/'+task,timeout=20).json().get(task)
    if not entry:print(json.dumps({'id':task,'state':'running or queued'}));raise SystemExit()
    save(HERE/f'{record_tag}-result.json',entry);save(OUT/f'{args.name}-分割执行记录.json',entry)
    folder=OUT/f'{args.name}-masks';folder.mkdir(exist_ok=True)
    files=[]
    for v in entry.get('outputs',{}).values():
        for it in v.get('images',[]):
            if it.get('type')!='output' or not it.get('filename','').endswith('.png'):continue
            src=Path(core.comfy_output())/it.get('subfolder','')/it['filename']
            dst=folder/f'{len(files):05d}.png';shutil.copy2(src,dst);files.append(str(dst))
    print(json.dumps({'id':task,'status':entry['status'],'masks':len(files)},ensure_ascii=False));raise SystemExit()

info=requests.get(BASE+'/object_info/CheckpointLoaderSimple',timeout=20).json()
options=info['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0]
names=[n for n in options if Path(n).name.startswith('sam3.1_multiplex_fp16') and n.endswith('.safetensors')]
assert len(names)==1,names
g={'4':{'class_type':'CheckpointLoaderSimple','inputs':{'ckpt_name':names[0]}},'5':{'class_type':'CLIPTextEncode','inputs':{'text':'person','clip':['4',1]}}}
if args.action=='image':
    g['1']={'class_type':'LoadImage','inputs':{'image':'h3studio/hinata-grey-20261118/character.png'}}
    g['6']={'class_type':'SAM3_Detect','inputs':{'model':['4',0],'image':['1',0],'conditioning':['5',0],'threshold':.5,'refine_iterations':2,'individual_masks':False}}
    g['8']={'class_type':'MaskToImage','inputs':{'mask':['6',0]}}
else:
    src=OUT/f'{args.name}-原音轨.mp4';assert src.exists()
    staged=STAGE/f'{args.name}-output.mp4';shutil.copy2(src,staged)
    g['1']={'class_type':'LoadVideo','inputs':{'file':f'h3studio/hinata-grey-20261118/{staged.name}'}}
    g['2']={'class_type':'GetVideoComponents','inputs':{'video':['1',0]}}
    g['3']={'class_type':'ImageFromBatch','inputs':{'image':['2',0],'batch_index':0,'length':73}}
    g['6']={'class_type':'SAM3_VideoTrack','inputs':{'images':['3',0],'model':['4',0],'conditioning':['5',0],'detection_threshold':.5,'max_objects':1,'detect_interval':1}}
    g['7']={'class_type':'SAM3_TrackToMask','inputs':{'track_data':['6',0],'object_indices':''}}
    g['8']={'class_type':'MaskToImage','inputs':{'mask':['7',0]}}
g['9']={'class_type':'SaveImage','inputs':{'images':['8',0],'filename_prefix':'hinata-grey-masks/'+args.name}}
save(HERE/f'{record_tag}-api.json',g);save(OUT/f'{args.name}-分割工作流.json',g)
r=requests.post(BASE+'/prompt',json={'prompt':g,'client_id':'hinata-grey-seg-'+args.name},timeout=60)
save(HERE/f'{record_tag}-submit.json',r.json());print(r.status_code,r.text);r.raise_for_status()
