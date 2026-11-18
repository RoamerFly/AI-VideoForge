# -*- coding: utf-8 -*-
"""按《MiniMax H3 五种视频生成模式难度与本地部署规划.md》生成五个 ComfyUI 工作流 JSON。

母版用已经跑通的 05 换人工作流（fl2va/ref2va + turbo 4 步 + 640x1120 + 124 帧），
按模式增删节点：

  01 T2V         FL2VA / MiniMaxH3ImageToVideo，不接首帧
  02 I2V         FL2VA / MiniMaxH3ImageToVideo，接首帧角色图
  03 R2V         Ref2VA / ref_videos 吃参考视频（宽松参考，不加 AddGuide）
  04 CharacterSwap  Ref2VA + swap LoRA + AddGuide 锚定源视频（= 05 定稿版）
  05 PoseControl FL2VA + FunControlNet(pose) + 首帧角色图  ← 缺 controlnet 权重

输出到 user/default/workflows/MiniMax_H3_五模式/
"""
import copy
import json
import os

BASE = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/user/default/workflows"
SRC = os.path.join(BASE, "MiniMax_H3_本地", "05_H3本地_源视频换人_单人.json")
OUTDIR = os.path.join(BASE, "MiniMax_H3_五模式")

UNET_REF = "minimax_h3_ref2va_pruned_int8_convrot.safetensors"
UNET_FL2 = "minimax_h3_fl2va_pruned_int8_convrot.safetensors"
LORA_REF = "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors"
LORA_FL2 = "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors"
LORA_SWAP = "minimax_h3_character_swap_v1.1_ref2va_fro.safetensors"

W, H, LEN = 640, 1120, 124

# ---------------------------------------------------------------- 提示词
P_T2V = """画面：纯白摄影棚背景下，一位身穿蓝紫色开衩和服的成年女性站在画面中央，全身竖构图，机位固定不动，光线均匀柔和。写实摄影质感，皮肤有真实纹理与血色。

动作：她先缓缓转过身，再抬起右手向镜头挥了挥，衣料随动作自然摆动。

要求：动作连贯有重量感，面部自然，眼睛睁开有焦点。"""

P_I2V = """画面：全身竖构图，纯白摄影棚背景，机位固定不动，光线均匀柔和。写实摄影质感，皮肤有真实纹理与血色。

人物：与首帧完全一致——红褐色长发女性，头戴竹编斗笠，身穿蓝紫色开衩和服、白色内衬、黑色腰带系麻绳，手臂有深色护臂，脚穿黑色长筒袜，腰侧挂着葫芦。

动作：她站在原地随节奏轻快地跳舞，左右摆动腰胯，双臂抬起划出弧线，最后轻跳一下落地。

要求：动作连贯流畅、有重量感；面部自然，眼睛睁开有焦点，会自然眨眼；不要面无表情、不要身体僵直。"""

P_R2V = """画面：参考视频中的人物动作、镜头距离和构图，重新生成一段写实视频。纯白摄影棚背景，机位与原片一致。

人物：红褐色长发女性，头戴竹编斗笠，身穿蓝紫色开衩和服、白色内衬、黑色腰带系麻绳，手臂有深色护臂，脚穿黑色长筒袜。

要求：动作节奏和关键时间点尽量接近参考视频，服装颜色稳定不漂移，人物面部自然清晰。"""

P_SWAP = """画面风格：写实摄影质感，纯白摄影棚背景，全身构图，保持与原片一致的机位、景别、焦距、光线方向，镜头全程固定不移动。

人物身份：把舞者替换为 <Picture 1> 中的角色，保留她的脸、发型、服装、配饰与体型；脸部细节以 <Picture 2> 为准。

服装与配饰：红褐色长发，头戴竹编斗笠并有系带垂下，身穿蓝紫色开衩和服、白色内衬、黑色腰带系麻绳，手臂有深色过肘护臂，脚穿黑色长筒袜，腰侧挂着葫芦。

动作：完全跟随源视频中舞者的动作与节奏，不要改动动作幅度和节拍。

表情与神态：面部神态丰富自然，是会跳舞的活人——眼睛有焦点、眼神随动作和节奏移动、自然眨眼、双唇随节奏自然开合。禁止面无表情、目光空洞、五官冻结、面具感、蜡像感。

要求：只替换人物身份，保持原视频的背景、镜头、光照和动作不变。"""

P_POSE = """画面：全身竖构图，纯白摄影棚背景，机位固定不动，写实摄影质感。

人物：与首帧参考图一致——红褐色长发女性，头戴竹编斗笠，身穿蓝紫色开衩和服、白色内衬、黑色腰带系麻绳，手臂有深色护臂，脚穿黑色长筒袜。

动作：严格按照姿态控制视频中的骨架动作生成，保持每个关键帧的肢体位置、朝向与节奏。

要求：面部自然清晰，服装颜色稳定，肢体不要扭曲或穿模。"""


# ---------------------------------------------------------------- 工具
def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print("写出", os.path.basename(p), f"({len(d['nodes'])} 节点 / {len(d['links'])} 连线)")


def strip_links(node):
    """清空节点上的连线引用，稍后统一重连。"""
    for s in node.get("inputs") or []:
        s["link"] = None
    for o in node.get("outputs") or []:
        o["links"] = None


def note(nid, pos, text, size=(480, 900), title="说明"):
    return {
        "id": nid, "type": "MarkdownNote", "pos": list(pos), "size": list(size),
        "flags": {}, "order": 0, "mode": 0, "inputs": [], "outputs": [],
        "title": title, "properties": {}, "widgets_values": [text],
    }


def i2v_node(nid, pos, prompt, with_first_frame, image_pos=None):
    """MiniMaxH3ImageToVideo 节点：fl2va 的首帧/T2V 入口。"""
    inputs = [
        {"name": "clip", "type": "CLIP", "link": None},
        {"name": "vae", "type": "VAE", "link": None},
        {"name": "first_frame", "type": "IMAGE", "link": None},
    ]
    return {
        "id": nid, "type": "MiniMaxH3ImageToVideo", "pos": list(pos), "size": [420, 320],
        "flags": {}, "order": 10, "mode": 0,
        "inputs": inputs,
        "outputs": [
            {"name": "positive", "type": "CONDITIONING", "links": None},
            {"name": "LATENT", "type": "LATENT", "links": None},
        ],
        "title": "MiniMaxH3 图生视频（不接首帧=纯文生）",
        "properties": {"Node name for S&R": "MiniMaxH3ImageToVideo"},
        "widgets_values": [prompt, W, H, LEN],
    }


def ref2v_node(nid, pos, prompt):
    """Ref2VA 节点，槽位与 05 母版一致（含 autogrow）。"""
    names = [
        ("clip", "CLIP"), ("vae", "VAE"), ("audio_vae", "VAE"),
        ("ref_images.ref_image_0", "IMAGE"), ("ref_images.ref_image_1", "IMAGE"),
        ("ref_images.ref_image_2", "IMAGE"),
        ("ref_videos.ref_video_0", "IMAGE"),
        ("ref_video_audios.ref_video_audio_0", "AUDIO"),
        ("ref_audios.ref_audio_0", "AUDIO"),
        ("prompt", "STRING"), ("width", "INT"), ("height", "INT"), ("length", "INT"),
    ]
    return {
        "id": nid, "type": "MiniMaxH3ReferenceToVideo", "pos": list(pos), "size": [420, 380],
        "flags": {}, "order": 10, "mode": 0,
        "inputs": [{"name": n, "type": t, "link": None} for n, t in names],
        "outputs": [
            {"name": "positive", "type": "CONDITIONING", "links": None},
            {"name": "LATENT", "type": "LATENT", "links": None},
        ],
        "title": "MiniMaxH3 多模态参考生成",
        "properties": {"Node name for S&R": "MiniMaxH3ReferenceToVideo"},
        "widgets_values": [prompt, W, H, LEN, "match"],
    }


def fun_cn_node(nid, pos):
    return {
        "id": nid, "type": "MiniMaxH3FunControlNetApply", "pos": list(pos), "size": [340, 200],
        "flags": {}, "order": 10, "mode": 0,
        "inputs": [
            {"name": "model", "type": "MODEL", "link": None},
            {"name": "model_patch", "type": "MODEL_PATCH", "link": None},
            {"name": "vae", "type": "VAE", "link": None},
            {"name": "control_video", "type": "IMAGE", "link": None},
            {"name": "mask", "type": "MASK", "link": None},
            {"name": "source_video", "type": "IMAGE", "link": None},
        ],
        "outputs": [{"name": "MODEL", "type": "MODEL", "links": None}],
        "title": "H3 FunControlNet（需补 controlnet 权重）",
        "properties": {"Node name for S&R": "MiniMaxH3FunControlNetApply"},
        "widgets_values": [0.8, 0.0, 1.0],
    }


def build(name, nodes, links, extra_top=None):
    """组装 UI 工作流：links 用 (src_id, src_slot, dst_id, dst_slot_name) 描述。"""
    d = copy.deepcopy(TPL)
    d["nodes"] = nodes
    d["links"] = []
    d.pop("extra", None)
    if extra_top:
        d.update(extra_top)

    by_id = {n["id"]: n for n in nodes}
    lid = 1
    for src, sslot, dst, dslot in links:
        sn, dn = by_id.get(src), by_id.get(dst)
        if sn is None or dn is None:
            raise KeyError(f"{name}: 节点缺失 {src}->{dst}")
        tgt = None
        for s in dn.get("inputs") or []:
            if s["name"] == dslot:
                tgt = s
                break
        if tgt is None:
            raise KeyError(f"{name}: {dn['type']}({dst}) 缺少输入槽 {dslot}")
        # 类型取输出类型，前端靠它决定颜色
        otype = "IMAGE"
        if sn.get("outputs") and sslot < len(sn["outputs"]):
            otype = sn["outputs"][sslot].get("type") or otype
        d["links"].append([lid, src, sslot, dst, list(dn["inputs"]).index(tgt), otype])
        tgt["link"] = lid
        if sn.get("outputs") and sslot < len(sn["outputs"]):
            o = sn["outputs"][sslot]
            o["links"] = (o.get("links") or []) + [lid]
        lid += 1

    d["last_link_id"] = lid - 1
    d["last_node_id"] = max(n["id"] for n in nodes)
    save(os.path.join(OUTDIR, name), d)


# ---------------------------------------------------------------- 母版
BASE_WF = load(SRC)
TPL = {k: v for k, v in BASE_WF.items() if k not in ("nodes", "links")}
SRC_NODES = {n["id"]: copy.deepcopy(n) for n in BASE_WF["nodes"]}


def take(*ids, patch=None):
    """取母版节点副本并按需改 widgets_values。"""
    out = []
    for i in ids:
        n = copy.deepcopy(SRC_NODES[i])
        strip_links(n)
        if patch and i in patch:
            patch[i](n)
        out.append(n)
    return out


def set_vals(**kw):
    def f(n):
        for k, v in kw.items():
            if k == "widgets":
                n["widgets_values"] = v
            elif k == "title":
                n["title"] = v
    return f


# 采样 / 解码 / 输出主干（五个模式共用）
CORE_IDS = [92, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130,
            141, 142, 143, 144, 145, 146, 148, 149]
CORE_LINKS = [
    (120, 0, 121, "vae"),   # audio VAE 解音频
    (119, 0, 122, "vae"),   # video VAE 解画面
    (129, 0, 125, "noise"), (126, 0, 125, "guider"),
    (123, 0, 125, "sampler"), (124, 0, 125, "sigmas"),
    (122, 0, 130, "images"), (121, 0, 130, "audio"), (130, 0, 92, "video"),
    (125, 0, 122, "samples"), (125, 0, 121, "samples"),
    (144, 0, 142, "on_true"), (143, 0, 142, "on_false"),
    (145, 0, 141, "on_true"), (141, 0, 126, "model"),
    (142, 0, 124, "steps"),
    (146, 0, 141, "switch"), (146, 0, 142, "switch"),
    (127, 0, 148, "model"), (148, 0, 149, "model"),
    (149, 0, 145, "model"), (149, 0, 141, "on_false"), (149, 0, 124, "model"),
]


def core(model_vals, save_prefix, note_text, note_pos=(-2600, 4850)):
    """返回 (nodes, links)：主干 + 一段说明。"""
    nodes = take(*CORE_IDS, patch={
        127: set_vals(widgets=model_vals["unet"]),
        145: set_vals(widgets=[model_vals["lora"], 1]),
        92: set_vals(widgets=[save_prefix, "auto", "auto"]),
        143: set_vals(widgets=[20, "fixed"]),
        144: set_vals(widgets=[4, "fixed"]),
        146: set_vals(widgets=[True]),
        126: set_vals(title="BasicGuider（conditioning 来自生成节点）"),
    })
    nodes.append(note(9001, note_pos, note_text, size=(520, 1000)))
    return nodes, list(CORE_LINKS)


# ---------------------------------------------------------------- ① T2V
def wf_t2v():
    nodes, links = core(
        {"unet": [UNET_FL2, "default"], "lora": LORA_FL2},
        "video/H3_五模式/01_T2V",
        """## ① 文生视频 T2V

**难度 1/5 · 本地可行性高**

```
文本描述 → MiniMaxH3ImageToVideo（不接首帧） → 视频
```

- 主模型：`minimax_h3_fl2va_pruned_int8_convrot`
- 加速：`fl2v_turbo_4step`，4 步出片
- 画布 640×1120，124 帧（约 5.2 秒，24fps）
- 没有图片/视频输入，角色完全由提示词描述，**每次结果都不一样**

用法：改提示词 → 运行。想换分辨率改节点里的 width/height。
提示：640×1120 单条约 11 分钟；768×1344 约翻倍。""")
    n136 = i2v_node(136, (-620, 5420), P_T2V, False)
    nodes.append(n136)
    links += [
        (128, 0, 136, "clip"), (119, 0, 136, "vae"),
        (136, 0, 126, "conditioning"), (136, 1, 125, "latent_image"),
    ]
    build("01_T2V_文生视频.json", nodes, links)


# ---------------------------------------------------------------- ② I2V
def wf_i2v():
    nodes, links = core(
        {"unet": [UNET_FL2, "default"], "lora": LORA_FL2},
        "video/H3_五模式/02_I2V",
        """## ② 参考图 + 文生视频 I2V

**难度 2/5 · 本地可行性高**

```
角色图（首帧） + 动作描述 → MiniMaxH3ImageToVideo → 视频
```

- 主模型：`fl2va` + `fl2v_turbo_4step`
- 首帧由 `LoadImage` 固定，人物外观从第 0 帧开始
- 640×1120 / 124 帧 / 4 步，实测约 11 分钟

**实测要点**
- 这是目前面部质量最好的一条路线，脸清晰、不崩
- 动作**只能靠提示词描述，不受控**；说「跳两下」通常只小幅晃动
- 单次 5 秒左右最稳；要做长片得切多段，段间不连续
- 背景跟参考图走：参考图灰底 → 成片灰底

替换 `LoadImage` 里的图片即可换角色。""")
    n136 = i2v_node(136, (-620, 5420), P_I2V, True)
    nodes.append(n136)
    nodes += take(137, patch={137: set_vals(widgets=["role_swap_20261112/zhaomei_front.png", "image"])})
    links += [
        (128, 0, 136, "clip"), (119, 0, 136, "vae"),
        (137, 0, 136, "first_frame"),
        (136, 0, 126, "conditioning"), (136, 1, 125, "latent_image"),
    ]
    build("02_I2V_图生视频.json", nodes, links)


# ---------------------------------------------------------------- ③ R2V
def wf_r2v():
    nodes, links = core(
        {"unet": [UNET_REF, "default"], "lora": LORA_REF},
        "video/H3_五模式/03_R2V",
        """## ③ 参考视频 + 文生视频 R2V

**难度 3/5 · 本地可行性中高**

```
参考视频 + 文本 → MiniMaxH3ReferenceToVideo（ref_videos） → 视频
```

- 主模型：`ref2va` + `ref2v_turbo_4step`
- 源视频走 `ref_videos`（作为「参考」），**不是** AddGuide 逐帧锚定
- 所以动作/镜头是「相似」而非「逐帧一致」——这是方案里说的宽松参考

**限制**
- `ref_videos` 只吃 2–15 秒、24fps 的帧序列，长片要先切段
- 想在原片上整段换人，请用 04（那才是 AddGuide 锚定）

改 `LoadVideo` 里的文件名换素材。""")
    n136 = ref2v_node(136, (-620, 5420), P_R2V)
    nodes.append(n136)
    nodes += take(150, 151, patch={150: set_vals(widgets=["role_swap_20261112/seg01.mp4"])})
    links += CORE_LINKS and []  # noqa: 占位，避免误改
    links += [
        (128, 0, 136, "clip"), (119, 0, 136, "vae"), (120, 0, 136, "audio_vae"),
        (151, 0, 136, "ref_videos.ref_video_0"),
        (151, 1, 136, "ref_video_audios.ref_video_audio_0"),
        (136, 0, 126, "conditioning"), (136, 1, 125, "latent_image"),
        (150, 0, 151, "video"),
    ]
    build("03_R2V_视频参考.json", nodes, links)


# ---------------------------------------------------------------- ④ CharacterSwap
SWAP_NOTE = """## ④ 角色图 + 参考视频 + 换人（当前核心目标）

**难度 4/5 · 本地可行性中等**

```
角色图（全身 + 头肩） + 原视频（AddGuide 锚定） + 换人 LoRA → 新视频
```

就是已经跑通的 05 换人工作流，参数为本机实测定稿：
- `ref2va` + `ref2v_turbo_4step` + `character_swap_v1.1` LoRA（强度 1.0）
- 640×1120 / 每段 243 帧 / 4 步 / 单段约 26 分钟
- `<Picture 1>` 全身定妆、`<Picture 2>` 头肩特写，脸以 Picture 2 为准
- AddGuide 把源视频第 0 帧+原声锚定，后续动作由模型推断

**已知固有问题**
- 模型会复刻源片的 cosplay 上挑猫眼线，640 宽下人脸约 90px，容易糊成黑缝
- 换提示词 / 提分辨率 / 换淡妆参考图 三种办法都压不住
- 参考图**必须用棚拍白底**，带场景的图会污染背景（漂出墙面纹理和花瓣）

**音频**：H3 自带一条模型生成的音轨，和原曲无关。要原声请用
`mux_seg_audio.py`（单段）或 `assemble_full.py`（全片）挂回原片音轨。"""


def wf_swap():
    # 直接复用 05 母版全量节点，只改说明、提示词与输出前缀
    nodes = []
    for i in SRC_NODES:
        n = copy.deepcopy(SRC_NODES[i])
        strip_links(n)
        if i == 92:
            n["widgets_values"] = ["video/H3_五模式/04_CharacterSwap", "auto", "auto"]
        if i == 138:
            n["widgets_values"] = [P_SWAP]
        if i == 150:
            n["widgets_values"] = ["role_swap_20261112/seg01.mp4"]
        if i == 116:  # 母版的主说明，换成五模式版
            n["widgets_values"] = [SWAP_NOTE]
            n["size"] = [560, 1100]
        nodes.append(n)
    links = []
    for l in BASE_WF["links"]:
        lid, src, sslot, dst, dslot, typ = l[:6]
        dn = next(n for n in nodes if n["id"] == dst)
        links.append((src, sslot, dst, dn["inputs"][dslot]["name"]))
    build("04_CharacterSwap_角色替换.json", nodes, links)


# ---------------------------------------------------------------- ⑤ PoseControl
def wf_pose():
    nodes, links = core(
        {"unet": [UNET_FL2, "default"], "lora": LORA_FL2},
        "video/H3_五模式/05_PoseControl",
        """## ⑤ 严格动作控制（Pose / Depth + FunControlNet）

**难度 5/5 · 本地可行中低 · ⚠️ 当前缺模型，不能直接跑**

```
原视频 → Openpose 骨架提取 ──┐
                            ↓
角色图 → MiniMaxH3ImageToVideo → H3 + FunControlNet → 视频
```

**已连好的部分**
- 源视频 → `GetVideoComponents` → `OpenposePreprocessor` → `control_video`
- `ModelPatchLoader` → `MiniMaxH3FunControlNetApply` 插在 UNet 之后
- 首帧角色图固定外观

**还缺两个东西，缺任一个都会报红**
1. `models/model_patches/` 里没有 H3 FunControl Union 权重（约 6.8GiB）
   下载后把 `ModelPatchLoader` 指向它
2. `OpenposePreprocessor` 首次运行会自动下载 DWPose 检测模型（约数百 MB）

**注意**
- ControlNet 和主模型同时占显存，16GB 很可能要降到 480p 并且分段跑
- 骨架正确 ≠ 衣服道具正确；长袖、裙摆、斗笠的动态不由骨骼定义
- 想保背景不变，还需要 SAM 人物蒙版 + 局部合成（方案阶段 E）

建议先从 2–3 秒、480p 单人动作试起，别一上来做 15 秒高清全身。""")
    n136 = i2v_node(136, (-620, 5420), P_POSE, True)
    nodes.append(n136)
    nodes += take(137, 150, 151, patch={
        137: set_vals(widgets=["role_swap_20261112/zhaomei_front.png", "image"]),
        150: set_vals(widgets=["role_swap_20261112/seg01.mp4"]),
    })
    nodes.append({
        "id": 200, "type": "OpenposePreprocessor", "pos": [-1150, 4700], "size": [320, 180],
        "flags": {}, "order": 5, "mode": 0,
        "inputs": [{"name": "image", "type": "IMAGE", "link": None}],
        "outputs": [
            {"name": "IMAGE", "type": "IMAGE", "links": None},
            {"name": "POSE_KEYPOINT", "type": "POSE_KEYPOINT", "links": None},
        ],
        "title": "姿态提取（骨架）",
        "properties": {"Node name for S&R": "OpenposePreprocessor"},
        "widgets_values": ["enable", "enable", "enable", 512, "disable"],
    })
    nodes.append({
        "id": 201, "type": "ModelPatchLoader", "pos": [-1150, 4950], "size": [420, 70],
        "flags": {}, "order": 5, "mode": 0, "inputs": [],
        "outputs": [{"name": "MODEL_PATCH", "type": "MODEL_PATCH", "links": None}],
        "title": "H3 FunControl 权重（待补）",
        "properties": {"Node name for S&R": "ModelPatchLoader"},
        "widgets_values": ["H3_FunControl_Union_pose.safetensors"],
    })
    nodes.append(fun_cn_node(202, (-620, 4650)))

    # 模型链改道：149 → FunCN → 145 / 141.on_false
    links = [l for l in links if l not in ((149, 0, 145, "model"), (149, 0, 141, "on_false"))]
    links += [
        (149, 0, 202, "model"),
        (201, 0, 202, "model_patch"),
        (119, 0, 202, "vae"),
        (200, 0, 202, "control_video"),
        (202, 0, 145, "model"),
        (202, 0, 141, "on_false"),
        (128, 0, 136, "clip"), (119, 0, 136, "vae"),
        (137, 0, 136, "first_frame"),
        (136, 0, 126, "conditioning"), (136, 1, 125, "latent_image"),
        (150, 0, 151, "video"),
        (151, 0, 200, "image"),
    ]
    build("05_PoseControl_姿态控制.json", nodes, links)


if __name__ == "__main__":
    wf_t2v()
    wf_i2v()
    wf_r2v()
    wf_swap()
    wf_pose()
    print("\n全部写出到:", OUTDIR)
