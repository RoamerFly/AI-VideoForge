# -*- coding: utf-8 -*-
"""把生成片和源片同一时间点的头部区域裁出来拼成对比图（上排源片 / 下排生成）。

用法: python face_sheet.py <生成.mp4> <源seg.mp4> <out.png>
"""
import os, subprocess, sys

W, H = 640, 1120
# 头部裁剪框（在 640x1120 尺度上）
CX, CY, CS = 250, 105, 190
TIMES = [0.05, 0.30, 0.55, 0.85]


def grab(video, t, dst):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1",
                    "-vf", f"scale={W}:{H}:flags=lanczos,crop={CS}:{CS}:{CX}:{CY},scale=320:320",
                    dst], check=True)


def main():
    gen, src = sys.argv[1], sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else "face_compare.png"
    tmp = os.path.join(os.path.dirname(out) or ".", "_fs")
    os.makedirs(tmp, exist_ok=True)
    tiles = []
    for i, t in enumerate(TIMES):
        a = os.path.join(tmp, f"s{i}.png")
        b = os.path.join(tmp, f"g{i}.png")
        grab(src, t, a)
        grab(gen, t, b)
        tiles.append((a, b))

    # 上排 = 源片，下排 = 生成，中间不写字，纯图对比
    inputs = []
    for a, b in tiles:
        inputs += ["-i", a, "-i", b]
    order = []
    for i in range(4):
        order += [f"{i*2}:v", f"{i*2+1}:v"]
    filt = "".join(f"[{k}]" for k in order) + "xstack=inputs=8:layout=" + \
           "|".join(f"{c*320}_{r*320}" for r in range(2) for c in range(4)) + "[v]"
    # 注意 xstack 顺序：先 4 个源片再 4 个生成
    order2 = [f"{i*2}:v" for i in range(4)] + [f"{i*2+1}:v" for i in range(4)]
    filt = "".join(f"[{k}]" for k in order2) + "xstack=inputs=8:layout=" + \
           "|".join(f"{c*320}_{r*320}" for r in range(2) for c in range(4)) + "[v]"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs,
                    "-filter_complex", filt, "-map", "[v]", out], check=True)
    print("对比图:", out)


if __name__ == "__main__":
    main()
