# -*- coding: utf-8 -*-
"""校验本地 H3 工作流：节点类型存在性、连线完整性、子图引用、widget 数量"""
import json, os, urllib.request

BASE = "http://127.0.0.1:8189"
DIRS = [
    r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/user/default/workflows/MiniMax_H3_本地",
]
_oi = None
def oi():
    global _oi
    if _oi is None:
        with urllib.request.urlopen(f"{BASE}/object_info", timeout=60) as r:
            _oi = json.load(r)
    return _oi

def widget_count(t):
    d = oi().get(t)
    if d is None:
        return None
    spec = {}
    spec.update(d["input"].get("required", {}))
    spec.update(d["input"].get("optional", {}))
    order = d.get("input_order", {})
    n = 0
    for name in order.get("required", []) + order.get("optional", []):
        s = spec.get(name)
        if s is None:
            continue
        t0 = s[0]
        if isinstance(t0, list):
            t0 = "COMBO"
        if t0 == "COMFY_DYNAMICCOMBO_V3":
            n += 1
            continue
        if t0 in {"STRING", "INT", "FLOAT", "BOOLEAN", "COMBO"}:
            n += 1
            if t0 == "INT" and isinstance(s[1], dict) and s[1].get("control_after_generate"):
                n += 1
    return n

problems = 0
for D in DIRS:
    for f in sorted(os.listdir(D)):
        if not f.endswith(".json"):
            continue
        p = os.path.join(D, f)
        d = json.load(open(p, encoding="utf-8"))
        nodes = {n["id"]: n for n in d["nodes"]}
        sgs = {s["id"] for s in d.get("definitions", {}).get("subgraphs", [])}
        print("=" * 72)
        print(f)
        print(f"  节点 {len(nodes)} / 连线 {len(d['links'])} / 子图 {len(sgs)}")

        # 节点类型
        for n in d["nodes"]:
            t = n["type"]
            if t in sgs:
                continue
            if t in ("Note", "MarkdownNote", "Reroute", "PrimitiveNode"):
                continue
            if oi().get(t) is None:
                print(f"  [X] 未知节点类型 {t} (id {n['id']})")
                problems += 1

        # 连线
        for l in d["links"]:
            lid, on, oslot, tn, tslot, typ = l
            if on not in nodes or tn not in nodes:
                print(f"  [X] link {l} 端点缺失")
                problems += 1
                continue
            src, dst = nodes[on], nodes[tn]
            if oslot >= len(src.get("outputs") or []):
                print(f"  [X] link {l} 源输出槽越界")
                problems += 1
            elif lid not in (src["outputs"][oslot].get("links") or []):
                print(f"  [X] link {l} 源节点 outputs[{oslot}].links 未登记")
                problems += 1
            if tslot >= len(dst.get("inputs") or []):
                print(f"  [X] link {l} 目标输入槽越界")
                problems += 1
            elif dst["inputs"][tslot].get("link") != lid:
                print(f"  [X] link {l} 目标 inputs[{tslot}].link={dst['inputs'][tslot].get('link')}")
                problems += 1

        # 子图 id 引用
        for n in d["nodes"]:
            if len(n["type"]) == 36 and n["type"] not in sgs:
                print(f"  [X] 子图实例 {n['id']} 引用了不存在的子图定义")
                problems += 1

        # widget 数量
        for n in d["nodes"]:
            if n["type"] in sgs or n["type"] in ("Note", "MarkdownNote", "PrimitiveNode"):
                continue
            exp = widget_count(n["type"])
            got = len(n.get("widgets_values") or [])
            legacy_extra = n["type"] in ("LoadImage", "SaveVideo", "LoadAudio")  # 上传按钮/codec 等前端附加项
            if exp is not None and got != exp and not (legacy_extra and got == exp + 1):
                print(f"  [X] {n['type']}(id {n['id']}) widget 期望{exp} 实际{got}")
                problems += 1

print("\n" + ("全部通过" if problems == 0 else f"发现 {problems} 个问题"))
