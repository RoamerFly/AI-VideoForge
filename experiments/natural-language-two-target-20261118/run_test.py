import json,time,sys
from pathlib import Path
root=Path(r"E:\Agent\projects\freetime_AI_Video_Comfyui")
sys.path.insert(0,str(root/"app"))
import core
core.CFG=dict(core.CFG,port=8194,comfy_root=core.DEFAULT_CONFIG["comfy_root"],ffmpeg=r"E:\A-Environment\FFmpeg\bin\ffmpeg.exe")
source=r"C:\Users\RoverFly\Downloads\kling_20261118_作品_保留_视频1_全部动_2630_0.mp4"
hinata=r"E:\Agent\projects\freetime_AI_Draw\角色工坊库\角色库\宗师雏田\参考图"
loli=r"E:\Agent\projects\freetime_AI_Draw\角色工坊库\角色库\漂泊佩恩-萝莉道\参考图"
params={
 "natural_language":True,"video_abs":source,"time_start":0.0,"time_end":10.0,
 "width":832,"height":480,"frames":243,"steps":4,"turbo":True,"ref_size":"match",
 "keep_audio":True,"quality":"保持源视频动作、镜头、花田、砖墙和鸽群。",
 "prompt":"把两个目标人物替换成指定角色，保持其他人物、鸽子心形、花田、砖墙、镜头和原音轨。",
 "target_groups":[
  {"description":"花田画面左侧、橙色头发、穿黑色长衣并向右伸手驱赶鸽子的人",
   "images":[hinata+r"\宗师雏田_参考01_全身_正面.png",hinata+r"\宗师雏田_参考05_头部_正面.png"]},
  {"description":"花田画面右侧、紫色头发、穿黑白服装、站在花田另一侧的人",
   "images":[loli+r"\漂泊佩恩-萝莉道_参考01_全身_正面.png",loli+r"\漂泊佩恩-萝莉道_参考05_头部_正面.png"]}
 ],
 "target_descriptions":["花田画面左侧、橙色头发、穿黑色长衣并向右伸手驱赶鸽子的人","花田画面右侧、紫色头发、穿黑白服装、站在花田另一侧的人"],
 "images":[hinata+r"\宗师雏田_参考01_全身_正面.png",hinata+r"\宗师雏田_参考05_头部_正面.png",loli+r"\漂泊佩恩-萝莉道_参考01_全身_正面.png",loli+r"\漂泊佩恩-萝莉道_参考05_头部_正面.png"]
}
core.boot()
if not core.start_comfy(block=True).get("online"):raise RuntimeError("ComfyUI startup failed")
task=core.new_task("06","自然语言替换 · 双目标 0–10 秒",params)
out=root/"experiments/natural-language-two-target-20261118";out.mkdir(exist_ok=True)
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
