# -*- coding: utf-8 -*-
"""把五个 UI 工作流转成 API 模板，供 exe 程序直接改参数提交。

输出:
  app/templates/01..05.json    API 格式（{节点id: {class_type, inputs}}）
  app/templates/nodeinfo.json  只保留用到的节点类型定义（用于界面下拉选项/校验）
"""
import json
import os

WF_DIR = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/user/default/workflows/MiniMax_H3_五模式"
OI = r"C:/Users/RoverFly/AppData/Local/Temp/oi.json"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "templates")

SKIP = {"MarkdownNote", "Note", "Reroute", "PrimitiveNode"}
WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO",
                "COMFY_DYNAMICCOMBO_V3", "COMFY_AUTOGROW_V3"}

FILES = {
    "01": "01_T2V_文生视频.json",
    "02": "02_I2V_图生视频.json",
    "03": "03_R2V_视频参考.json",
    "04": "04_CharacterSwap_角色替换.json",
    "05": "05_PoseControl_姿态控制.json",
}


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


def main():
    os.makedirs(OUT, exist_ok=True)
    oi = json.load(open(OI, encoding="utf-8"))
    used = set()
    for key, fname in FILES.items():
        wf = json.load(open(os.path.join(WF_DIR, fname), encoding="utf-8"))
        api = to_api(wf, oi)
        used |= {v["class_type"] for v in api.values()}
        with open(os.path.join(OUT, f"{key}.json"), "w", encoding="utf-8") as f:
            json.dump(api, f, ensure_ascii=False, indent=1)
        print(f"{key}  {len(api):2d} 节点  {fname}")

    slim = {k: oi[k] for k in used if k in oi}
    with open(os.path.join(OUT, "nodeinfo.json"), "w", encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False)
    print("nodeinfo.json 保留", len(slim), "种节点，", 
          round(os.path.getsize(os.path.join(OUT, "nodeinfo.json")) / 1024), "KB")
    print("用到的类型:", sorted(used))


if __name__ == "__main__":
    main()
