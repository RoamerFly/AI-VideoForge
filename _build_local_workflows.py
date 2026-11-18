# -*- coding: utf-8 -*-
"""基于 ComfyUI 官方 MiniMax H3 本地模板，生成四套中文高质量工作流"""
import json, os, copy

TPL = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/python/Lib/site-packages/comfyui_workflow_templates_json/templates"
OUT = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/user/default/workflows/MiniMax_H3_本地"
os.makedirs(OUT, exist_ok=True)

P_T2V = """一个连续长镜头，8 秒，全程不剪切。写实电影质感，35mm 变形宽银幕，浅景深，细腻胶片颗粒，专业调色。

场景：1990 年代南方小城的雨夜大排档。霓虹灯牌在积水里晕成红与青，蒸笼白汽翻滚，中年摊主穿白色背心，在铁锅前颠勺，火光映在湿漉漉的地面上。

镜头：从雨棚边缘一颗水珠的特写开始，缓慢上摇并后拉，一气呵成地展开整个摊位；炉火在颠勺的瞬间窜起；最后推近到摊主被火光从下方照亮的侧脸。

声音：铁锅爆炒声、中雨声、远处车流声，无人声对白。

不要字幕，不要文字，不要 logo，不要水印。"""

P_I2V = """以输入图片作为开场第一帧，连续单镜头，8 秒，不剪切。写实电影质感，浅景深，细腻胶片颗粒。

动作：画面中的人物/主体缓慢向前移动半步后停住，自然转头看向镜头，发丝与衣料随动作轻微摆动，背景有微风带动的水汽或浮尘。镜头从当前位置极缓慢地向前推进几厘米，保持构图稳定。

要求：人物身份、服装、场景结构、光线方向与输入图片完全一致，不得变形或漂移。

声音：与场景匹配的环境声，无对白。

不要字幕，不要文字，不要 logo，不要水印。"""

P_FLF = """从首帧到末帧的连续单镜头过渡，8 秒，不剪切。写实电影质感，浅景深，胶片颗粒。

以首帧为开场构图、末帧为收尾构图，中间补一段可信的摄影机运动：镜头匀速前推（或按两张图的构图差自然过渡），主体动作、发丝与衣料随动自然，光线方向全程保持一致。

要求：人物身份、服装、空间结构不得漂移，过渡平滑、物理可信。

不要形变，不要闪烁，不要重影，不要文字，不要水印。"""

P_R2V = """画面风格：写实电影感，柔和的自然光，浅景深，细腻颗粒。

角色：以 <Picture 1> 中的人物为唯一身份参考，脸型、五官、发型、肤色、服装完全保持一致。
环境：以 <Picture 2> 中的场景与光线为参考，保持同一地点、同一时间感、同一色调。

一个连续长镜头，8 秒，不剪切：人物从画面深处缓慢走向镜头，走到中景停住，侧头看向镜头，微风带动发丝；镜头随之极缓慢地前推。人物运动有自然的重量感，衣料、皮肤、环境光都要真实。

声音：与场景一致的环境声，无对白。

不要文字，不要 logo，不要水印。"""

NOTE_USAGE = """## MiniMax H3 本地 · 高质量视频

**这是本地推理工作流**，不吃 API 额度，只吃显卡。模型放在 `ComfyUI/models/` 下。

### 关键参数
| 参数 | 建议 | 说明 |
|---|---|---|
| {res_label} | {res_val} | 官方 768p 原生画布 |
| duration | {dur} 秒 | 会按 17k+5 帧网格自动对齐到 24fps |
| turbo_mode | 关（False） | 关 = 20 步质量模式；开 = 8 步加速，速度快约 2.5 倍、细节下降 |
| seed | 固定 42 / randomize | 抽卡时切成 randomize |

### 出片时间（RTX 5060 Ti 16G 参考）
768p / 8 秒 / 20 步：约 8–15 分钟（含模型换入换出）。首次运行要把 20G 主模型和 15G 文本编码器读进内存，会明显更慢。

### 想要更快
把 `turbo_mode` 打开（8 步 + Turbo LoRA），或换 `duration` 到 4–5 秒先试提示词。
"""

# ── 读取模板 ─────────────────────────────────────────────
def load(name):
    with open(os.path.join(TPL, name), encoding="utf-8") as f:
        return json.load(f)

def find_uuid_node(d):
    return [n for n in d["nodes"] if len(n["type"]) == 36 and n["type"].count("-") == 4]

def set_note(d, nid, text):
    for n in d["nodes"]:
        if n["id"] == nid and n["type"] in ("MarkdownNote", "Note"):
            n["widgets_values"] = [text]
            return True
    return False

def save(d, name):
    p = os.path.join(OUT, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print("written", name)

# ── 1. 文生视频 ──────────────────────────────────────────
d = load("video_minimax_h3_t2v.json")
for n in d["nodes"]:
    if n["type"] == "ResolutionSelector":
        n["widgets_values"] = ["16:9 (Widescreen)", 0.98, 32]
for n in find_uuid_node(d):
    w = n["widgets_values"]
    w[0] = P_T2V      # prompt
    w[1], w[2] = 1344, 768
    w[3] = 8          # duration
    w[9] = False      # turbo_mode = 质量模式
for n in d["nodes"]:
    if n["type"] == "SaveVideo":
        n["widgets_values"][0] = "video/H3_T2V_高质量"
set_note(d, 116, NOTE_USAGE.format(res_label="Resolution Selector", res_val="16:9 · 0.98MP = 1344×768", dur=8))
save(d, "01_H3本地_文生视频_768p高质量.json")

# ── 2. 图生视频 ──────────────────────────────────────────
d = load("video_minimax_h3_i2v.json")
for n in d["nodes"]:
    if n["type"] == "LoadImage":
        n["widgets_values"][0] = "h3_input.png"
    if n["type"] == "ResolutionSelector":
        n["widgets_values"] = ["16:9 (Widescreen)", 0.98, 32]
for n in find_uuid_node(d):
    w = n["widgets_values"]
    w[0] = P_I2V
    w[1], w[2] = 1344, 768
    w[3] = 8
    w[9] = False
for n in d["nodes"]:
    if n["type"] == "SaveVideo":
        n["widgets_values"][0] = "video/H3_I2V_高质量"
set_note(d, 116, NOTE_USAGE.format(res_label="Resolution Selector", res_val="16:9 · 0.98MP = 1344×768", dur=8)
         + "\n### 图生视频要点\n- 左上 LoadImage 接你自己的图，画布比例按图片实际比例在 Resolution Selector 里选\n- 图片会按画布等比缩放裁切，主体别贴边\n- 想只锁首帧时这张图就是首帧；要锁尾帧请用「首尾帧」工作流")
save(d, "02_H3本地_图生视频_768p高质量.json")

# ── 3. 首尾帧 ────────────────────────────────────────────
d = load("video_minimax_h3_t2v.json")
sg = find_uuid_node(d)[0]
base_link = d["last_link_id"]
l1, l2 = base_link + 1, base_link + 2
img_tpl = {
    "id": 0, "type": "LoadImage", "pos": [0, 0], "size": [300, 400], "flags": {},
    "order": 0, "mode": 0, "inputs": [],
    "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": []},
                {"name": "MASK", "type": "MASK", "links": None}],
    "properties": {"Node name for S&R": "LoadImage"},
    "widgets_values": ["h3_first_frame.png", "image"],
}
a = copy.deepcopy(img_tpl)
a["id"], a["pos"], a["order"] = 141, [-1520, 640], 5
a["outputs"][0]["links"] = [l1]
b = copy.deepcopy(img_tpl)
b["id"], b["pos"], b["order"] = 142, [-1520, 1080], 6
b["outputs"][0]["links"] = [l2]
b["widgets_values"] = ["h3_last_frame.png", "image"]
d["nodes"].extend([a, b])
d["links"] += [[l1, 141, 0, sg["id"], 0, "IMAGE"], [l2, 142, 0, sg["id"], 1, "IMAGE"]]
for i in sg["inputs"]:
    if i["name"] == "first_frame":
        i["link"] = l1
    if i["name"] == "last_frame":
        i["link"] = l2
for n in d["nodes"]:
    if n["type"] == "ResolutionSelector":
        n["widgets_values"] = ["16:9 (Widescreen)", 0.98, 32]
    if n["type"] == "SaveVideo":
        n["widgets_values"][0] = "video/H3_FLF_首尾帧_高质量"
w = sg["widgets_values"]
w[0] = P_FLF
w[1], w[2], w[3] = 1344, 768, 8
w[9] = False
d["last_node_id"] = 142
d["last_link_id"] = l2
set_note(d, 116, NOTE_USAGE.format(res_label="Resolution Selector", res_val="16:9 · 0.98MP = 1344×768", dur=8)
         + "\n### 首尾帧要点\n- 左侧两张 LoadImage 分别接首帧、尾帧；**只接首帧也能跑**（就是普通图生视频），把尾帧那条线删掉即可\n- 两张图的构图差不要太夸张，差异越大越容易出现形变\n- 画布比例按你图片的实际比例在 Resolution Selector 里改")
save(d, "03_H3本地_首尾帧_768p高质量.json")

# ── 4. 参考生视频 ────────────────────────────────────────
d = load("video_minimax_h3_r2v.json")
for n in d["nodes"]:
    if n["type"] == "LoadImage":
        n["widgets_values"][0] = "h3_ref_character.png" if n["id"] == 137 else "h3_ref_scene.png"
    if n["type"] == "PrimitiveStringMultiline":
        n["widgets_values"] = [P_R2V]
    if n["type"] == "SaveVideo":
        n["widgets_values"][0] = "video/H3_R2V_参考生视频"
set_note(d, 116, """## MiniMax H3 本地 · 参考生视频

**额外依赖**：本工作流用的是 `minimax_h3_ref2va_pruned_int8_convrot.safetensors`（21 GB），
与文生/图生那套 `fl2va` 不是同一个模型，需要单独下载：
`bash download_h3_models.sh ref`

### 用法
1. 左侧两张 LoadImage：第一张放**人物定妆图**，第二张放**场景/风格图**（顺序决定 `<Picture 1>` `<Picture 2>`）
2. 提示词里用 `<Picture 1>` `<Picture 2>` 指代上面的图片
3. 最多 3 张参考图 + 视频/音频参考槽位（节点上有 `ref_image_2`、`ref_video_0` 等空位）

### 质量设置
- 右侧 PrimitiveInt 默认 20 步（质量模式），PrimitiveBoolean 关掉 Turbo
- 打开 Turbo 换 4 步，速度快 5 倍，适合试构图
""")
save(d, "04_H3本地_参考生视频_角色一致性.json")

print("done")
