# -*- coding: utf-8 -*-
"""表情/神态 A-B 测试：124 帧 · 640×1120，只变「步数 + turbo」一个变量。

用法:
  python ab_face_test.py            # 跑默认两组
  python ab_face_test.py 4 12       # 只跑步数列出的组
"""
import json, sys, time, urllib.request, urllib.error

sys.path.insert(0, "E:/Agent/projects/freetime_AI_Video_Comfyui")
import run_h3_swap_full as R

VIDEO = "role_swap_20261112/ab_124f.mp4"
FRAMES = 124           # 17*7+5，H3 合法网格
PREFIX = "video/H3_swap/ab"

# (标签, 步数, 是否启用 turbo LoRA, swap LoRA 强度)
CASES = [
    ("s04_turbo_sw100", 4, True, 1.00),
    ("s12_full_sw100", 12, False, 1.00),
]

NODE_STEPS_TURBO = "144"
NODE_STEPS_FULL = "143"
NODE_BOOL = "146"
NODE_SWAP_LORA = "147"
NODE_VIDEO = "150"
NODE_FRAMES = "153"
NODE_SAVE = "92"


def build(api, label, steps, turbo, swap):
    api = json.loads(json.dumps(api))
    api[NODE_STEPS_TURBO]["inputs"]["value"] = int(steps)
    api[NODE_STEPS_FULL]["inputs"]["value"] = int(steps)
    api[NODE_BOOL]["inputs"]["value"] = bool(turbo)
    api[NODE_SWAP_LORA]["inputs"]["strength_model"] = float(swap)
    api[NODE_VIDEO]["inputs"]["file"] = VIDEO
    api[NODE_FRAMES]["inputs"]["value"] = FRAMES
    api[NODE_SAVE]["inputs"]["filename_prefix"] = f"{PREFIX}_{label}"
    return api


def post(prompt):
    body = json.dumps({"prompt": prompt, "client_id": "h3-ab"}).encode()
    req = urllib.request.Request(R.HOST + "/prompt", body, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode("utf-8", "replace")}


def main():
    want = sys.argv[1:]
    oi = R.load(R.OI)
    base = R.to_api(R.load(R.WF), oi)
    cases = [c for c in CASES if not want or c[1] in want]

    for label, steps, turbo, swap in cases:
        api = build(base, label, steps, turbo, swap)
        print(f"\n===== {label}  steps={steps} turbo={turbo} swap={swap}  frames={FRAMES}", flush=True)
        res = post(api)
        if "error" in res:
            print("提交失败:", str(res["error"])[:2000], flush=True)
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
                    print("执行报错:", json.dumps(st, ensure_ascii=False)[:2000], flush=True)
                    return 2
                files = []
                for node in h[pid].get("outputs", {}).values():
                    for v in node.values():
                        if isinstance(v, list):
                            for it in v:
                                if isinstance(it, dict) and it.get("filename"):
                                    files.append(it["filename"])
                print(f"{label} 完成，用时 {(time.time()-t0)/60:.1f} 分钟，输出 {files}", flush=True)
                break
            if int(time.time() - t0) % 180 < 10:
                try:
                    q = R.get("/queue")
                    print(f"  [{label}] {(time.time()-t0)/60:.1f} 分钟  running={len(q.get('queue_running',[]))}", flush=True)
                except Exception:
                    pass
    print("\n全部完成", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
