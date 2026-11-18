# -*- coding: utf-8 -*-
"""hf-mirror 多连接分片下载器：Ref2VA NVFP4 主模型 + 换人 LoRA
分片落盘为 <file>.partNNN，全部完成后拼接；中断后重跑自动跳过已完成分片。
"""
import os, sys, json, time, threading, urllib.request, urllib.error

BASE = "https://hf-mirror.com"
JOBS = [
    ("DmitryDB/MiniMax-H3-ComfyUI-Quants", "Ref2VA/MiniMax-H3_Ref2VA-NVFP4.safetensors",
     r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/models/diffusion_models/MiniMax-H3_Ref2VA-NVFP4.safetensors"),
    ("Alissonerdx/Minimax-H3-ComfyUI", "loras/minimax_h3_character_swap_v1.1_ref2va_fro.safetensors",
     r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI/models/loras/minimax_h3_character_swap_v1.1_ref2va_fro.safetensors"),
]
CHUNK = 64 * 1024 * 1024
THREADS = 8


def head_size(url):
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=30) as r:
        return int(r.headers["Content-Length"])


def fetch_range(url, start, end, dst, retries=12):
    if os.path.exists(dst) and os.path.getsize(dst) == end - start + 1:
        return True
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
            with urllib.request.urlopen(req, timeout=90) as r, open(dst, "wb") as f:
                f.write(r.read())
            if os.path.getsize(dst) == end - start + 1:
                return True
        except Exception as e:
            print(f"    retry {attempt+1} {start}-{end}: {e}", flush=True)
            time.sleep(2 + attempt)
    return False


def download(repo, path, dest):
    url = f"{BASE}/{repo}/resolve/main/{path}"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    total = head_size(url)
    if os.path.exists(dest) and os.path.getsize(dest) == total:
        print(f"[SKIP] {os.path.basename(dest)} 已存在 {total/1e9:.2f}GB", flush=True)
        return
    n = (total + CHUNK - 1) // CHUNK
    print(f"[GET ] {os.path.basename(dest)}  {total/1e9:.2f}GB  {n} 片 x {CHUNK//1048576}MB", flush=True)

    todo = []
    for i in range(n):
        s = i * CHUNK
        e = min(total - 1, s + CHUNK - 1)
        todo.append((i, s, e))

    lock = threading.Lock()
    done = [0]
    failed = []

    def worker():
        while True:
            with lock:
                if not todo:
                    return
                i, s, e = todo.pop(0)
            ok = fetch_range(url, s, e, f"{dest}.part{i:04d}")
            with lock:
                if ok:
                    done[0] += 1
                    if done[0] % 5 == 0 or done[0] == n:
                        print(f"    进度 {done[0]}/{n} 片", flush=True)
                else:
                    failed.append(i)

    ts = [threading.Thread(target=worker, daemon=True) for _ in range(THREADS)]
    [t.start() for t in ts]
    [t.join() for t in ts]

    if failed:
        print(f"[FAIL] {len(failed)} 片失败，重跑本脚本可续传", flush=True)
        return

    print("    拼接中…", flush=True)
    with open(dest, "wb") as out:
        for i in range(n):
            p = f"{dest}.part{i:04d}"
            with open(p, "rb") as f:
                out.write(f.read())
            os.remove(p)
    got = os.path.getsize(dest)
    print(f"[{'DONE' if got == total else 'SIZE-MISMATCH'}] {os.path.basename(dest)} {got/1e9:.2f}GB", flush=True)


if __name__ == "__main__":
    print("===== START", time.strftime("%F %T"), flush=True)
    for repo, path, dest in JOBS:
        try:
            download(repo, path, dest)
        except Exception as e:
            print(f"[ERR] {path}: {e}", flush=True)
    print("===== END", time.strftime("%F %T"), flush=True)
