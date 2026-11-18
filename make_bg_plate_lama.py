import json,sys,time,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'app'))
import core
api={
 '1':{'class_type':'LoadImage','inputs':{'image':'h3studio/compare_exact_20261115_t16/target_character.png'}},
 '2':{'class_type':'LoadImage','inputs':{'image':'h3studio/bgmask_compare_exact_20261115_00001_.png'}},
 '3':{'class_type':'ImageToMask','inputs':{'image':['2',0],'channel':'red'}},
 '4':{'class_type':'AILab_LamaRemover','inputs':{'images':['1',0],'masks':['3',0],'removal_strength':230,'edge_smoothness':8}},
 '5':{'class_type':'SaveImage','inputs':{'images':['4',0],'filename_prefix':'H3影栈/bgplate_lama_compare_exact_20261115'}}
}
Path('compare_exact_20261115/bgplate_lama_api.json').write_text(json.dumps(api,ensure_ascii=False,indent=2),encoding='utf-8')
pid=core.submit(api);print('PID',pid,flush=True);t=time.time()
while True:
 e=core.history(pid)
 if e:
  st=e.get('status') or {}
  if st.get('status_str')=='error': print('ERROR',json.dumps(st,ensure_ascii=False)[:5000]);sys.exit(1)
  if st.get('completed') or e.get('outputs'):
   fs=[f for f in core.collect_outputs(e) if f.startswith('H3影栈/')]; print('DONE',fs,flush=True)
   for f in fs:
    src=Path(core.comfy_output())/f; dst=Path('compare_exact_20261115')/Path(f).name; shutil.copy2(src,dst); print(dst,flush=True)
   break
 if time.time()-t>1200: print('TIMEOUT');sys.exit(2)
 time.sleep(5)
