# -*- coding: utf-8 -*-
"""34 秒完整版：自动分段 → 逐段 ref_videos（表情跟随）生成 → 去重叠拼接 → 挂原音轨。
可续跑：每段成品落盘到 work 目录，重跑自动跳过已存在的段。"""
import os
import subprocess
import sys
import time

sys.path.insert(0, "app")
import core

SRC = "E:/Agent/projects/AI视频模板/申鹤站立扭身舞.mp4"
CI = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/input"
WORK = os.path.join(CI, "h3studio", "full34")
os.makedirs(WORK, exist_ok=True)

STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 4
W = int(sys.argv[2]) if len(sys.argv) > 2 else 640
H = int(sys.argv[3]) if len(sys.argv) > 3 else 1120
SEG, OVERLAP = 243, 49
STRIDE = SEG - OVERLAP
TOTAL = 816  # 34s @24fps

# 1) 统一转成 24fps 母带
full = os.path.join(WORK, "full34_24fps.mp4")
if not os.path.exists(full):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", SRC,
                    "-vf", "fps=24", "-frames:v", str(TOTAL),
                    "-c:v", "libx264", "-crf", "16", "-preset", "medium",
                    "-pix_fmt", "yuv420p", "-an", full], check=True)
print("母带就绪:", full, flush=True)

starts = list(range(0, TOTAL - OVERLAP, STRIDE))
print("分段起点(帧):", starts, flush=True)

PROMPT = ("全身镜头，纯白摄影棚背景，木地板。黑长直少女，红色挂脖短上衣，银色腰带，"
          "红色短裙，红色护腕与红色短靴。")
QUALITY = ("真实摄影质感，皮肤细腻有光泽，面部表情自然生动，眼神有戏，发丝清晰，"
           "服装细节完整，画面稳定不闪烁，人体结构正确。")

def _find_done(i):
    """output/H3影栈 下已生成的第 i 段（重跑复用，避免白等）。"""
    import glob
    hits = sorted(glob.glob(os.path.join(core.comfy_output(), "H3影栈", f"full34_seg{i}_*.mp4")))
    return hits[-1] if hits else ""

for i, st in enumerate(starts):
    out = os.path.join(WORK, f"seg{i}.mp4")
    if not (os.path.exists(out) and os.path.getsize(out) > 100000):
        done = _find_done(i)
        if done:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", done,
                            "-c", "copy", out], check=True)
            print(f"[{i}] 复用已有产物 {os.path.basename(done)}", flush=True)
    if os.path.exists(out) and os.path.getsize(out) > 100000:
        print(f"[{i}] 已存在，跳过", flush=True)
        continue
    clip = os.path.join(WORK, f"in{i}.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{st/24:.4f}",
                    "-i", full, "-frames:v", str(SEG),
                    "-c:v", "libx264", "-crf", "16", "-preset", "medium",
                    "-pix_fmt", "yuv420p", "-an", clip], check=True)

    api = core.load_template("03")
    api["150"]["inputs"]["file"] = f"h3studio/full34/in{i}.mp4"
    gen = api["136"]
    gen["inputs"].update(width=W, height=H, length=SEG, ref_image_size="match")
    core._wire_ref_images(api, gen, ["h3studio/pose_test/hinata.png"], "match")
    gen["inputs"]["prompt"] = core._augment_prompt(PROMPT, ["h3studio/pose_test/hinata.png"],
                                                   has_video_ref=True, guide=True, char_count=1)
    gen["inputs"]["prompt"] = gen["inputs"]["prompt"] + "\n\n" + QUALITY
    api["146"]["inputs"]["value"] = (STEPS <= 6)
    api["143"]["inputs"]["value"] = 20 if STEPS <= 6 else STEPS
    api["144"]["inputs"]["value"] = STEPS if STEPS <= 6 else 4
    api["129"]["inputs"]["noise_seed"] = 20261114 + i
    api["92"]["inputs"]["filename_prefix"] = f"H3影栈/full34_seg{i}"

    t0 = time.time()
    pid = core.submit(api)
    print(f"[{i}] 提交 {pid} 从第 {st} 帧", flush=True)
    while True:
        h = core.history(pid)
        if h and ((h.get("status") or {}).get("completed") or h.get("outputs")):
            files = [f for f in core.collect_outputs(h) if f.startswith("H3影栈/")]
            src_out = os.path.join(core.comfy_output(), files[0])
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src_out,
                            "-c", "copy", out], check=True)
            print(f"[{i}] 完成 {round(time.time()-t0)}s → {os.path.basename(out)}", flush=True)
            break
        if h and (h.get("status") or {}).get("status_str") == "error":
            for m in h["status"].get("messages", []):
                if m and m[0] == "execution_error":
                    print(f"[{i}] 失败:", (m[1] or {}).get("exception_message", "")[:400], flush=True)
            sys.exit(1)
        time.sleep(10)

# 拼接：非首段丢掉前 OVERLAP 帧
segs = [os.path.join(WORK, f"seg{i}.mp4") for i in range(len(starts))]
inputs, filters, labels = [], [], []
for i, p in enumerate(segs):
    inputs += ["-i", p]
    skip = 0 if i == 0 else OVERLAP
    filters.append(f"[{i}:v]trim=start_frame={skip},setpts=PTS-STARTPTS,fps=24,format=yuv420p[v{i}]")
    labels.append(f"[v{i}]")
graph = ";".join(filters) + f";{''.join(labels)}concat=n={len(labels)}:v=1:a=0[vout]"
out_mp4 = os.path.join(core.out_dir(), "05_雏田_申鹤舞_34s_表情跟随.mp4")
cmd = ["ffmpeg", "-y", "-loglevel", "error"] + inputs + [
    "-i", SRC, "-filter_complex", graph, "-map", "[vout]", "-map", f"{len(segs)}:a:0?",
    "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "192k", "-shortest", out_mp4]
subprocess.run(cmd, check=True)
print("FINAL:", out_mp4, flush=True)
