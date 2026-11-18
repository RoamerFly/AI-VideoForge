# -*- coding: utf-8 -*-
"""34 秒完整版（SCAIL-2 路线）：分段生成 → 去重叠拼接 → 补帧 24fps → 挂原音轨。

分段参数与产品 _run_scail 一致：每段 65 帧 @16fps、重叠 5 帧、步长 60 帧。
支持范围执行（--from/--to），避免单次跑太久被系统回收；已完成的段落盘可续跑。

用法：
    python _scail34.py 6 0 5      # 6 步，跑第 0..4 段
    python _scail34.py 6 5 10     # 续跑第 5..9 段（自动复用前 5 段）
"""
import glob
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, "app")
import core

STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 6
I0 = int(sys.argv[2]) if len(sys.argv) > 2 else 0
I1 = int(sys.argv[3]) if len(sys.argv) > 3 else 10

SRC = "E:/Agent/projects/AI视频模板/申鹤站立扭身舞.mp4"
REF_ABS = r"E:/Agent/projects/freetime_AI_Draw/角色工坊库/角色库/宗师雏田/参考图/宗师雏田_参考01_全身_正面.png"
CI = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/input"
WORK = os.path.join(CI, "h3studio", "scail34")
os.makedirs(WORK, exist_ok=True)

W, H = 512, 896
SEG, OVERLAP = 65, 5
STRIDE = SEG - OVERLAP

# 注意：背景词只能写纯白无缝。"wooden floor" 之类的具体材质会被模型当作场景线索，
# 在遮挡重、遮罩弱化的段落里把白棚重建成室内木地板（seg6 实测踩过）。
PROMPT = ("A young woman with long straight black hair, wearing a red chinese halter dress with "
          "silver belt, red wrist guards and red boots, dancing in a clean empty white studio "
          "with seamless white backdrop and white floor, plain background, full body shot")
QUALITY = ("natural lighting, sharp details, smooth motion, correct anatomy, no extra limbs, "
           "clean background")

# 母带：16fps 512x896
master = os.path.join(WORK, "master16.mp4")
if not os.path.exists(master):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", SRC,
                    "-vf", f"fps=16,scale={W}:{H}:flags=lanczos",
                    "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-an", master],
                   check=True)
info = core.probe_video(master)
TOTAL = int(info.get("frames") or round(float(info["duration"]) * 16))
print(f"母带 {TOTAL} 帧 @16fps", flush=True)

# 起始帧必须保证 start+SEG 不越过母带末尾，否则最后一段只切到几帧、模型会凭空补满 SEG 帧
starts = list(range(0, max(1, TOTAL - SEG + 1), STRIDE))
print(f"共 {len(starts)} 段，本次跑 {I0}..{min(I1, len(starts)) - 1}", flush=True)

# 参考图入档
ref_name = "h3studio/scail34/ref.png"
ref_dst = os.path.join(CI, "h3studio", "scail34", "ref.png")
if not os.path.exists(ref_dst):
    shutil.copy2(REF_ABS, ref_dst)

for i in range(I0, min(I1, len(starts))):
    out = os.path.join(WORK, f"seg{i}.mp4")
    if os.path.exists(out) and os.path.getsize(out) > 50000:
        print(f"[{i}] 已存在，跳过", flush=True)
        continue

    # 复用 output 里已生成的同号段
    hits = sorted(glob.glob(os.path.join(core.comfy_output(), "H3影栈", f"07_SCAIL_s34_{i:02d}_*.mp4")))
    if hits:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", hits[-1],
                        "-c", "copy", out], check=True)
        print(f"[{i}] 复用 {os.path.basename(hits[-1])}", flush=True)
        continue

    s0 = starts[i]
    clip = os.path.join(WORK, f"in{i:02d}.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{s0/16.0:.4f}",
                    "-i", master, "-frames:v", str(SEG),
                    "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-an", clip],
                   check=True)

    p = {
        "engine": "scail",
        "images": [ref_name],
        "char_count": 1,
        "video": f"h3studio/scail34/in{i:02d}.mp4",
        "prompt": PROMPT, "quality": QUALITY,
        "width": W, "height": H, "frames": SEG,
        "steps": STEPS, "seed": 20261114 + i,
        "tag": f"s34_{i:02d}",
    }
    api = core.build_api("05", p)
    t0 = time.time()
    pid = core.submit(api)
    print(f"[{i}] 提交 {pid}（第 {s0} 帧起，{SEG} 帧，{STEPS} 步）", flush=True)
    while True:
        h = core.history(pid)
        if h and ((h.get("status") or {}).get("completed") or h.get("outputs")):
            outs = [f for f in core.collect_outputs(h) if f.startswith("H3影栈/")]
            if not outs:
                print(f"[{i}] 没有输出", flush=True)
                sys.exit(1)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                            "-i", os.path.join(core.comfy_output(), outs[0]),
                            "-c", "copy", out], check=True)
            print(f"[{i}] 完成 {round(time.time() - t0)}s", flush=True)
            break
        if h and (h.get("status") or {}).get("status_str") == "error":
            for m in h["status"].get("messages", []):
                if m and m[0] == "execution_error":
                    print(f"[{i}] 失败:", (m[1] or {}).get("exception_message", "")[:400], flush=True)
            sys.exit(1)
        time.sleep(5)

# 全段齐了才拼接
segs = [os.path.join(WORK, f"seg{i}.mp4") for i in range(len(starts))]
if all(os.path.exists(x) for x in segs):
    print("全部段落就绪，开始拼接", flush=True)
    merged = os.path.join(WORK, "merged.mp4")
    core.concat_with_overlap(segs, OVERLAP, 16, merged, audio_src=None)
    final = os.path.join(core.out_dir(), f"05_SCAIL_雏田_申鹤舞_34s_{STEPS}步.mp4")
    vf = ("minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
          "format=yuv420p")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", merged, "-i", SRC,
                    "-map", "0:v", "-map", "1:a?", "-c:a", "aac", "-b:a", "192k",
                    "-vf", vf, "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", final],
                   check=True)
    print("FINAL:", final, flush=True)
else:
    missing = [i for i, x in enumerate(segs) if not os.path.exists(x)]
    print("尚未完成的段:", missing, flush=True)
