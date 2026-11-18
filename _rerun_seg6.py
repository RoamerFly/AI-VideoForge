# -*- coding: utf-8 -*-
"""只重跑 34 秒版的 seg6（背景被重建成木地板室内的那段）。

原 PROMPT 里写了 "clean white studio with wooden floor" —— "wooden floor" 会被模型
当成场景线索，在被遮挡/遮罩失效的段落里把白棚重建成室内木地板。

本脚本把背景描述改成纯白无缝，其余参数（seed / 步数 / 尺寸）保持不变，
以便判断「到底是提示词还是遮罩」导致的背景漂移。

用法：
    python _rerun_seg6.py            # 用新 prompt + 原 seed
    python _rerun_seg6.py 12345      # 指定 seed
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, "app")
import core

SEG_IDX = 6
STEPS = 6
W, H, SEG = 512, 896, 65
WORK = os.path.join(core.comfy_input(), "h3studio", "scail34")

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 20261114 + SEG_IDX

PROMPT = ("A young woman with long straight black hair, wearing a red chinese halter dress with "
          "silver belt, red wrist guards and red boots, dancing in a clean empty white studio "
          "with seamless white backdrop and white floor, plain background, full body shot")
QUALITY = ("natural lighting, sharp details, smooth motion, correct anatomy, no extra limbs, "
           "clean background")

out = os.path.join(WORK, f"seg{SEG_IDX}.mp4")
if os.path.exists(out):
    os.rename(out, out + ".bak")
    print(f"旧文件已改名 {os.path.basename(out)}.bak", flush=True)

p = {
    "engine": "scail",
    "images": ["h3studio/scail34/ref.png"],
    "char_count": 1,
    "video": f"h3studio/scail34/in{SEG_IDX:02d}.mp4",
    "prompt": PROMPT, "quality": QUALITY,
    "width": W, "height": H, "frames": SEG,
    "steps": STEPS, "seed": SEED,
    "tag": f"s34_{SEG_IDX:02d}_cleanbg",
}
api = core.build_api("05", p)
t0 = time.time()
pid = core.submit(api)
print(f"提交 {pid} | seed={SEED} | 无 wooden floor", flush=True)

while True:
    h = core.history(pid)
    if h and ((h.get("status") or {}).get("completed") or h.get("outputs")):
        outs = [f for f in core.collect_outputs(h) if f.startswith("H3影栈/")]
        if not outs:
            print("没有输出", flush=True)
            sys.exit(1)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                        "-i", os.path.join(core.comfy_output(), outs[0]),
                        "-c", "copy", out], check=True)
        print(f"完成 {round(time.time()-t0)}s → {out}", flush=True)
        break
    if h and (h.get("status") or {}).get("status_str") == "error":
        for m in h["status"].get("messages", []):
            if m and m[0] == "execution_error":
                print("失败:", (m[1] or {}).get("exception_message", "")[:600], flush=True)
        sys.exit(1)
    time.sleep(5)
