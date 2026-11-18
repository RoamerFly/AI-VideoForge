# -*- coding: utf-8 -*-
"""H3 影栈 —— 本地服务：静态页面 + 接口 + 视频流，外套一个 WebView 窗口。"""
import json
import mimetypes
import os
import re
import socket
import sys
import threading
import time
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import core

RES_DIR = core.RES_DIR
UI_DIR = os.path.join(RES_DIR, "ui")
FIXED_PORT = 8765


# ---------------------------------------------------------------- 工具
def free_port(start=FIXED_PORT):
    for p in range(start, start + 40):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return start


def json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "H3Studio/1.0"

    def log_message(self, *a):
        pass

    # -------------------------------------------------- 基础响应
    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass

    def _ok(self, obj=None):
        self._send(200, json_bytes(obj if obj is not None else {"ok": True}))

    def _err(self, msg, code=400):
        self._send(code, json_bytes({"ok": False, "error": str(msg)}))

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        raw = self.rfile.read(n)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    # -------------------------------------------------- GET
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        path = u.path
        try:
            if path in ("/", "/index.html"):
                return self._file(os.path.join(UI_DIR, "index.html"))
            if path.startswith("/ui/"):
                return self._file(os.path.join(UI_DIR, path[4:]))
            if path == "/api/state":
                return self._ok(self._state())
            if path == "/api/tasks":
                return self._ok({"tasks": core.task_list()})
            if path == "/api/pose/runs":
                import pose_pipeline
                return self._ok({"runs": pose_pipeline.runs(core)})
            if path == "/api/config":
                return self._ok(core.CFG)
            if path == "/api/models":
                q = urllib.parse.parse_qs(u.query)
                return self._ok(core.models_snapshot())
            if path == "/api/comfy/log":
                return self._ok({"log": core.log_tail(80)})
            if path == "/api/probe":
                q = urllib.parse.parse_qs(u.query)
                p = q.get("path", [""])[0]
                if not p or not os.path.exists(p):
                    return self._err("文件不存在")
                return self._ok(core.probe_video(p))
            if path == "/api/history":
                return self._ok({"items": self._history()})
            if path == "/media":
                q = urllib.parse.parse_qs(u.query)
                p = q.get("path", [""])[0]
                return self._media(p, inline=True)
            if path == "/thumb":
                q = urllib.parse.parse_qs(u.query)
                p = q.get("path", [""])[0]
                return self._media(p, inline=True)
            return self._err("未知接口", 404)
        except Exception as e:
            traceback.print_exc()
            return self._err(e, 500)

    # -------------------------------------------------- POST
    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            body = self._body()
            if path == "/api/comfy/start":
                # 立刻返回，实际启动在后台线程；界面靠 /api/state 显示「启动中 12 秒」
                return self._ok(core.start_comfy(block=False))
            if path == "/api/comfy/stop":
                return self._ok(core.stop_comfy())
            if path == "/api/comfy/open":
                url = core.base_url()
                if os.name == "nt":
                    os.startfile(url)
                return self._ok({"url": url})
            if path == "/api/models":
                sel = body.get("models") or {}
                core.save_config({"models": sel})
                return self._ok(core.models_snapshot())
            if path == "/api/upload":
                p = core.save_upload(body.get("name"), body.get("data") or "")
                return self._ok({"path": p, "name": os.path.basename(p)})
            if path == "/api/generate":
                mode = str(body.get("mode") or "")
                if mode not in core.MODES:
                    return self._err("未知模式")
                params = body.get("params") or {}
                title = body.get("title") or core.MODES[mode]["name"]
                need_start = not core.online(timeout=1)
                t = core.new_task(mode, title, params)
                if need_start:
                    core.start_comfy(block=False)
                return self._ok({"task": t, "autostart": need_start})
            if path.startswith("/api/cancel/"):
                return self._ok(core.cancel_task(path.rsplit("/", 1)[-1]))
            if path == "/api/config":
                cfg = core.save_config(body or {})
                return self._ok(cfg)
            if path == "/api/mount":
                return self._ok(core.mount_models(body.get("comfy_root") or ""))
            if path == "/api/open":
                target = body.get("path") or core.out_dir()
                if os.path.isfile(target):
                    target = os.path.dirname(target)
                os.startfile(target) if os.name == "nt" else None
                return self._ok()
            if path == "/api/reveal":
                target = body.get("path") or ""
                if os.path.exists(target):
                    if os.name == "nt":
                        os.system(f'explorer /select,"{os.path.normpath(target)}"')
                    else:
                        os.startfile(os.path.dirname(target))
                return self._ok()
            if path == "/api/delete":
                target = os.path.normpath(body.get("path") or "")
                roots = [os.path.normpath(core.out_dir()),
                         os.path.normpath(core.comfy_output())]
                exts = (".mp4", ".webm", ".mov")
                if not target.startswith(tuple(roots)):
                    return self._err("只能删除本程序输出目录里的视频文件")
                if not os.path.isfile(target) or not target.lower().endswith(exts):
                    return self._err("文件不存在或不是视频文件")
                try:
                    os.remove(target)
                except Exception as e:
                    return self._err(f"删除失败：{e}")
                return self._ok({"deleted": os.path.basename(target)})
            return self._err("未知接口", 404)
        except Exception as e:
            traceback.print_exc()
            return self._err(e, 500)

    # -------------------------------------------------- 业务
    def _state(self):
        eng = core.engine_state()
        stats = core.system_stats()
        return {
            "online": eng["online"],
            "engine": eng,
            "gpu": eng.get("gpu"),
            "queue": core.queue_info() if eng["online"] else {"running": 0, "pending": 0},
            "modes": core.MODES,
            "config": core.CFG,
            "out_dir": core.out_dir(),
            "ffmpeg": core.ffmpeg_ok(),
        }

    def _history(self):
        d = core.out_dir()
        items = []
        try:
            for fn in os.listdir(d):
                if not fn.lower().endswith((".mp4", ".webm", ".mov")):
                    continue
                p = os.path.join(d, fn)
                items.append({"name": fn, "path": p, "size": os.path.getsize(p),
                              "mtime": os.path.getmtime(p)})
        except Exception:
            pass
        items.sort(key=lambda x: -x["mtime"])
        return items[:60]

    # -------------------------------------------------- 文件
    def _file(self, path):
        path = os.path.normpath(path)
        if not path.startswith(os.path.normpath(UI_DIR)) or not os.path.isfile(path):
            return self._err("not found", 404)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        with open(path, "rb") as f:
            data = f.read()
        self._send(200, data, ctype)

    def _media(self, path, inline=False):
        path = os.path.normpath(path or "")
        roots = [os.path.normpath(core.out_dir()), os.path.normpath(core.comfy_output()),
                 os.path.normpath(core.UPLOAD_DIR)]
        if not any(path.startswith(r) for r in roots) or not os.path.isfile(path):
            return self._err("no file", 404)
        size = os.path.getsize(path)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        code = 200
        if rng and rng.startswith("bytes="):
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                if m.group(1):
                    start = int(m.group(1))
                if m.group(2):
                    end = min(int(m.group(2)), size - 1)
                code = 206
        length = end - start + 1
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            left = length
            while left > 0:
                chunk = f.read(min(262144, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except Exception:
                    return
                left -= len(chunk)


def serve(port):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main():
    try:
        _main()
    except Exception:
        tb = traceback.format_exc()
        try:
            with open(os.path.join(core.DATA_DIR, "error.log"), "a", encoding="utf-8") as f:
                f.write(tb + "\n")
        except Exception:
            pass
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, tb[-900:], "H3 影栈 启动失败（详情见 %APPDATA%\\H3Studio\\error.log）", 0x10)
        except Exception:
            pass


def _main():
    core.boot()
    port = free_port()
    serve(port)
    url = f"http://127.0.0.1:{port}"

    # 兜底：无论从哪条路径退出，都只清理「自己拉起」的子进程
    import atexit
    atexit.register(core.stop_owned)

    if "--nobrowser" in sys.argv or "--server" in sys.argv:
        print(url, flush=True)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        return

    if core.CFG.get("auto_start_comfy"):
        threading.Thread(target=core.start_comfy, daemon=True).start()

    import webview
    webview.create_window(
        title=f"{core.APP_NAME} · MiniMax H3 视频工坊", url=url,
        width=1320, height=880, min_size=(1120, 720),
        background_color="#F3EEE4", text_select=True,
    )
    webview.start(debug="--debug" in sys.argv)

    # 窗口已全部关闭 = 用户退出程序：停掉自己拉起的 ComfyUI；
    # 若 ComfyUI 是用户自己开的（不是本程序拉起），则不动它。
    try:
        core.stop_owned()
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()
