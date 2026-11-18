# -*- coding: utf-8 -*-
"""MiniMax H3 模型就绪检查：文件是否齐全、体积是否完整、safetensors 头是否可解析"""
import json, os, struct, sys

MODELS = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/models"

# rel_path, 精确字节数, 用途, 是否换人必需
EXPECT = [
    ("text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", 15687142551, "文本/图像编码器", True),
    ("diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors", 20970379616, "换人/参考生视频 DiT", True),
    ("vae/minimax_h3_video_vae_int8_convrot.safetensors", 2811065184, "视频解码", True),
    ("vae/minimax_h3_audio_vae_fp32.safetensors", 605254808, "音频解码", True),
    ("loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors", 1956192992, "4步加速 LoRA", True),
    ("loras/minimax_h3_character_swap_v1.1_ref2va_fro.safetensors", 80673112, "换人 LoRA v1.1", True),
    ("diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors", 20970379616, "文生/图生/首尾帧 DiT", False),
    ("loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors", 1956193000, "文生 8步加速", False),
    ("loras/minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors", 1956192992, "文生 4步加速", False),
]

def safetensors_ok(path):
    """读 safetensors 头：8 字节小端长度 + JSON，并核对张量数据区终点是否等于文件长度。
    返回 (ok, 说明)"""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            head = f.read(8)
            if len(head) < 8:
                return False, "文件过短"
            n = struct.unpack("<Q", head)[0]
            if n <= 0 or n > 200 * 1024 * 1024:
                return False, f"头长度异常 {n}"
            raw = f.read(n)
            hdr = json.loads(raw.decode("utf-8"))
        end = max(v["data_offsets"][1] for k, v in hdr.items() if k != "__metadata__")
        expect_len = 8 + n + end
        if expect_len != size:
            return False, f"数据区终点 {expect_len} ≠ 文件长度 {size}（差 {size-expect_len:+d}B）"
        return True, f"头 {n} 字节可解析，{len(hdr)-1} 个张量，长度吻合"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

def human(n):
    return f"{n/1e9:.2f} GB" if n >= 1e9 else f"{n/1e6:.0f} MB"

rows, need_missing, opt_missing = [], [], []
for rel, want, use, must in EXPECT:
    p = os.path.join(MODELS, rel)
    have = os.path.getsize(p) if os.path.exists(p) else 0
    if have == 0:
        state = "缺失"
    elif have < want:
        state = f"下载中 {have*100//want}%"
    else:
        # 体积达标：以 safetensors 头 + 张量数据区终点是否等于文件长度为准，
        # 允许与参考体积有 +/-4KB 的元数据差异
        ok, msg = safetensors_ok(p)
        if not ok:
            state = f"损坏: {msg}"
        elif abs(have - want) <= 4096:
            state = "完整✓" if have == want else f"完整✓ ({have-want:+d}B)"
        else:
            state = f"偏大 +{have-want}B"
    rows.append((state, rel, f"{human(have)}/{human(want)}", use, must))
    if not state.startswith("完整"):
        (need_missing if must else opt_missing).append(rel)

w1 = max(len(r[0]) for r in rows) + 1
w3 = max(len(r[2]) for r in rows) + 1
for state, rel, size, use, must in rows:
    tag = "必需" if must else "可选"
    print(f"{state:<{w1}} {size:<{w3}} [{tag}] {rel}")
    print(f"{'':<{w1}} {'':<{w3}}        └ {use}")

print()
if need_missing:
    print(f"换人路线还差 {len(need_missing)} 个必需文件，继续跑 download_h3_models.sh 即可续传")
elif opt_missing:
    print(f"换人路线已就绪 ✓　文生/图生还差 {len(opt_missing)} 个可选文件")
else:
    print("全部就绪 ✓　可以启动 ComfyUI 实跑")

sys.exit(0 if not need_missing else 1)
