# -*- coding: utf-8 -*-
"""用已生成的 seg0..seg8（跳过尾部无效的 seg9）重新拼接，补足尾帧后挂原音轨。

seg9 的输入只有 10 帧（母带 550 帧，540 起切不够 65 帧），模型仍输出 65 帧，
尾部 55 帧是凭空生成，必须丢弃。
"""
import os
import subprocess
import sys

sys.path.insert(0, "app")
import core

WORK = os.path.join(core.comfy_input(), "h3studio", "scail34")
SRC = "E:/Agent/projects/AI视频模板/申鹤站立扭身舞.mp4"
SEG, OVERLAP, FPS = 65, 5, 16

segs = [os.path.join(WORK, f"seg{i}.mp4") for i in range(9)]
for s in segs:
    assert os.path.exists(s), f"缺 {s}"

merged = os.path.join(WORK, "merged9.mp4")
core.concat_with_overlap(segs, OVERLAP, FPS, merged, audio_src=None)
mi = core.probe_video(merged)
dur = float(mi["duration"])
print(f"拼接完成 {dur:.4f}s / {mi.get('frames')} 帧")

src_dur = float(core.probe_video(SRC)["duration"])
pad = max(0.0, src_dur - dur)
print(f"源片 {src_dur:.4f}s，需补 {pad:.4f}s")

final = os.path.join(core.out_dir(), "05_SCAIL_雏田_申鹤舞_34s_6步.mp4")
vf = (f"tpad=stop_mode=clone:stop_duration={pad:.3f},"
      "minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
      "format=yuv420p")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", merged, "-i", SRC,
                "-map", "0:v", "-map", "1:a?", "-c:a", "aac", "-b:a", "192k",
                "-vf", vf, "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
                "-shortest", final], check=True)
info = core.probe_video(final)
print("FINAL:", final)
print("规格:", {k: info.get(k) for k in ("width", "height", "frames", "fps", "duration")})
