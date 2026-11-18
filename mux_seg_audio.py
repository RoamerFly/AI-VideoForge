# -*- coding: utf-8 -*-
"""给某一段换人成片挂回「原片音轨」的对应时间片，出预览。

H3 会自己生成一条音轨（和原曲毫无关系），预览/成片一律用原片音轨覆盖。
用法:
  python mux_seg_audio.py <生成的segXX.mp4> <seg序号1-4> <输出.mp4>
"""
import os, subprocess, sys

SRC = r"E:/Agent/projects/AI视频模板/申鹤依赖摇.mp4"
FPS = 24
# 各段在 24fps 时间轴上的起始帧（与 seg01..04 切分表一致）
START_FRAME = {1: 0, 2: 194, 3: 388, 4: 582}


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print("FFMPEG FAIL:", " ".join(cmd)[:300])
        print(p.stderr[-1200:])
        sys.exit(1)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    gen, seg = sys.argv[1], int(sys.argv[2])
    out = sys.argv[3] if len(sys.argv) > 3 else os.path.splitext(gen)[0] + "_origaudio.mp4"
    start = START_FRAME[seg] / FPS
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", gen],
        capture_output=True, text=True).stdout.strip() or 10.125)

    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-i", gen,
         "-ss", f"{start:.4f}", "-t", f"{dur:.4f}", "-i", SRC,
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-shortest", out])
    print("输出:", out, f"(原片音轨 {start:.2f}s ~ {start+dur:.2f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
