from pathlib import Path
import subprocess
from PIL import Image, ImageDraw

root = Path(r"E:\\Agent\\projects\\freetime_AI_Video_Comfyui")
video = Path(r"E:\\Agent\\projects\\freetime_AI_Draw\\AI_Draw\\ComfyUI-aki\\ComfyUI-aki-v3\\ComfyUI\\output\\H3影栈\\夏日黑土_两阶段_720p.mp4")
frame_dir = root / "experiments/natural-language-hutao-kurotsuchi-20261118/finalframes"
frame_dir.mkdir(parents=True, exist_ok=True)
for p in frame_dir.glob("*.jpg"):
    p.unlink()
ffmpeg = r"E:\\A-Environment\\FFmpeg\\bin\\ffmpeg.exe"
subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video), "-vf", "fps=1/2,scale=240:-1", str(frame_dir / "frame-%02d.jpg")], check=True)
frames = sorted(frame_dir.glob("*.jpg"))
images = [Image.open(p).convert("RGB") for p in frames]
out = Image.new("RGB", (sum(im.width for im in images), max(im.height for im in images)), "white")
x = 0
for i, im in enumerate(images):
    out.paste(im, (x, 0))
    ImageDraw.Draw(out).text((x + 4, 4), f"{i * 2}s", fill="red")
    x += im.width
out.save(frame_dir.parent / "final-720p-contact.jpg", quality=92)
