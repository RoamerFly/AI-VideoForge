# -*- coding: utf-8 -*-
"""基于官方 r2v 模板，生成「源视频换人」工作流：Ref2VA + swap LoRA + AddGuide 动作锚定"""
import json, os

TPL = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/python/Lib/site-packages/comfyui_workflow_templates_json/templates"
OUT = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/user/default/workflows/MiniMax_H3_本地"
os.makedirs(OUT, exist_ok=True)

PROMPT = """画面风格：写实摄影质感，纯白摄影棚背景，全身构图，保持与原片一致的机位、景别、焦距、光线方向，镜头全程固定不移动。

人物：把舞者替换为 <Picture 1> 中的角色——深棕红色长发、头戴浅色竹编斗笠并系带、蓝紫色无袖高开衩和服配白色内衬、黑色宽腰带外缠麻绳、黑色长筒袜与过肘护臂、腰侧挂褐色葫芦。脸型、五官、肤色、体型严格沿用 <Picture 1>，不得残留原舞者的白发或黑色紧身衣。

表情与神态：面部神态丰富自然，是会跳舞的活人——眼睛有焦点、眼神随动作和节奏移动、自然眨眼，嘴角带轻微笑意并在动作发力时有细微变化，呼吸带动肩颈起伏。禁止面无表情、目光空洞、五官冻结、面具感、蜡像感。

动作：完整复刻原片的舞蹈动作——重心左右转移、胯部与肩部同步摆动、手臂上举与收回、转身与回正，节奏与时间轴逐帧对齐，不加速、不减速、不改变方向。

皮肤与质感：皮肤有真实纹理、血色与次表面散射，唇部与眼周有自然湿润感。不要塑料感、不要过度磨皮、不要蜡像质感。

服装动态：和服下摆与宽袖随舞动自然甩动，斗笠系带与长发同步摆动，布料褶皱、遮挡关系与脚踩地面的接触点物理可信。

背景：纯白摄影棚背景与地面反光保持不变，不添加任何场景元素。

声音：沿用原片背景音乐，节拍与动作对齐。

不要文字，不要 logo，不要水印。"""

with open(os.path.join(TPL, "video_minimax_h3_r2v.json"), encoding="utf-8") as f:
    d = json.load(f)

nodes = {n["id"]: n for n in d["nodes"]}
lid = d["last_link_id"]
nid = d["last_node_id"]

def new_link(a, aslot, b, bslot, typ):
    global lid
    lid += 1
    d["links"].append([lid, a, aslot, b, bslot, typ])
    # 更新源节点 outputs
    src = nodes[a]
    out = src["outputs"][aslot]
    if out.get("links") is None:
        out["links"] = []
    out["links"].append(lid)
    tgt = nodes[b]
    tgt["inputs"][bslot]["link"] = lid
    return lid

def add_node(n):
    d["nodes"].append(n)
    nodes[n["id"]] = n
    return n

def kill_link(l):
    """断链：从 links 列表和两端槽位里移除"""
    row = [x for x in d["links"] if x[0] == l][0]
    d["links"] = [x for x in d["links"] if x[0] != l]
    _, a, aslot, b, bslot, _t = row
    src = nodes[a]
    if src["outputs"][aslot]["links"]:
        src["outputs"][aslot]["links"] = [x for x in src["outputs"][aslot]["links"] if x != l]
    if nodes[b]["inputs"][bslot].get("link") == l:
        nodes[b]["inputs"][bslot]["link"] = None

# ── 1. 主模型链接入 swap LoRA ──────────────────────────────
# 原：127.UNETLoader.MODEL -> 145(LoraLoader turbo).model / 141(switch).on_false
kill_link([x for x in d["links"] if x[1] == 127 and x[2] == 0][0][0])
kill_link([x for x in d["links"] if x[1] == 127 and x[2] == 0][0][0])

nid += 1
swap = add_node({
    "id": nid, "type": "LoraLoaderModelOnly", "pos": [40, 900], "size": [320, 90],
    "flags": {}, "order": 1, "mode": 0,
    "inputs": [{"name": "model", "type": "MODEL", "link": None}],
    "outputs": [{"name": "MODEL", "type": "MODEL", "links": []}],
    "properties": {"Node name for S&R": "LoraLoaderModelOnly"},
    "widgets_values": ["minimax_h3_character_swap_v1.1_ref2va_fro.safetensors", 1.0],
})
new_link(127, 0, swap["id"], 0, "MODEL")
new_link(swap["id"], 0, 145, 0, "MODEL")   # -> turbo LoRA
new_link(swap["id"], 0, 141, 0, "MODEL")   # -> switch.on_false（非 turbo 支路）

# ── 2. 低显存补丁（数学等价，16G 卡建议开） ────────────────
# 插在 swap LoRA 与下游之间
kill_link([x for x in d["links"] if x[1] == swap["id"] and x[3] == 145][0][0])
kill_link([x for x in d["links"] if x[1] == swap["id"] and x[3] == 141][0][0])

nid += 1
lowattn = add_node({
    "id": nid, "type": "MiniMaxLowVRAMAttention", "pos": [40, 1030], "size": [320, 90],
    "flags": {}, "order": 2, "mode": 0,
    "inputs": [{"name": "model", "type": "MODEL", "link": None}],
    "outputs": [{"name": "model", "type": "MODEL", "links": []}],
    "properties": {"Node name for S&R": "MiniMaxLowVRAMAttention"},
    "widgets_values": [4],
})
nid += 1
chunkff = add_node({
    "id": nid, "type": "MiniMaxChunkFeedForward", "pos": [40, 1160], "size": [320, 110],
    "flags": {}, "order": 3, "mode": 0,
    "inputs": [{"name": "model", "type": "MODEL", "link": None}],
    "outputs": [{"name": "model", "type": "MODEL", "links": []}],
    "properties": {"Node name for S&R": "MiniMaxChunkFeedForward"},
    "widgets_values": [2, 4096],
})
new_link(swap["id"], 0, lowattn["id"], 0, "MODEL")
new_link(lowattn["id"], 0, chunkff["id"], 0, "MODEL")
new_link(chunkff["id"], 0, 145, 0, "MODEL")
new_link(chunkff["id"], 0, 141, 0, "MODEL")

# ── 3. 源视频加载 ─────────────────────────────────────────
nid += 1
loadv = add_node({
    "id": nid, "type": "LoadVideo", "pos": [-2000, 420], "size": [340, 340],
    "flags": {}, "order": 0, "mode": 0,
    "inputs": [],
    "outputs": [{"name": "VIDEO", "type": "VIDEO", "links": []}],
    "properties": {"Node name for S&R": "LoadVideo"},
    "widgets_values": ["role_swap_20261112/seg01.mp4"],
})
nid += 1
gvc = add_node({
    "id": nid, "type": "GetVideoComponents", "pos": [-1620, 420], "size": [260, 150],
    "flags": {}, "order": 4, "mode": 0,
    "inputs": [{"name": "video", "type": "VIDEO", "link": None}],
    "outputs": [
        {"name": "images", "type": "IMAGE", "links": []},
        {"name": "audio", "type": "AUDIO", "links": []},
        {"name": "fps", "type": "FLOAT", "links": []},
        {"name": "bit_depth", "type": "COMBO", "links": []},
        {"name": "color_space", "type": "COMBO", "links": []},
    ],
    "properties": {"Node name for S&R": "GetVideoComponents"},
})
new_link(loadv["id"], 0, gvc["id"], 0, "VIDEO")

# ── 4. Add Guide：把源视频画面+原声锚定到第 0 帧 ───────────
nid += 1
guide = add_node({
    "id": nid, "type": "MiniMaxH3AddGuide", "pos": [-660, 60], "size": [320, 210],
    "flags": {}, "order": 5, "mode": 0,
    "inputs": [
        {"name": "positive", "type": "CONDITIONING", "link": None},
        {"name": "vae", "type": "VAE", "link": None},
        {"name": "audio_vae", "type": "VAE", "link": None},
        {"name": "latent", "type": "LATENT", "link": None},
        {"name": "image", "type": "IMAGE", "link": None},
        {"name": "audio", "type": "AUDIO", "link": None},
    ],
    "outputs": [{"name": "positive", "type": "CONDITIONING", "links": []}],
    "properties": {"Node name for S&R": "MiniMaxH3AddGuide"},
    "widgets_values": [0],
})
# 136.positive -> 126.conditioning 改成 136.positive -> guide -> 126.conditioning
old = [x for x in d["links"] if x[1] == 136 and x[2] == 0 and x[3] == 126][0][0]
kill_link(old)
new_link(136, 0, guide["id"], 0, "CONDITIONING")
new_link(guide["id"], 0, 126, 1, "CONDITIONING")
# 136.LATENT -> guide.latent（原 link 271 是 136.LATENT -> 125.latent_image）
new_link(136, 1, guide["id"], 3, "LATENT")
new_link(119, 0, guide["id"], 1, "VAE")      # 视频 VAE
new_link(120, 0, guide["id"], 2, "VAE")      # 音频 VAE
new_link(gvc["id"], 0, guide["id"], 4, "IMAGE")
new_link(gvc["id"], 1, guide["id"], 5, "AUDIO")

# ── 5. 参数与站位 ─────────────────────────────────────────
for n in d["nodes"]:
    pass
    if n["type"] == "SaveVideo":
        n["widgets_values"][0] = "video/H3_swap/zhaomei"
    if n["type"] == "PrimitiveFloat":      # 时长（秒）
        n["widgets_values"] = [5]
    if n["type"] == "LoadImage" and n["id"] == 137:
        n["widgets_values"] = ["role_swap_20261112/zhaomei_front.png", "image"]
    if n["type"] == "LoadImage" and n["id"] == 139:
        n["widgets_values"] = ["role_swap_20261112/zhaomei_head.png", "image"]
    if n["type"] == "PrimitiveStringMultiline":
        n["widgets_values"] = [PROMPT]

# 第二参考图默认断开（换人 LoRA 只吃一张更稳），节点保留可手动接
def drop_links(pred):
    """按谓词断链：从 links 表移除，并把对应输入槽置空"""
    removed = [r for r in d["links"] if pred(r)]
    d["links"] = [r for r in d["links"] if not pred(r)]
    for r in removed:
        b, bslot = r[3], r[4]
        if nodes[b]["inputs"][bslot].get("link") == r[0]:
            nodes[b]["inputs"][bslot]["link"] = None
    return len(removed)

print("drop ref_image_1:", drop_links(lambda r: r[3] == 136 and r[4] == 4))

# ── 6. 修 BasicScheduler.model ───────────────────────────
# 官模板里 124.BasicScheduler.model 原本直连 127.UNETLoader，
# 而第 1 步为了插 swap LoRA 把 127 的两条出线都断了，这里补到补丁链末端。
new_link(chunkff["id"], 0, 124, 0, "MODEL")

# ── 7. 帧数改用 PrimitiveInt ─────────────────────────────
# ComfyMathExpression 的 values 是 autogrow 输入，API 侧传值格式不稳；
# 换人按固定段长渲染，直接给整数帧数更可靠（243 = 17*14+5，10.125 秒）。
kill_link(261)
d["nodes"] = [n for n in d["nodes"] if n["id"] not in (131, 132)]
for k in (131, 132):
    nodes.pop(k, None)

nid += 1
frames = add_node({
    "id": nid, "type": "PrimitiveInt", "pos": [-1490, 6300], "size": [270, 90],
    "flags": {}, "order": 9, "mode": 0,
    "inputs": [],
    "outputs": [{"name": "INT", "type": "INT", "links": []}],
    "title": "Int (Frames @24fps)",
    "properties": {"cnr_id": "comfy-core", "Node name for S&R": "PrimitiveInt"},
    "widgets_values": [243, "fixed"],
    "widgets_values_named": {"value": 243, "fixed": "fixed"},
    "color": "#322", "bgcolor": "#533",
})
new_link(frames["id"], 0, 136, 12, "INT")
# ── 8. 用固定宽高替换 ResolutionSelector ─────────────────
# 该节点的比例档位只有 1:1/2:3/3:2/3:4/4:3/9:16/16:9/21:9，凑不出 768×1344，
# 而换人必须让生成分辨率和源视频逐像素一致（AddGuide 是按图锚定的）。
kill_link([x for x in d["links"] if x[3] == 136 and x[4] == 10][0][0])
kill_link([x for x in d["links"] if x[3] == 136 and x[4] == 11][0][0])
d["nodes"] = [n for n in d["nodes"] if n["id"] != 115]
nodes.pop(115, None)

for title, val, slot in (("Int (Width)", 640, 10), ("Int (Height)", 1120, 11)):
    nid += 1
    pn = add_node({
        "id": nid, "type": "PrimitiveInt", "pos": [-1490, 6450 + slot * 130], "size": [270, 90],
        "flags": {}, "order": 9, "mode": 0,
        "inputs": [],
        "outputs": [{"name": "INT", "type": "INT", "links": []}],
        "title": title,
        "properties": {"cnr_id": "comfy-core", "Node name for S&R": "PrimitiveInt"},
        "widgets_values": [val, "fixed"],
        "widgets_values_named": {"value": val, "fixed": "fixed"},
        "color": "#322", "bgcolor": "#533",
    })
    new_link(pn["id"], 0, 136, slot, "INT")

NOTE = """## MiniMax H3 · 源视频换人：申鹤依赖摇（34.4s 全片）→ 侠隐照美冥

**思路**：`Ref2VA` 吃照美冥定妆图，`Add Guide` 把源视频整段锚定到第 0 帧，
模型复刻舞蹈动作/运镜/光线、只换人；再叠 `character_swap v1.1` LoRA 强化"保留运动、替换身份"。

### 全片按 4 段渲染，每段 243 帧
H3 训练区间只有 **124–362 帧**，34.4 秒（825 帧）必须切段。已在 `input/role_swap_20261112/` 切好：

| 段 | 文件 | 源帧区间 |
|---|---|---|
| 1 | `seg01.mp4` | 0–242 |
| 2 | `seg02.mp4` | 194–436 |
| 3 | `seg03.mp4` | 388–630 |
| 4 | `seg04.mp4` | 582–824 |

相邻段有 **49 帧重叠**（防接缝跳变），拼片时后段丢掉前 49 帧，正好拼回 825 帧。

### 当前预设（第 1 段）
| 节点 | 预设值 |
|---|---|
| Load Video | `role_swap_20261112/seg01.mp4`（768×1344，243 帧，10.125s） |
| Load Image (137) | `role_swap_20261112/zhaomei_front.png`（全身正面定妆） |
| Int (Frames @24fps) | `243` |
| Resolution Selector | `9:16 (Portrait)` · 0.98MP → 768×1344 |

换段只需改两个值：Load Video 选 `seg02/03/04.mp4`，帧数保持 243（四段等长）。

### 为什么不能直接喂 34 秒原片
`申鹤依赖摇.mp4` 是 **1080×1920 / 60fps / 34.4s / AV1**：
1. 超训练区间，模型会乱（人物漂移、动作断裂）
2. 60fps 直接给会变成 **0.4 倍慢动作**（帧网格按 24fps 算）
3. `Get Video Components` 整段解码 2063 帧 1080p ≈ 50GB 内存，必崩

### 帧数必须是 17k+5
124 / 141 / 158 / … / 226 / 243 / 260。报 `frame_idx ... does not fit` 就是帧数没对齐网格。

### 显存与步数（RTX 5060 Ti 16G）
- 20 步质量模式：243 帧约 20–30 分钟/段，全片 4 段约 1.5–2 小时
- 想快：右侧 `Primitive Boolean` 打开 turbo（4 步），快 4–5 倍，适合先验证换人成不成立
- 中间两个补丁节点（LowVRAM Attention / Chunk FeedForward）**数学等价、只降峰值**，16G 卡保持开启

### 出片不对按这个顺序查
1. **斗笠丢了 / 脸变回申鹤白发** → swap LoRA 强度 1.0 → 1.15
2. 脸不像 → `Ref2VA` 的 `ref_image_size` 由 `match` 改 `max`（身份更准，但慢数倍）
3. 动作速度不对 → 查源视频是不是 24fps
4. 段与段接缝跳变 → 重叠已给 49 帧，仍跳就把重叠加到 73 帧（3 秒）
5. 画面糊 → Resolution Selector 保持 0.98MP，别往上加（16G 会换页）
"""

for n in d["nodes"]:
    if n["type"] == "MarkdownNote" and n["id"] == 116:
        n["widgets_values"] = [NOTE]

# ── 6. 归一化：以节点输入声明为准，清掉所有孤儿连线并重建 outputs.links ──
def normalize(d):
    live = {}
    for n in d["nodes"]:
        for i, s in enumerate(n.get("inputs") or []):
            l = s.get("link")
            if l is not None:
                live[l] = (n["id"], i)
    kept = []
    for row in d["links"]:
        l, a, aslot, b, bslot, _t = row
        if live.get(l) == (b, bslot):
            kept.append(row)
    d["links"] = kept
    for n in d["nodes"]:
        for o in (n.get("outputs") or []):
            o["links"] = []
    by_src = {}
    for row in kept:
        by_src.setdefault((row[1], row[2]), []).append(row[0])
    for n in d["nodes"]:
        for i, o in enumerate(n.get("outputs") or []):
            ls = by_src.get((n["id"], i))
            o["links"] = ls if ls else None
    dropped = len(live) - len(kept)
    return dropped

print("normalize dropped", normalize(d), "orphan links")

d["last_node_id"] = nid
d["last_link_id"] = lid
p = os.path.join(OUT, "05_H3本地_源视频换人_单人.json")
with open(p, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=1)
print("written", p, "nodes", len(d["nodes"]), "links", len(d["links"]))
