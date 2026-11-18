import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

directory = Path(__file__).resolve().parent
assets = Path(r"E:\Agent\projects\freetime_AI_Draw\AI_Draw\ComfyUI-aki\ComfyUI-aki-v3\ComfyUI\input\h3_image_motion_20261118")
source = cv2.VideoCapture(str(assets / "pose-first-73.mp4"))
width, height = 576, 1024
# Align the source skeleton's initial eye area and ankle baseline to the photo.
# Use a single uniform scale and translation for every frame.
scale = (930 - 100) / (890 - 190)
offset_x = 289 - scale * 295
offset_y = 100 - scale * 190
transform = np.float32([[scale, 0, offset_x], [0, scale, offset_y]])
writer = cv2.VideoWriter(str(assets / "pose-aligned-73.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 24, (width, height))
assert writer.isOpened()
occupied = np.zeros((height, width), dtype=bool)
frames = 0
try:
    while True:
        ok, frame = source.read()
        if not ok:
            break
        aligned = cv2.warpAffine(frame, transform, (width, height))
        occupied |= aligned.max(axis=2) > 55
        writer.write(aligned)
        frames += 1
finally:
    source.release()
    writer.release()
assert frames == 73
ys, xs = np.where(occupied)
# Leave room around the entire movement envelope and reference silhouette.
# The outer area is conditioned on the existing photo through the inpaint input.
left = max(0, min(int(xs.min()) - 40, 120))
top = max(0, min(int(ys.min()) - 35, 8))
right = min(width, max(int(xs.max()) + 40, 455))
bottom = min(height, max(int(ys.max()) + 45, 1008))
mask = np.zeros((height, width), dtype=np.uint8)
mask[top:bottom, left:right] = 255
Image.fromarray(mask).save(assets / "motion-region.png")

api = json.loads((directory / "角色图动作驱动_保留原背景_API.json").read_text(encoding="utf-8"))
api["150"]["inputs"]["file"] = "h3_image_motion_20261118/pose-aligned-73.mp4"
api["92"]["inputs"]["filename_prefix"] += "-aligned"
api["136"]["inputs"]["prompt"] += " Keep the exposure, gray tone and subject scale stable as in the first frame. Follow the supplied arm, hip and ankle positions closely."
api["203"] = {"class_type": "LoadImage", "inputs": {"image": "h3_image_motion_20261118/motion-region.png"}}
api["204"] = {"class_type": "ImageToMask", "inputs": {"image": ["203", 0], "channel": "red"}}
api["202"]["inputs"].update(strength=1.35, mask=["204", 0], source_video=["137", 0])
(directory / "角色图动作驱动_骨架对齐_API.json").write_text(json.dumps(api, ensure_ascii=False, indent=2), encoding="utf-8")
(directory / "alignment.json").write_text(json.dumps({
    "scale": scale, "offset_x": offset_x, "offset_y": offset_y, "frames": frames,
    "editable_region_xyxy": [left, top, right, bottom], "control_strength": 1.35,
}, indent=2), encoding="utf-8")
print("Aligned", frames, "frames; editable region", (left, top, right, bottom))
