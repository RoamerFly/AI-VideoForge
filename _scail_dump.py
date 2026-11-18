# -*- coding: utf-8 -*-
"""把 SCAIL-2 官方模板的子图展平成「节点 + 连线」清单，便于构造 API 图。"""
import json

P = (r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/python/"
     r"Lib/site-packages/comfyui_workflow_templates_json/templates/"
     r"video_wan21_scail2_character_replacement.json")
d = json.load(open(P, encoding="utf-8"))
sub = [s for s in d["definitions"]["subgraphs"] if s.get("name", "").endswith("Base)")][0]
nodes = {n["id"]: n for n in sub["nodes"]}
names = {nid: n.get("type") for nid, n in nodes.items()}

print("link 样例:", json.dumps(sub["links"][0], ensure_ascii=False))
print("\n=== 子图输入槽位（下标对应 api 里用多少号） ===")
for i, x in enumerate(sub.get("inputs") or []):
    print(f"  [{i}] {x.get('name')} : {x.get('type')}")

print("\n=== 连线 ===")
for l in sub["links"]:
    if isinstance(l, dict):
        s, ss, t, ts = l.get("origin_id"), l.get("origin_slot"), l.get("target_id"), l.get("target_slot")
        tp = l.get("type")
    else:
        s, ss, t, ts, tp = l[1], l[2], l[3], l[4], l[5]
    sn = names.get(s) or f"IN#{s}"
    tn = names.get(t) or f"OUT#{t}"
    print(f"  {sn}({s})[{ss}] -> {tn}({t})[{ts}]  {tp}")

print("\n=== 关键节点参数 ===")
for nid in (114, 154, 156, 177, 196, 197, 198, 95, 11, 318, 19, 18, 27):
    n = nodes.get(nid)
    if not n:
        continue
    print(f"#{nid} {n.get('type')}: {json.dumps(n.get('widgets_values'), ensure_ascii=False)}")
