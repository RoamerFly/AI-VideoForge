# -*- coding: utf-8 -*-
"""常驻引擎：启动 ComfyUI 并保活（引擎是本进程的子进程，任务结束会被带走，所以要长驻）。"""
import sys, time
sys.path.insert(0, "app")
import core

if not core.online(3):
    core.start_comfy(block=True)
print("引擎在线:", core.online(30), flush=True)
t0 = time.time()
while time.time() - t0 < 8 * 3600:
    time.sleep(600)
    print(f"[hold] 存活 {round((time.time()-t0)/60)} 分钟 | 引擎在线: {core.online(5)}", flush=True)
