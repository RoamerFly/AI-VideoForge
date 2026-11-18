"""Join direct H3 outputs without compositing and verify full source audio."""
import argparse
import hashlib
from pathlib import Path
import subprocess

from generate_full import DirectGeneration, OUT, SOURCE
from pose_pipeline import FPS, choose_cuts, timeline, write_json

FINAL = OUT / "宗师雏田_申鹤扭身舞_MiniMaxH3_原灰棚_34秒.mp4"

def audio_hash(job, path):
    return job.ff("-i", path, "-map", "0:a:0", "-c:a", "copy",
                  "-f", "hash", "-hash", "sha256", "-").strip()

def join(job, override):
    segments = job.m["segments"]
    count = job.m["total_frames"]
    files = [OUT / "raw" / f"{s['index']:03d}.mp4" for s in segments]
    if not all(job.valid_video(path) for path in files):
        raise RuntimeError("One or more 73-frame segments are incomplete.")
    cuts, seams = choose_cuts(segments, files)
    for position, frame in override.items():
        start = segments[position + 1]["start"]
        last = segments[position]["start"] + 73
        if not start <= frame < last:
            raise ValueError(f"Cut {position + 1} falls outside overlap.")
        cuts[position] = frame
        seams[position] = {"frame": frame, "second": frame / FPS, "manual": True}
    mapping = list(timeline(segments, cuts, count))
    assert [f for f, _, _ in mapping] == list(range(count))
    write_json(OUT / "接缝.json", seams)
    write_json(OUT / "逐帧时间线.json", mapping)
    args = ["-filter_complex_threads", "2"]
    filt = []
    for index, (path, seg, begin, end) in enumerate(zip(files, segments, [0] + cuts, cuts + [count])):
        args.extend(["-threads", "2", "-i", path])
        start, stop = begin - seg["start"], end - seg["start"]
        filt.append(f"[{index}:v]trim=start_frame={start}:end_frame={stop},setpts=PTS-STARTPTS,setsar=1[v{index}]")
    filt.append("".join(f"[v{i}]" for i in range(len(files))) + f"concat=n={len(files)}:v=1:a=0[v]")
    video_only = OUT / "过程_拼接视频.mp4"
    job.update("按原动作时间线拼接", 95)
    job.ff(*args, "-filter_complex", ";".join(filt), "-map", "[v]", "-an",
           "-r", FPS, "-c:v", "libx264", "-threads", 4, "-crf", 16, "-pix_fmt", "yuv420p",
           "-frames:v", count, video_only)
    result = FINAL.with_suffix(".tmp.mp4")
    job.ff("-i", video_only, "-i", SOURCE, "-map", "0:v:0", "-map", "1:a:0",
           "-c", "copy", "-movflags", "+faststart", result)
    meta = job.probe(result, True)
    video = next(s for s in meta["streams"] if s["codec_type"] == "video")
    audio = next(s for s in meta["streams"] if s["codec_type"] == "audio")
    assert int(video["nb_read_frames"]) == count
    assert video["avg_frame_rate"] == "24/1"
    assert abs(float(video["duration"]) - job.m["duration_source"]) < 1 / FPS
    assert float(video["start_time"]) == float(audio["start_time"]) == 0
    sound = audio_hash(job, result)
    assert sound == audio_hash(job, SOURCE), "AAC packet data differs from source."
    result.replace(FINAL)
    report = {
        "file": str(FINAL), "video_seconds": float(video["duration"]),
        "source_seconds": job.m["duration_source"], "frames": count, "fps": FPS,
        "resolution": [video["width"], video["height"]], "cuts": len(seams),
        "audio_codec": audio["codec_name"], "audio_seconds": float(audio["duration"]),
        "audio_packet_sha256": sound.split("=")[-1], "audio_packets_match_source": True,
        "video_start": float(video["start_time"]), "audio_start": float(audio["start_time"]),
        "file_sha256": hashlib.sha256(FINAL.read_bytes()).hexdigest(),
        "pipeline": "Ref2VA + AddGuide + Character Swap LoRA",
    }
    write_json(OUT / "完整性核验.json", report)
    job.m.update(status="assembled", final=str(FINAL), seams=seams)
    job.save()
    job.update("已拼接，等待画面核查", 98)
    print(f"Decoded {count} frames. Original AAC verified. Saved {FINAL}", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cut", action="append", default=[], metavar="SEAM:FRAME")
    args = parser.parse_args()
    override = {}
    for value in args.cut:
        seam, frame = map(int, value.split(":"))
        override[seam - 1] = frame
    join(DirectGeneration(), override)
