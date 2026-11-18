# -*- coding: utf-8 -*-
"""量化「生成动作」与「引导动作」的骨架位置偏差。

思路：两路骨架先二值化，各自做高斯模糊（半径 ~ 骨架线宽），
再取绝对差并降到 1x1 求均值 —— 等于「平均每像素的骨架亮度差异」。
0 = 完全重合；数值越大 = 肢体位置差得越远。

用法：python _pose_dist.py <骨架A> <骨架B>
"""
import subprocess
import sys

LUT = "if(gt(val\\,40)\\,255\\,0)"
SIGMA = 8

GRAPH = (
    "[0:v]format=gray,lut=y='{lut}',gblur=sigma={s}[a];"
    "[1:v]format=gray,lut=y='{lut}',gblur=sigma={s}[b];"
    "[a][b]blend=all_mode=difference,scale=1:1,format=gray"
).format(lut=LUT, s=SIGMA)


def dist(a, b):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", a, "-i", b,
                        "-lavfi", GRAPH, "-f", "rawvideo", "-"],
                       capture_output=True)
    if p.returncode != 0:
        print("ERR", p.stderr.decode()[:400])
        sys.exit(1)
    d = p.stdout
    vals = [v for v in d]
    return len(vals), sum(vals) / max(1, len(vals)), max(vals) if vals else 0


if __name__ == "__main__":
    n, mean, mx = dist(sys.argv[1], sys.argv[2])
    print("帧数 %d | 平均骨架偏移量 %.2f | 峰值 %d" % (n, mean, mx))
