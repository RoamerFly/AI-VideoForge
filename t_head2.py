# -*- coding: utf-8 -*-
"""换掉头部参考图：参考05（上挑猫眼浓妆）-> 图集 003 的头部（细眼线、自然眼型）。

用法: python t_head2.py [宽度] [高度] [label]
"""
import json, sys, time

sys.path.insert(0, "E:/Agent/projects/freetime_AI_Video_Comfyui")
import run_h3_swap_full as R
import ab_face_test as A
from prompt_v3 import PROMPT_V3

HEAD2 = "role_swap_20261112/zhaomei_head2.png"
FULL2 = "role_swap_20261112/zhaomei_full2.png"


def main():
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 640
    h = int(sys.argv[2]) if len(sys.argv) > 2 else 1120
    label = sys.argv[3] if len(sys.argv) > 3 else f"head2_{w}"

    oi = R.load(R.OI)
    api = R.to_api(R.load(R.WF), oi)
    api = A.build(api, label, 4, True, 1.00)
    api["136"]["inputs"]["ref_images.ref_image_1"] = ["139", 0]
    api["139"]["inputs"]["image"] = HEAD2
    if label.endswith("_full2"):
        api["137"]["inputs"]["image"] = FULL2  # Picture 1 也换成淡妆全身图
    api["138"]["inputs"]["value"] = PROMPT_V3
    api["154"]["inputs"]["value"] = w
    api["155"]["inputs"]["value"] = h
    print(f"\n===== {label} {w}x{h} 124f 4steps ref2=head2", flush=True)

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


if __name__ == "__main__":
    sys.exit(main())
