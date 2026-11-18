# -*- coding: utf-8 -*-
"""LTX-2.5 低显存组合下载（ModelScope 源，支持断点续传 / 重试）。

用法：
    python _dl_ltx25.py            # 下全部
    python _dl_ltx25.py 3          # 只下前 3 个
进度写 logs/ltx25_dl.log
"""
import os
import subprocess
import sys
import time

MODELS = r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/models"
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "ltx25_dl.log")
os.makedirs(os.path.dirname(LOG), exist_ok=True)

MS = "https://modelscope.cn/api/v1/models/{repo}/repo?Revision=master&FilePath={path}"

# (repo, 仓库内路径, 本地子目录, 落地文件名, 大小GB)
FILES = [
    ("Lightricks/LTX-2.5", "vae/ltx-2.5-audio-vae-bf16.safetensors",
     "vae", "ltx-2.5-audio-vae-bf16.safetensors", 0.36),
    ("Lightricks/LTX-2.3-22b-IC-LoRA-Union-Control",
     "ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors",
     "loras", "ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors", 0.65),
    ("Lightricks/LTX-2.5", "latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors",
     "latent_upscale_models", "ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors", 1.00),
    ("Lightricks/LTX-2.5", "vae/ltx-2.5-video-vae-conv-bf16.safetensors",
     "vae", "ltx-2.5-video-vae-conv-bf16.safetensors", 1.45),
    ("Lightricks/LTX-2.5", "text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors",
     "text_encoders", "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors", 15.37),
    # 文本增强器（prompt enhance 支路需要，工作流 CLIPLoader 会校验存在性）
    ("Comfy-Org/gemma-4", "text_encoders/gemma4_e2b_it_bf16.safetensors",
     "text_encoders", "gemma4_e2b_it_bf16.safetensors", 10.28),
    ("Lightricks/LTX-2.5", "diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors",
     "diffusion_models", "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors", 21.50),
]


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def fetch(item, limit=None):
    repo, path, sub, name, gb = item
    dst_dir = os.path.join(MODELS, sub)
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, name)
    url = MS.format(repo=repo, path=path)

    if os.path.exists(dst):
        have = os.path.getsize(dst) / 1e9
        if have >= gb * 0.98:
            log(f"跳过（已完整 {have:.2f}GB）: {name}")
            return True
        log(f"续传（已有 {have:.2f}/{gb:.2f}GB）: {name}")

    env = {k: v for k, v in os.environ.items()
           if k.lower() not in ("http_proxy", "https_proxy", "all_proxy")}

    for attempt in range(1, 6):
        log(f"下载 {name}（第 {attempt} 次，{gb:.2f}GB）")
        cmd = ["curl", "-L", "--noproxy", "*", "-C", "-", "--retry", "3",
               "--retry-delay", "2", "-o", dst, url]
        r = subprocess.run(cmd, env=env)
        if os.path.exists(dst) and os.path.getsize(dst) / 1e9 >= gb * 0.98:
            log(f"完成 {name}（{os.path.getsize(dst)/1e9:.2f}GB, curl={r.returncode}）")
            return True
        time.sleep(3)
    log(f"失败 {name}，稍后重跑脚本可续传")
    return False


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else len(FILES)
    log(f"=== 开始 LTX-2.5 下载，共 {min(n, len(FILES))} 个文件 ===")
    ok = 0
    for it in FILES[:n]:
        if fetch(it):
            ok += 1
    log(f"=== 结束：成功 {ok}/{min(n, len(FILES))} ===")
