import json
from pathlib import Path
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

directory = Path(__file__).resolve().parent
assets = Path(r"E:\Agent\projects\freetime_AI_Draw\AI_Draw\ComfyUI-aki\ComfyUI-aki-v3\ComfyUI\input\h3_image_motion_20261118")
video = Path(sys.argv[1]) if len(sys.argv) > 1 else None
indices = (0, 8, 18, 30, 42, 54, 72)

def load_frames(path):
    capture = cv2.VideoCapture(str(path))
    frames = []
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    finally:
        capture.release()
    assert len(frames) >= 73, (path, len(frames))
    return frames

photo = Image.open(assets / "character-first-frame.png").convert("RGB")
pose_source = assets / "pose-first-73.mp4"
driver_label = "Pose"
if video:
    api = json.loads(video.with_suffix(".json").read_text(encoding="utf-8"))
    pose_source = assets.parent / api["150"]["inputs"]["file"]
    if any(node["class_type"] == "MiniMaxH3AddGuide" for node in api.values()):
        driver_label = "Source video"
pose = load_frames(pose_source)
out = load_frames(video) if video else None
rows = 3 if out else 2
cw, ch = 180, 320
board = Image.new("RGB", ((len(indices) + 1) * cw, rows * (ch + 24)), (25, 28, 32))
draw = ImageDraw.Draw(board)

def tile(image, x, y, label):
    board.paste(ImageOps.contain(image, (cw, ch), Image.Resampling.LANCZOS), (x * cw, y * (ch + 24) + 24))
    draw.text((x * cw + 8, y * (ch + 24) + 5), label, fill="white")

for row in range(rows):
    if row == 2:
        ref_for_crop = photo.resize((576, 1024), Image.Resampling.LANCZOS)
        tile(ref_for_crop.crop((185, 35, 410, 280)), 0, row, "Original face region")
    else:
        tile(photo, 0, row, "Original photo")
for x, index in enumerate(indices, 1):
    tile(Image.fromarray(pose[index]), x, 0, f"{driver_label} {index / 24:.2f}s")
    if out:
        tile(Image.fromarray(out[index]), x, 1, f"Output {index / 24:.2f}s")
        # Fixed central crop covering expected head travel. No sharpening.
        tile(Image.fromarray(out[index]).crop((185, 35, 410, 280)), x, 2, f"Face region {index / 24:.2f}s")
    else:
        tile(Image.fromarray(pose[index]).crop((100, 40, 490, 740)), x, 1, f"Pose detail {index / 24:.2f}s")
board.save(video.with_suffix(".jpg") if video else directory / "input-review.jpg", quality=93)

if out:
    h, w = out[0].shape[:2]
    ref = np.asarray(photo.resize((w, h), Image.Resampling.LANCZOS)).astype(np.float32)
    side = np.s_[:, np.r_[8:64, w-64:w-8], :]
    differences = [float(np.abs(frame[side].astype(np.float32) - ref[side]).mean()) for frame in out]
    print(f"Decoded {len(out)} frames, {w}x{h}. Side background mean absolute RGB difference: "
          f"median={np.median(differences):.2f}/255 max={max(differences):.2f}/255.")
