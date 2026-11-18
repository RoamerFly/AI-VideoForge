# -*- coding: utf-8 -*-
"""A/B 结果对比拼图：源片 / 4步 / 12步，全身 + 脸部特写两组网格。"""
import os, subprocess, glob

COMFY = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI"
SRC = f"{COMFY}/input/role_swap_20261112/ab_124f.mp4"
OUT = f"{COMFY}/output/video/H3_swap"
TMP = r"C:/Users/RoverFly/AppData/Local/Temp"
TIMES = [0.3, 1.6, 2.9, 4.2]

COLS = [("源片", SRC)]
for lbl in ("s04_turbo_sw100", "s12_full_sw100"):
    fs = sorted(glob.glob(f"{OUT}/ab_{lbl}*.mp4"))
    if fs:
        COLS.append((lbl, fs[-1]))


def ff(*a):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *a], check=True)


def grab(video, t, w, out):
    ff("-ss", str(t), "-i", video, "-frames:v", "1", "-vf", f"scale={w}:-2", out)


def grid(cols, tiles, out_path, name):
    """cols×rows 拼图；tiles[col][row] = 图片路径"""
    inputs = []
    for c in tiles:
        inputs.extend(c)
    n = len(cols)
    rows = len(tiles[0])
    fc = "".join(f"[{i}]" for i in range(len(inputs)))
    fc += f"xstack=inputs={len(inputs)}:layout=" + "|".join(
        f"{c}*w0_{0}" if False else
        "".join([]) or f"{(i % n)}*iw_{i}//{n}*ih_{i}" if False else ""
        for i in range(len(inputs))
    )
    return None  # 用 simplify 版


def stack_rows(rows, out_path):
    """rows: [[img,...], ...] -> vstack 各 hstack"""
    cmd = []
    for r in rows:
        for p in r:
            cmd += ["-i", p]
    n = len(rows[0])
    parts, idx = [], 0
    for _ in rows:
        ins = "".join(f"[{idx+i}]" for i in range(n))
        parts.append(f"{ins}hstack={n}[r{idx}]")
        idx += n
    labs = "".join(f"[r{idx-n+i}]" for i in range(len(rows))) if False else "".join(f"[r{k*len(rows[0])}]" for k in range(len(rows)))
    parts.append(f"{labs}vstack={len(rows)}[v]")
    ff(*cmd, "-filter_complex", ";".join(parts), "-map", "[v]", out_path)


def main():
    print("列:", [c[0] for c in COLS])
    for tag, w, crop in (("full", 210, None), ("face", 300, "crop=iw*0.62:ih*0.42:iw*0.19:ih*0.02")):
        rows = []
        for t in TIMES:
            row = []
            for name, video in COLS:
                p = os.path.join(TMP, f"ab_{tag}_{name}_{t}.jpg")
                vf = f"scale={w}:-2"
                if crop:
                    vf = f"{crop},scale={w}:-2"
                ff("-ss", str(t), "-i", video, "-frames:v", "1", "-vf", vf, p)
                row.append(p)
            rows.append(row)
        out = os.path.join(TMP, f"ab_{tag}_grid.jpg")
        stack_rows(rows, out)
        print("生成", out)


if __name__ == "__main__":
    main()
