# -*- coding: utf-8 -*-
"""按色相拆分 OpenPose 骨架，逐肢体比对新旧骨架的质心位移（像素）。

用法：
    <comfy_python> _pose_keypoints.py <骨架A> <骨架B> [采样间隔]
"""
import subprocess
import sys
import os
import tempfile

from PIL import Image

A, B = sys.argv[1], sys.argv[2]
STEP = int(sys.argv[3]) if len(sys.argv) > 3 else 12
TMP = tempfile.mkdtemp(prefix="posekp_")


def dump(video, tag):
    out = os.path.join(TMP, tag + "_%04d.png")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video,
                    "-vf", "select='not(mod(n\\,%d))'" % STEP, "-vsync", "0", out],
                   check=True)
    return sorted(f for f in os.listdir(TMP) if f.startswith(tag + "_"))


def centroids(path):
    """按 30 度色相分桶，返回 {桶: (x, y, 像素数)}"""
    im = Image.open(path).convert("RGB")
    W, H = im.size
    px = im.load()
    acc = {}
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            r, g, b = px[x, y]
            mx, mn = max(r, g, b), min(r, g, b)
            if mx < 90 or mx - mn < 60:      # 去黑底与白点
                continue
            if mx == r:
                h = (60 * ((g - b) / float(mx - mn))) % 360
            elif mx == g:
                h = 60 * ((b - r) / float(mx - mn)) + 120
            else:
                h = 60 * ((r - g) / float(mx - mn)) + 240
            k = int(h // 30)
            a = acc.setdefault(k, [0.0, 0.0, 0])
            a[0] += x
            a[1] += y
            a[2] += 1
    return {k: (v[0] / v[2], v[1] / v[2], v[2]) for k, v in acc.items() if v[2] >= 20}


fa, fb = dump(A, "a"), dump(B, "b")
n = min(len(fa), len(fb))
dists, per_frame = [], []
for i in range(n):
    ca = centroids(os.path.join(TMP, fa[i]))
    cb = centroids(os.path.join(TMP, fb[i]))
    common = [k for k in ca if k in cb and ca[k][2] >= 30 and cb[k][2] >= 30]
    if not common:
        continue
    ds = [((ca[k][0] - cb[k][0]) ** 2 + (ca[k][1] - cb[k][1]) ** 2) ** 0.5 for k in common]
    per_frame.append((i * STEP, round(sum(ds) / len(ds), 1), len(common)))
    dists.extend(ds)

dists.sort()
mid = dists[len(dists) // 2]
print("比对帧数 %d | 匹配肢体段总数 %d" % (len(per_frame), len(dists)))
print("肢体质心位移：均值 %.1f px | 中位 %.1f px | P90 %.1f px"
      % (sum(dists) / len(dists), mid, dists[int(len(dists) * 0.9)]))
print("逐帧(帧号, 平均位移px, 匹配段数):")
for row in per_frame:
    print("  ", row)
