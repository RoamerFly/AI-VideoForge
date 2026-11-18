import sys,time,json
sys.path.insert(0,r'E:\Agent\projects\freetime_AI_Video_Comfyui\app')
import core
api={
 '1':{'class_type':'LoadVideo','inputs':{'file':'h3studio/compare_exact_20261115_t16/h3_short_output.mp4'}},
 '2':{'class_type':'GetVideoComponents','inputs':{'video':['1',0]}},
 '3':{'class_type':'ImageFromBatch','inputs':{'image':['2',0],'batch_index':0,'length':73}},
 '4':{'class_type':'CheckpointLoaderSimple','inputs':{'ckpt_name':'sam3.1_multiplex_fp16.safetensors'}},
 '5':{'class_type':'CLIPTextEncode','inputs':{'text':'human','clip':['4',1]}},
 '6':{'class_type':'SAM3_VideoTrack','inputs':{'images':['3',0],'model':['4',0],'conditioning':['5',0],'detection_threshold':0.5,'max_objects':1,'detect_interval':1}},
 '7':{'class_type':'SAM3_TrackToMask','inputs':{'track_data':['6',0],'object_indices':''}},
 '8':{'class_type':'MaskToImage','inputs':{'mask':['7',0]}},
 '9':{'class_type':'SaveImage','inputs':{'images':['8',0],'filename_prefix':'bg_probe/h3_short_masks'}}
}
pid=core.submit(api); print('PID',pid,flush=True)
while True:
 e=core.history(pid)
 if e:
  st=e.get('status') or {}
  if st.get('status_str')=='error': print('ERR',json.dumps(st,ensure_ascii=False)[:3000],flush=True); raise SystemExit(2)
  if st.get('completed') or e.get('outputs'):
   print('OUT',core.collect_outputs(e),flush=True); break
 time.sleep(5)
