import sys,time,json
sys.path.insert(0,r'E:\Agent\projects\freetime_AI_Video_Comfyui\app')
import core
api={
 '1':{'class_type':'LoadImage','inputs':{'image':'h3studio/compare_exact_20261115_t16/target_character.png'}},
 '2':{'class_type':'UnetLoaderGGUF','inputs':{'unet_name':'qwen-image-2.1-step90000-Q8_0.gguf','weight_dtype':'default'}},
 '3':{'class_type':'CLIPLoader','inputs':{'clip_name':'qwen_2.5_vl_7b_fp8_scaled.safetensors','type':'qwen_image','device':'default'}},
 '4':{'class_type':'VAELoader','inputs':{'vae_name':'qwen_image_vae.safetensors'}},
 '5':{'class_type':'TextEncodeQwenImage21','inputs':{'clip':['3',0],'prompt':'A clean empty wooden covered bridge over a clear pond in a Japanese garden, viewed from the same camera and perspective as the reference image, matching the same warm sunlight and composition. No person, no human, no character, no body, no face, no clothing, no foreground subject. Preserve the bridge roof, wooden railings, pond, rocks, trees and autumn foliage.','negative_prompt':'person, human, character, body, face, hair, clothing, duplicate subject, text, watermark','resolution':1024,'images.image_1':['1',0],'vae':['4',0]}},
 '6':{'class_type':'ModelSamplingAuraFlow','inputs':{'model':['2',0],'shift':3.1}},
 '7':{'class_type':'KSampler','inputs':{'model':['6',0],'positive':['5',0],'negative':['5',1],'latent_image':['5',2],'seed':20261115,'steps':20,'cfg':4.0,'sampler_name':'euler','scheduler':'simple','denoise':1.0}},
 '8':{'class_type':'VAEDecode','inputs':{'samples':['7',0],'vae':['4',0]}},
 '9':{'class_type':'SaveImage','inputs':{'images':['8',0],'filename_prefix':'bg_probe/qwen_empty_scene'}}
}
print('submit',flush=True); pid=core.submit(api); print(pid,flush=True)
while True:
 e=core.history(pid)
 if e:
  st=e.get('status') or {}
  if st.get('status_str')=='error': print('ERR',json.dumps(st,ensure_ascii=False)[:5000],flush=True); raise SystemExit(2)
  if st.get('completed') or e.get('outputs'):
   print('OUT',core.collect_outputs(e),flush=True); break
 time.sleep(5)
