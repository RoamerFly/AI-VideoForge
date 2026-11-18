# -*- coding: utf-8 -*-
"""表情动态专项：降 swap LoRA 强度，看脸部是否解冻（4 步 · 124 帧 · 640×1120）。"""
import json, sys, time

sys.path.insert(0, "E:/Agent/projects/freetime_AI_Video_Comfyui")
import run_h3_swap_full as R
import ab_face_test as A

CASES = [
    ("sw075", 0.75),
    ("sw085", 0.85),
]


def main():
    oi = R.load(R.OI)
    base = R.to_api(R.load(R.WF), oi)
    for label, sw in CASES:
        api = A.build(base, f"s04_{label}", 4, True, sw)
        print(f"\n===== {label} swap={sw}", flush=True)
        res = A.post(api)
        if "error" in res:
            print("提交失败:", str(res["error"])[:1500], flush=True)
            return 1
        pid = res["prompt_id"]
        print("prompt_id", pid, flush=True)
        t0 = time.time()
        while True:
            time.sleep(10)
            h = R.get(f"/history/{pid}")
            if pid in h:
                st = h[pid].get("status", {})
                if st.get("status_str") == "error":
                    print("执行报错:", json.dumps(st, ensure_ascii=False)[:1500], flush=True)
                    return 2
                files = [it["filename"] for node in h[pid].get("outputs", {}).values()
                         for v in node.values() if isinstance(v, list)
                         for it in v if isinstance(it, dict) and it.get("filename")]
                print(f"{label} 完成 {(time.time()-t0)/60:.1f} 分钟 {files}", flush=True)
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
