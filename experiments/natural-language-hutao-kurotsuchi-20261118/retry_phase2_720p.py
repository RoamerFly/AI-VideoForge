import json
import os
import sys
import time
from pathlib import Path

root = Path(r"E:\\Agent\\projects\\freetime_AI_Video_Comfyui")
sys.path.insert(0, str(root / "app"))
import core

work = Path(os.environ.get("APPDATA", str(Path.home() / "AppData/Roaming"))) / "H3Studio/work/06cb3f99_natural_two_phase"
scene_video = work / "scene-stage.mp4"
guide_video = work / "scene-stage-guide-test.mp4"
source_range = work / "source-range.mp4"
if not scene_video.is_file() or not source_range.is_file():
    raise RuntimeError("第一阶段中间视频不存在")

print("guide", guide_video, flush=True)

sub = "h3studio/06cb3f99_natural_two_phase_retry"
video_ref = core.stage_asset(str(guide_video), sub=sub)
char = Path(r"E:\\Agent\\projects\\freetime_AI_Draw\\角色工坊库\\角色库\\夏日黑土\\参考图")
role_refs = [core.stage_asset(str(char / "夏日黑土_参考01_全身_正面.png"), sub=sub),
             core.stage_asset(str(char / "夏日黑土_参考05_头部_正面.png"), sub=sub)]
params = {
    "video": video_ref, "images": role_refs, "frames": 192, "width": 736, "height": 1280,
    "steps": 4, "turbo": True, "ref_size": "max", "keep_audio": False,
    "natural_scene": False, "natural_route": "reference", "char_count": 0,
    "target_groups": [{"description": "将人物替换为角色参考图中的夏日黑土，保持动作和镜头节奏。", "images": role_refs}],
    "prompt": "只替换人物为角色参考图中的夏日黑土。保留第一阶段已经生成的卧室、床铺、床品、家具、光线、遮挡关系、镜头运动、人物动作、姿势和时间节奏，不重新设计背景，不恢复源视频人物，不添加水印。",
}
api = core.build_api("06", params)
task = core.new_task("06", "夏日黑土 · 两阶段第二阶段重试 · 720p", params)
tag = "06_retry_phase2_720p"
pid_entry = core._run_one(task["id"], api, tag, "04", params)
files = [x for x in pid_entry if x.lower().endswith(".mp4")]
if not files:
    raise RuntimeError("重试阶段没有视频输出")
outputs = core._export(files, "06", time.strftime("%m%d_%H%M%S"), "夏日黑土_两阶段_720p")
original = core.stage_asset(str(source_range), sub=sub)
core._mux_original_audio(outputs, original)
core._upd(task["id"], status="done", progress=100, stage="完成", files=outputs, finished=time.time(), eta=0)
print(json.dumps(outputs, ensure_ascii=False, indent=2))
