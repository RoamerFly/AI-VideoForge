# -*- coding: utf-8 -*-
"""生成 MiniMax H3 高质量视频工作流 JSON（写入 ComfyUI user/default/workflows/MiniMax_H3）"""
import json, os, uuid

OUT = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/user/default/workflows/MiniMax_H3"
os.makedirs(OUT, exist_ok=True)

PROMPT_T2V = (
    "One continuous 10-second take, no cuts. Photoreal cinematic, 2K ultra-high-definition, "
    "35mm anamorphic lens, shallow depth of field, subtle film grain, professional color grading.\n\n"
    "SCENE: A rain-soaked midnight street market in southern China, late 1990s. Neon signs bleed "
    "red and cyan into the puddles, steam pours off a noodle stall, a lone middle-aged vendor in a "
    "white singlet works a cast-iron wok.\n\n"
    "CAMERA: Opens as an extreme close-up of a raindrop swelling on the awning edge, then tilts up "
    "and pulls back in one fluid steadicam arc, revealing the vendor tossing noodles as wok fire "
    "flares; the move settles and pushes in slowly past a customer's shoulder, landing on the "
    "vendor's weathered face lit from below by the flame.\n\n"
    "MOTION: The fire flare syncs with the wok toss; steam unspools frame-right; rain streaks "
    "across the lens during the pull-back.\n\n"
    "LIGHT: Warm tungsten practicals against a cold blue night, hard rim light from the neon, wet "
    "specular highlights on skin and steel.\n\n"
    "AUDIO: Wok sizzle, steady rain, distant traffic.\n\n"
    "No text, no logos, no captions, no dialogue."
)

PROMPT_FLF = (
    "One continuous shot from the first frame to the last frame, no cuts, photoreal cinematic 2K, "
    "anamorphic lens, subtle film grain.\n\n"
    "The first frame is the exact starting composition and the last frame is the exact ending "
    "composition. Interpolate a single believable camera move between them: the camera glides "
    "forward at constant speed while the subject turns naturally toward the light, clothing and "
    "hair reacting to the motion. Keep identity, wardrobe, architecture and colour palette "
    "consistent across the whole shot; lighting direction must not break. Motion is smooth and "
    "physically plausible, with realistic fabric, skin and atmospheric behaviour.\n\n"
    "No morphing, no warping, no flicker, no text, no logos, no watermark."
)

PROMPT_R2V = (
    "Use @Image1 as the exact identity reference for the character: keep the same face, hairstyle, "
    "skin texture and body proportions. Use @Image2 as the environment and lighting reference: "
    "same location, same palette, same time of day.\n\n"
    "One continuous 10-second take, no cuts, photoreal cinematic 2K, shallow depth of field, subtle "
    "film grain. The character walks slowly through the referenced environment toward the camera, "
    "then stops and looks directly into the lens as a soft breeze moves their hair; the camera "
    "holds and drifts a few centimetres closer. Natural weight shift, realistic cloth simulation, "
    "consistent identity in every frame.\n\n"
    "No text, no logos, no watermark."
)

PROMPT_DRAFT = (
    "One continuous 10-second take, no cuts. Photoreal cinematic, 35mm anamorphic, shallow depth of "
    "field, professional color grading. A rain-soaked midnight street market in southern China, "
    "1990s: neon signs bleed into puddles, steam pours off a noodle stall, a lone vendor in a white "
    "singlet works a cast-iron wok. Camera tilts up from a close-up of a raindrop and pulls back in "
    "one fluid steadicam arc to reveal the vendor tossing noodles as wok fire flares, then pushes in "
    "to the vendor's face lit by the flame. Warm tungsten practicals against cold blue night. "
    "No text, no logos, no watermark."
)

NOTE_COMMON = """# MiniMax H3 高质量视频 · 使用说明

**前置条件（一次性）**
1. 启动 ComfyUI（绘世启动器）
2. 右上角 `Sign in` 登录 comfy.org 账号，或 设置 → API Nodes 填 API Key
3. 账号内需有额度（Partner API 按秒计费，直接从 comfy.org 余额扣）

**当前配置**
- 模型：{model}
- 分辨率：{res}｜比例：{ratio}｜时长：{dur}s
- 预计消耗：约 ${cost}

**调参建议**
- 时长 4-15s，越长越贵；先用 5s 试提示词，满意后再拉到 {dur}s
- 同一提示词换 seed 反复抽卡，比改提示词更有效
- 提示词结构：镜头运动 → 场景 → 主体动作 → 光线 → 质感 → 排除项
- 结尾固定加 `No text, no logos, no watermark` 可避免乱码字幕
"""

def note(id_, pos, size, text):
    return {
        "id": id_, "type": "Note", "pos": pos, "size": size, "flags": {},
        "order": 0, "mode": 0, "inputs": [], "outputs": [],
        "properties": {}, "widgets_values": [text],
    }

def save_video(id_, pos, size, prefix, link):
    return {
        "id": id_, "type": "SaveVideo", "pos": pos, "size": size, "flags": {},
        "order": 2, "mode": 0,
        "inputs": [{"name": "video", "type": "VIDEO", "link": link}],
        "outputs": [{"name": "video", "type": "VIDEO", "links": None}],
        "properties": {}, "widgets_values": [prefix, "auto", "auto"],
    }

def load_image(id_, pos, filename, link, order=0):
    return {
        "id": id_, "type": "LoadImage", "pos": pos, "size": [300, 400], "flags": {},
        "order": order, "mode": 0, "inputs": [],
        "outputs": [
            {"name": "IMAGE", "type": "IMAGE", "links": [link]},
            {"name": "MASK", "type": "MASK", "links": None},
        ],
        "properties": {"Node name for S&R": "LoadImage"},
        "widgets_values": [filename, "image"],
    }

def doc(nodes, links):
    return {
        "id": str(uuid.uuid4()),
        "revision": 0,
        "last_node_id": max(n["id"] for n in nodes),
        "last_link_id": max([l[0] for l in links], default=0),
        "nodes": nodes,
        "links": links,
        "groups": [],
        "config": {},
        "extra": {"ds": {"scale": 0.75, "offset": [900, 120]}, "frontendVersion": "1.58.5"},
        "version": 0.4,
    }

def api_node(id_, type_, pos, size, widgets, inputs=None, outputs=None, order=1):
    return {
        "id": id_, "type": type_, "pos": pos, "size": size, "flags": {},
        "order": order, "mode": 0,
        "inputs": inputs if inputs is not None else [],
        "outputs": outputs if outputs is not None else [{"name": "VIDEO", "type": "VIDEO", "links": []}],
        "properties": {"Node name for S&R": type_},
        "widgets_values": widgets,
        "color": "#432", "bgcolor": "#653",
    }

files = {}

# ── 1. 文生视频 2K ───────────────────────────────────────────────
n = [
    api_node(1, "MinimaxHailuo03TextToVideoNode", [-620, 60], [560, 620],
             ["MiniMax H3", PROMPT_T2V, "2K", "16:9", 10, 42, "randomize", False],
             outputs=[{"name": "VIDEO", "type": "VIDEO", "links": [1]}]),
    save_video(2, [-20, 60], [560, 640], "video/MiniMax_H3_2K_t2v", 1),
    note(3, [-620, -420], [560, 400], NOTE_COMMON.format(
        model="MiniMax H3（旗舰）", res="2K", ratio="16:9", dur=10, cost="1.86 USD"))
]
files["MiniMax_H3_2K_文生视频.json"] = doc(n, [[1, 1, 0, 2, 0, "VIDEO"]])

# ── 2. 首尾帧 2K ────────────────────────────────────────────────
n = [
    load_image(1, [-1180, 60], "h3_first_frame.png", 1, 0),
    load_image(2, [-1180, 500], "h3_last_frame.png", 2, 1),
    api_node(3, "MinimaxHailuo03FirstLastFrameNode", [-820, 60], [520, 460],
             ["MiniMax H3", PROMPT_FLF, "2K", 10, 42, "randomize", False],
             inputs=[
                 {"name": "first_frame", "type": "IMAGE", "link": 1},
                 {"name": "last_frame", "type": "IMAGE", "link": 2},
             ],
             outputs=[{"name": "VIDEO", "type": "VIDEO", "links": [3]}]),
    save_video(4, [-260, 60], [560, 640], "video/MiniMax_H3_2K_flf2v", 3),
    note(5, [-1180, -420], [700, 380], NOTE_COMMON.format(
        model="MiniMax H3（旗舰）", res="2K", ratio="跟随图片", dur=10, cost="1.86 USD")
        + "\n**首尾帧要点**\n- 首帧必填、尾帧可留空（留空即普通图生视频）\n"
          "- 两图构图越接近，过渡越自然；差异过大易出现形变\n"
          "- 只接首帧时不接尾帧，节点会自动按 I2V 处理"),
]
files["MiniMax_H3_2K_首尾帧生视频.json"] = doc(
    n, [[1, 1, 0, 3, 0, "IMAGE"], [2, 2, 0, 3, 1, "IMAGE"], [3, 3, 0, 4, 0, "VIDEO"]])

# ── 3. 参考生视频 2K ────────────────────────────────────────────
n = [
    load_image(1, [-1180, 40], "h3_ref_character.png", 1, 0),
    load_image(2, [-1180, 480], "h3_ref_scene.png", 2, 1),
    api_node(3, "MinimaxHailuo03ReferenceNode", [-820, 40], [560, 560],
             ["MiniMax H3", PROMPT_R2V, "2K", "adaptive", 10, 42, "randomize", False],
             inputs=[
                 {"label": "image_1", "name": "model.reference_images.image_1", "shape": 7, "type": "IMAGE", "link": 1},
                 {"label": "image_2", "name": "model.reference_images.image_2", "shape": 7, "type": "IMAGE", "link": 2},
                 {"label": "video_1", "name": "model.reference_videos.video_1", "shape": 7, "type": "VIDEO", "link": None},
                 {"label": "audio_1", "name": "model.reference_audios.audio_1", "shape": 7, "type": "AUDIO", "link": None},
             ],
             outputs=[{"name": "VIDEO", "type": "VIDEO", "links": [3]}]),
    save_video(4, [-220, 40], [560, 640], "video/MiniMax_H3_2K_r2v", 3),
    note(5, [-1180, -460], [760, 460], NOTE_COMMON.format(
        model="MiniMax H3（旗舰）", res="2K", ratio="adaptive 自适应", dur=10, cost="1.86 USD")
        + "\n**参考生视频要点**\n- 提示词里用 `@Image1` `@Image2` 指代连接的图片，顺序即连线顺序\n"
          "- 最多 9 张图 / 3 段视频 / 3 段音频（音频必须搭配图像或视频）\n"
          "- 角色一致性场景：图 1 = 人物定妆，图 2 = 场景/光线，效果最稳\n"
          "- 接不满 2 张图时，把提示词里的 `@Image2` 删掉，否则会报参数错误"),
]
files["MiniMax_H3_2K_参考生视频.json"] = doc(
    n, [[1, 1, 0, 3, 0, "IMAGE"], [2, 2, 0, 3, 1, "IMAGE"], [3, 3, 0, 4, 0, "VIDEO"]])

# ── 4. 两段式：768P 打样 → 2K 精修 ──────────────────────────────
n = [
    api_node(1, "MinimaxHailuo03TextToVideoNode", [-900, 60], [520, 480],
             ["MiniMax H3", PROMPT_DRAFT, "768P", "16:9", 10, 42, "randomize", False],
             outputs=[{"name": "VIDEO", "type": "VIDEO", "links": [1, 2]}]),
    save_video(2, [-320, 60], [520, 460], "video/H3_draft_768p", 1),
    api_node(3, "MinimaxHailuo03RegenerateNode", [-320, 580], [520, 300],
             ["MiniMax H3", PROMPT_DRAFT, "2K", False],
             inputs=[
                 {"name": "video", "type": "VIDEO", "link": 2},
                 {"name": "first_frame", "type": "IMAGE", "shape": 7, "link": None},
                 {"name": "last_frame", "type": "IMAGE", "shape": 7, "link": None},
             ],
             outputs=[{"name": "VIDEO", "type": "VIDEO", "links": [3]}]),
    save_video(4, [260, 580], [520, 460], "video/H3_final_2k", 3),
    note(5, [-900, -420], [600, 400],
         "# 两段式：768P 打样 → 2K 精修\n\n"
         "**为什么这样搭**\n"
         "768P 单条 10s 约 $1.29，2K 直接生成约 $1.86。用 768P 反复抽卡挑中意的镜头，"
         "只对选中的那条做 2K 重渲染（$0.0715/秒，10s ≈ $0.72）。\n\n"
         "**必须遵守**\n"
         "- 右侧 Regenerate 节点的提示词必须与左侧 768P 生成时**完全一致**\n"
         "- 只能喂**未修改**的 768P 原始输出（24fps、4-15s），不要剪辑/调色后再喂\n"
         "- 若原生成用了首帧/尾帧/参考图，Regenerate 节点要接同样的输入\n"
         "- 想省钱可把左侧 SaveVideo 节点静音（Ctrl+M），只留 2K 结果"),
]
files["MiniMax_H3_两段式_768P打样转2K.json"] = doc(
    n, [[1, 1, 0, 2, 0, "VIDEO"], [2, 1, 0, 3, 0, "VIDEO"], [3, 3, 0, 4, 0, "VIDEO"]])

for name, data in files.items():
    p = os.path.join(OUT, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("written:", p)
