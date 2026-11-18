# -*- coding: utf-8 -*-
"""纯图生视频测试：把 05 换人工作流改造为 ImageToVideo（fl2va）。

思路：
  - 136 MiniMaxH3ReferenceToVideo  → MiniMaxH3ImageToVideo（first_frame 接全身棚拍图）
  - 152 MiniMaxH3AddGuide 删除（图生视频靠首帧锚定，不需要源视频）
  - 127 UNETLoader 换成 fl2va 权重
  - 145 turbo LoRA 换成 fl2v_4step_768p
  - 147 swap LoRA 删除（换人 LoRA 在图生视频里会带人脸偏置）
  - BasicGuider.conditioning 直连 ImageToVideo 的 positive 输出

用法:
  python i2v_test.py --frames=124 --w=640 --h=1120 --prefix=i2v
"""
import json, sys, time, urllib.request, urllib.error

WF = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/user/default/workflows/MiniMax_H3_本地/05_H3本地_源视频换人_单人.json"
OI = r"C:/Users/RoverFly/AppData/Local/Temp/oi.json"
HOST = "http://127.0.0.1:8188"
SKIP = {"MarkdownNote", "Note", "Reroute", "PrimitiveNode"}
WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO", "COMFY_DYNAMICCOMBO_V3"}

UNET_I2V = "minimax_h3_fl2va_pruned_int8_convrot.safetensors"
LORA_I2V = "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors"

PROMPT_BIG = """画面：全身竖构图，纯白摄影棚背景，机位固定不动，光线均匀柔和。写实摄影质感，皮肤有真实纹理与血色。

人物：红褐色长发女性，头戴竹编斗笠，身穿蓝紫色开衩和服、白色内衬、黑色腰带系麻绳，手臂有深色护臂，脚穿黑色长筒袜。

动作：她大幅跳舞——双臂高高举过头顶再向两侧甩开，腰胯左右大幅摆动，一条腿抬起做踢步，连续小跳两次落地，上身跟着节拍前后起伏，宽大的袖口和裙摆随着动作甩开。

要求：动作幅度大、有力量感和重量感；面部自然，眼睛睁开有焦点；整段持续在动，不要中途停下来站着不动。"""

PROMPT = """画面：全身竖构图，纯白摄影棚背景，机位固定不动，光线均匀柔和。写实摄影质感，皮肤有真实纹理与血色。

人物：红褐色长发女性，头戴竹编斗笠，身穿蓝紫色开衩和服、白色内衬、黑色腰带系麻绳，手臂有深色护臂，脚穿黑色长筒袜，腰侧挂着葫芦。

动作：她站在原地随节奏轻快地跳舞——左右摆动腰胯，双臂抬起划出弧线，肩膀跟着节拍起伏，身体重心在两腿之间来回移动，最后轻跳两下落地。

要求：动作连贯流畅、有重量感不生硬；面部自然，眼睛睁开有焦点，会自然眨眼；不要面无表情、不要身体僵直、不要原地抖动。"""


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def to_api(wf, oi):
    links = {l[0]: (l[1], l[2]) for l in wf["links"]}
    api = {}
    for n in wf["nodes"]:
        t = n["type"]
        if t in SKIP or t not in oi:
            continue
        info = oi[t]
        order = info.get("input_order", {})
        names = list(order.get("required", [])) + list(order.get("optional", []))
        specs = dict(info["input"].get("required", {}))
        specs.update(info["input"].get("optional", {}))
        widgets = []
        for nm in names:
            spec = specs.get(nm)
            if not spec:
                continue
            cfg = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
            if cfg.get("socketless"):
                continue
            if isinstance(spec[0], list) or spec[0] in WIDGET_TYPES:
                widgets.append(nm)
        wv = n.get("widgets_values") or []
        if isinstance(wv, dict):
            inputs = dict(wv)
        else:
            inputs = {}
            for i, nm in enumerate(widgets):
                if i < len(wv):
                    inputs[nm] = wv[i]
        for s in n.get("inputs") or []:
            if s.get("link") is None:
                continue
            src, slot = links[s["link"]]
            inputs[s["name"]] = [str(src), slot]
        api[str(n["id"])] = {"class_type": t, "inputs": inputs,
                             "_meta": {"title": n.get("title") or t}}
    return api


def build(api, frames, w, h, image, prefix, prompt):
    # 1) 换掉 Ref2VA → ImageToVideo
    old = api.pop("136")
    api["136"] = {
        "class_type": "MiniMaxH3ImageToVideo",
        "inputs": {
            "clip": ["128", 0],
            "vae": ["119", 0],
            "prompt": prompt,
            "width": int(w),
            "height": int(h),
            "length": int(frames),
            "first_frame": ["137", 0],
        },
        "_meta": {"title": "MiniMaxH3 ImageToVideo"},
    }
    # 2) 去掉 AddGuide，BasicGuider 直连 positive
    api.pop("152", None)
    api["126"]["inputs"]["conditioning"] = ["136", 0]

    # 3) 换模型：fl2va + fl2v turbo lora；摘掉 swap LoRA
    api["127"]["inputs"]["unet_name"] = UNET_I2V
    api["147"].pop("inputs", None)
    api.pop("147", None)
    api["148"]["inputs"]["model"] = ["127", 0]   # LowVRAMAttention 直接吃 UNet
    api["145"]["inputs"]["lora_name"] = LORA_I2V
    api["145"]["inputs"]["strength_model"] = 1.0

    # 4) 分辨率 / 首帧 / 输出名
    api["154"]["inputs"]["value"] = int(w)
    api["155"]["inputs"]["value"] = int(h)
    api["153"]["inputs"]["value"] = int(frames)
    api["137"]["inputs"]["image"] = image
    api["92"]["inputs"]["filename_prefix"] = prefix
    return api


def post(prompt):
    body = json.dumps({"prompt": prompt, "client_id": "h3-i2v"}).encode()
    req = urllib.request.Request(HOST + "/prompt", body, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode("utf-8", "replace")}


def get(path):
    with urllib.request.urlopen(HOST + path, timeout=30) as r:
        return json.loads(r.read())


def main():
    opts = {"frames": 124, "w": 640, "h": 1120, "prefix": "video/H3_swap/i2v/i2v_test",
            "image": "role_swap_20261112/zhaomei_front.png", "save": "", "big": "0"}
    for a in sys.argv[1:]:
        k, _, v = a[2:].partition("=")
        if k in ("frames", "w", "h"):
            opts[k] = int(v)
        else:
            opts[k] = v

    oi = load(OI)
    api = to_api(load(WF), oi)
    api = build(api, opts["frames"], opts["w"], opts["h"],
                opts["image"], opts["prefix"],
                PROMPT_BIG if opts.get("big") == "1" else PROMPT)

    if opts["save"]:
        with open(opts["save"], "w", encoding="utf-8") as f:
            json.dump(api, f, ensure_ascii=False, indent=1)
        print("API 已存:", opts["save"])

    print(f"提交 {opts['w']}x{opts['h']} / {opts['frames']} 帧 / 4 步", flush=True)
    res = post(api)
    if "error" in res:
        print("提交失败:", str(res["error"])[:2500], flush=True)
        return 1
    pid = res.get("prompt_id")
    print("prompt_id", pid, flush=True)

    t0 = time.time()
    while True:
        time.sleep(10)
        h = get(f"/history/{pid}")
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                print("执行报错:", json.dumps(st, ensure_ascii=False)[:3000], flush=True)
                return 2
            files = [it["filename"]
                     for node in h[pid].get("outputs", {}).values()
                     for v in node.values() if isinstance(v, list)
                     for it in v if isinstance(it, dict) and it.get("filename")]
            print(f"完成，用时 {(time.time()-t0)/60:.1f} 分钟，输出 {files}", flush=True)
            return 0
        if int(time.time() - t0) % 90 < 10:
            print(f"  {(time.time()-t0)/60:.1f} 分钟...", flush=True)


if __name__ == "__main__":
    sys.exit(main())
