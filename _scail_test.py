# -*- coding: utf-8 -*-
"""SCAIL-2 角色替换最小验证：按官方子图展平的接线直连提交。

与 Wan-Animate 的关键区别：用 SAM3 自动跟踪人物遮罩（pose_video_mask /
reference_image_mask），不需要骨架，也不会让参考图决定构图。
"""
import sys
import time

sys.path.insert(0, "app")
import core

W = int(sys.argv[1]) if len(sys.argv) > 1 else 512
H = int(sys.argv[2]) if len(sys.argv) > 2 else 896
LEN = int(sys.argv[3]) if len(sys.argv) > 3 else 65
STEPS = int(sys.argv[4]) if len(sys.argv) > 4 else 6
TAG = sys.argv[5] if len(sys.argv) > 5 else "s1"
ANIM = (sys.argv[6] if len(sys.argv) > 6 else "0") == "1"   # 1=Animation(换背景) 0=Replacement

DRIVE = "h3studio/scail/drive_65f_512x896.mp4"
REF = "h3studio/scail/hinata.png"

PROMPT = ("A young woman with long straight black hair, wearing a red chinese halter dress "
          "with silver belt, red wrist guards and red boots, dancing in a clean white studio "
          "with wooden floor, natural lighting, full body shot, sharp details, smooth motion")

api = {
    # ---- 模型链：SCAIL-2 → DPO LoRA → 蒸馏 LoRA → switch → ModelSamplingSD3 ----
    "1": {"class_type": "UNETLoader",
          "inputs": {"unet_name": "wan2.1_14B_SCAIL_2_nvfp4_mxpf8_mix.safetensors",
                     "weight_dtype": "default"}},
    "2": {"class_type": "LoraLoaderModelOnly",
          "inputs": {"lora_name": "wan2.1_SCAIL_2_DPO_lora_bf16.safetensors",
                     "strength_model": 1.0, "model": ["1", 0]}},
    "3": {"class_type": "LoraLoaderModelOnly",
          "inputs": {"lora_name": "lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
                     "strength_model": 0.8, "model": ["2", 0]}},
    "4": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["3", 0], "shift": 5.0}},

    # ---- 文本 / 视觉编码 ----
    "5": {"class_type": "CLIPLoader",
          "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                     "type": "wan", "device": "default"}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": PROMPT, "clip": ["5", 0]}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["5", 0]}},
    "8": {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "clip_vision_h.safetensors"}},
    "9": {"class_type": "LoadImage", "inputs": {"image": REF}},
    "10": {"class_type": "CLIPVisionEncode",
           "inputs": {"clip_vision": ["8", 0], "image": ["9", 0], "crop": "none"}},
    "11": {"class_type": "VAELoader", "inputs": {"vae_name": "Wan2_1_VAE_bf16.safetensors"}},

    # ---- 驱动视频（已用 ffmpeg 预缩放到目标尺寸，跳过 ResizeImageMaskNode）----
    "12": {"class_type": "LoadVideo", "inputs": {"file": DRIVE}},
    "13": {"class_type": "GetVideoComponents", "inputs": {"video": ["12", 0]}},
    "14": {"class_type": "ImageFromBatch",
           "inputs": {"image": ["13", 0], "batch_index": 0, "length": LEN}},

    # ---- SAM3 人物遮罩跟踪 ----
    "15": {"class_type": "CheckpointLoaderSimple",
           "inputs": {"ckpt_name": "sam3.1_multiplex_fp16.safetensors"}},
    "16": {"class_type": "CLIPTextEncode", "inputs": {"text": "human", "clip": ["15", 1]}},
    "17": {"class_type": "CLIPTextEncode", "inputs": {"text": "human", "clip": ["15", 1]}},
    "18": {"class_type": "SAM3_VideoTrack",
           "inputs": {"images": ["14", 0], "model": ["15", 0], "conditioning": ["16", 0],
                      "detection_threshold": 0.5, "max_objects": 1, "detect_interval": 1}},
    "19": {"class_type": "SAM3_VideoTrack",
           "inputs": {"images": ["9", 0], "model": ["15", 0], "conditioning": ["17", 0],
                      "detection_threshold": 0.5, "max_objects": 1, "detect_interval": 1}},
    "20": {"class_type": "SCAIL2ColoredMask",
           "inputs": {"driving_track_data": ["18", 0], "ref_track_data": ["19", 0],
                      "object_indices": "", "sort_by": "left_to_right",
                      "replacement_mode": (not ANIM)}},

    # ---- 核心：SCAIL-2 视频生成 ----
    "21": {"class_type": "WanSCAILToVideo",
           "inputs": {"positive": ["6", 0], "negative": ["7", 0], "vae": ["11", 0],
                      "width": W, "height": H, "length": LEN, "batch_size": 1,
                      "pose_strength": 1.0, "pose_start": 0.0, "pose_end": 1.0,
                      "video_frame_offset": 0, "previous_frame_count": 5,
                      "pose_video": ["14", 0], "pose_video_mask": ["20", 0],
                      "replacement_mode": (not ANIM),
                      "reference_image": ["9", 0], "reference_image_mask": ["20", 1],
                      "clip_vision_output": ["10", 0]}},

    # ---- 采样（turbo：euler + 6 步 + cfg 1）----
    "22": {"class_type": "BasicScheduler",
           "inputs": {"model": ["3", 0], "scheduler": "simple", "steps": STEPS, "denoise": 1.0}},
    "23": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
    "24": {"class_type": "SamplerCustom",
           "inputs": {"model": ["4", 0], "add_noise": True, "noise_seed": 20261114, "cfg": 1.0,
                      "positive": ["21", 0], "negative": ["21", 1],
                      "sampler": ["23", 0], "sigmas": ["22", 0], "latent_image": ["21", 2]}},
    "25": {"class_type": "VAEDecode", "inputs": {"samples": ["24", 0], "vae": ["11", 0]}},
    "26": {"class_type": "CreateVideo", "inputs": {"images": ["25", 0], "fps": 16}},
    "27": {"class_type": "SaveVideo",
           "inputs": {"video": ["26", 0], "filename_prefix": f"H3影栈/scail_{TAG}",
                      "format": "auto", "codec": "auto"}},
}

pid = core.submit(api)
print(f"submitted {pid} | {W}x{H} len={LEN} steps={STEPS}", flush=True)
t0 = time.time()
while True:
    h = core.history(pid)
    if h and ((h.get("status") or {}).get("completed") or h.get("outputs")):
        outs = [f for f in core.collect_outputs(h) if f.startswith("H3影栈/")]
        print("DONE", round(time.time() - t0), "s →", outs, flush=True)
        break
    if h and (h.get("status") or {}).get("status_str") == "error":
        for m in h["status"].get("messages", []):
            if m and m[0] == "execution_error":
                print("ERROR:", (m[1] or {}).get("exception_message", "")[:900], flush=True)
                print("node:", (m[1] or {}).get("node_type"), (m[1] or {}).get("node_id"), flush=True)
        break
    time.sleep(5)
