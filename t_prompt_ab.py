# -*- coding: utf-8 -*-
"""验证「表情/皮肤提示词」本身的作用：4 步 · 124 帧 · 640×1120，只换提示词。"""
import json, sys, time, urllib.request, urllib.error

sys.path.insert(0, "E:/Agent/projects/freetime_AI_Video_Comfyui")
import run_h3_swap_full as R
import ab_face_test as A

NEW_PROMPT = None


def strip_expression(p):
    """删掉表情与神态、皮肤与质感两段，还原成上一版提示词"""
    parts = [x for x in p.split("\n\n")
             if not x.startswith("表情与神态") and not x.startswith("皮肤与质感")]
    return "\n\n".join(parts)


def main():
    oi = R.load(R.OI)
    api = A.build(R.to_api(R.load(R.WF), oi), "s04_oldprompt", 4, True, 1.00)
    full = api["138"]["inputs"]["value"]
    api["138"]["inputs"]["value"] = strip_expression(full)
    print("旧提示词段数:", len(api["138"]["inputs"]["value"].split("\n\n")),
          "| 新提示词段数:", len(full.split("\n\n")), flush=True)

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
            print(f"完成 {(time.time()-t0)/60:.1f} 分钟 {files}", flush=True)
            return 0


if __name__ == "__main__":
    sys.exit(main())
