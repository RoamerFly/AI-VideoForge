# -*- coding: utf-8 -*-
"""工作流图结构校验：连线双向一致、槽位类型匹配、无悬挂 link"""
import json, sys, glob, os

WK = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/user/default/workflows/MiniMax_H3_本地"

def check(path):
    d = json.load(open(path, encoding="utf-8"))
    errs, warns = [], []
    nodes = {n["id"]: n for n in d["nodes"]}
    if len(nodes) != len(d["nodes"]):
        errs.append("节点 id 重复")
    lmap = {}
    for row in d["links"]:
        if len(row) != 6:
            errs.append(f"link 行长度异常 {row}")
            continue
        l, a, aslot, b, bslot, t = row
        if l in lmap:
            errs.append(f"link id 重复 {l}")
        lmap[l] = row
        if a not in nodes:
            errs.append(f"link {l} 源节点 {a} 不存在"); continue
        if b not in nodes:
            errs.append(f"link {l} 目标节点 {b} 不存在"); continue
        so = nodes[a].get("outputs") or []
        ti = nodes[b].get("inputs") or []
        if aslot >= len(so):
            errs.append(f"link {l} 源 {a} 槽位 {aslot} 越界(共{len(so)})"); continue
        if bslot >= len(ti):
            errs.append(f"link {l} 目标 {b} 槽位 {bslot} 越界(共{len(ti)})"); continue
        if so[aslot].get("type") != ti[bslot].get("type"):
            # 允许 * 通配
            if "*" not in (so[aslot].get("type"), ti[bslot].get("type")):
                warns.append(f"类型不一致 {l}: {a}.{so[aslot]['name']}({so[aslot].get('type')}) -> {b}.{ti[bslot]['name']}({ti[bslot].get('type')})")
        if l not in (so[aslot].get("links") or []):
            errs.append(f"link {l} 未登记在源 {a}.{aslot}.links")
        if ti[bslot].get("link") != l:
            errs.append(f"link {l} 与目标 {b}.{bslot}.link={ti[bslot].get('link')} 不一致")

    # 输入声明的 link 必须在表里
    for n in d["nodes"]:
        for i, s in enumerate(n.get("inputs") or []):
            l = s.get("link")
            if l is None:
                continue
            if l not in lmap:
                errs.append(f"{n['id']}({n['type']}).{s['name']} 指向不存在的 link {l}")
            elif lmap[l][3] != n["id"] or lmap[l][4] != i:
                errs.append(f"{n['id']}({n['type']}).{s['name']} link {l} 归属错误")
        for i, s in enumerate(n.get("outputs") or []):
            for l in (s.get("links") or []):
                if l not in lmap:
                    errs.append(f"{n['id']}({n['type']}).{s['name']} 输出登记了不存在的 link {l}")
                elif lmap[l][1] != n["id"] or lmap[l][2] != i:
                    errs.append(f"{n['id']}({n['type']}).{s['name']} link {l} 源归属错误")

    # 必填输入必须接上（忽略有 widget 的转换槽和 optional）
    name = os.path.basename(path)
    print(f"===== {name}  节点 {len(d['nodes'])} 连线 {len(d['links'])}")
    for w in warns[:6]:
        print("  [warn]", w)
    if errs:
        for e in errs[:12]:
            print("  [ERR ]", e)
        print(f"  => {len(errs)} 个错误")
        return False
    print("  => OK")
    return True

ok = True
for p in sorted(glob.glob(os.path.join(WK, "*.json"))):
    ok &= check(p)
sys.exit(0 if ok else 1)
