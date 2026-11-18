# -*- coding: utf-8 -*-
"""把 4 段换人结果拼回 34.4 秒全片：后段丢掉前 49 帧重叠，再挂回原片音轨。
用法: python assemble_full.py [子目录]     子目录默认 full，可传 v2
"""
import os, subprocess, sys, glob

OUT = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/output/video/H3_swap"
TMP = os.path.join(OUT, "_assemble")
SRC_VIDEO = r"E:/Agent/projects/AI视频模板/申鹤依赖摇.mp4"
FINAL = r"E:/Agent/projects/AI视频模板/申鹤依赖摇_换人_侠隐照美冥.mp4"
OVERLAP = 49  # 帧
FPS = 24
SUB = sys.argv[1] if len(sys.argv) > 1 else "full"
if len(sys.argv) > 2:
    FINAL = sys.argv[2]


def find(seg, sub=None):
    sub = sub or SUB
    pat = os.path.join(OUT, sub, f"{seg}*.mp4")
    hits = [h for h in sorted(glob.glob(pat)) if "_assemble" not in h]
    return hits[-1] if hits else None


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print("FFMPEG FAIL:", " ".join(cmd)[:300])
        print(p.stderr[-1500:])
        sys.exit(1)


def main():
    os.makedirs(TMP, exist_ok=True)
    segs = []
    for i in range(1, 5):
        f = find(f"seg0{i}")
        if not f:
            print(f"缺少 seg0{i} 的输出，先跑 run_h3_swap_full.py seg0{i}")
            return 1
        segs.append(f)
        print("找到", os.path.basename(f))

    parts = []
    for i, f in enumerate(segs):
        dst = os.path.join(TMP, f"p{i+1}.mp4")
        cut = 0 if i == 0 else OVERLAP
        vf = f"trim=start_frame={cut},setpts=PTS-STARTPTS" if cut else "setpts=PTS-STARTPTS"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", f,
             "-vf", vf, "-an", "-r", str(FPS),
             "-c:v", "libx264", "-crf", "15", "-pix_fmt", "yuv420p", dst])
        parts.append(dst)

    lst = os.path.join(TMP, "list.txt")
    with open(lst, "w", encoding="utf-8") as fh:
        for p in parts:
            fh.write(f"file '{p.replace(chr(92), '/')}'\n")
    joined = os.path.join(TMP, "joined.mp4")
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", lst, "-c", "copy", joined])

    # 挂回原片音轨（H3 自己生成的那条音轨和原曲无关，必须整条替换成原片音轨）
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-i", joined, "-i", SRC_VIDEO,
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-shortest", FINAL])
    print("成片:", FINAL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
