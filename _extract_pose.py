# -*- coding: utf-8 -*-
"""从动作库的规范化视频抽取骨架 → pose.mp4

节点选择（实测结论）：
  - DWPose(DWPreprocessor) 对二次元角色近乎不可用：825 帧里 45% 空白，出图的也常缺肢
  - OpenPose(OpenposePreprocessor) 全开 576：抽样 6/6 骨架完整，故默认用 OpenPose

用法：
    python _extract_pose.py dance_001_shenhe_stand_twist [resolution] [node]
        node: openpose(默认) | dwpose
"""
import json
import os
import shutil
import sys
import time

sys.path.insert(0, "app")
import core

LIB = r"E:/Agent/projects/LTX25_ActionLibrary"
ACTION = sys.argv[1] if len(sys.argv) > 1 else "dance_001_shenhe_stand_twist"
ADIR = os.path.join(LIB, "actions", ACTION)
SRC = os.path.join(ADIR, "source_trimmed.mp4")
DST = os.path.join(ADIR, "pose.mp4")

# resolution 是"短边目标值"。源片短边 576；设成会把高度算成奇数的值（如 768→1365）
# 会让 SaveVideo 的 libx264 直接报错，务必保证 结果高/宽 是偶数。
RES = int(sys.argv[2]) if len(sys.argv) > 2 else 576
NODE = (sys.argv[3] if len(sys.argv) > 3 else "openpose").lower()

assert os.path.exists(SRC), f"缺 {SRC}"

CI = core.comfy_input()
stage = os.path.join(CI, "h3studio", "ltx25")
os.makedirs(stage, exist_ok=True)
name = f"{ACTION}.mp4"
shutil.copy2(SRC, os.path.join(stage, name))

if NODE == "dwpose":
    pre = {"class_type": "DWPreprocessor", "inputs": {
        "image": ["2", 0], "detect_hand": "enable", "detect_body": "enable",
        "detect_face": "enable", "resolution": RES,
        "bbox_detector": "yolox_l.onnx", "pose_estimator": "dw-ll_ucoco_384.onnx",
        "scale_stick_for_xinsr_cn": "disable"}}
else:
    pre = {"class_type": "OpenposePreprocessor", "inputs": {
        "image": ["2", 0], "detect_hand": "enable", "detect_body": "enable",
        "detect_face": "enable", "resolution": RES,
        "scale_stick_for_xinsr_cn": "disable"}}

api = {
    "1": {"class_type": "LoadVideo", "inputs": {"file": f"h3studio/ltx25/{name}"}},
    "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
    "3": pre,
    "4": {"class_type": "CreateVideo", "inputs": {"images": ["3", 0], "fps": 24.0}},
    "5": {"class_type": "SaveVideo", "inputs": {
        "video": ["4", 0], "filename_prefix": f"H3影栈/pose_{NODE}_{ACTION}",
        "format": "mp4", "codec": "h264"}},
}

pid = core.submit(api)
print(f"提交 {pid} | {NODE} | res={RES}", flush=True)
t0 = time.time()
while True:
    h = core.history(pid)
    if h and ((h.get("status") or {}).get("completed") or h.get("outputs")):
        outs = [f for f in core.collect_outputs(h) if f.startswith("H3影栈/")]
        if not outs:
            print("没有输出"); sys.exit(1)
        shutil.copy2(os.path.join(core.comfy_output(), outs[0]), DST)
        info = core.probe_video(DST)
        print(f"骨架完成 {round(time.time()-t0)}s → {DST}")
        print("规格:", json.dumps({k: info.get(k) for k in ("width", "height", "fps", "frames", "duration")}, ensure_ascii=False))
        break
    if h and (h.get("status") or {}).get("status_str") == "error":
        for m in h["status"].get("messages", []):
            if m and m[0] == "execution_error":
                print("失败:", (m[1] or {}).get("exception_message", "")[:600])
        sys.exit(1)
    time.sleep(4)
