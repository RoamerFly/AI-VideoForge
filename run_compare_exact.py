# -*- coding: utf-8 -*-
"""Run a reproducible 2-3s SCAIL-2 vs MiniMax H3 comparison for the requested assets.

Usage (from this directory):
  E:\A-Environment\Python\Python310\python.exe run_compare_exact.py
  E:\A-Environment\Python\Python310\python.exe run_compare_exact.py --background E:\path\bg.png

The primary character image is always the requested image. A supplied background image is
passed as an optional second H3 reference image; SCAIL-2 baseline stays in Replacement mode
so the comparison isolates character replacement. Background compositing is recorded as a
separate follow-up step rather than silently changing the baseline.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "app"))
import core  # noqa: E402

SRC = Path(r"E:\Agent\projects\AI视频模板\申鹤站立扭身舞.mp4")
CHAR = Path(r"E:\Agent\projects\freetime_AI_Draw\角色工坊库\角色库\宗师雏田\图集\通用姿势_单手抬起招呼_宗师雏田_池塘廊桥庭园_池塘廊桥庭园_001.png")
COMFY_INPUT = Path(core.comfy_input())
COMFY_OUTPUT = Path(core.comfy_output())
RUN_TAG = "compare_exact_20261115_t16"
WORK = ROOT / "compare_exact_20261115"
INPUT_REL = Path("h3studio") / RUN_TAG
INPUT_DIR = COMFY_INPUT / INPUT_REL

# Choose a difficult but bounded segment: the source notes place side-turning at 16-22 s.
START_SEC = 16.0
SCAIL_FRAMES = 49       # 4n+1, 16fps ~= 3.06s
SCAIL_FPS = 16
H3_FRAMES = 73          # 17n+5, 24fps ~= 3.04s
H3_FPS = 24


def run(cmd: list[str]) -> None:
    print("$", " ".join(str(x) for x in cmd), flush=True)
    subprocess.run(cmd, check=True)


def ffmpeg_path() -> str:
    return core.ffmpeg_exe()


def stage_inputs(background: Path | None) -> dict[str, str]:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    if not SRC.exists():
        raise FileNotFoundError(SRC)
    if not CHAR.exists():
        raise FileNotFoundError(CHAR)

    target_rel = INPUT_REL / "target_character.png"
    target_abs = COMFY_INPUT / target_rel
    shutil.copy2(CHAR, target_abs)

    scail_abs = INPUT_DIR / "scail_src_16fps_512x896.mp4"
    h3_abs = INPUT_DIR / "h3_src_24fps_640x1120.mp4"
    ff = ffmpeg_path()
    run([ff, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{START_SEC:.6f}", "-i", str(SRC),
         "-vf", f"fps={SCAIL_FPS},scale=512:896:flags=lanczos", "-frames:v", str(SCAIL_FRAMES),
         "-an", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(scail_abs)])
    run([ff, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{START_SEC:.6f}", "-i", str(SRC),
         "-vf", f"fps={H3_FPS},scale=640:1120:flags=lanczos", "-frames:v", str(H3_FRAMES),
         "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
         "-shortest", str(h3_abs)])

    bg_rel = None
    if background:
        if not background.exists():
            raise FileNotFoundError(background)
        bg_name = "optional_background" + background.suffix.lower()
        bg_abs = INPUT_DIR / bg_name
        shutil.copy2(background, bg_abs)
        bg_rel = str(INPUT_REL / bg_name).replace("\\", "/")

    meta = {
        "source": str(SRC),
        "character": str(CHAR),
        "background": str(background) if background else None,
        "start_sec": START_SEC,
        "scail": {"input": str(INPUT_REL / scail_abs.name).replace("\\", "/"), "fps": SCAIL_FPS, "frames": SCAIL_FRAMES, "width": 512, "height": 896},
        "h3": {"input": str(INPUT_REL / h3_abs.name).replace("\\", "/"), "fps": H3_FPS, "frames": H3_FRAMES, "width": 640, "height": 1120},
    }
    (WORK / "inputs.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "target": str(target_rel).replace("\\", "/"),
        "scail_video": str(INPUT_REL / scail_abs.name).replace("\\", "/"),
        "h3_video": str(INPUT_REL / h3_abs.name).replace("\\", "/"),
        "background": bg_rel or "",
    }


def wait_prompt(pid: str, label: str) -> list[str]:
    started = time.time()
    last_report = 0.0
    while True:
        entry = core.history(pid)
        if entry:
            status = entry.get("status") or {}
            if status.get("status_str") == "error":
                raise RuntimeError(f"{label} failed: {json.dumps(status, ensure_ascii=False)[:3000]}")
            if status.get("completed") or entry.get("outputs"):
                files = [f for f in core.collect_outputs(entry) if f.startswith("H3影栈/")]
                if not files:
                    raise RuntimeError(f"{label} completed without H3影栈 output: {entry.keys()}")
                print(f"{label} done in {(time.time()-started)/60:.1f} min: {files}", flush=True)
                return files
        if time.time() - last_report > 60:
            q = core.queue_info()
            print(f"{label} running {(time.time()-started)/60:.1f} min; queue={q}", flush=True)
            last_report = time.time()
        time.sleep(8)


def save_api(name: str, api: dict) -> None:
    (WORK / f"{name}_api.json").write_text(json.dumps(api, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_outputs(label: str, files: list[str]) -> list[str]:
    out = []
    dst_dir = WORK / "outputs"
    dst_dir.mkdir(exist_ok=True)
    for f in files:
        src = COMFY_OUTPUT / f
        dst = dst_dir / f"{label}_{Path(f).name}"
        shutil.copy2(src, dst)
        out.append(str(dst))
    return out


def run_scail(paths: dict[str, str]) -> list[str]:
    prompt = ("A full-body young woman with long straight black hair, wearing the exact red and burgundy "
              "Chinese halter outfit, silver belt, red arm guards, blue ribbon details and red boots from "
              "the reference image. Preserve the driving video's body motion, turning timing, camera framing "
              "and full-body composition. Replace only the original person; keep the source studio background "
              "for this baseline. Natural lighting, sharp details, correct anatomy, consistent identity.")
    p = {
        "engine": "scail",
        "images": [paths["target"]],
        "char_count": 1,
        "video": paths["scail_video"],
        "prompt": prompt,
        "quality": "full body, smooth motion, no extra limbs, no duplicated person",
        "width": 512, "height": 896, "frames": SCAIL_FRAMES,
        "steps": 6, "seed": 20261115, "swap_str": 1.0,
        "tag": f"{RUN_TAG}_scail",
    }
    api = core.build_api("05", p)
    save_api("scail", api)
    print("Submitting SCAIL-2 Replacement", flush=True)
    pid = core.submit(api)
    print("SCAIL prompt_id", pid, flush=True)
    return copy_outputs("scail", wait_prompt(pid, "SCAIL-2"))


def run_h3(paths: dict[str, str]) -> list[str]:
    prompt = ("A full-body young woman with long straight black hair, wearing the exact red and burgundy "
              "Chinese halter outfit, silver belt, red arm guards, blue ribbon details and red boots from "
              "<Picture 1>. Preserve the source video's dance motion, turning timing, camera framing and "
              "full-body composition. Do not copy the original character's face, hair or clothes.")
    images = [paths["target"]]
    if paths.get("background"):
        images.append(paths["background"])
        prompt += " Use <Picture 2> only as an optional background and environment reference; keep the character identity from <Picture 1>."
    p = {
        "images": images,
        "char_count": 1,
        "video": paths["h3_video"],
        "width": 640, "height": 1120, "frames": H3_FRAMES,
        "steps": 20, "turbo": False, "swap_str": 1.0,
        "seed": 20261115, "tag": f"{RUN_TAG}_h3",
        "prompt": prompt,
        "quality": "full body, natural lighting, sharp details, correct anatomy, consistent identity",
    }
    api = core.build_api("04", p)
    save_api("h3", api)
    print("Submitting MiniMax H3 Ref2VA + Character Swap", flush=True)
    pid = core.submit(api)
    print("H3 prompt_id", pid, flush=True)
    return copy_outputs("h3", wait_prompt(pid, "MiniMax H3"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--background", type=Path, default=None, help="optional independent background image")
    ap.add_argument("--engine", choices=("both", "scail", "h3"), default="both")
    args = ap.parse_args()
    paths = stage_inputs(args.background)
    print(json.dumps(paths, ensure_ascii=False, indent=2), flush=True)
    results = {}
    if args.engine in ("both", "scail"):
        results["scail"] = run_scail(paths)
    if args.engine in ("both", "h3"):
        results["h3"] = run_h3(paths)
    (WORK / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
