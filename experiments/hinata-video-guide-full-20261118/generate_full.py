"""Generate the approved H3 direct video-guide recipe across the source timeline."""
import copy
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import time
import subprocess
import cv2
import numpy as np
import psutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))
import core
from pose_pipeline import FPS, LENGTH, Pipeline, outputs, plan_frames, write_json

core.CFG = dict(core.CFG, port=8193, comfy_root=core.DEFAULT_CONFIG["comfy_root"],
                ffmpeg=r"E:\A-Environment\FFmpeg\bin\ffmpeg.exe")
SOURCE = ROOT.parent / "AI视频模板" / "申鹤站立扭身舞.mp4"
BASE = ROOT / "experiments/image-motion-original-background-20261118"
OUT = ROOT / "experiments/hinata-video-guide-full-20261118"
STATE = OUT / "流程状态.json"
STAGE = Path(core.comfy_input()) / "h3_image_motion_20261118"
API = BASE / "宗师雏田_MiniMaxH3视频引导_API.json"
OPENING = API.with_suffix(".mp4")

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def digest(path):
    with path.open("rb") as stream:
        h = hashlib.sha256()
        for block in iter(lambda: stream.read(2 ** 20), b""):
            h.update(block)
    return h.hexdigest()

class ResumedServer:
    def __init__(self, process):
        self.process = process
        self.pid = process.pid

    def poll(self):
        return None if self.process.is_running() else 1

    def wait(self, timeout):
        return self.process.wait(timeout)

class DirectGeneration(Pipeline):
    def __init__(self):
        self.c, self.tid, self.work, self.state_path = core, "direct-full", OUT, STATE
        self.m = read_json(STATE) if STATE.exists() else {}
        self.status_path = OUT / "当前进度.json"
        for directory in ("raw", "api", "results", "review"):
            (OUT / directory).mkdir(parents=True, exist_ok=True)

    def canceled(self):
        if core._proc and core._proc.poll() is not None:
            raise RuntimeError(f"Experiment ComfyUI exited ({core._proc.returncode})")

    def update(self, stage, progress):
        self.canceled()
        write_json(self.status_path, {
            "stage": stage, "progress": round(progress, 1), "updated": time.time(),
            "done": sum(bool(s.get("ready")) for s in self.m.get("segments", [])),
            "total": len(self.m.get("segments", [])), "prompt": core.WATCHER.prompt_id,
        })

    def prepare(self):
        self.graph = read_json(API)
        meta = self.probe(SOURCE)
        duration = float(meta["format"]["duration"])
        signature = {
            "source": digest(SOURCE), "api": digest(API),
            "body": digest(STAGE / "character-first-frame.png"),
            "identity": digest(STAGE / "character-identity.png"),
            "approved_opening": digest(OPENING),
        }
        total = math.ceil(duration * FPS)
        if self.m:
            if self.m["signature"] != signature or self.m["total_frames"] != total:
                raise ValueError("Source or reference differs from the saved task.")
        else:
            self.m = {"signature": signature, "duration_source": duration, "total_frames": total,
                      "segments": plan_frames(total), "status": "prepared"}
        last = self.m["segments"][-1]
        if last["valid"] < LENGTH and not last.get("generation_job") and not last.get("guide-mask_job"):
            # Pull the last window backward to include real motion through the final frame.
            last.update(start=max(0,total-LENGTH), valid=min(total,LENGTH))
        if not self.valid_video(OPENING):
            raise RuntimeError("Approved opening preview is missing frames.")
        self.save()

    def stage_input(self, segment):
        index, start = segment["index"], segment["start"]
        name = f"full-direct-20261118-seg-{index:03d}.mp4"
        target = STAGE / name
        if not target.exists() or not self.valid_video(target):
            temp = target.with_suffix(".tmp.mp4")
            # Decode from the source time base on each cut, then sample the 24 fps guide.
            self.ff("-ss", f"{start / FPS:.9f}", "-i", SOURCE,
                    "-map", "0:v:0", "-map", "0:a:0",
                    "-vf", "fps=24,scale=576:1024:flags=lanczos,setsar=1,tpad=stop_mode=clone:stop_duration=4",
                    "-af", "apad=pad_dur=4", "-frames:v", LENGTH, "-t", LENGTH / FPS,
                    "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", temp)
            if not self.valid_video(temp):
                raise RuntimeError(f"Guide for segment {index + 1} is incomplete.")
            temp.replace(target)
        return f"{STAGE.name}/{name}"

    def connect(self):
        if core.online():
            pid = self.m.get("server_pid")
            if not pid or core._port_pid(core.CFG["port"]) != pid:
                raise RuntimeError("Experiment port belongs to another server.")
            process = psutil.Process(pid)
            args = process.cmdline()
            if not any(Path(arg).name == "main.py" for arg in args) or str(core.CFG["port"]) not in args:
                raise RuntimeError("Saved server PID does not match the experiment.")
            core._proc = ResumedServer(process)
        elif not core.start_comfy(block=True).get("online") or not core._proc:
            raise RuntimeError("Dedicated ComfyUI could not start.")
        self.m.update(server_pid=core._proc.pid, port=core.CFG["port"])
        self.save()
        core.WATCHER.start()

    def clean_guide(self, segment, filename):
        """Suppress stage details in the guidance input while keeping all source motion."""
        number = segment["index"]
        guide = STAGE.parent / filename
        target = guide.with_stem(guide.stem + "-subject-guide")
        if self.valid_video(target):
            return target.relative_to(STAGE.parent).as_posix()
        graph = core.load_template("05m")
        graph["1"]["inputs"]["file"] = filename
        graph["9"]["inputs"]["filename_prefix"] = f"video/H3_HinataDirectFull/guide-mask-{number:03d}"
        self.update(f"提取第 {number+1} 段动作主体", 93 * number / len(self.m["segments"]))
        result = self.execute(graph, segment, "guide-mask", 93 * number / len(self.m["segments"]), 0)
        paths = sorted(outputs(core, result, ".png"))
        if len(paths) != LENGTH:
            raise RuntimeError(f"Motion guide requires {LENGTH} masks, got {len(paths)}.")
        reference = cv2.imdecode(np.fromfile(STAGE / "character-first-frame.png",dtype=np.uint8),cv2.IMREAD_COLOR)
        reference = cv2.resize(reference,(576,1024),interpolation=cv2.INTER_AREA)
        edges = np.concatenate((reference[:, :70], reference[:, -70:]),axis=1)
        gray = np.median(edges,axis=1).astype(np.float32).reshape(1024,1,3)
        gray = cv2.GaussianBlur(gray,(1,41),0)
        reader = cv2.VideoCapture(str(guide))
        silent = OUT / f"引导处理-{number:03d}.mp4"
        with (OUT / f"引导处理-{number:03d}.log").open("wb") as log:
            process = subprocess.Popen([core.ffmpeg_exe(),"-hide_banner","-loglevel","error",
                "-y","-f","rawvideo","-pixel_format","bgr24","-video_size","576x1024","-framerate","24",
                "-i","pipe:0","-an","-c:v","libx264","-crf","16","-pix_fmt","yuv420p",str(silent)],
                stdin=subprocess.PIPE,stderr=log,creationflags=0x08000000)
            try:
                for path in paths:
                    ok, frame = reader.read()
                    mask = cv2.imdecode(np.fromfile(path,dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
                    if not ok or mask is None or not 0.025 < float((mask > 127).mean()) < 0.62:
                        raise RuntimeError(f"Invalid subject guide mask: {path}")
                    alpha = cv2.dilate(mask,np.ones((5,5),np.uint8))
                    alpha = cv2.GaussianBlur(alpha,(5,5),0).astype(np.float32)[...,None] / 255
                    process.stdin.write(np.rint(frame*alpha+gray*(1-alpha)).astype(np.uint8).tobytes())
            finally:
                reader.release()
                process.stdin.close()
                process.wait()
        if process.returncode or not self.valid_video(silent):
            raise RuntimeError("Subject guide encoding is incomplete.")
        temp = target.with_suffix(".tmp.mp4")
        self.ff("-i",silent,"-i",guide,"-map","0:v:0","-map","1:a:0","-c","copy",temp)
        if not self.valid_video(temp):
            raise RuntimeError("Subject guide mux is incomplete.")
        temp.replace(target)
        return target.relative_to(STAGE.parent).as_posix()

    def generate(self, selection=None, clean=False, regenerate=False):
        self.prepare()
        segments = self.m["segments"]
        first = OUT / "raw/000.mp4"
        if not first.exists():
            shutil.copy2(OPENING, first)
        if not self.valid_video(first) or digest(first) != self.m["signature"]["approved_opening"]:
            raise RuntimeError("Saved opening no longer matches the approved preview.")
        segments[0].update(ready=True, reused_approved=True)
        if regenerate:
            if not selection:
                raise ValueError("Select segments before regenerating.")
            baseline = OUT / "baseline"
            baseline.mkdir(exist_ok=True)
            for i in sorted(selection):
                if not 0 < i < len(segments):
                    raise ValueError(f"Invalid repair segment {i+1}.")
                dest = OUT / "raw" / f"{i:03d}.mp4"
                if dest.exists():
                    dest.replace(baseline / f"{i:03d}-{int(time.time())}.mp4")
                if "generation_job" in segments[i]:
                    segments[i].setdefault("earlier_jobs", []).append(segments[i].pop("generation_job"))
                segments[i]["ready"] = False
        pending = [s for s in segments if (selection is None or s["index"] in selection)
                   and s["index"] and not self.valid_video(OUT / "raw" / f"{s['index']:03d}.mp4")]
        self.m.update(status="generating")
        self.save()
        if pending:
            self.connect()
        for segment in segments:
            i = segment["index"]
            dest = OUT / "raw" / f"{i:03d}.mp4"
            if not self.valid_video(dest):
                if segment not in pending:
                    continue
                graph = copy.deepcopy(self.graph)
                filename = self.stage_input(segment)
                existing_api = OUT / "api" / f"generation-{i:03d}.json"
                recovering = bool((segment.get("generation_job") or {}).get("pid"))
                if recovering and existing_api.exists():
                    filename = read_json(existing_api)["150"]["inputs"]["file"]
                elif clean:
                    filename = self.clean_guide(segment,filename)
                graph["150"]["inputs"]["file"] = filename
                segment["guide_file"] = filename
                graph["92"]["inputs"]["filename_prefix"] = f"video/H3_HinataDirectFull/seg-{i:03d}"
                if segment.get("repair_prompt"):
                    graph["138"]["inputs"]["value"] += " " + segment["repair_prompt"]
                    graph["129"]["inputs"]["noise_seed"] = segment["repair_seed"]
                self.update(f"提交片段 {i + 1}/{len(segments)}", 93 * i / len(segments))
                result = self.execute(graph, segment, "generation", 93 * i / len(segments), 93 / len(segments))
                files = outputs(core, result, ".mp4")
                if len(files) != 1:
                    raise RuntimeError(f"Missing unique output from segment {i + 1}.")
                temp = dest.with_suffix(".tmp.mp4")
                shutil.copy2(files[0], temp)
                if not self.valid_video(temp):
                    raise RuntimeError(f"Segment {i + 1} has incomplete frames.")
                temp.replace(dest)
            segment["ready"] = True
            self.save()
        if all(s.get("ready") for s in segments):
            self.m["status"] = "generated"
            self.save()
            self.update("分段完成，准备拼接", 94)

    def prepare_guides(self, selection):
        self.prepare()
        self.connect()
        for segment in self.m["segments"][1:]:
            if selection is not None and segment["index"] not in selection:
                continue
            filename = self.stage_input(segment)
            segment["sanitized_guide"] = self.clean_guide(segment, filename)
            self.save()
        self.update("动作引导预处理完成", 20)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("segments", type=int, nargs="*")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--redo", action="store_true")
    parser.add_argument("--prepare-guides", action="store_true")
    parser.add_argument("--keep-server", action="store_true")
    args = parser.parse_args()
    job = DirectGeneration()
    try:
        selection = {s-1 for s in args.segments} or None
        if args.prepare_guides:
            job.prepare_guides(selection)
        else:
            job.generate(selection,args.clean,args.redo)
    except Exception as exc:
        job.m.update(status="interrupted", error=str(exc))
        job.save()
        raise
    finally:
        if not args.keep_server and core._proc and core._proc.poll() is None:
            try:
                q = core.http_json("/queue", timeout=12)
                if not q["queue_running"] and not q["queue_pending"]:
                    core.stop_owned()
            except OSError:
                pass

if __name__ == "__main__":
    main()
