# -*- coding: utf-8 -*-
"""用运行中的 ComfyUI /object_info 校验工作流 JSON 的 widget 数量与顺序是否匹配"""
import json, os, urllib.request

BASE = "http://127.0.0.1:8189"
WF = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/user/default/workflows/MiniMax_H3"

WIDGET_TYPES = {"STRING", "INT", "FLOAT", "BOOLEAN", "COMBO", "COMFY_DYNAMICCOMBO_V3", "AUDIOUPLOAD"}
LINK_TYPES = {"IMAGE", "VIDEO", "AUDIO", "MASK", "LATENT", "MODEL", "CLIP", "VAE", "CONDITIONING"}

_cache = {}
def info(t):
    if t not in _cache:
        with urllib.request.urlopen(f"{BASE}/object_info/{t}", timeout=20) as r:
            _cache[t] = json.load(r).get(t)
    return _cache[t]


def expected_widgets(node_type, selected):
    d = info(node_type)
    if d is None:
        return None, f"节点类型不存在: {node_type}"
    order = d.get("input_order", {})
    spec = {}
    spec.update(d["input"].get("required", {}))
    spec.update(d["input"].get("optional", {}))
    exp = []
    for name in order.get("required", []) + order.get("optional", []):
        s = spec[name]
        t = s[0]
        if isinstance(t, list):  # 老式 COMBO：选项直接是列表
            t = "COMBO"
        if t == "COMFY_DYNAMICCOMBO_V3":
            exp.append((name, "COMBO"))
            opts = {o["key"]: o["inputs"] for o in s[1]["options"]}
            if selected not in opts:
                return exp, f"dynamic combo 选中值 {selected!r} 不在选项中: {list(opts)}"
            sub = opts[selected]
            suborder = sub.get("input_order", {})
            subreq = sub.get("required", {})
            subopt = sub.get("optional", {})
            allsub = {}
            allsub.update(subreq); allsub.update(subopt)
            closed = sub.get("input_order", {}).get("required", list(subreq))
            closed = closed + sub.get("input_order", {}).get("optional", list(subopt))
            if not closed:
                closed = list(allsub)
            for sn in closed:
                st = allsub[sn][0]
                if st in ("IMAGE", "VIDEO", "AUDIO"):
                    continue
                if st in WIDGET_TYPES:
                    exp.append((f"{name}.{sn}", st))
                    if st == "INT" and isinstance(allsub[sn][1], dict) and allsub[sn][1].get("control_after_generate"):
                        exp.append((f"{name}.{sn}.control", "CONTROL"))
            continue
        if t == "COMFY_DYNAMICCOMBO_V2":
            return exp, "旧版动态 combo，请手工确认"
        if t in WIDGET_TYPES:
            exp.append((name, t))
            opts = s[1] if len(s) > 1 and isinstance(s[1], dict) else {}
            if t == "INT" and opts.get("control_after_generate"):
                exp.append((name + ".control", "CONTROL"))
        elif t in LINK_TYPES:
            continue
        else:
            return exp, f"未知输入类型 {t}（{name}）"
    return exp, None


ok_all = True
for f in sorted(os.listdir(WF)):
    if not f.endswith(".json"):
        continue
    p = os.path.join(WF, f)
    d = json.load(open(p, encoding="utf-8"))
    print("=" * 70)
    print(f)
    for n in d["nodes"]:
        t = n["type"]
        wv = n.get("widgets_values", [])
        if t in ("Note", "MarkdownNote"):
            print(f"  [note] {t}: ok")
            continue
        exp, err = expected_widgets(t, wv[0] if wv else None)
        if exp is None:
            print(f"  [FAIL] {t}: {err}")
            ok_all = False
            continue
        names = [e[0] for e in exp]
        got = len(wv)
        flag = "OK " if got == len(exp) else "MISMATCH"
        if got != len(exp):
            ok_all = False
        print(f"  [{flag}] {t}  期望{len(exp)}个widget / 实际{got}")
        print(f"        期望: {names}")
        if got != len(exp):
            print(f"        实际: {wv[:6]}...")
        # 值类型粗校验
        for i, val in enumerate(wv[: len(exp)]):
            et = exp[i][1]
            if et == "BOOLEAN" and not isinstance(val, bool):
                print(f"        !! {exp[i][0]} 期望 bool，实际 {type(val).__name__}")
                ok_all = False
            if et == "INT" and not isinstance(val, (int, float)):
                print(f"        !! {exp[i][0]} 期望 int，实际 {type(val).__name__}")
                ok_all = False
        # 连线完整性
        in_links = {i["name"]: i.get("link") for i in n.get("inputs", [])}
        for name, lk in in_links.items():
            if lk is not None and lk not in [l[0] for l in d["links"]]:
                print(f"        !! 输入 {name} 引用了不存在的 link {lk}")
                ok_all = False
    for l in d["links"]:
        if l[1] not in [n["id"] for n in d["nodes"]] or l[3] not in [n["id"] for n in d["nodes"]]:
            print(f"  !! link {l} 指向不存在的节点")
            ok_all = False

print("\nALL OK" if ok_all else "\n存在不匹配项")
