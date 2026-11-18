# -*- coding: utf-8 -*-
"""把角色图重排成与驱动片相同的构图（人物高度占比 88%、水平居中、脚踩 95% 线）。"""
import sys
import numpy as np
from PIL import Image

def figure_mask(a):
    """浅底棚拍图：把"明显不是背景"的像素当作人物（亮度低或饱和度高）。"""
    mx = a.max(axis=2); mn = a.min(axis=2)
    bright = mx > 205
    sat = (mx - mn) > 26
    return (~bright) | sat

def subject_box(path, max_side=512):
    im = Image.open(path).convert("RGB")
    k = max_side / max(im.size)
    if k < 1:
        im = im.resize((int(im.width*k), int(im.height*k)), Image.LANCZOS)
    a = np.asarray(im).astype(np.int16)
    m = figure_mask(a)
    # 去掉零星噪点：只保留行/列方向上显著的行列
    rows = m.sum(axis=1); cols = m.sum(axis=0)
    ry = np.where(rows > im.height * 0.02)[0]; cx = np.where(cols > im.width * 0.02)[0]
    if len(ry) < 5 or len(cx) < 5:
        return None, im
    return (cx[0], ry[0], cx[-1], ry[-1]), im

def fit_reference(ref_path, out_path, ratio_h=0.88, bottom=0.95, canvas=(480, 832)):
    box, im = subject_box(ref_path)
    if box is None:
        im.save(out_path); return None
    x0, y0, x1, y1 = box
    fig = im.crop((x0, y0, x1 + 1, y1 + 1))
    W, H = canvas
    target_h = int(H * ratio_h)
    k = target_h / fig.height
    fig = fig.resize((max(1, int(fig.width * k)), target_h), Image.LANCZOS)
    base = Image.new("RGB", (W, H), (238, 238, 238))
    if fig.width > W:
        fig = fig.crop(((fig.width - W)//2, 0, (fig.width + W)//2, fig.height))
    x = (W - fig.width) // 2
    y = int(H * bottom) - fig.height
    base.paste(fig, (x, max(0, y)))
    base.save(out_path)
    return box

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/input/h3studio/pose_test/hinata.png"
    dst = sys.argv[2] if len(sys.argv) > 2 else "_shot/ref_fitted.png"
    b = fit_reference(src, dst)
    print("人物框:", b, "→", dst)
    im = Image.open(dst); print("输出尺寸:", im.size)
