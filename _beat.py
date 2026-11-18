# -*- coding: utf-8 -*-
"""轻量节拍分析：RMS 起音包络 + 自相关估速 + 峰值取拍点（无第三方依赖）。"""
import subprocess, wave, sys
import numpy as np

SRC = "E:/Agent/projects/AI视频模板/申鹤站立扭身舞.mp4"
WAV = "_beat_tmp.wav"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", SRC, "-ac", "1", "-ar", "16000", "-vn", WAV], check=True)

with wave.open(WAV, "rb") as w:
    sr = w.getframerate()
    data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0

hop, win = 160, 512   # 10ms 步长
n = 1 + max(0, (len(data) - win) // hop)
env = np.array([np.sqrt(np.mean(data[i*hop:i*hop+win]**2)) for i in range(n)])
flux = np.maximum(0, np.diff(env))          # 起音强度
flux = (flux - flux.mean()) / (flux.std() + 1e-8)

# 自相关估 BPM（0.3–1.2s 周期）
ac = np.correlate(flux, flux, mode="full")[len(flux)-1:]
lo, hi = int(0.30 / 0.01), int(1.20 / 0.01)
lag = lo + int(np.argmax(ac[lo:hi]))
bpm = 60.0 / (lag * 0.01)

# 取拍点：局部极大 + 最小间隔
thr = flux.mean() + 0.8 * flux.std()
peaks = [i for i in range(1, len(flux)-1) if flux[i] > thr and flux[i] >= flux[i-1] and flux[i] >= flux[i+1]]
beats, last = [], -99
for p in peaks:
    if p - last >= lag * 0.6:
        beats.append(p * 0.01); last = p

print(f"时长 {len(data)/sr:.2f}s | 估计 BPM {bpm:.1f} | 拍点 {len(beats)} 个")
print("前 12 个拍点(s):", [round(b, 2) for b in beats[:12]])
print("\n当前分段边界(s): 8.08 / 16.17 / 24.25")
for b in (8.08, 16.17, 24.25):
    near = min(beats, key=lambda x: abs(x - b)) if beats else 0
    print(f"  {b:.2f}s → 最近拍点 {near:.2f}s，偏差 {abs(near-b)*1000:.0f}ms")
