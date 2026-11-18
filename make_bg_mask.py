import json,sys,time,os,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'app'))
import core
input_rel='h3studio/compare_exact_20261115_t16/target_character.png'
api={
 '1':{'class_type':'LoadImage','inputs':{'image':input_rel}},
 '2':{'class_type':'CheckpointLoaderSimple','inputs':{'ckpt_name':'sam3.1_multiplex_fp16.safetensors'}},
 '3':{'class_type':'CLIPTextEncode','inputs':{'text':'human','clip':['2',1]}},
 '4':{'class_type':'SAM3_Detect','inputs':{'model':['2',0],'image':['1',0],'conditioning':['3',0],'threshold':0.5,'refine_iterations':2,'individual_masks':False}},
 '5':{'class_type':'MaskToImage','inputs':{'mask':['4',0]}},
 '6':{'class_type':'SaveImage','inputs':{'images':['5',0],'filename_prefix':'H3影栈/bgmask_compare_exact_20261115'}}
}
Path('compare_exact_20261115/bgmask_api.json').write_text(json.dumps(api,ensure_ascii=False,indent=2),encoding='utf-8')
pid=core.submit(api);print('PID',pid,flush=True);t=time.time()
while True:
 e=core.history(pid)
 if e:
  st=e.get('status') or {}
  if st.get('status_str')=='error': print('ERROR',json.dumps(st,ensure_ascii=False)[:4000]);sys.exit(1)
  if st.get('completed') or e.get('outputs'):
   fs=[f for f in core.collect_outputs(e) if f.startswith('H3影栈/')]; print('DONE',fs,flush=True)
   for f in fs:
    src=Path(core.comfy_output())/f; dst=Path('compare_exact_20261115')/Path(f).name; shutil.copy2(src,dst); print(dst,flush=True)
   break
 if time.time()-t>600: print('TIMEOUT');sys.exit(2)
 time.sleep(5)
