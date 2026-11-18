# -*- coding: utf-8 -*-
"""比较两段 OpenPose 骨架视频的重合度（IoU），用于量化「生成动作 vs 引导动作」的贴合度。

用法：python _pose_iou.py <骨架A> <骨架B>

做法：把两路骨架二值化后分别做 multiply（交集）与 screen（并集），
缩到 8x8 网格累计亮度，按帧求 交集/并集。
"""
import subprocess
import sys

LUT = "if(gt(val\\,40)\\,255\\,0)"
G = 8

GRAPH = (
    "[0:v]format=gray,lut=y='{lut}'[a];"
    "[a]split[aa][ab];"
    "[1:v]format=gray,lut=y='{lut}'[b];"
    "[b]split[ba][bb];"
    "[aa][ba]blend=all_mode=multiply,scale={g}:{g}[m1];"
    "[ab][bb]blend=all_mode=screen,scale={g}:{g}[m2];"
    "[m1][m2]hstack=inputs=2,format=gray"
).format(lut=LUT, g=G)


def iou(a, b):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", a, "-i", b,
                        "-lavfi", GRAPH, "-f", "rawvideo", "-"],
                       capture_output=True)
    if p.returncode != 0:
        print("ERR", p.stderr.decode()[:400])
        sys.exit(1)
    d = p.stdout
    frame = G * G * 2          # hstack 后每行 2G 字节，逐行交织，不是前后两块
    n = len(d) // frame
    ratios, empties = [], 0
    for i in range(n):
        base = i * frame
        inter = union = 0.0
        for row in range(G):
            rs = base + row * G * 2
            inter += sum(d[rs:rs + G]) / 255.0
            union += sum(d[rs + G:rs + G * 2]) / 255.0
        if union < 0.5:
            empties += 1
            continue
        ratios.append(inter / union)
    return n, sum(ratios) / max(1, len(ratios)), len(ratios), empties


if __name__ == "__main__":
    n, mean, valid, empty = iou(sys.argv[1], sys.argv[2])
    print("帧数 %d | 有效比对 %d 帧 | 骨架 IoU 均值 %.3f | 空帧 %d"
          % (n, valid, mean, empty))
