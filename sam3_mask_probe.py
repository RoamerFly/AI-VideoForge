import sys,time,json
sys.path.insert(0,r'E:\Agent\projects\freetime_AI_Video_Comfyui\app')
import core
api={
 '1':{'class_type':'LoadImage','inputs':{'image':'h3studio/compare_exact_20261115_t16/target_character.png'}},
 '2':{'class_type':'CheckpointLoaderSimple','inputs':{'ckpt_name':'sam3.1_multiplex_fp16.safetensors'}},
 '3':{'class_type':'CLIPTextEncode','inputs':{'text':'human','clip':['2',1]}},
 '4':{'class_type':'SAM3_Detect','inputs':{'model':['2',0],'image':['1',0],'conditioning':['3',0],'threshold':0.5,'refine_iterations':2,'individual_masks':False}},
 '5':{'class_type':'MaskToImage','inputs':{'mask':['4',0]}},
 '6':{'class_type':'SaveImage','inputs':{'images':['5',0],'filename_prefix':'bg_probe/sam3_target_mask'}}
}
print('submit',flush=True); pid=core.submit(api); print(pid,flush=True)
while True:
 e=core.history(pid)
 if e:
  st=e.get('status') or {}
  if st.get('status_str')=='error': print('ERR',json.dumps(st,ensure_ascii=False)[:3000],flush=True); raise SystemExit(2)
  if st.get('completed') or e.get('outputs'):
   print('OUT',core.collect_outputs(e),flush=True);break
 time.sleep(5)
