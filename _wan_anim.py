# -*- coding: utf-8 -*-
"""Wan-Animate 2 动作迁移：角色图 + 驱动视频 → 换人动画（16fps 原生）。"""
import sys, time
sys.path.insert(0, "app")
import core

W = int(sys.argv[1]) if len(sys.argv) > 1 else 480
H = int(sys.argv[2]) if len(sys.argv) > 2 else 832
LEN = int(sys.argv[3]) if len(sys.argv) > 3 else 81
STEPS = int(sys.argv[4]) if len(sys.argv) > 4 else 6

POS = ("a young woman with long black hair, red chinese halter dress, silver belt, red boots, "
       "clean white studio background, soft even lighting")
NEG = "blurry, low quality, distorted face, extra limbs, watermark, text, jitter"

api = {
  "1":  {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "Wan2.2-Animate-14B-Q4_K_S.gguf"}},
  "2":  {"class_type": "LoraLoaderModelOnly", "inputs": {
            "lora_name": "lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
            "strength_model": 1.0, "model": ["1", 0]}},
  "3":  {"class_type": "WanAnimate2Cache", "inputs": {"model": ["2", 0], "device": "cpu", "dtype": "default"}},
  "4":  {"class_type": "ModelSamplingSD3", "inputs": {"model": ["3", 0], "shift": 8.0}},
  "5":  {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_wan_native_fp8_tokenizer.safetensors",
                                                "type": "wan", "device": "default"}},
  "6":  {"class_type": "CLIPTextEncode", "inputs": {"text": POS, "clip": ["5", 0]}},
  "7":  {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["5", 0]}},
  "8":  {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "clip_vision_h.safetensors"}},
  "9":  {"class_type": "LoadImage", "inputs": {"image": "h3studio/pose_test/hinata.png"}},
  "10": {"class_type": "CLIPVisionEncode", "inputs": {"clip_vision": ["8", 0], "image": ["9", 0], "crop": "none"}},
  "11": {"class_type": "LoadVideo", "inputs": {"file": "h3studio/pose_test/shenhe_81f_16fps.mp4"}},
  "12": {"class_type": "GetVideoComponents", "inputs": {"video": ["11", 0]}},
  "13": {"class_type": "VAELoader", "inputs": {"vae_name": "Wan2_1_VAE_bf16.safetensors"}},
  "14": {"class_type": "WanAnimate2ToVideo", "inputs": {
            "positive": ["6", 0], "negative": ["7", 0], "vae": ["13", 0],
            "width": W, "height": H, "length": LEN, "batch_size": 1,
            "video_frame_offset": 0, "pose_strength": 1.0,
            "pose_start_percent": 0.0, "pose_end_percent": 1.0,
            "reference_image_strength": 1.0,
            "reference_image": ["9", 0], "pose_video": ["12", 0], "clip_vision_output": ["10", 0]}},
  "15": {"class_type": "BasicGuider", "inputs": {"model": ["4", 0], "conditioning": ["14", 0]}},
  "16": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "lcm"}},
  "17": {"class_type": "BasicScheduler", "inputs": {"model": ["4", 0], "scheduler": "simple",
                                                    "steps": STEPS, "denoise": 1.0}},
  "18": {"class_type": "RandomNoise", "inputs": {"noise_seed": 20261114}},
  "19": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["18", 0], "guider": ["15", 0], "sampler": ["16", 0],
            "sigmas": ["17", 0], "latent_image": ["14", 2]}},
  "20": {"class_type": "TrimVideoLatent", "inputs": {"samples": ["19", 0], "trim_amount": ["14", 3]}},
  "21": {"class_type": "VAEDecode", "inputs": {"samples": ["20", 0], "vae": ["13", 0]}},
  "22": {"class_type": "CreateVideo", "inputs": {"images": ["21", 0], "fps": 16}},
  "23": {"class_type": "SaveVideo", "inputs": {"video": ["22", 0], "filename_prefix": "H3影栈/wan_anim_test",
                                                "format": "auto", "codec": "auto"}},
}
pid = core.submit(api)
print("submitted:", pid, "|", W, "x", H, "len", LEN, "steps", STEPS, flush=True)
t0 = time.time()
while True:
    h = core.history(pid)
    if h and ((h.get("status") or {}).get("completed") or h.get("outputs")):
        print("DONE", round(time.time() - t0), "s", core.collect_outputs(h), flush=True)
        break
    if h and (h.get("status") or {}).get("status_str") == "error":
        for m in h["status"].get("messages", []):
            if m and m[0] == "execution_error":
                print("ERROR:", (m[1] or {}).get("exception_message", "")[:900], flush=True)
                print("node:", (m[1] or {}).get("node_type"), flush=True)
        break
    time.sleep(5)
