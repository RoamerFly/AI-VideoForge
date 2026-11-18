# -*- coding: utf-8 -*-
"""眼部专项测试：v3 提示词（清淡眼妆）在 640×1120 与 768×1344 两个尺寸下各跑一遍。

用法: python t_eye_v3.py
"""
import json, sys, time

sys.path.insert(0, "E:/Agent/projects/freetime_AI_Video_Comfyui")
import run_h3_swap_full as R
import ab_face_test as A
from prompt_v3 import PROMPT_V3

VIDEO = "role_swap_20261112/ab_124f.mp4"
FRAMES = 124

ARMS = [
    ("eye640", 640, 1120),
    ("eye768", 768, 1344),
]


def run_arm(base, label, w, h):
    api = A.build(base, label, 4, True, 1.00)
    api["136"]["inputs"]["ref_images.ref_image_1"] = ["139", 0]
    api["138"]["inputs"]["value"] = PROMPT_V3
    api["154"]["inputs"]["value"] = w
    api["155"]["inputs"]["value"] = h
    print(f"\n===== {label} {w}x{h} 124f 4steps", flush=True)
    res = A.post(api)
    if "error" in res:
        print("提交失败:", str(res["error"])[:1500], flush=True)
        return 1
    pid = res["prompt_id"]
    print("prompt_id", pid, flush=True)
    t0 = time.time()
    while True:
        time.sleep(10)
        hist = R.get(f"/history/{pid}")
        if pid in hist:
            st = hist[pid].get("status", {})
            if st.get("status_str") == "error":
                print("执行报错:", json.dumps(st, ensure_ascii=False)[:1500], flush=True)
                return 2
            files = [it["filename"] for node in hist[pid].get("outputs", {}).values()
                     for v in node.values() if isinstance(v, list)
                     for it in v if isinstance(it, dict) and it.get("filename")]
            print(f"{label} 完成 {(time.time()-t0)/60:.1f} 分钟 {files}", flush=True)
            return 0
        if int(time.time() - t0) % 180 < 10:
            try:
                q = R.get("/queue")
                print(f"  [{label}] {(time.time()-t0)/60:.1f} 分钟 running={len(q.get('queue_running', []))}", flush=True)
            except Exception:
                pass


def main():
    oi = R.load(R.OI)
    base = R.to_api(R.load(R.WF), oi)
    for label, w, h in ARMS:
        rc = run_arm(base, label, w, h)
        if rc:
            return rc
    print("\n两组都完成", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
