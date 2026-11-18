# -*- coding: utf-8 -*-
"""把「头肩特写参考图 + 修正版提示词」写回 05 工作流，让 GUI 里看到的和实际跑的一致。"""
import json, sys

sys.path.insert(0, "E:/Agent/projects/freetime_AI_Video_Comfyui")
from prompt_v2 import PROMPT_V2

WF = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/user/default/workflows/MiniMax_H3_本地/05_H3本地_源视频换人_单人.json"

d = json.load(open(WF, encoding="utf-8"))
nodes = {n["id"]: n for n in d["nodes"]}

# 1) 接上 139 (LoadImage 头肩特写) -> 136.ref_images.ref_image_1
n136, n139 = nodes[136], nodes[139]
slot = next(i for i, s in enumerate(n136["inputs"]) if s["name"] == "ref_images.ref_image_1")
if n136["inputs"][slot].get("link") is None:
    lid = max(l[0] for l in d["links"]) + 1
    d["links"].append([lid, 139, 0, 136, slot, "IMAGE"])
    n136["inputs"][slot]["link"] = lid
    n139.setdefault("outputs", [{"name": "IMAGE", "type": "IMAGE", "links": []}])
    n139["outputs"][0]["links"] = [lid]
    print("已接 ref_image_1 ->", lid)
else:
    print("ref_image_1 已连接")

# 2) 换提示词
nodes[138]["widgets_values"] = [PROMPT_V2]
print("提示词已更新，段数", len(PROMPT_V2.split("\n\n")))

# 3) 备注里记一笔这次的口径
for n in d["nodes"]:
    if n["type"] == "MarkdownNote" and n["id"] == 116:
        t = n["widgets_values"][0]
        if "头肩特写" not in t:
            t = t.replace(
                "### 当前预设（第 1 段）",
                "### 两张参考图（重要）\n"
                "`ref_image_0` = 全身定妆图 → `<Picture 1>`（服装/体型/整体身份）\n"
                "`ref_image_1` = 头肩特写 → `<Picture 2>`（发型、五官、瞳色、唇形、皮肤质感）\n"
                "只喂全身图时，脸在参考图里只有几十像素，模型只能编一张「人偶脸」——表情僵硬诡异基本都出在这。\n\n"
                "### 音频\n"
                "H3 自己生成的那条音轨和原曲无关，**预览和成片一律用原片音轨**"
                "（`mux_seg_audio.py` 挂单段、`assemble_full.py` 挂全片）。\n\n"
                "### 当前预设（第 1 段）")
            n["widgets_values"] = [t]
        break

json.dump(d, open(WF, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("写回", WF, "links", len(d["links"]))
