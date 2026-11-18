# -*- coding: utf-8 -*-
"""走产品路径验证 SCAIL-2 高质量档：build_api('05', engine=scail) → 提交。"""
import sys
import time

sys.path.insert(0, "app")
import core

STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 12
TAG = sys.argv[2] if len(sys.argv) > 2 else "hq"

p = {
    "engine": "scail",
    "images": ["h3studio/scail/hinata.png"],
    "char_count": 1,
    "video": "h3studio/scail/drive_65f_512x896.mp4",
    "prompt": ("A young woman with long straight black hair, wearing a red chinese halter dress "
               "with silver belt, red wrist guards and red boots, dancing in a clean white studio "
               "with wooden floor, full body shot"),
    "quality": ("natural lighting, sharp details, smooth motion, correct anatomy, "
                "no extra limbs, clean background"),
    "width": 512, "height": 896, "frames": 65,
    "steps": STEPS, "seed": 20261114, "tag": f"scail_{TAG}",
}
api = core.build_api("05", p)
g = api["21"]["inputs"]
print(f"画布 {g['width']}x{g['height']} | len {g['length']} | steps {api['22']['inputs']['steps']} "
      f"| cfg {api['24']['inputs']['cfg']}", flush=True)

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
                print("ERROR:", (m[1] or {}).get("exception_message", "")[:800], flush=True)
                print("node:", (m[1] or {}).get("node_type"), flush=True)
        break
    time.sleep(5)
