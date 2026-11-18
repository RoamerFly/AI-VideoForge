import json,time,sys
from pathlib import Path
root=Path(r"E:\Agent\projects\freetime_AI_Video_Comfyui")
sys.path.insert(0,str(root/"app"))
import core
core.CFG=dict(core.CFG,port=8194,comfy_root=core.DEFAULT_CONFIG["comfy_root"],ffmpeg=r"E:\A-Environment\FFmpeg\bin\ffmpeg.exe")
source=r"E:\Agent\projects\AI视频模板\胡桃坐姿抬腿.mp4"
char=r"E:\Agent\projects\freetime_AI_Draw\角色工坊库\角色库\夏日黑土\参考图"
scene=r"E:\Agent\projects\freetime_AI_Draw\角色工坊库\公共素材\场景\S22-屋主海景卧室\S22-BED_主卧_01-前视-朝北.png"
params={
 "natural_language":True,"video_abs":source,"time_start":0.0,"time_end":8.0,
 "width":480,"height":832,"frames":192,"steps":4,"turbo":True,"ref_size":"max","natural_route":"reference",
 "keep_audio":True,"quality":"原视频动作、抬腿姿势、镜头节奏和原音轨保持一致。",
 "prompt":"参考图1是角色参考，参考图2是场景参考。把原视频人物替换为夏日黑土，把原视频场景完整替换为参考图2的屋主海景卧室。生成真实的床、床垫、床单、枕头、床头背景、室内光线、遮挡关系、接触阴影和人物与床面的互动，不要把场景当成平面背景贴图。清除源视频原有水印和原房间物件，保留坐姿抬腿动作、人物比例、镜头运动和原音轨。",
 "target_groups":[
  {"description":"参考图1中的夏日黑土角色，替换源视频中的人物","images":[char+r"\夏日黑土_参考01_全身_正面.png",char+r"\夏日黑土_参考05_头部_正面.png"]},
  {"description":"参考图2中的屋主海景卧室，用于替换整个源视频场景","images":[scene]}
 ],
 "images":[char+r"\夏日黑土_参考01_全身_正面.png",char+r"\夏日黑土_参考05_头部_正面.png",scene]
}
out=root/"experiments/natural-language-hutao-kurotsuchi-20261118";out.mkdir(exist_ok=True)
core.boot()
if not core.start_comfy(block=True).get("online"):raise RuntimeError("ComfyUI startup failed")
task=core.new_task("06","夏日黑土 · 卧室场景 · 480p",params)
(out/"task.json").write_text(json.dumps(task,ensure_ascii=False,indent=2),encoding="utf-8")
print("task",task["id"],flush=True)
while True:
 t=core.task_get(task["id"])
 (out/"task-current.json").write_text(json.dumps(t,ensure_ascii=False,indent=2),encoding="utf-8")
 print(t["status"],t.get("progress"),t.get("stage"),t.get("error",""),flush=True)
 if t["status"] in ("done","error","canceled"):break
 time.sleep(10)
if t["status"]!="done":raise RuntimeError(t.get("error") or t["status"])
if core._proc and core._proc.poll() is None:
 try:
  q=core.http_json("/queue")
  if not q["queue_running"] and not q["queue_pending"]:core.stop_owned()
 except Exception:pass
