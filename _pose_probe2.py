# -*- coding: utf-8 -*-
"""第二组探针：换 OpenPose（CMU body_pose_model），看对二次元角色是否比 DWPose 稳。"""
import os
import sys
import time

sys.path.insert(0, "app")
import core

STAGE = "h3studio/poseprobe"
IMGS = [f"{STAGE}/bad{i:02d}.png" for i in range(6)]

CASES = [
    ("op_all_576",   "enable",  "enable",  "enable",  576),
    ("op_body_576",  "disable", "enable",  "disable", 576),
    ("op_body_1024", "disable", "enable",  "disable", 1024),
]


def run(label, dh, db, df, res):
    api = {}
    nid = 1
    for img in IMGS:
        api[str(nid)] = {"class_type": "LoadImage", "inputs": {"image": img, "upload": "image"}}
        lid = str(nid); nid += 1
        api[str(nid)] = {"class_type": "OpenposePreprocessor", "inputs": {
            "image": [lid, 0], "detect_hand": dh, "detect_body": db, "detect_face": df,
            "resolution": res, "scale_stick_for_xinsr_cn": "disable"}}
        pid_node = str(nid); nid += 1
        api[str(nid)] = {"class_type": "SaveImage", "inputs": {
            "images": [pid_node, 0], "filename_prefix": f"poseprobe/{label}"}}
        nid += 1
    pid = core.submit(api)
    t0 = time.time()
    while True:
        h = core.history(pid)
        if h and ((h.get("status") or {}).get("completed") or h.get("outputs")):
            print(f"[{label}] {round(time.time()-t0)}s ok", flush=True)
            return
        if h and (h.get("status") or {}).get("status_str") == "error":
            for m in h["status"].get("messages", []):
                if m and m[0] == "execution_error":
                    print(f"[{label}] 失败:", (m[1] or {}).get("exception_message", "")[:300])
            return
        time.sleep(3)


if __name__ == "__main__":
    for c in CASES:
        run(*c)
    print("done")
