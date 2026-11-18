import json
import sys
import time
from pathlib import Path

root = Path(r"E:\\Agent\\projects\\freetime_AI_Video_Comfyui")
sys.path.insert(0, str(root / "app"))
import core

source = r"E:\\Agent\\projects\\AI视频模板\\胡桃坐姿抬腿.mp4"
char = Path(r"E:\\Agent\\projects\\freetime_AI_Draw\\角色工坊库\\角色库\\夏日黑土\\参考图")
scene = Path(r"E:\\Agent\\projects\\freetime_AI_Draw\\角色工坊库\\公共素材\\场景\\S22-屋主海景卧室\\S22-BED_主卧_01-前视-朝北.png")
out = root / "experiments/natural-language-hutao-kurotsuchi-20261118"
out.mkdir(parents=True, exist_ok=True)

params = {
    "natural_language": True,
    "two_phase": True,
    "video_abs": source,
    "time_start": 0.0,
    "time_end": 8.4,
    "width": 720,
    "height": 1280,
    "frames": 209,
    "steps": 4,
    "turbo": True,
    "ref_size": "max",
    "keep_audio": True,
    "export_name": "夏日黑土_两阶段_720p",
    "prompt": (
        "一键执行两阶段处理：先只替换场景并保留源视频人物，再只替换人物并锁定已生成场景。"
        "角色替换为角色参考图中的夏日黑土，场景替换为场景参考图中的屋主海景卧室。"
        "保留原视频动作、姿势、镜头运动、时间节奏和原音轨，清除源视频水印。"
    ),
    "target_groups": [
        {
            "description": "将源视频中的人物替换为角色参考图中的夏日黑土，保持动作、姿势和镜头节奏。",
            "images": [str(char / "夏日黑土_参考01_全身_正面.png"), str(char / "夏日黑土_参考05_头部_正面.png")],
        },
        {
            "description": "将源视频场景替换为场景参考图中的屋主海景卧室，生成床、床品、光线、遮挡和人物与床面的合理互动。",
            "images": [str(scene)],
        },
    ],
    "images": [
        str(char / "夏日黑土_参考01_全身_正面.png"),
        str(char / "夏日黑土_参考05_头部_正面.png"),
        str(scene),
    ],
}

core.boot()
ready = core.start_comfy(block=True)
if not ready.get("online"):
    raise RuntimeError(ready.get("msg") or "ComfyUI startup failed")
task = core.new_task("06", "夏日黑土 · 两阶段场景人物替换 · 720p", params)
(out / "task-two-phase.json").write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
print("task", task["id"], flush=True)
while True:
    current = core.task_get(task["id"])
    (out / "task-two-phase-current.json").write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    print(current["status"], current.get("progress"), current.get("stage"), current.get("error", ""), flush=True)
    if current["status"] in ("done", "error", "canceled"):
        break
    time.sleep(10)
if current["status"] != "done":
    raise RuntimeError(current.get("error") or current["status"])
