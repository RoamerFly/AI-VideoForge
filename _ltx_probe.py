# -*- coding: utf-8 -*-
"""LTX-2.5 最小可行性探针：纯文生视频，只验证 22B int8 在 16GB 卡上能否跑、速度多少。

不接 Union Control、不接参考视频——那些等这里跑通再加。
用法：
    python _ltx_probe.py [宽] [高] [帧数] [步数]
    python _ltx_probe.py 576 1024 33 8
"""
import json
import sys
import time

sys.path.insert(0, "app")
import core

W = int(sys.argv[1]) if len(sys.argv) > 1 else 576
H = int(sys.argv[2]) if len(sys.argv) > 2 else 1024
FRAMES = int(sys.argv[3]) if len(sys.argv) > 3 else 33
STEPS = int(sys.argv[4]) if len(sys.argv) > 4 else 8

SIGMAS_8 = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"

PROMPT = ("A young woman with long straight black hair, wearing a red chinese halter dress, "
          "dancing in a clean white studio, full body shot, natural lighting, sharp details")

api = {
    "1": {"class_type": "UNETLoader", "inputs": {
        "unet_name": "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors",
        "weight_dtype": "default"}},
    "2": {"class_type": "CLIPLoader", "inputs": {
        "clip_name": "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors",
        "type": "ltxv", "device": "default"}},
    "3": {"class_type": "VAELoader", "inputs": {
        "vae_name": "ltx-2.5-video-vae-conv-bf16.safetensors"}},
    "4": {"class_type": "VAELoader", "inputs": {
        "vae_name": "ltx-2.5-audio-vae-bf16.safetensors"}},
    "5": {"class_type": "CLIPTextEncode", "inputs": {
        "text": PROMPT, "clip": ["2", 0]}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {
        "text": "", "clip": ["2", 0]}},
    "7": {"class_type": "LTXVConditioning", "inputs": {
        "positive": ["5", 0], "negative": ["6", 0], "frame_rate": 24.0}},
    "8": {"class_type": "EmptyLTXVLatentVideo", "inputs": {
        "width": W, "height": H, "length": FRAMES, "batch_size": 1}},
    "9": {"class_type": "LTXVEmptyLatentAudio", "inputs": {
        "frames_number": FRAMES, "frame_rate": 24.0, "batch_size": 1,
        "audio_vae": ["4", 0]}},
    "10": {"class_type": "LTXVConcatAVLatent", "inputs": {
        "video_latent": ["8", 0], "audio_latent": ["9", 0]}},
    "11": {"class_type": "RandomNoise", "inputs": {
        "noise_seed": 42, "control_after_generate": "fixed"}},
    "12": {"class_type": "CFGGuider", "inputs": {
        "model": ["1", 0], "positive": ["7", 0], "negative": ["7", 1], "cfg": 1.0}},
    "13": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler_ancestral"}},
    "14": {"class_type": "ManualSigmas", "inputs": {"sigmas": SIGMAS_8}},
    "15": {"class_type": "SamplerCustomAdvanced", "inputs": {
        "noise": ["11", 0], "guider": ["12", 0], "sampler": ["13", 0],
        "sigmas": ["14", 0], "latent_image": ["10", 0]}},
    "16": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["15", 0]}},
    "17": {"class_type": "VAEDecodeTiled", "inputs": {
        "samples": ["16", 0], "vae": ["3", 0],
        "tile_size": 512, "overlap": 64, "temporal_size": 64, "temporal_overlap": 8}},
    "18": {"class_type": "LTXVAudioVAEDecode", "inputs": {
        "samples": ["16", 1], "audio_vae": ["4", 0]}},
    "19": {"class_type": "CreateVideo", "inputs": {
        "images": ["17", 0], "audio": ["18", 0], "fps": 24}},
    "20": {"class_type": "SaveVideo", "inputs": {
        "video": ["19", 0], "filename_prefix": "H3影栈/09_LTXprobe",
        "format": "auto", "codec": "auto"}},
}

print(f"探针 {W}x{H} / {FRAMES} 帧 / {STEPS} 步", flush=True)
pid = core.submit(api)
print("提交", pid, flush=True)

t0 = time.time()
while True:
    h = core.history(pid)
    if h and ((h.get("status") or {}).get("completed") or h.get("outputs")):
        outs = core.collect_outputs(h)
        print("完成", round(time.time() - t0), "s")
        print("输出:", outs)
        break
    if h and (h.get("status") or {}).get("status_str") == "error":
        for m in h["status"].get("messages", []):
            if m and m[0] == "execution_error":
                print("失败:", (m[1] or {}).get("exception_message", "")[:800])
        sys.exit(1)
    time.sleep(5)
