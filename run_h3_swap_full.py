# -*- coding: utf-8 -*-
"""把 05 换人工作流（UI 格式）转成 API 格式，按分段依次提交给 ComfyUI 并等待出片。

用法: python run_h3_swap_full.py [seg01 seg02 ...]   默认 4 段
"""
import json, os, sys, time, urllib.request, urllib.error

from prompt_v2 import PROMPT_V2  # 修正版提示词（脸部以 <Picture 2> 头肩照为准）

WF = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/user/default/workflows/MiniMax_H3_本地/05_H3本地_源视频换人_单人.json"
OI = r"C:/Users/RoverFly/AppData/Local/Temp/oi.json"
HOST = "http://127.0.0.1:8188"
SKIP = {"MarkdownNote", "Note", "Reroute", "PrimitiveNode"}
WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO", "COMFY_DYNAMICCOMBO_V3"}

SEGS = ["seg01", "seg02", "seg03", "seg04"]


def load(path):
    with open(path, encoding="utf-8") as f:
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
        if isinstance(wv, dict):  # 少数节点用 dict 存 widget
            inputs = dict(wv)
        else:
            inputs = {}
            for i, nm in enumerate(widgets):
                if i < len(wv):
                    inputs[nm] = wv[i]

        # 连线覆盖
        for s in n.get("inputs") or []:
            if s.get("link") is None:
                continue
            src, slot = links[s["link"]]
            inputs[s["name"]] = [str(src), slot]

        api[str(n["id"])] = {
            "class_type": t,
            "inputs": inputs,
            "_meta": {"title": n.get("title") or t},
        }
    return api


def patch(wf, seg, turbo=True, steps=None, swap=1.0, frames=243, prefix=None):
    """按段打补丁：视频、帧数、步数、turbo 开关、swap LoRA 强度、输出前缀"""
    for n in wf["nodes"]:
        t = n["type"]
        title = n.get("title", "") or ""
        if t == "LoadVideo":
            n["widgets_values"][0] = f"role_swap_20261112/{seg}.mp4"
        elif t == "PrimitiveInt" and title.startswith("Int (Frames"):
            n["widgets_values"] = [int(frames), "fixed"]
        elif t == "PrimitiveInt" and (title.startswith("Int (Full)") or title.startswith("Int (Lightning")):
            if steps:
                n["widgets_values"] = [int(steps), "fixed"]
        elif t == "PrimitiveBoolean":
            n["widgets_values"] = [bool(turbo)]
            n["widgets_values_named"] = {"value": bool(turbo)}
        elif t == "LoraLoaderModelOnly":
            nm = (n.get("widgets_values") or [""])[0]
            if "character_swap" in str(nm):
                n["widgets_values"][1] = float(swap)
        elif t == "SaveVideo":
            n["widgets_values"][0] = prefix or f"video/H3_swap/zhaomei_{seg}"
    return wf


def post(prompt):
    body = json.dumps({"prompt": prompt, "client_id": "h3-runner"}).encode()
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
    oi = load(OI)
    base = load(WF)

    # 可选参数：--steps=4 --swap=1.0 --frames=243 --turbo=1 --prefix=full
    #   --headref=0   不接头肩特写参考图（默认接，脸部以 <Picture 2> 为准）
    #   --prompt=v2   用修正版提示词（默认 v2）
    opts = {"steps": None, "swap": 1.0, "frames": 243, "turbo": True, "prefix": "full",
            "headref": True, "prompt": "v2", "refs": "orig"}
    segs = []
    for a in sys.argv[1:]:
        if a.startswith("--"):
            k, _, v = a[2:].partition("=")
            if k == "steps":
                opts["steps"] = int(v)
            elif k == "swap":
                opts["swap"] = float(v)
            elif k == "frames":
                opts["frames"] = int(v)
            elif k == "turbo":
                opts["turbo"] = v not in ("0", "false", "False")
            elif k == "prefix":
                opts["prefix"] = v
            elif k == "headref":
                opts["headref"] = v not in ("0", "false", "False")
            elif k == "prompt":
                opts["prompt"] = v
            elif k == "refs":
                opts["refs"] = v
        else:
            segs.append(a)
    segs = segs or SEGS
    print("参数:", opts, "段落:", segs, flush=True)

    for seg in segs:
        wf = json.loads(json.dumps(base))
        patch(wf, seg, turbo=opts["turbo"], steps=opts["steps"], swap=opts["swap"],
              frames=opts["frames"], prefix=f"video/H3_swap/{opts['prefix']}/{seg}")
        api = to_api(wf, oi)
        if opts["headref"]:
            api["136"]["inputs"]["ref_images.ref_image_1"] = ["139", 0]
        if opts["prompt"] == "v2":
            api["138"]["inputs"]["value"] = PROMPT_V2
        elif opts["prompt"] == "v3":
            from prompt_v3 import PROMPT_V3
            api["138"]["inputs"]["value"] = PROMPT_V3
        if opts["refs"] == "soft":
            # 淡妆版参考：全身用图集 022（细眼线），头肩用图集 003 裁图
            api["137"]["inputs"]["image"] = "role_swap_20261112/zhaomei_full2.png"
            api["139"]["inputs"]["image"] = "role_swap_20261112/zhaomei_head2.png"
        print(f"\n===== {seg}: {len(api)} nodes  refs={opts['refs']}  prompt={opts['prompt']}", flush=True)
        res = post(api)
        if "error" in res:
            print("提交失败:", str(res["error"])[:1500], flush=True)
            return 1
        pid = res.get("prompt_id")
        print("prompt_id", pid, flush=True)
        t0 = time.time()
        while True:
            time.sleep(8)
            h = get(f"/history/{pid}")
            if pid in h:
                st = h[pid].get("status", {})
                if st.get("status_str") == "error" or st.get("completed") is False and st.get("status_str") == "error":
                    print("执行报错:", json.dumps(st, ensure_ascii=False)[:2000], flush=True)
                    return 2
                outs = h[pid].get("outputs", {})
                files = []
                for node in outs.values():
                    for v in node.values():
                        if isinstance(v, list):
                            for it in v:
                                if isinstance(it, dict) and it.get("filename"):
                                    files.append(it["filename"])
                print(f"{seg} 完成，用时 {(time.time()-t0)/60:.1f} 分钟，输出 {files}", flush=True)
                break
            if int(time.time() - t0) % 120 < 8:
                q = get("/queue")
                run = len(q.get("queue_running", []))
                pend = len(q.get("queue_pending", []))
                print(f"  [{seg}] {(time.time()-t0)/60:.1f} 分钟  running={run} pending={pend}", flush=True)
    print("\n全部完成", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
