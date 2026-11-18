# -*- coding: utf-8 -*-
"""把五个工作流转成 API，用极小尺寸提交一次，验证链路是否真的能跑。

尺寸压到 256x448 / 5 帧 / 4 步，只为验证节点接线与参数位次，不看画质。
05 缺 controlnet 权重，跳过。
"""
import json
import os
import sys
import time

from i2v_test import to_api, load, post, get

OI = load(r"C:/Users/RoverFly/AppData/Local/Temp/oi.json")
D = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/user/default/workflows/MiniMax_H3_五模式"

TARGETS = [
    ("01_T2V_文生视频.json", "01_t2v"),
    ("02_I2V_图生视频.json", "02_i2v"),
    ("03_R2V_视频参考.json", "03_r2v"),
]

GEN = ("MiniMaxH3ImageToVideo", "MiniMaxH3ReferenceToVideo")


def run(fname, tag, w=256, h=448, length=124):
    wf = load(os.path.join(D, fname))
    api = to_api(wf, OI)
    hit = []
    for nid, n in api.items():
        if n["class_type"] in GEN:
            n["inputs"]["width"] = w
            n["inputs"]["height"] = h
            n["inputs"]["length"] = length
            hit.append(nid)
        if n["class_type"] == "SaveVideo":
            n["inputs"]["filename_prefix"] = f"video/H3_五模式/_validate_{tag}"
    if not hit:
        return f"FAIL: 没找到生成节点"
    res = post(api)
    if "error" in res:
        msg = str(res["error"])
        return f"提交失败: {msg[:900]}"
    pid = res["prompt_id"]
    t0 = time.time()
    while time.time() - t0 < 900:
        time.sleep(6)
        hh = get(f"/history/{pid}")
        if pid in hh:
            st = hh[pid].get("status", {})
            if st.get("status_str") == "error":
                for m in st.get("messages", []):
                    if m[0] in ("execution_error", "execution_interrupted"):
                        return "执行报错: " + json.dumps(m[1], ensure_ascii=False)[:900]
                return "执行报错(未知): " + json.dumps(st, ensure_ascii=False)[:600]
            outs = [it.get("filename") for node in hh[pid].get("outputs", {}).values()
                    for v in node.values() if isinstance(v, list)
                    for it in v if isinstance(it, dict)]
            return f"OK  {(time.time()-t0)/60:.1f} 分钟  输出 {outs}"
    return "超时"


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for fname, tag in TARGETS:
        if only and only not in tag:
            continue
        print(f"\n=== {fname}", flush=True)
        r = run(fname, tag)
        print("   ", r, flush=True)
        if r.startswith(("提交失败", "FAIL")):
            break
