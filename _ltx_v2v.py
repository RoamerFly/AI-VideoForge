# -*- coding: utf-8 -*-
"""LTX-2.5 V2V 对照试验：把「原始画面」当 IC-LoRA guide（而非骨架），验证动作贴合度上限。

对照对象：
    _ltx_control.py  = 骨架 guide（Union Control，结构被压缩成 18 个关节点）
    _ltx_v2v.py      = 原片画面 guide（整帧结构，几乎无信息损失）

用法：
    python _ltx_v2v.py [宽] [高] [帧数] [步数] [guide视频] [输出前缀] [LDF] [guide强度] [LoRA强度]

注意：guide 必须是「与目标画幅一致、帧数=8k+1」的片段。
"""
import sys
import time

sys.path.insert(0, "app")
import core

W = int(sys.argv[1]) if len(sys.argv) > 1 else 576
H = int(sys.argv[2]) if len(sys.argv) > 2 else 1024
FRAMES = int(sys.argv[3]) if len(sys.argv) > 3 else 121
STEPS = int(sys.argv[4]) if len(sys.argv) > 4 else 8
GUIDE = sys.argv[5] if len(sys.argv) > 5 else "h3studio/ltx25/src_121.mp4"
PREFIX = sys.argv[6] if len(sys.argv) > 6 else "H3影栈/11_LTXv2v"
LDF = float(sys.argv[7]) if len(sys.argv) > 7 else 0.0
GSTR = float(sys.argv[8]) if len(sys.argv) > 8 else 1.0
LSTR = float(sys.argv[9]) if len(sys.argv) > 9 else 1.0

REF_IMG = "h3studio/h3studio_1794620746_9fcc71________01______.png"

SIGMAS = {
    8: "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0",
}

PROMPT = ("A beautiful young woman with long straight black hair and a short side braid, "
          "wearing a red chinese halter qipao mini dress with black trim, a silver buckle belt, "
          "blue tassels, maroon wrist guards and maroon boots, "
          "dancing gracefully, full body shot, seamless white studio backdrop, white floor, "
          "plain background, natural studio lighting, sharp details, cinematic")

NEG = ("blurry, low quality, distorted face, extra limbs, deformed hands, text, watermark, "
       "cluttered background, furniture, plants, wooden floor")

api = {
    "1": {"class_type": "UNETLoader", "inputs": {
        "unet_name": "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors",
        "weight_dtype": "default"}},
    "2": {"class_type": "LTXICLoRALoaderModelOnly", "inputs": {
        "model": ["1", 0],
        "lora_name": "ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors",
        "strength_model": LSTR}},
    "3": {"class_type": "CLIPLoader", "inputs": {
        "clip_name": "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors",
        "type": "ltxv", "device": "default"}},
    "4": {"class_type": "VAELoader", "inputs": {
        "vae_name": "ltx-2.5-video-vae-conv-bf16.safetensors"}},
    "5": {"class_type": "VAELoader", "inputs": {
        "vae_name": "ltx-2.5-audio-vae-bf16.safetensors"}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": PROMPT, "clip": ["3", 0]}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["3", 0]}},
    "8": {"class_type": "LTXVConditioning", "inputs": {
        "positive": ["6", 0], "negative": ["7", 0], "frame_rate": 24.0}},
    "9": {"class_type": "LoadImage", "inputs": {"image": REF_IMG}},
    "10": {"class_type": "EmptyLTXVLatentVideo", "inputs": {
        "width": W, "height": H, "length": FRAMES, "batch_size": 1}},
    "11": {"class_type": "LTXVImgToVideoInplace", "inputs": {
        "vae": ["4", 0], "image": ["9", 0], "latent": ["10", 0],
        "strength": 1.0, "bypass": False}},
    "12": {"class_type": "LoadVideo", "inputs": {"file": GUIDE}},
    "13": {"class_type": "GetVideoComponents", "inputs": {"video": ["12", 0]}},
    "14": {"class_type": "LTXAddVideoICLoRAGuide", "inputs": {
        "positive": ["8", 0], "negative": ["8", 1], "vae": ["4", 0],
        "latent": ["11", 0], "image": ["13", 0],
        "frame_idx": 0, "strength": GSTR,
        "latent_downscale_factor": ["2", 1] if LDF <= 0 else LDF,
        "crop": "disabled", "use_tiled_encode": False,
        "tile_size": 256, "tile_overlap": 64}},
    "15": {"class_type": "LTXVEmptyLatentAudio", "inputs": {
        "frames_number": FRAMES, "frame_rate": 24.0, "batch_size": 1,
        "audio_vae": ["5", 0]}},
    "16": {"class_type": "LTXVConcatAVLatent", "inputs": {
        "video_latent": ["14", 2], "audio_latent": ["15", 0]}},
    "17": {"class_type": "RandomNoise", "inputs": {
        "noise_seed": 42, "control_after_generate": "fixed"}},
    "18": {"class_type": "CFGGuider", "inputs": {
        "model": ["2", 0], "positive": ["14", 0], "negative": ["14", 1], "cfg": 1.0}},
    "19": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler_ancestral"}},
    "20": {"class_type": "ManualSigmas", "inputs": {"sigmas": SIGMAS.get(STEPS, SIGMAS[8])}},
    "21": {"class_type": "SamplerCustomAdvanced", "inputs": {
        "noise": ["17", 0], "guider": ["18", 0], "sampler": ["19", 0],
        "sigmas": ["20", 0], "latent_image": ["16", 0]}},
    "22": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["21", 0]}},
    "27": {"class_type": "LTXVCropGuides", "inputs": {
        "positive": ["14", 0], "negative": ["14", 1], "latent": ["22", 0]}},
    "23": {"class_type": "VAEDecodeTiled", "inputs": {
        "samples": ["27", 2], "vae": ["4", 0],
        "tile_size": 512, "overlap": 64, "temporal_size": 64, "temporal_overlap": 8}},
    "24": {"class_type": "LTXVAudioVAEDecode", "inputs": {
        "samples": ["22", 1], "audio_vae": ["5", 0]}},
    "25": {"class_type": "CreateVideo", "inputs": {
        "images": ["23", 0], "audio": ["24", 0], "fps": 24}},
    "26": {"class_type": "SaveVideo", "inputs": {
        "video": ["25", 0], "filename_prefix": PREFIX,
        "format": "auto", "codec": "auto"}},
}

print(f"LTX V2V {W}x{H} / {FRAMES} 帧 / {STEPS} 步 / guide={GUIDE} / lora强度={LSTR} / guide强度={GSTR}", flush=True)
pid = core.submit(api)
print("提交", pid, flush=True)

t0 = time.time()
while True:
    h = core.history(pid)
    if h and ((h.get("status") or {}).get("completed") or h.get("outputs")):
        print("完成", round(time.time() - t0), "s", flush=True)
        print("输出:", core.collect_outputs(h), flush=True)
        break
    st = (h or {}).get("status") or {}
    if st.get("status_str") == "error":
        for m in st.get("messages", []):
            if m and m[0] == "execution_error":
                print("失败:", (m[1] or {}).get("exception_message", "")[:900], flush=True)
        sys.exit(1)
    el = int(time.time() - t0)
    if el % 30 < 6:
        print(f"  ...{el}s", flush=True)
    time.sleep(5)
