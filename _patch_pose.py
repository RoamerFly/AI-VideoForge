# -*- coding: utf-8 -*-
"""修补骨架视频里的空白帧：用最近的有效帧克隆填充，避免 LTX 控制信号闪断。

OpenPose 对二次元角色仍有约 9% 帧检不出（人物转身/遮挡时），这些帧在控制视频里是纯黑，
会让生成结果出现瞬间姿态归零。这里逐帧检测并回填。

用法：python _patch_pose.py dance_001_shenhe_stand_twist
"""
import glob
import os
import shutil
import subprocess
import sys

LIB = r"E:/Agent/projects/LTX25_ActionLibrary"
ACTION = sys.argv[1] if len(sys.argv) > 1 else "dance_001_shenhe_stand_twist"
ADIR = os.path.join(LIB, "actions", ACTION)
SRC = os.path.join(ADIR, "pose.mp4")
TMP = os.path.join(ADIR, "_poseframes")
BAK = os.path.join(ADIR, "pose_raw.mp4")

if not os.path.exists(SRC):
    print("缺 pose.mp4"); sys.exit(1)

if not os.path.exists(BAK):
    shutil.copy2(SRC, BAK)

shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(TMP)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", SRC,
                os.path.join(TMP, "%05d.png")], check=True)

files = sorted(glob.glob(os.path.join(TMP, "*.png")))
print(f"解出 {len(files)} 帧")

from PIL import Image  # noqa: E402

def blank(p):
    im = Image.open(p).convert("L")
    px = list(im.getdata())
    return sum(1 for v in px if v > 60) / len(px) < 0.005

prev = None
filled = []
for i, p in enumerate(files):
    if blank(p):
        if prev:
            shutil.copy2(prev, p)
            filled.append(i + 1)
        else:
            # 开头就是空白：往后找第一个有效帧
            for q in files[i + 1:]:
                if not blank(q):
                    shutil.copy2(q, p)
                    filled.append(i + 1)
                    break
    else:
        prev = p

print(f"回填 {len(filled)} 帧: {filled[:40]}{'...' if len(filled) > 40 else ''}")

out = SRC
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "24",
                "-i", os.path.join(TMP, "%05d.png"),
                "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", out], check=True)
shutil.rmtree(TMP, ignore_errors=True)

# 复查
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", out,
                "-vf", "select='not(mod(n,25))',scale=180:-1", "-vsync", "0",
                os.path.join(ADIR, "_chk_%03d.png")], check=True)
chk = sorted(glob.glob(os.path.join(ADIR, "_chk_*.png")))
left = sum(1 for p in chk if blank(p))
for p in chk:
    os.remove(p)
print(f"复查：抽样 {len(chk)} 帧，剩余空白 {left} 帧")
print("完成 →", out)
