# -*- coding: utf-8 -*-
"""生成应用图标 icon.ico（暖棕渐变 + 播放符号）。"""
import os
from PIL import Image, ImageDraw, ImageFilter

S = 512
SS = 4  # 超采样


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make():
    W = S * SS
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))

    # 对角渐变底
    grad = Image.new("RGBA", (W, W))
    d = ImageDraw.Draw(grad)
    c1, c2 = (200, 143, 96), (146, 92, 58)
    for y in range(W):
        t = y / (W - 1)
        d.line([(0, y), (W, y)], fill=lerp(c1, c2, t) + (255,))

    # 圆角遮罩
    mask = Image.new("L", (W, W), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, W - 1, W - 1], radius=int(W * 0.225), fill=255)
    img.paste(grad, (0, 0), mask)

    # 顶部柔光（径向，模糊过渡）
    hi = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hi)
    hd.ellipse([W * 0.04, -W * 0.62, W * 0.96, W * 0.40], fill=(255, 255, 255, 30))
    hi = hi.filter(ImageFilter.GaussianBlur(W * 0.05))
    img = Image.alpha_composite(img, Image.composite(hi, Image.new("RGBA", (W, W), (0, 0, 0, 0)), mask))

    d = ImageDraw.Draw(img)
    # 播放三角（圆角）
    cx, cy, r = W * 0.5, W * 0.5, W * 0.175
    tri = [
        (cx - r * 0.72, cy - r),
        (cx - r * 0.72, cy + r),
        (cx + r * 1.02, cy),
    ]
    d.polygon(tri, fill=(255, 252, 246, 255))

    # 金色光点
    d.ellipse([W * .70, W * .20, W * .80, W * .30], fill=(255, 214, 150, 235))

    out = img.resize((S, S), Image.LANCZOS)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    out.save(path, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    out.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png"))
    print("已生成", path)


if __name__ == "__main__":
    make()
