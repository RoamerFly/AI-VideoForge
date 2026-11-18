# -*- coding: utf-8 -*-
"""SCAIL-2 串联长视频：段间用 previous_frames 接力，一次提交跑完整条片子。

背景——为什么必须串联：
    WanSCAILToVideo 的 previous_frames 输入是 SCAIL-2 唯一的段间一致机制
    （节点内部取末 previous_frame_count 帧做锚定，并把 video_frame_offset 自动回退）。
    之前每段单独提交、这个输入是空的，等于每段从零生成，所以服装/背景段段不同。

训练配置对齐：
    节点 tooltip 写明 "SCAIL-2 trained at 5 (81-frame chunks, 76-frame step)"。
    因此 length=81、previous_frame_count=5、相邻段偏移 76 帧，与训练一致。

用法：
    python _scail_chain.py <steps> <段数> [标签] [起始秒] [总秒]
    python _scail_chain.py 6 2 chain_test          # 2 段验证接力是否生效
    python _scail_chain.py 6 7 chain_full 0 34     # 7 段跑满 34 秒
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, "app")
import core

STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 6
NSEG = int(sys.argv[2]) if len(sys.argv) > 2 else 2
TAG = sys.argv[3] if len(sys.argv) > 3 else "chain"
T0 = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
DUR = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0

SRC = "E:/Agent/projects/AI视频模板/申鹤站立扭身舞.mp4"
REF_ABS = r"E:/Agent/projects/freetime_AI_Draw/角色工坊库/角色库/宗师雏田/参考图/宗师雏田_参考01_全身_正面.png"
CI = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/input"
WORK = os.path.join(CI, "h3studio", "scail34")
os.makedirs(WORK, exist_ok=True)

W, H = 512, 896
FPS = 16
LEN = 81          # 与训练一致
PREV = 5          # 与训练一致
STEP = LEN - PREV  # 76

PROMPT = ("A young woman with long straight black hair, wearing a red chinese halter dress with "
          "silver belt, red wrist guards and red boots, dancing in a clean empty white studio "
          "with seamless white backdrop and white floor, plain background, full body shot")
QUALITY = ("natural lighting, sharp details, smooth motion, correct anatomy, no extra limbs, "
           "clean background")

# 驱动视频：按需裁一段
src = os.path.join(WORK, f"chain_src_{TAG}.mp4")
vf = f"fps={FPS},scale={W}:{H}:flags=lanczos"
cmd = ["ffmpeg", "-y", "-loglevel", "error"]
if T0 > 0:
    cmd += ["-ss", f"{T0:.3f}"]
cmd += ["-i", SRC]
if DUR > 0:
    cmd += ["-t", f"{DUR:.3f}"]
cmd += ["-vf", vf, "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-an", src]
subprocess.run(cmd, check=True)
info = core.probe_video(src)
TOTAL = int(info.get("frames") or round(float(info["duration"]) * FPS))
print(f"驱动素材 {TOTAL} 帧 / {TOTAL / FPS:.2f}s", flush=True)

need = (NSEG - 1) * STEP + LEN
if TOTAL < need:
    print(f"素材不够：需要 {need} 帧，只有 {TOTAL} 帧", flush=True)
    sys.exit(1)

# 参考图入档
ref_name = f"h3studio/scail34/ref_chain.png"
subprocess.run(["cp", REF_ABS, os.path.join(CI, "h3studio", "scail34", "ref_chain.png")], check=False)
video_name = f"h3studio/scail34/{os.path.basename(src)}"

tpl = core.load_template("07")

# 共享节点参数
tpl["6"]["inputs"]["text"] = (PROMPT + "\n\n" + QUALITY).strip()
tpl["9"]["inputs"]["image"] = ref_name
tpl["12"]["inputs"]["file"] = video_name
# 驱动视频要给全片：节点内部按 video_frame_offset 自己切
tpl["14"]["inputs"]["batch_index"] = 0
tpl["14"]["inputs"]["length"] = max(1024, TOTAL + 8)
tpl["18"]["inputs"]["detect_interval"] = 2   # 全片跟踪降频，省时间
tpl["21"]["inputs"]["length"] = LEN
tpl["21"]["inputs"]["previous_frame_count"] = PREV
tpl["21"]["inputs"]["width"] = W
tpl["21"]["inputs"]["height"] = H
tpl["22"]["inputs"]["steps"] = STEPS
tpl["24"]["inputs"]["cfg"] = 1.0 if STEPS <= 8 else 1.5
tpl["27"]["inputs"]["filename_prefix"] = f"H3影栈/08_SCAILchunk_{TAG}_00"

api = dict(tpl)

# 逐段复制 21-27，串成链
for i in range(1, NSEG):
    b = 21 + i * 10
    api[str(b)] = json.loads(json.dumps(tpl["21"]))
    api[str(b)].update({"inputs": dict(tpl["21"]["inputs"])})
    api[str(b + 1)] = json.loads(json.dumps(tpl["22"]))
    api[str(b + 2)] = json.loads(json.dumps(tpl["23"]))
    api[str(b + 3)] = json.loads(json.dumps(tpl["24"]))
    api[str(b + 4)] = json.loads(json.dumps(tpl["25"]))
    api[str(b + 5)] = json.loads(json.dumps(tpl["26"]))
    api[str(b + 6)] = json.loads(json.dumps(tpl["27"]))

    prev_base = 21 + (i - 1) * 10
    api[str(b)]["inputs"]["video_frame_offset"] = [str(prev_base), 3]     # 上一段的累计偏移
    api[str(b)]["inputs"]["previous_frames"] = [str(prev_base + 4), 0]    # 上一段的解码帧
    api[str(b + 3)]["inputs"]["positive"] = [str(b), 0]
    api[str(b + 3)]["inputs"]["negative"] = [str(b), 1]
    api[str(b + 3)]["inputs"]["latent_image"] = [str(b), 2]
    api[str(b + 3)]["inputs"]["noise_seed"] = 20261114 + i * 7
    api[str(b + 4)]["inputs"]["samples"] = [str(b + 3), 0]
    api[str(b + 5)]["inputs"]["images"] = [str(b + 4), 0]
    api[str(b + 6)]["inputs"]["video"] = [str(b + 5), 0]
    api[str(b + 6)]["inputs"]["filename_prefix"] = f"H3影栈/08_SCAILchunk_{TAG}_{i:02d}"

print(f"链式工作流 {NSEG} 段 × {LEN} 帧（步长 {STEP}），覆盖 {need} 帧 = {need / FPS:.2f}s", flush=True)
pid = core.submit(api)
print("提交", pid, flush=True)

t0 = time.time()
while True:
    h = core.history(pid)
    if h and ((h.get("status") or {}).get("completed") or h.get("outputs")):
        outs = [f for f in core.collect_outputs(h) if f.startswith("H3影栈/08_SCAILchunk")]
        print("完成", round(time.time() - t0), "s，输出:", outs, flush=True)
        for f in outs:
            dst = os.path.join(WORK, os.path.basename(f))
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                            "-i", os.path.join(core.comfy_output(), f), "-c", "copy", dst], check=True)
        break
    if h and (h.get("status") or {}).get("status_str") == "error":
        for m in h["status"].get("messages", []):
            if m and m[0] == "execution_error":
                print("失败:", (m[1] or {}).get("exception_message", "")[:600], flush=True)
        sys.exit(1)
    time.sleep(5)
