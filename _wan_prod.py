# -*- coding: utf-8 -*-
"""走产品路径验证 Wan 引擎：build_api('05', engine=wan) → 提交 → 计时。"""
import sys, time
sys.path.insert(0, "app")
import core

p = {
    "engine": "wan",
    "images": ["h3studio/pose_test/hinata_fitted.png"],
    "char_count": 1,
    "video": "h3studio/pose_test/shenhe_81f_480x832.mp4",
    "prompt": "full body shot, head to toe, wide shot, a young woman with long black hair, red chinese halter dress, silver belt, red boots, standing on wooden floor, clean white studio background, soft even lighting",
    "quality": "sharp, detailed face, natural motion, stable background",
    "width": 640, "height": 1120, "frames": 81,
    "steps": 6, "seed": 20261114, "tag": "wan_refstr055",
}
api = core.build_api("05", p)
api["14"]["inputs"]["reference_image_strength"] = 0.55
g = api["14"]["inputs"]
print("画布:", g["width"], "x", g["height"], "| 帧数:", g["length"], "| 步数:", api["17"]["inputs"]["steps"], flush=True)
pid = core.submit(api)
t0 = time.time()
while True:
    h = core.history(pid)
    if h and ((h.get("status") or {}).get("completed") or h.get("outputs")):
        outs = [f for f in core.collect_outputs(h) if f.startswith("H3影栈/")]
        print("DONE", round(time.time() - t0), "s →", outs, flush=True)
        break
    if h and (h.get("status") or {}).get("status_str") == "error":
        for m in h["status"].get("messages", []):
            if m and m[0] == "execution_error":
                print("ERROR:", (m[1] or {}).get("exception_message", "")[:700], flush=True)
                print("node:", (m[1] or {}).get("node_type"), flush=True)
        break
    time.sleep(5)
