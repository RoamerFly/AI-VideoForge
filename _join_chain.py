# -*- coding: utf-8 -*-
"""把 _scail_chain.py 产出的分段拼成整片：去重叠 → 插帧 24fps → 挂原音轨。

段间重叠 5 帧（previous_frame_count 的锚定帧），所以第 1 段起每段丢掉前 5 帧：
    总帧数 = 81 + (N-1) * 76

用法：
    python _join_chain.py <标签> [段数]
    python _join_chain.py chain_full 7
"""
import os
import subprocess
import sys

CI = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/input"
WORK = os.path.join(CI, "h3studio", "scail34")
SRC = "E:/Agent/projects/AI视频模板/申鹤站立扭身舞.mp4"
FPS_IN, FPS_OUT = 16, 24
LEN, PREV = 81, 5

TAG = sys.argv[1] if len(sys.argv) > 1 else "chain_full"
NSEG = int(sys.argv[2]) if len(sys.argv) > 2 else 7

segs = [os.path.join(WORK, f"08_SCAILchunk_{TAG}_{i:02d}_00001_.mp4") for i in range(NSEG)]
missing = [s for s in segs if not os.path.exists(s)]
if missing:
    print("缺段:", [os.path.basename(m) for m in missing])
    sys.exit(1)

# 逐段裁掉锚定帧，得到干净片段，再无损拼接
parts = []
for i, s in enumerate(segs):
    dst = os.path.join(WORK, f"_join_{TAG}_{i:02d}.mp4")
    vf = [] if i == 0 else [f"select='gte(n\\,{PREV})'", "setpts=N/FRAME_RATE/TB"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", s]
    if vf:
        cmd += ["-vf", ",".join(vf), "-vsync", "0"]
    cmd += ["-an", "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", dst]
    subprocess.run(cmd, check=True)
    parts.append(dst)

lst = os.path.join(WORK, f"_join_{TAG}_list.txt")
with open(lst, "w", encoding="utf-8") as f:
    for p in parts:
        f.write(f"file '{p.replace(os.sep, '/')}'\n")

merged = os.path.join(WORK, f"_join_{TAG}_merged.mp4")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                "-i", lst, "-c", "copy", merged], check=True)

# 插帧 24fps + 挂原音轨
final = os.path.join(WORK, f"05_SCAIL_雏田_申鹤舞_{NSEG}段串联_6步.mp4")
vf_out = ("minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
          "format=yuv420p")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", merged, "-i", SRC,
                "-map", "0:v", "-map", "1:a?", "-c:a", "aac", "-b:a", "192k",
                "-vf", vf_out, "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
                "-shortest", final], check=True)

info = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                       "stream=codec_type,width,height,nb_frames,r_frame_rate,duration",
                       "-of", "default=noprint_wrappers=1", final],
                      capture_output=True, text=True).stdout
print(f"FINAL: {final}")
print(info.strip())
