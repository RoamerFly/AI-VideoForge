import json,shutil,subprocess,time,sys,traceback
from pathlib import Path
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/"app"))
import core
core.CFG=dict(core.CFG,port=8194,comfy_root=core.DEFAULT_CONFIG["comfy_root"],ffmpeg=r"E:\A-Environment\FFmpeg\bin\ffmpeg.exe")
d=root/"experiments/yahiko-role-replace-20261118";d.mkdir(parents=True,exist_ok=True)
assets=Path(core.comfy_input())/"yahiko-role-replace-20261118";assets.mkdir(parents=True,exist_ok=True)
source=Path(r"C:\Users\RoverFly\Downloads\kling_20261118_作品_保留_视频1_全部动_2630_0.mp4")
refdir=Path(r"E:\Agent\projects\freetime_AI_Draw\角色工坊库\角色库\生前弥彦\参考图")
ref=assets/"yahiko-full.png";identity=assets/"yahiko-face.png"
shutil.copy2(refdir/"生前弥彦_参考05_全身_正面.png",ref);shutil.copy2(refdir/"生前弥彦_参考01_头部_正面.png",identity)
clip=assets/"driver-5to8.mp4"
if not clip.exists():
 core.run_ff([core.ffmpeg_exe(),"-y","-v","error","-ss","5","-i",source,
   "-map","0:v:0","-map","0:a:0","-vf","fps=24,scale=832:480:flags=lanczos,setsar=1",
   "-frames:v","73","-t","3.041667","-c:v","libx264","-crf","16","-pix_fmt","yuv420p",
   "-c:a","aac","-b:a","128k",clip])
api=json.loads((root/"compare_exact_20261115/h3_api.json").read_text(encoding="utf-8"))
p="yahiko-role-replace-20261118/"
api["150"]["inputs"]["file"]=p+"driver-5to8.mp4"
api["156"]["inputs"]["image"]=p+"yahiko-full.png"
api["157"]={"class_type":"LoadImage","inputs":{"image":p+"yahiko-face.png"}}
api["136"]["inputs"]["ref_images.ref_image_1"]=["157",0]
api["136"]["inputs"]["ref_image_size"]="max"
api["136"]["inputs"]["width"]=["154",0];api["136"]["inputs"]["height"]=["155",0];api["136"]["inputs"]["length"]=["153",0]
api["153"]["inputs"]["value"]=73;api["154"]["inputs"]["value"]=832;api["155"]["inputs"]["value"]=480
api["146"]["inputs"]["value"]=True
api["147"]["inputs"]["strength_model"]=1.15
api["129"]["inputs"]["noise_seed"]=20261118
api["92"]["inputs"]["filename_prefix"]="video/YahikoRoleReplace/5to8"
prompt=[v["inputs"] for v in api.values() if v["class_type"]=="PrimitiveStringMultiline"][0]
prompt["value"]=("Replace only the central person in the driving clip with the same adult male character from <Picture 1>. "
 "Use <Picture 2> for facial identity. Preserve orange spiky hair, metal forehead protector, black high-collar long coat with red trim, wide gray and brown waist belts, dark cropped pants, white leg wraps and black open-toe shinobi sandals. "
 "Keep the exact original 16:9 framing, the brick wall, flower garden, pigeons forming a heart, lighting and camera motion from the driving clip. "
 "Only the central person changes. Keep all pigeons and the surrounding background intact. One replacement person, stable face, natural hands and feet, no extra people, no new scenery.")
(d/"宗师弥彦_5至8秒_H3角色替换_API.json").write_text(json.dumps(api,ensure_ascii=False,indent=2),encoding="utf-8")
state=d/"run.json"
if state.exists(): raise RuntimeError("Existing run record, inspect it first")
if not core.start_comfy(block=True).get("online") or not core._proc:raise RuntimeError("ComfyUI startup failed")
core.WATCHER.start()
res=core.http_json("/prompt",{"prompt":api,"client_id":core.CLIENT_ID,"extra_data":{"experiment":"yahiko-role-replace-5to8"}})
pid=res["prompt_id"];state.write_text(json.dumps({"pid":pid,"port":8194,"status":"running","server_pid":core._proc.pid},ensure_ascii=False,indent=2),encoding="utf-8");print("prompt",pid,flush=True)
try:
 while True:
  h=core.http_json("/history/"+pid,timeout=20).get(pid)
  if h:
   (d/"history.json").write_text(json.dumps(h,ensure_ascii=False,indent=2),encoding="utf-8")
   if h["status"].get("status_str")=="error":raise RuntimeError(h["status"])
   if h["status"].get("completed"):break
  print("progress",core.WATCHER.value,core.WATCHER.max,flush=True);time.sleep(6)
 files=core.collect_outputs(h);outs=[Path(core.comfy_output())/x for x in files if x.endswith(".mp4")]
 if len(outs)!=1:raise RuntimeError(files)
 out=d/"宗师弥彦_5至8秒_H3角色替换.mp4";shutil.copy2(outs[0],out)
 state.write_text(json.dumps({"pid":pid,"port":8194,"status":"done","output":str(out)},ensure_ascii=False,indent=2),encoding="utf-8");print(out,flush=True)
finally:
 if core._proc and core._proc.poll() is None:
  try:
   q=core.http_json("/queue",timeout=10)
   if not q["queue_running"] and not q["queue_pending"]:core.stop_owned()
  except Exception:pass
