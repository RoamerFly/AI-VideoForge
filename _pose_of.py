# -*- coding: utf-8 -*-
"""对任意视频跑 OpenPose，输出骨架视频到 ComfyUI output。

用法：python _pose_of.py <input目录下的文件名> [短边分辨率]
"""
import sys
import time

sys.path.insert(0, "app")
import core

SRC = sys.argv[1]
RES = int(sys.argv[2]) if len(sys.argv) > 2 else 576

api = {
    "1": {"class_type": "LoadVideo", "inputs": {"file": SRC}},
    "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
    "3": {"class_type": "OpenposePreprocessor", "inputs": {
        "image": ["2", 0], "detect_hand": "enable", "detect_body": "enable",
        "detect_face": "enable", "resolution": RES,
        "scale_stick_for_xinsr_cn": "disable"}},
    "4": {"class_type": "CreateVideo", "inputs": {"images": ["3", 0], "fps": 24.0}},
    "5": {"class_type": "SaveVideo", "inputs": {
        "video": ["4", 0], "filename_prefix": "H3影栈/posechk",
        "format": "mp4", "codec": "h264"}},
}

pid = core.submit(api)
print("提交", pid, flush=True)
t0 = time.time()
while True:
    h = core.history(pid)
    if h and ((h.get("status") or {}).get("completed") or h.get("outputs")):
        print("完成", round(time.time() - t0), "s", flush=True)
        print("输出:", [f for f in core.collect_outputs(h) if "posechk" in f], flush=True)
        break
    st = (h or {}).get("status") or {}
    if st.get("status_str") == "error":
        for m in st.get("messages", []):
            if m and m[0] == "execution_error":
                print("失败:", (m[1] or {}).get("exception_message", "")[:600], flush=True)
        sys.exit(1)
    time.sleep(4)
