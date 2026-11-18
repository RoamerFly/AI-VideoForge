# -*- coding: utf-8 -*-
"""DWPose 参数探针：拿同一批失败帧，试不同 detect/resolution 组合，看哪种最稳。

用法：
    python _pose_probe.py                 # 默认测 6 组
    python _pose_probe.py 3               # 只测前 3 组
"""
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, "app")
import core

ADIR = r"E:/Agent/projects/LTX25_ActionLibrary/actions/dance_001_shenhe_stand_twist"
SRC = os.path.join(ADIR, "source_trimmed.mp4")
CI = core.comfy_input()
STAGE = os.path.join(CI, "h3studio", "poseprobe")
os.makedirs(STAGE, exist_ok=True)

# 已知骨架失败的秒数（由空白帧统计反推）
BAD_TIMES = [0.0, 1.1, 3.2, 5.1, 7.5, 9.6]

# (标签, detect_hand, detect_body, detect_face, resolution)
CASES = [
    ("A_all_576",   "enable",  "enable",  "enable",  576),
    ("B_body_576",  "disable", "enable",  "disable", 576),
    ("C_all_640",   "enable",  "enable",  "enable",  640),
    ("D_bodyhand_640", "enable", "enable", "disable", 640),
    ("E_body_640",  "disable", "enable",  "disable", 640),
    ("F_all_512",   "enable",  "enable",  "enable",  512),
]


def cut_frames():
    names = []
    for i, t in enumerate(BAD_TIMES):
        n = f"bad{i:02d}.png"
        p = os.path.join(STAGE, n)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}",
                        "-i", SRC, "-frames:v", "1", p], check=True)
        names.append(f"h3studio/poseprobe/{n}")
    return names


def run_case(label, dh, db, df, res, imgs):
    api = {}
    nid = 1
    saved = []
    for img in imgs:
        api[str(nid)] = {"class_type": "LoadImage", "inputs": {"image": img, "upload": "image"}}
        load_id = str(nid); nid += 1
        api[str(nid)] = {"class_type": "DWPreprocessor", "inputs": {
            "image": [load_id, 0], "detect_hand": dh, "detect_body": db, "detect_face": df,
            "resolution": res, "bbox_detector": "yolox_l.onnx",
            "pose_estimator": "dw-ll_ucoco_384.onnx", "scale_stick_for_xinsr_cn": "disable",
        }}
        pose_id = str(nid); nid += 1
        api[str(nid)] = {"class_type": "SaveImage", "inputs": {
            "images": [pose_id, 0], "filename_prefix": f"poseprobe/{label}"}}
        saved.append(str(nid)); nid += 1

    pid = core.submit(api)
    t0 = time.time()
    while True:
        h = core.history(pid)
        if h and ((h.get("status") or {}).get("completed") or h.get("outputs")):
            outs = [f for f in core.collect_outputs(h)]
            print(f"[{label}] {round(time.time()-t0)}s 输出 {len(outs)} 张", flush=True)
            return outs
        if h and (h.get("status") or {}).get("status_str") == "error":
            for m in h["status"].get("messages", []):
                if m and m[0] == "execution_error":
                    print(f"[{label}] 失败:", (m[1] or {}).get("exception_message", "")[:300])
            return []
        time.sleep(3)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else len(CASES)
    imgs = cut_frames()
    print(f"探针帧 {len(imgs)} 张：{BAD_TIMES}", flush=True)
    for case in CASES[:n]:
        run_case(*case, imgs)
    print("完成，结果在 output/poseprobe/")
