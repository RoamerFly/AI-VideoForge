"""Create synchronized source/output review sheets and native face crops."""
import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from generate_full import DirectGeneration, OUT, SOURCE, STAGE, FPS
from stitch_full import FINAL

REVIEW = OUT / "review"
FONT = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 15)

def frames(path, indices):
    capture = cv2.VideoCapture(str(path))
    wanted = set(indices)
    result = {}
    try:
        for index in range(max(wanted) + 1):
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(f"Decoder stopped at {index}: {path}")
            if index in wanted:
                result[index] = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    finally:
        capture.release()
    return result

def board(panels, path, width, height, cols):
    canvas = Image.new("RGB", (width*cols, (height+25)*((len(panels)+cols-1)//cols)), "#1F252B")
    draw = ImageDraw.Draw(canvas)
    for index, (label, *images) in enumerate(panels):
        x, y = (index%cols)*width, (index//cols)*(height+25)
        draw.text((x+5, y+2), label, font=FONT, fill="white")
        tile_width = width // len(images)
        for col, image in enumerate(images):
            canvas.paste(image.resize((tile_width, height), Image.Resampling.LANCZOS),
                         (x+col*tile_width,y+25))
    canvas.save(path, quality=93)

def segment_reviews(job):
    for seg in job.m["segments"]:
        index = seg["index"]
        if not seg.get("ready"):
            continue
        path = REVIEW / f"片段-{index+1:02d}.jpg"
        raw = OUT / "raw" / f"{index:03d}.mp4"
        if path.exists() and path.stat().st_mtime >= raw.stat().st_mtime:
            continue
        guide = STAGE / (f"full-direct-20261118-seg-{index:03d}.mp4" if index else "driving-first-73.mp4")
        limit = seg["valid"] - 1
        indices = sorted(set([0, min(12,limit), min(30,limit), min(46,limit), min(61,limit), limit]))
        src, generated = frames(guide, indices), frames(raw, indices)
        panels = [(f"{(seg['start']+i)/FPS:.2f}s   原片 / H3", src[i], generated[i]) for i in indices]
        board(panels, path, 320, 284, 3)

def whole_review(job):
    full = job.m["total_frames"]
    source = OUT / "过程_源动作24fps.mp4"
    if not source.exists() or not job.valid_video(source, full):
        job.ff("-i", SOURCE, "-map", "0:v:0", "-an",
               "-vf", "fps=24,scale=576:1024:flags=lanczos,setsar=1,tpad=stop_mode=clone:stop_duration=0.1",
               "-frames:v", full, "-c:v", "libx264", "-crf", 16, "-pix_fmt", "yuv420p", source)
    samples = sorted(set(list(range(0,full,12)) + [full-1]))
    seams = [s["frame"] for s in job.m["seams"]]
    detail = sorted({index+k for index in seams for k in (-3,-1,0,2)})
    src = frames(source, samples+detail)
    gen = frames(FINAL, samples+detail)
    for group, size, prefix in ((samples, 12, "动作对照"), (detail, 12, "接缝对照")):
        for page, start in enumerate(range(0,len(group),size),1):
            subset = group[start:start+size]
            panels = [(f"{i/FPS:.2f}s  帧{i}  原片 / H3", src[i], gen[i]) for i in subset]
            board(panels, REVIEW / f"{prefix}-{page:02d}.jpg", 252, 224, 4)
    for page, start in enumerate(range(0,len(samples),20), 1):
        subset = samples[start:start+20]
        panels = [(f"{i/FPS:.2f}s  帧{i}", gen[i].crop((155,55,420,320))) for i in subset]
        board(panels, REVIEW / f"脸眼细节-{page:02d}.jpg", 192, 192, 5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--whole", action="store_true")
    args = parser.parse_args()
    job = DirectGeneration()
    segment_reviews(job)
    if args.whole:
        whole_review(job)
