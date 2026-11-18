# -*- coding: utf-8 -*-
"""诊断：直连 ComfyUI 的 WebSocket，打印收到的所有事件类型，验证进度推送是否可达。"""
import json
import os
import time
import urllib.request

for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(k, None)

import websocket

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def post(path, data):
    req = urllib.request.Request("http://127.0.0.1:8188" + path,
                                 data=json.dumps(data).encode(),
                                 headers={"Content-Type": "application/json"})
    with opener.open(req, timeout=30) as r:
        return json.loads(r.read().decode())


ws = websocket.create_connection("ws://127.0.0.1:8188/ws?clientId=probe",
                                 timeout=8, http_no_proxy=["127.0.0.1", "localhost", "*"])
print("ws 已连接", flush=True)

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa

core.CFG["port"] = 8188
api = core.load_template("01")
gen = [v for v in api.values() if v["class_type"] == "MiniMaxH3ImageToVideo"][0]
gen["inputs"]["prompt"] = "纯白背景，一位穿和服的女性缓缓抬手挥手。写实摄影质感。"
gen["inputs"]["width"] = 256
gen["inputs"]["height"] = 448
gen["inputs"]["length"] = 124
pid = post("/prompt", {"prompt": api, "client_id": "probe"})["prompt_id"]
print("已提交", pid, flush=True)

t0 = time.time()
counts = {}
while time.time() - t0 < 150:
    try:
        raw = ws.recv()
    except Exception as e:
        print("recv 超时/断线:", e, flush=True)
        break
    if not raw or isinstance(raw, bytes):
        continue
    m = json.loads(raw)
    t = m.get("type")
    counts[t] = counts.get(t, 0) + 1
    d = m.get("data") or {}
    if t in ("progress", "execution_start", "execution_success", "execution_error", "executing", "status"):
        extra = ""
        if t == "progress":
            extra = f" value={d.get('value')} max={d.get('max')} node={d.get('node')}"
        elif t == "execution_start":
            extra = f" prompt_id={d.get('prompt_id')}"
        elif t == "executing":
            extra = f" node={d.get('node')} prompt_id={d.get('prompt_id')}"
        print(f"{time.strftime('%H:%M:%S')} {t}{extra}", flush=True)
    if t == "execution_success":
        break
print("事件统计:", counts, flush=True)
