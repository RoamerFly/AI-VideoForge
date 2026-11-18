# -*- coding: utf-8 -*-
"""H3 影栈 —— 核心逻辑：配置、ComfyUI 进程管理、任务引擎、ffmpeg 处理。"""
import base64
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

APP_NAME = "H3影栈"

# 本程序只跟 127.0.0.1 通信。系统里若配了 HTTP_PROXY，urllib 与 websocket-client
# 都会把本地请求丢给代理，导致「连不上 ComfyUI / 收不到进度」。启动时直接摘掉代理。
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
           "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_k, None)
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"

DATA_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "H3Studio")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")

# 打包后资源目录（templates / ui）
if getattr(sys, "frozen", False):
    RES_DIR = os.path.join(sys._MEIPASS, "res")
else:
    RES_DIR = os.path.dirname(os.path.abspath(__file__))

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

DEFAULT_CONFIG = {
    "comfy_root": r"E:/Agent/projects/freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3",
    "port": 8188,
    "ffmpeg": "ffmpeg",
    "out_dir": "",
    "auto_start_comfy": True,
    "theme": "warm",
    # 模型选择：留空表示用工作流模板里的默认值
    "models": {"unet_fl2v": "", "unet_ref2v": "", "lora_fl2v": "", "lora_ref2v": "", "lora_swap": ""},
}


def _load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    if not cfg.get("out_dir"):
        cfg["out_dir"] = os.path.join(cfg["comfy_root"], "ComfyUI", "output", "H3影栈")
    return cfg


CFG = _load_config()
_lock = threading.RLock()


def save_config(patch):
    global CFG
    with _lock:
        cfg = dict(CFG)
        cfg.update(patch or {})
        CFG = cfg
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("保存配置失败", e)
    return CFG


# ---------------------------------------------------------------- 路径
def comfy_root():
    return CFG["comfy_root"].replace("\\", "/").rstrip("/")


def comfy_input():
    return os.path.join(comfy_root(), "ComfyUI", "input")


def comfy_output():
    return os.path.join(comfy_root(), "ComfyUI", "output")


def comfy_python():
    return os.path.join(comfy_root(), "python", "python.exe")


def comfy_main():
    return os.path.join(comfy_root(), "ComfyUI", "main.py")


def base_url():
    return f"http://127.0.0.1:{CFG['port']}"


def out_dir():
    p = CFG["out_dir"].replace("\\", "/")
    os.makedirs(p, exist_ok=True)
    return p


def ffmpeg_exe():
    exe = CFG.get("ffmpeg") or "ffmpeg"
    if os.path.isabs(exe):
        return exe
    return shutil.which(exe) or exe


# ---------------------------------------------------------------- 自带模型包
def models_dir():
    """release 自带的模型包目录（与成品 exe 放在一起）。"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)      # exe 所在目录（release/）
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根
        base = os.path.join(base, "release")
    d = os.path.join(base, "models")
    return d if os.path.isdir(d) else ""


MOUNT_KEY = "H3Studio"


def _yaml_replace_block(txt):
    """把已有的 H3Studio: 块从 yaml 文本里摘掉（幂等重写）。"""
    if MOUNT_KEY + ":" not in txt:
        return txt.rstrip() + "\n" if txt.strip() else ""
    out, skip, indent_seen = [], False, None
    for line in txt.splitlines():
        if not skip and line.strip().startswith(MOUNT_KEY + ":"):
            skip = True
            continue
        if skip:
            s = line.strip()
            ind = len(line) - len(line.lstrip(" "))
            if s and ind > 0:
                continue          # 还在块内
            if not s:
                continue          # 块内空行
            skip = False          # 顶格新内容，块结束
        if not skip:
            out.append(line)
    return "\n".join(out).rstrip() + "\n" if out else ""


def mount_models(comfy_root=""):
    """把 release/models 挂接到 ComfyUI（写 extra_model_paths.yaml）。

    新电脑部署：装好基础 ComfyUI + 拷一份 release，在设置里填好 ComfyUI 位置，
    点一下「挂接模型」即可——不用往 ComfyUI 里复制任何模型。
    """
    root = comfy_root or CFG.get("comfy_root") or ""
    md = models_dir()
    if not md:
        return {"ok": False, "error": "没有找到自带的模型包（models 目录需与 exe 放在一起）"}
    if not os.path.isdir(os.path.join(root, "ComfyUI")):
        return {"ok": False, "error": f"ComfyUI 目录不对：{root}（应选包含 ComfyUI/python 两个文件夹的那一层）"}
    ypath = os.path.join(root, "ComfyUI", "extra_model_paths.yaml")
    try:
        old = ""
        if os.path.exists(ypath):
            with open(ypath, encoding="utf-8") as f:
                old = f.read()
        body = _yaml_replace_block(old)
        block = (
            f"\n{MOUNT_KEY}:\n"
            f"  base_path: {md.replace(chr(92), '/')}\n"
            f"  is_default: false\n"
            f"  diffusion_models: diffusion_models\n"
            f"  loras: loras\n"
            f"  vae: vae\n"
            f"  text_encoders: text_encoders\n"
            f"  controlnet: controlnet\n"
            f"  model_patches: model_patches\n"
        )
        with open(ypath, "w", encoding="utf-8") as f:
            f.write((body + block) if body else block.lstrip("\n"))
    except Exception as e:
        return {"ok": False, "error": f"写入失败：{e}"}
    return {"ok": True, "yaml": ypath, "models_dir": md,
            "msg": "已挂接，重启 ComfyUI 后生效"}


def ffmpeg_ok():
    exe = CFG.get("ffmpeg") or "ffmpeg"
    return os.path.exists(exe) if os.path.isabs(exe) else bool(shutil.which(exe))


# ---------------------------------------------------------------- ComfyUI 通讯
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http_json(path, data=None, timeout=15, method=None):
    url = base_url() + path
    body = None
    headers = {"Content-Type": "application/json"}
    if data is not None:
        body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with _opener.open(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw.decode("utf-8")) if raw else {}


def online(timeout=3):
    try:
        return bool(system_stats(max_age=1.0))
    except Exception:
        return False


_stats_cache = {"t": 0.0, "v": None}


def system_stats(max_age=1.0):
    """查 ComfyUI 状态。带 1 秒缓存：界面每 2 秒轮询一次，引擎离线时也不会卡住。"""
    now = time.time()
    if max_age and now - _stats_cache["t"] < max_age:
        return _stats_cache["v"]
    try:
        v = http_json("/system_stats", timeout=4)
    except Exception:
        v = None
    _stats_cache["t"] = time.time()
    _stats_cache["v"] = v
    return v


_proc = None
ENGINE = {"starting": False, "since": 0.0, "msg": "", "error": "", "last": ""}
_engine_lock = threading.Lock()


def engine_state():
    """给界面的引擎状态：在线 / 启动中 / 版本 / 队列 / 出错信息。"""
    st = system_stats()
    online = bool(st)
    ver = ""
    gpu = None
    if st:
        ver = (st.get("system") or {}).get("comfyui_version", "")
        devs = st.get("devices") or []
        if devs:
            d = devs[0]
            total = d.get("vram_total") or 0
            free = d.get("vram_free") or 0
            gpu = {"name": d.get("name", ""),
                   "total": round(total / 1073741824, 1),
                   "used": round((total - free) / 1073741824, 1),
                   "pct": round((total - free) / total * 100) if total else 0}
    with _engine_lock:
        starting = ENGINE["starting"]
        since = ENGINE["since"]
        msg = ENGINE["msg"]
        err = ENGINE["error"]
    if online:
        starting = False
    return {
        "online": online,
        "starting": starting and not online,
        "start_elapsed": int(time.time() - since) if (starting and since) else 0,
        "msg": msg,
        "error": err,
        "version": ver,
        "gpu": gpu,
        "port": CFG["port"],
        "watch": {"connected": WATCHER.connected, "msgs": WATCHER.msgs,
                  "alive": WATCHER.is_alive(),
                  "value": WATCHER.value, "max": WATCHER.max,
                  "err": WATCHER.last_err},
    }


def _set_engine(**kw):
    with _engine_lock:
        ENGINE.update(kw)


def _tail_log(n=24):
    p = os.path.join(DATA_DIR, "comfy.log")
    try:
        with open(p, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 24000))
            txt = f.read().decode("utf-8", "ignore")
        lines = [l for l in txt.splitlines() if l.strip()]
        return "\n".join(lines[-n:])
    except Exception:
        return ""


def log_tail(n=80):
    """给界面看的引擎日志（最近 n 行）。"""
    txt = _tail_log(n)
    return txt or "（还没有日志，引擎可能从未启动过）"


def _proc_start(wait_sec=240):
    """真正拉起 ComfyUI，并把结果写进 ENGINE。"""
    global _proc
    if online():
        _set_engine(starting=False, msg="ComfyUI 已在运行", error="")
        return
    if not os.path.exists(comfy_python()):
        _set_engine(starting=False, error=f"找不到 ComfyUI 的 Python：{comfy_python()}",
                    msg="路径不对，请到设置里改 ComfyUI 安装位置")
        return
    if not os.path.exists(comfy_main()):
        _set_engine(starting=False, error=f"找不到 ComfyUI 主程序：{comfy_main()}",
                    msg="路径不对，请到设置里改 ComfyUI 安装位置")
        return
    env = dict(os.environ)
    env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    env["PYTHONIOENCODING"] = "utf-8"
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(k, None)
    log_path = os.path.join(DATA_DIR, "comfy.log")
    log = open(log_path, "ab", buffering=0)
    creation = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    try:
        _proc = subprocess.Popen(
            [comfy_python(), "-s", comfy_main(),
             "--listen", "127.0.0.1", "--port", str(CFG["port"]),
             "--preview-method", "none"],
            cwd=comfy_root(), env=env, stdout=log, stderr=subprocess.STDOUT,
            creationflags=creation,
        )
    except Exception as e:
        _set_engine(starting=False, error=f"启动失败：{e}", msg="启动失败")
        return
    for i in range(int(wait_sec)):
        if online(timeout=1):
            _set_engine(starting=False, msg="引擎已就绪", error="")
            return
        if _proc.poll() is not None:
            tail = _tail_log(12)
            _set_engine(starting=False, msg="引擎启动失败",
                        error=f"进程已退出（日志末尾）：\n{tail[-900:]}")
            return
        time.sleep(1)
    _set_engine(starting=False, msg="启动超时", error="等待超过 4 分钟仍未就绪，详见日志")


def start_comfy(block=False):
    """启动 ComfyUI。默认立刻返回，实际启动在后台线程里做，界面能显示启动进度。"""
    if online():
        _set_engine(starting=False, msg="ComfyUI 已在运行", error="")
        return {"ok": True, "msg": "引擎已在运行", "online": True}
    with _engine_lock:
        already = ENGINE["starting"]
        if not already:
            ENGINE.update(starting=True, since=time.time(), msg="正在启动引擎…", error="")
    if not already:
        threading.Thread(target=_proc_start, daemon=True).start()
    if block:
        for _ in range(240):
            st = engine_state()
            if st["online"]:
                return {"ok": True, "msg": "引擎已启动", "online": True}
            if not st["starting"] and st["error"]:
                return {"ok": False, "msg": st["error"][:300], "online": False}
            time.sleep(1)
    return {"ok": True, "msg": "正在启动引擎", "starting": True, "online": False}


def _port_pid(port):
    """找出监听指定端口的进程（ComfyUI 可能不是本程序拉起的）。"""
    if os.name != "nt":
        return None
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                             timeout=8, creationflags=0x08000000).stdout
    except Exception:
        return None
    for line in out.splitlines():
        if "LISTENING" not in line:
            continue
        parts = line.split()
        if len(parts) >= 5 and parts[1].endswith(f":{port}"):
            try:
                return int(parts[-1])
            except ValueError:
                pass
    return None


def stop_owned():
    """程序退出时收尾：只停掉「本程序自己拉起」的子进程（ComfyUI）。

    外部（比如用户自己在终端里跑的）ComfyUI 完全不动 —— _proc 只有在
    _proc_start 里由本进程 Popen 出来时才会有值。
    """
    global _proc
    p, _proc = _proc, None
    killed = False
    if p is not None:
        try:
            if p.poll() is None:  # 还活着才需要杀
                if os.name == "nt":
                    # /T 连同子进程树一起停（ComfyUI 还会再拉 ffmpeg 之类）
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(p.pid)],
                        capture_output=True, timeout=15,
                        creationflags=0x08000000)
                else:
                    p.terminate()
                try:
                    p.wait(timeout=10)
                except Exception:
                    pass
                killed = True
        except Exception:
            pass
    _set_engine(starting=False, msg="", error="")
    return {"ok": True, "stopped": killed}


def stop_comfy():
    global _proc
    killed = False
    if _proc and _proc.poll() is None:
        try:
            _proc.terminate()
            _proc.wait(timeout=12)
            killed = True
        except Exception:
            try:
                _proc.kill()
                killed = True
            except Exception:
                pass
    _proc = None
    if not killed:
        pid = _port_pid(CFG["port"])
        if pid:
            try:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                               capture_output=True, timeout=12,
                               creationflags=0x08000000)
                killed = True
            except Exception:
                pass
    for _ in range(20):
        if not online(timeout=1):
            break
        time.sleep(1)
    _set_engine(starting=False, msg="引擎已关闭" if killed else "引擎本来就未运行", error="")
    return {"ok": True, "stopped": killed,
            "msg": "引擎已关闭" if killed else "引擎本来就未运行",
            "online": online(timeout=1)}


# ---------------------------------------------------------------- 进度监听
def _wlog(text):
    """把进度通道的关键事件写到 %APPDATA%/H3Studio/ws.log，便于排查。"""
    try:
        p = os.path.join(DATA_DIR, "ws.log")
        if os.path.exists(p) and os.path.getsize(p) > 512 * 1024:
            os.remove(p)
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {text}\n")
    except Exception:
        pass


class ProgressWatcher(threading.Thread):
    """连 ComfyUI 的 WebSocket，缓存最新进度。断线自动重连。

    注意：websocket-client 读的是 HTTP_PROXY 环境变量，系统里配了代理时
    会把 ws://127.0.0.1 也丢给代理，导致一条消息都收不到。所以显式指定
    http_no_proxy，并且在模块顶部已经把代理变量摘掉。
    """

    def __init__(self):
        super().__init__(daemon=True)
        self.value = 0
        self.max = 0
        self.node = ""
        self.node_id = ""
        self.prompt_id = ""
        self.connected = False
        self.msgs = 0
        self.connects = 0
        self.last_err = ""
        self.started_at = 0.0
        self.last_progress = 0.0
        self._stop = False

    def reset(self):
        self.value = self.max = 0
        self.node = ""
        self.node_id = ""
        self.prompt_id = ""
        self.last_progress = 0.0

    def run(self):
        try:
            import websocket
        except Exception as e:  # pragma: no cover
            self.last_err = f"缺少 websocket-client：{e}"
            return
        url = f"ws://127.0.0.1:{CFG['port']}/ws?clientId={CLIENT_ID}"
        self.connects = 0
        while not self._stop:
            try:
                ws = websocket.create_connection(
                    url, timeout=120, http_proxy_host=None,
                    http_no_proxy=["127.0.0.1", "localhost", "*"])
                ws.settimeout(120)
                self.connected = True
                self.last_err = ""
                self.connects += 1
                _wlog(f"connected #{self.connects} {url}")
                while not self._stop:
                    try:
                        raw = ws.recv()
                    except Exception as ie:
                        # 采样中途可能几分钟没有任何消息，超时不能当成断线
                        if "timeout" in str(ie).lower() or "timed out" in str(ie).lower():
                            continue
                        raise
                    if not raw or isinstance(raw, bytes):
                        continue
                    self.msgs += 1
                    msg = json.loads(raw)
                    t, d = msg.get("type"), msg.get("data") or {}
                    if t in ("execution_start", "progress", "execution_success", "execution_error"):
                        _wlog(f"{t} {json.dumps(d, ensure_ascii=False)[:160]}")
                    if t == "execution_start":
                        self.prompt_id = d.get("prompt_id", "")
                        self.started_at = time.time()
                        self.value = self.max = 0
                        self.node = "start"
                    elif t == "progress":
                        self.prompt_id = d.get("prompt_id") or self.prompt_id
                        self.node_id = str(d.get("node") or self.node or "")
                        self.value = d.get("value", 0)
                        self.max = max(1, d.get("max", 1))
                        self.last_progress = time.time()
                    elif t == "executing":
                        self.prompt_id = d.get("prompt_id") or self.prompt_id
                        self.node = d.get("node") or ""
            except Exception as e:
                self.connected = False
                self.last_err = str(e)[:200]
                _wlog(f"disconnected: {type(e).__name__} {e}")
                time.sleep(2)


WATCHER = ProgressWatcher()


# ---------------------------------------------------------------- 节点图操作
def first_ns(api, class_type):
    for nid, v in api.items():
        if v["class_type"] == class_type:
            return nid, v
    return None, None


def _set_scalar(api, node, field, value):
    """给节点字段赋值；若该字段是连线，则追到源节点改它的 value。"""
    cur = node["inputs"].get(field)
    if isinstance(cur, list) and len(cur) == 2 and cur[0] in api:
        api[cur[0]]["inputs"]["value"] = value
    else:
        node["inputs"][field] = value


MODES = {
    "01": {"name": "文生视频", "short": "写描述，出画面", "needs": [], "difficulty": "入门", "family": "fl2v"},
    "02": {"name": "图生视频", "short": "一张图让人物动起来", "needs": ["image"], "difficulty": "入门", "family": "fl2v"},
    "03": {"name": "视频参考", "short": "照着视频的动作重画", "needs": ["video"], "difficulty": "进阶", "family": "ref2v"},
    "04": {"name": "角色替换", "short": "把视频里的人换成你的角色", "needs": ["video", "image", "image2"], "difficulty": "进阶", "family": "ref2v"},
    "05": {"name": "姿态控制", "short": "视频驱动动作与角色替换", "needs": ["video", "image"], "difficulty": "实验", "family": "ref2v"},
    "06": {"name": "自然语言替换", "short": "按时间和人物描述替换多个目标", "needs": ["video", "image"], "difficulty": "进阶", "family": "ref2v"},
}

# 模型库：界面里能看到并切换的几类文件
MODEL_DIRS = {
    "unet": ("models/diffusion_models", (".safetensors", ".ckpt", ".pt", ".gguf")),
    "lora": ("models/loras", (".safetensors", ".ckpt", ".pt")),
    "vae": ("models/vae", (".safetensors", ".ckpt", ".pt")),
}


def list_models(kind="unet"):
    """扫描 ComfyUI 的模型目录，返回文件名 + 大小。"""
    rel, exts = MODEL_DIRS.get(kind, MODEL_DIRS["unet"])
    root = os.path.join(comfy_root(), "ComfyUI", rel.replace("/", os.sep))
    out = []
    if not os.path.isdir(root):
        return out
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.endswith(".chunks")]
        for fn in files:
            if not fn.lower().endswith(exts):
                continue
            p = os.path.join(base, fn)
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            if size < 1024 * 1024:  # 跳过占位文件
                continue
            name = os.path.relpath(p, root).replace("\\", "/")
            out.append({"name": name, "size": size,
                        "gb": round(size / 1073741824, 2)})
    out.sort(key=lambda x: -x["size"])
    return out


def models_snapshot():
    """当前生效的模型（配置值或模板默认值）+ 可选列表。"""
    cfgm = dict(DEFAULT_CONFIG["models"])
    cfgm.update(CFG.get("models") or {})
    cur = {}
    for mode in ("01", "02", "03", "04"):
        try:
            api = load_template(mode)
        except Exception:
            continue
        for _, v in api.items():
            if v["class_type"] == "UNETLoader":
                cur.setdefault("unet_" + MODES[mode]["family"], v["inputs"]["unet_name"])
            if v["class_type"] == "LoraLoaderModelOnly":
                nm = v["inputs"].get("lora_name", "")
                if "character_swap" in nm:
                    cur.setdefault("lora_swap", nm)
                elif "turbo" in nm:
                    cur.setdefault("lora_" + MODES[mode]["family"], nm)
    return {
        "selected": cfgm,
        "effective": cur,
        "files": {k: list_models(k) for k in MODEL_DIRS},
    }


def load_template(mode):
    with open(os.path.join(RES_DIR, "templates", f"{mode}.json"), encoding="utf-8") as f:
        return json.load(f)


def _step_prims(api):
    """找出步数分流用的两个 PrimitiveInt：(turbo 分支, 高质量分支)。"""
    for _, v in api.items():
        if v["class_type"] != "ComfySwitchNode":
            continue
        a, b = v["inputs"].get("on_true"), v["inputs"].get("on_false")
        if isinstance(a, list) and isinstance(b, list):
            na, nb = api.get(a[0]), api.get(b[0])
            if na and nb and na["class_type"] == "PrimitiveInt" and nb["class_type"] == "PrimitiveInt":
                return na, nb
    return None, None


def _next_id(api):
    m = 0
    for k in api:
        try:
            m = max(m, int(k))
        except (TypeError, ValueError):
            pass
    return str(m + 1)


def _ref_count(api, nid):
    """外部还有多少输入引用着这个节点。"""
    n = 0
    for a, v in api.items():
        if a == nid:
            continue
        for val in v["inputs"].values():
            if isinstance(val, list) and len(val) == 2 and str(val[0]) == str(nid):
                n += 1
    return n


def _drop_orphan(api, nid):
    if nid in api and _ref_count(api, nid) == 0:
        api.pop(nid, None)


def _pick_images(p):
    """取上传的参考图，兼容老参数 image / image2。"""
    out = [x for x in (p.get("images") or []) if x]
    if not out:
        for k in ("image", "image2"):
            if p.get(k):
                out.append(p[k])
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq[:9]


def _wire_ref_images(api, gen, imgs, ref_size="match"):
    """把参考图接到 ref2va 节点的 ref_images 槽。

    模板里预置的参考图必须整体清掉：否则用户没传图时会继续用模板自带的
    角色脸，传了 1 张时又会残留模板的第 2 张，人物长相被悄悄污染。
    """
    for k in [k for k in list(gen["inputs"]) if k.startswith("ref_images.")]:
        old = gen["inputs"].pop(k)
        if isinstance(old, list) and len(old) == 2:
            _drop_orphan(api, str(old[0]))
    for i, path in enumerate(imgs):
        nid = _next_id(api)
        api[nid] = {"class_type": "LoadImage", "inputs": {"image": path}}
        gen["inputs"][f"ref_images.ref_image_{i}"] = [nid, 0]
    if imgs:
        gen["inputs"]["ref_image_size"] = ref_size or "match"


def _pic_range(a, b):
    if a == b:
        return "<Picture %d>" % a
    return "<Picture %d>–<Picture %d>" % (a, b)


def _snap_scail_frames(n):
    """SCAIL-2 的 length 必须是 4n+1（65/81/97…），否则时间维对不齐。"""
    n = max(33, min(193, int(n)))
    return (n // 4) * 4 + 1


def _scail_canvas(w, h):
    """SCAIL-2（14B nvfp4）在 16G 卡上的现实画布：短边 ≤ 512，32 对齐。"""
    if min(w, h) > 512:
        k = 512.0 / min(w, h)
        w, h = int(w * k), int(h * k)
    w = max(256, min(1024, (w // 32) * 32))
    h = max(256, min(1024, (h // 32) * 32))
    return w, h


def _h3_canvas(w, h):
    """H3 latent patchify 需要宽高落在安全的 32 像素网格。"""
    def safe(v):
        v = max(32, int(v or 32))
        return max(32, int((v + 16) // 32) * 32)
    return safe(w), safe(h)


def _build_scail(p):
    """⑤ 的 SCAIL-2 路线：SAM3 遮罩跟踪 + 端到端角色替换。

    与 Wan-Animate 的本质区别：它靠 SAM3 把「驱动视频里的人」和「参考图里的人」
    分割成彩色部位遮罩做对应，所以**构图跟随驱动视频**，参考图只负责长相和衣服。
    实测 5 分钟出 4 秒，动作逐帧贴合、全身构图稳定。
    """
    api = load_template("07")
    imgs = _pick_images(p)
    char = imgs[0] if imgs else ""
    if char:
        api["9"]["inputs"]["image"] = char
    if p.get("video"):
        api["12"]["inputs"]["file"] = p["video"]

    w, h = _scail_canvas(int(p.get("width") or 512), int(p.get("height") or 896))
    frames = _snap_scail_frames(int(p.get("frames") or 65))
    api["21"]["inputs"].update(width=w, height=h, length=frames)
    api["14"]["inputs"]["length"] = frames

    text = (p.get("prompt") or "").strip()
    quality = (p.get("quality") or "").strip()
    if quality:
        text = (text + "\n\n" + quality).strip()
    if text:
        api["6"]["inputs"]["text"] = text

    if p.get("seed") not in (None, ""):
        try:
            api["24"]["inputs"]["noise_seed"] = int(p["seed"])
        except (TypeError, ValueError):
            pass

    steps = int(p.get("steps") or 6)
    steps = max(4, min(30, steps))
    api["22"]["inputs"]["steps"] = steps
    # 蒸馏 LoRA 在 cfg=1 下最稳；步数少时更明显
    api["24"]["inputs"]["cfg"] = 1.0 if steps <= 8 else 1.5
    try:
        sstr = float(p.get("swap_str") or 1.0)
    except (TypeError, ValueError):
        sstr = 1.0
    api["2"]["inputs"]["strength_model"] = max(0.0, min(2.0, sstr))
    api["27"]["inputs"]["filename_prefix"] = f"H3影栈/07_SCAIL_{p.get('tag') or 'run'}"
    return api


def _build_wan(p):
    """⑤ 的 Wan-Animate 2 路线：角色图 + 驱动视频（16fps）→ 动作/表情迁移。

    H3 是"软参考"，Wan-Animate 是专门训练的动作迁移，动作更贴；代价是 16fps 原生、
    没有原生音频，需要事后补帧并挂原片音轨。
    """
    api = load_template("06")
    imgs = _pick_images(p)
    char = imgs[0] if imgs else ""
    if char:
        api["9"]["inputs"]["image"] = char
    if p.get("video"):
        api["11"]["inputs"]["file"] = p["video"]

    w = int(p.get("width") or 480)
    h = int(p.get("height") or 832)
    # Wan-Animate 14B 在 16G 卡上跑不动大画布：短边统一压到 480，保持比例并 16 对齐
    if min(w, h) > 480:
        k = 480.0 / min(w, h)
        w, h = int(w * k), int(h * k)
    w = max(256, min(1280, (w // 16) * 16))
    h = max(256, min(1280, (h // 16) * 16))
    frames = int(p.get("frames") or 81)
    frames = max(17, min(241, frames))
    api["14"]["inputs"].update(width=w, height=h, length=frames)

    text = (p.get("prompt") or "").strip()
    quality = (p.get("quality") or "").strip()
    if quality:
        text = (text + "\n\n" + quality).strip()
    if text:
        api["6"]["inputs"]["text"] = text

    if p.get("seed") not in (None, ""):
        try:
            api["18"]["inputs"]["noise_seed"] = int(p["seed"])
        except (TypeError, ValueError):
            pass
    steps = int(p.get("steps") or 6)
    api["17"]["inputs"]["steps"] = max(4, min(20, steps))
    api["23"]["inputs"]["filename_prefix"] = f"H3影栈/06_Wan_{p.get('tag') or 'run'}"
    return api


def _augment_prompt(prompt, imgs, has_video_ref, keyframe=False, guide=False, char_count=None):
    """把 <Picture i> / <Video 1> 显式写进提示词。

    H3 的图是按「顺序编号」进文本编码器的，提示词里不点名，模型就容易只
    照抄参考视频、忽略上传的图。界面上角色图和场景图是分两个框传的，
    合起来送模型时角色在前、场景在后，这里按 char_count 分段指认。
    """
    extra = []
    low = prompt.lower()
    n = len(imgs)
    if n and "<picture" not in low:
        nc = n if char_count is None else max(0, min(int(char_count), n))
        if keyframe:
            extra.append("以 <Picture 1> 作为视频的第 1 帧，人物长相、发型、服装、构图和机位都以它为准。")
        else:
            if nc == 1:
                extra.append("人物长相、发型、服装和配饰以 <Picture 1> 为准。")
            elif nc > 1:
                extra.append("人物长相、发型、服装和配饰以 %s 为准（同一角色的不同角度）。" % _pic_range(1, nc))
            if n > nc:
                extra.append("场景、背景环境、光线与色调以 %s 为准。" % _pic_range(nc + 1, n))
    if has_video_ref and "<video" not in low:
        extra.append("动作节奏、关键时间点、镜头距离和构图参考 <Video 1>。")
    elif guide:
        # ④换人：原片不是以 <Video 1> 进模型的，而是首帧 + 音轨作 guide
        extra.append("景别、机位、镜头运动和光线方向都与原片保持一致，动作节奏跟着原片走。")
    if (has_video_ref or guide) and imgs:
        extra.append("不要沿用原片里那个人的长相和穿着。")
    if not extra:
        return prompt
    if not prompt:
        return "\n".join(extra)
    return prompt.rstrip() + "\n\n" + "\n".join(extra)


def build_api(mode, p):
    """按界面参数生成待提交的 API 图。"""
    if mode == "05" and (p.get("engine") or "h3") == "scail":
        return _build_scail(p)
    if mode == "05" and (p.get("engine") or "h3") == "wan":
        return _build_wan(p)
    imgs = _pick_images(p)
    char_count = p.get("char_count")
    if char_count is None:
        char_count = len(imgs)
    # ②图生视频：只有角色图 -> fl2v 首帧路线；同时给了场景图 -> ref2v「角色进场景」路线
    need_scene = int(char_count) < len(imgs)
    # 自然语言替换同时提供角色和场景时，默认使用 ref2v + AddGuide。
    # 05v 的整段源视频参考会强烈保留源人物外观，适合动作/表情跟随，
    # 不适合作为角色替换默认路线。只有显式指定 natural_route=video 时才启用。
    tpl = "05v" if (mode == "06" and p.get("natural_scene") and p.get("natural_route") == "video") else (
        "04" if mode == "06" else ("02r" if (mode == "02" and (need_scene or len(imgs) > 1)) else mode))
    # ⑤姿态控制：
    #   默认 AddGuide（锚定首帧+音轨）——动作逐帧最稳，但脸容易定格；
    #   勾了「表情跟随」走 ref_videos 整段参考（05v）——表情/眼神/嘴型都跟原片，背景也更容易换。
    if mode == "05":
        tpl = "05v" if p.get("express") else "05g"
    api = load_template(tpl)
    gen_id, gen = first_ns(api, "MiniMaxH3ImageToVideo")
    if gen is None:
        gen_id, gen = first_ns(api, "MiniMaxH3ReferenceToVideo")

    is_ref = bool(gen and gen["class_type"] == "MiniMaxH3ReferenceToVideo")
    has_video_ref = bool(gen and any(k.startswith("ref_videos.") for k in gen["inputs"]))
    has_guide = bool(gen and p.get("video")
                     and any(v["class_type"] == "MiniMaxH3AddGuide" for v in api.values()))

    action = (p.get("prompt") or "").strip()
    quality = (p.get("quality") or "").strip()
    prompt = _augment_prompt(action, imgs, has_video_ref, keyframe=not is_ref,
                             guide=has_guide, char_count=char_count)
    if mode == "06":
        groups = p.get("target_groups") or []
        parts = [action or "保持源视频动作、镜头和场景，只替换指定目标人物。"]
        cursor = 1
        for index, group in enumerate(groups[:2], 1):
            count = max(1, len(group.get("images") or []))
            end = cursor + count - 1
            ref = _pic_range(cursor, end)
            parts.append(f"参考图 {ref} 对应自然语言中说明的用途。它可以用于人物、场景、物体或光线参考，不要擅自改变用户指定的用途。")
            cursor = end + 1
        parts.append("严格保留自然语言要求中指定要保留的其他人物、物体、背景和镜头运动，只替换自然语言要求中指定的人物或场景。")
        parts.append("保持自然的人体结构、手指、脚和跨帧脸眼一致。")
        parts.append("如果自然语言要求用某张参考图替换场景或背景，就重建该参考图指定的场景，清除源场景中的水印和原有背景元素。")
        prompt = "\n".join(parts)
    # ⑤ 没传场景图时，明确要求沿用原片背景，避免模型自由发挥把白棚换掉
    if mode == "05" and p.get("express"):
        has_scene = len(imgs) > int(char_count)
        if not has_scene:
            prompt = prompt.rstrip() + ("\n\n背景、机位和光线方向保持参考视频里的原样，"
                                        "不要更换场景、不要新增物体。")
    if quality:
        prompt = (prompt + "\n\n" + quality).strip()
    if prompt:
        if gen is not None and isinstance(gen["inputs"].get("prompt"), str):
            gen["inputs"]["prompt"] = prompt
        else:
            sid, sn = first_ns(api, "PrimitiveStringMultiline")
            if sn is not None:
                sn["inputs"]["value"] = prompt

    w = int(p.get("width") or 640)
    h = int(p.get("height") or 1120)
    frames = int(p.get("frames") or 124)
    # ⑤ 姿态控制对画布尺寸敏感：骨架线太细会被 VAE 压没，控制直接失效。
    # 短边不低于 448（实测 256 宽完全不动、512 宽动作才跟得上）。
    if mode == "05" and min(w, h) < 448:
        k = 448.0 / min(w, h)
        w = int(round(w * k / 32.0) * 32)
        h = int(round(h * k / 32.0) * 32)
    if gen:
        _set_scalar(api, gen, "width", w)
        _set_scalar(api, gen, "height", h)
        _set_scalar(api, gen, "length", frames)

    # 步数 / turbo：步数由 BasicScheduler.steps 上游的 ComfySwitchNode 决定，
    # on_true 是 turbo 分支（4 步），on_false 是高质量分支（20 步）。
    turbo = bool(p.get("turbo", True))
    steps = int(p.get("steps") or (4 if turbo else 20))
    t_prim, h_prim = _step_prims(api)
    if turbo and t_prim is not None:
        t_prim["inputs"]["value"] = steps
    if not turbo and h_prim is not None:
        h_prim["inputs"]["value"] = steps
    bid, bn = first_ns(api, "PrimitiveBoolean")
    if bn is not None:
        bn["inputs"]["value"] = turbo

    # 随机种子：填了就固定，留空保持模板里的随机值
    seed = p.get("seed")
    if seed not in (None, ""):
        try:
            seed = int(seed)
        except (TypeError, ValueError):
            seed = None
        if seed is not None:
            for n in api.values():
                if n["class_type"] == "RandomNoise":
                    n["inputs"]["noise_seed"] = seed

    # 模型选择：界面里选过就覆盖模板默认值
    fam = MODES.get(mode, {}).get("family", "fl2v")
    sel = dict(DEFAULT_CONFIG["models"])
    sel.update(CFG.get("models") or {})
    unet = (p.get("unet") or sel.get("unet_" + fam) or "").strip()
    lora = (p.get("lora") or sel.get("lora_" + fam) or "").strip()
    swap = (sel.get("lora_swap") or "").strip()
    for _, v in api.items():
        ct = v["class_type"]
        if ct == "UNETLoader" and unet:
            v["inputs"]["unet_name"] = unet
        elif ct == "LoraLoaderModelOnly":
            nm = str(v["inputs"].get("lora_name") or "")
            if "character_swap" in nm and swap:
                v["inputs"]["lora_name"] = swap
            elif "turbo" in nm and lora:
                v["inputs"]["lora_name"] = lora

    # 参考图：ref2v 走 ref_images（角色 + 场景可多张）；fl2v 只有首帧一个槽
    if is_ref:
        _wire_ref_images(api, gen, imgs, p.get("ref_size") or "match")
    elif imgs:
        lid, ln = first_ns(api, "LoadImage")
        if ln is not None:
            ln["inputs"]["image"] = imgs[0]
    # 源视频
    if p.get("video"):
        vid, vn = first_ns(api, "LoadVideo")
        if vn is not None:
            vn["inputs"]["file"] = p["video"]

    # ⑤ 换人 LoRA 强度（1.0 标准；角色没换干净时加到 1.15~1.3）
    if mode in ("05", "06"):
        try:
            sstr = float(p.get("swap_str") or (1.15 if mode == "06" else 1.0))
        except (TypeError, ValueError):
            sstr = 1.0
        sstr = max(0.0, min(2.0, sstr))
        for n in api.values():
            if n["class_type"] == "LoraLoaderModelOnly" and "character_swap" in str(n["inputs"].get("lora_name")):
                n["inputs"]["strength_model"] = sstr

    # 音轨跟随：保持 24fps
    cid, cn = first_ns(api, "CreateVideo")
    if cn is not None:
        cn["inputs"]["fps"] = 24

    # 输出名
    sid, sn = first_ns(api, "SaveVideo")
    tag = p.get("tag") or time.strftime("%Y%m%d_%H%M%S")
    if sn is not None:
        sn["inputs"]["filename_prefix"] = f"H3影栈/{tag}"
    return api


# ComfyUI 只把 progress / executing 这类执行事件发给「提交任务时的 client_id」，
# 所以提交与 WebSocket 必须用同一个固定 ID，否则进度永远收不到。
CLIENT_ID = "h3studio"


def submit(api):
    res = http_json("/prompt", {"prompt": api, "client_id": CLIENT_ID}, timeout=60)
    if "prompt_id" not in res:
        raise RuntimeError(f"ComfyUI 拒绝任务：{json.dumps(res, ensure_ascii=False)[:400]}")
    return res["prompt_id"]


def history(pid):
    try:
        return http_json(f"/history/{pid}", timeout=10).get(pid)
    except Exception:
        return None


def queue_info():
    try:
        d = http_json("/queue", timeout=6)
        return {"running": len(d.get("queue_running", [])),
                "pending": len(d.get("queue_pending", []))}
    except Exception:
        return {"running": 0, "pending": 0}


def collect_outputs(entry):
    files = []
    for _, out in (entry.get("outputs") or {}).items():
        for key in ("images", "gifs", "videos"):
            for it in out.get(key) or []:
                if it.get("type") == "input":
                    continue
                fn = it.get("filename")
                if fn:
                    sub = it.get("subfolder") or ""
                    files.append(os.path.join(sub, fn).replace("\\", "/"))
    return files


# ---------------------------------------------------------------- ffmpeg
def run_ff(cmd, timeout=3600):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout, creationflags=0x08000000 if os.name == "nt" else 0)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg 失败：" + p.stdout.decode("utf-8", "ignore")[-600:])
    return p.stdout.decode("utf-8", "ignore")


def probe_video(path):
    out = run_ff([ffmpeg_exe().replace("ffmpeg", "ffprobe") if os.path.basename(
        ffmpeg_exe()).lower().startswith("ffmpeg") else "ffprobe",
        "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,nb_frames,r_frame_rate,duration",
        "-show_entries", "format=duration",
        "-of", "json", path])
    d = json.loads(out)
    st = (d.get("streams") or [{}])[0]
    fps_s = st.get("r_frame_rate") or "24/1"
    try:
        num, den = fps_s.split("/")
        fps = float(num) / float(den or 1)
    except Exception:
        fps = 24.0
    nb = st.get("nb_frames")
    dur = float(st.get("duration") or (d.get("format") or {}).get("duration") or 0)
    if not nb or str(nb) == "N/A":
        nb = int(round(dur * fps)) if dur else 0
    return {"width": st.get("width"), "height": st.get("height"),
            "fps": round(fps, 3), "frames": int(nb), "duration": round(dur, 3)}


def cut_segment(src, start_frame, frames, fps, dst):
    """按帧精确切一段（重编码，保证帧数准确）。"""
    t0 = start_frame / fps
    run_ff([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{t0:.4f}", "-i", src, "-frames:v", str(frames),
            "-r", "24", "-an", "-c:v", "libx264", "-crf", "16",
            "-pix_fmt", "yuv420p", dst])


def cut_segment_time(src, t0, dur, dst):
    """按时间切段并统一到 24fps —— 无论源片多少帧率，时间轴都和原片对齐。"""
    run_ff([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
            "-i", src, "-ss", f"{max(0.0, t0):.4f}", "-t", f"{dur:.4f}",
            "-r", "24", "-an", "-c:v", "libx264", "-crf", "16",
            "-pix_fmt", "yuv420p", dst])


def snap_frames(f):
    """把帧数吸附到模型要求的 17k+5 网格（124/141/…/243/260/…）。"""
    if f <= 22:
        return 22
    k = max(1, (int(f) - 5) // 17)
    return 17 * k + 5


def concat_with_overlap(seg_paths, overlap, fps, out_path, audio_src=None):
    """拼接分段：非首段丢弃前面重叠的帧，最后挂回原音轨。

    overlap 可以是 int（每段相同）或 list（按节拍切段时每段重叠不同）。
    """
    inputs, filters, labels = [], [], []
    for i, p in enumerate(seg_paths):
        inputs += ["-i", p]
        if i == 0:
            skip = 0
        else:
            skip = overlap[i - 1] if isinstance(overlap, (list, tuple)) else overlap
        filters.append(f"[{i}:v]trim=start_frame={skip},setpts=PTS-STARTPTS,"
                       f"fps=24,format=yuv420p[v{i}]")
        labels.append(f"[v{i}]")
    graph = ";".join(filters) + f";{''.join(labels)}concat=n={len(labels)}:v=1:a=0[vout]"
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y"] + inputs
    if audio_src:
        cmd += ["-i", audio_src]
        graph += f";[vout]copy[vf]"
        cmd += ["-filter_complex", graph, "-map", "[vf]", "-map", f"{len(seg_paths)}:a:0?",
                "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-shortest", out_path]
    else:
        cmd += ["-filter_complex", graph, "-map", "[vout]",
                "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", out_path]
    run_ff(cmd)


# ---------------------------------------------------------------- 上传
def save_upload(name, b64):
    raw = base64.b64decode(b64.split(",")[-1])
    safe = re.sub(r"[^0-9A-Za-z_.\-]", "_", name or "file")
    fn = f"h3studio_{int(time.time())}_{uuid.uuid4().hex[:6]}_{safe}"
    path = os.path.join(UPLOAD_DIR, fn)
    with open(path, "wb") as f:
        f.write(raw)
    return path


def stage_asset(path, sub="h3studio"):
    """把素材复制进 ComfyUI 的 input 目录，返回 ComfyUI 侧相对路径。"""
    d = os.path.join(comfy_input(), sub)
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, os.path.basename(path))
    shutil.copy2(path, dst)
    return f"{sub}/{os.path.basename(path)}"


def prep_assets(p):
    """把界面传来的本地素材路径转成 ComfyUI input 下的相对路径。"""
    q = dict(p)
    for key in ("image", "image2", "video"):
        v = q.get(key)
        if v and os.path.isabs(v) and os.path.exists(v):
            q[key] = stage_asset(v)
    staged = []
    for v in (q.get("images") or []):
        if v and os.path.isabs(v) and os.path.exists(v):
            staged.append(stage_asset(v))
        elif v:
            staged.append(v)
    if staged:
        q["images"] = staged
    return q


# ---------------------------------------------------------------- 任务引擎
TASKS = {}
TASK_ORDER = []
TASK_LOCK = threading.RLock()
JOB_QUEUE = queue.Queue()


def new_task(mode, title, params):
    params = dict(params)
    if params.get("engine") == "h3_pipeline":
        params.setdefault("pipeline_models", dict(CFG.get("models") or {}))
        if params.get("seed") in (None, ""):
            params["seed"] = uuid.uuid4().int % (2 ** 32)
        if params.get("repair_segments"):
            params.setdefault("repair_token", uuid.uuid4().hex)
        resume = params.get("resume_work")
        if resume:
            with TASK_LOCK:
                for existing in TASKS.values():
                    work = existing.get("work_dir") or existing.get("params", {}).get("resume_work")
                    if (work and os.path.normcase(os.path.abspath(work)) == os.path.normcase(os.path.abspath(resume))
                            and existing.get("status") in ("queued", "running")):
                        return existing
    tid = uuid.uuid4().hex[:8]
    t = {"id": tid, "mode": mode, "title": title, "params": params,
         "status": "queued", "progress": 0, "stage": "排队中",
         "created": time.time(), "started": None, "finished": None,
         "files": [], "error": "", "eta": estimate_seconds(mode, params),
         "elapsed": 0}
    with TASK_LOCK:
        TASKS[tid] = t
        TASK_ORDER.insert(0, tid)
    JOB_QUEUE.put(tid)
    return t


def task_list():
    now = time.time()
    out = []
    with TASK_LOCK:
        for i in TASK_ORDER:
            t = dict(TASKS[i])
            if t.get("started") and not t.get("finished"):
                t["elapsed"] = int(now - t["started"])
            out.append(t)
    return out


def task_get(tid):
    with TASK_LOCK:
        t = TASKS.get(tid)
        return dict(t) if t else None


def _upd(tid, **kw):
    with TASK_LOCK:
        t = TASKS.get(tid)
        if t:
            t.update(kw)


# 平均耗时（秒），用于估算剩余时间
COST = {"01": 660, "02": 660, "03": 700, "04": 1560, "05": 700}


def fmt_dur(sec):
    sec = int(max(0, sec))
    if sec < 60:
        return f"{sec} 秒"
    m, s = divmod(sec, 60)
    if m < 60:
        return f"{m} 分 {s:02d} 秒" if s else f"{m} 分钟"
    h, m = divmod(m, 60)
    return f"{h} 小时 {m} 分"


def estimate_seconds(mode, p):
    """按分辨率 / 帧数 / 步数粗估一次生成要多久（秒）。"""
    if mode == "04":
        frames = int(p.get("frames") or 243)
        return max(120, 26 * 60 * (frames / 243))
    w = int(p.get("width") or 640)
    h = int(p.get("height") or 1120)
    frames = int(p.get("frames") or 124)
    steps = int(p.get("steps") or 4)
    px = (w * h) / (640 * 1120)
    return max(60, 660 * (px ** 0.85) * (frames / 124) * ((steps / 4) ** 0.72))


def queue_detail(pid=None):
    """查这个任务在 ComfyUI 队列里的位置：running / 前面还有几个。"""
    try:
        d = http_json("/queue", timeout=6)
    except Exception:
        return {"ok": False, "running": False, "pos": 0}
    run = d.get("queue_running") or []
    pend = d.get("queue_pending") or []
    for it in run:
        if pid and len(it) > 1 and it[1] == pid:
            return {"ok": True, "running": True, "pos": 0}
    for i, it in enumerate(pend):
        if pid and len(it) > 1 and it[1] == pid:
            return {"ok": True, "running": False, "pos": i + 1}
    return {"ok": True, "running": False, "pos": 0, "missing": bool(pid)}


def _wait_prompt(pid, tid, base_pct=0, span=100, est=None, mode=""):
    """等待 ComfyUI 执行完一个 prompt，期间持续刷新进度。

    进度有两个来源：WebSocket 的 progress 事件（精确步数），以及队列 + 预计
    耗时的兜底估算。WebSocket 掉线时也不会再出现「一直 0%」。
    """
    t0 = time.time()
    est = int(est or COST.get(mode, 660))
    limit = max(1200, est * 4)
    gone = 0
    while True:
        t = task_get(tid)
        if t and t["status"] == "canceled":
            try:
                http_json("/interrupt", {}, timeout=8)
            except Exception:
                pass
            raise RuntimeError("已取消")
        h = history(pid)
        if h and ((h.get("status") or {}).get("completed") or h.get("outputs")):
            return h
        if h and (h.get("status") or {}).get("status_str") == "error":
            msg = ""
            for m in h["status"].get("messages", []):
                if m and m[0] == "execution_error":
                    msg = (m[1] or {}).get("exception_message", "")
            raise RuntimeError("生成失败：" + (msg or "未知错误")[:400])

        el = time.time() - t0
        v, mx = WATCHER.value, WATCHER.max
        ratio = (v / mx) if mx else 0
        same = (WATCHER.prompt_id == pid) or (not WATCHER.prompt_id)
        # 一次生成分两段：先加载模型/算首帧，再逐步采样。真实步数到达前只允许
        # 走到 LOAD 这一小段，避免「估算冲到 80% 又掉回 25%」的倒退观感。
        LOAD = 0.18
        prev = float(t.get("progress") or 0) if t else 0.0
        if mx and ratio > 0 and same:
            pct = base_pct + (LOAD + (1 - LOAD) * ratio) * span
            stage = f"采样中 {v}/{mx} 步 · 已用 {fmt_dur(el)}"
            eta = int(el / ratio - el) if ratio > 0.02 else 0
        else:
            q = queue_detail(pid)
            r = min(LOAD, el / max(60, est))
            if not q.get("ok"):
                pct = base_pct
                stage = f"引擎连接中断，正在重连… · 已等 {fmt_dur(el)}"
                eta = 0
            elif q.get("running"):
                pct = base_pct + r * span
                stage = f"加载模型 / 计算首帧 · 已用 {fmt_dur(el)}"
                eta = int(max(0, est - el))
            elif q.get("pos"):
                pct = base_pct
                stage = f"排队中，前面还有 {q['pos']} 个任务 · 已等 {fmt_dur(el)}"
                eta = 0
            else:
                gone += 1
                pct = base_pct + r * span
                stage = f"生成中 · 已用 {fmt_dur(el)}"
                eta = int(max(0, est - el))
                if gone > 24:
                    raise RuntimeError(
                        "任务从 ComfyUI 队列里消失了（可能被手动中断或引擎重启过），请重新提交")
        pct = max(pct, prev)
        _upd(tid, progress=round(min(99, pct), 1), stage=stage, eta=eta, elapsed=int(el))
        if el > limit:
            raise RuntimeError(f"超过 {fmt_dur(limit)} 仍未完成，已放弃（可查看引擎日志）")
        time.sleep(1.5)


def _run_one(tid, api, tag, mode="", params=None, base_pct=0, span=100):
    WATCHER.reset()
    pid = submit(api)
    est = estimate_seconds(mode or "02", params or {})
    _upd(tid, status="running", started=time.time(), prompt_id=pid,
         stage=f"已交给引擎，预计 {fmt_dur(est)}", eta=est)
    entry = _wait_prompt(pid, tid, base_pct=base_pct, span=span, est=est, mode=mode)
    return collect_outputs(entry or {})


def _worker():
    while True:
        tid = JOB_QUEUE.get()
        t = task_get(tid)
        if not t or t["status"] == "canceled":
            continue
        try:
            _upd(tid, status="running", started=time.time(), stage="准备中")
            if not online():
                _upd(tid, stage="引擎未启动，正在拉起 ComfyUI…")
                r = start_comfy(block=True)
                if not r.get("online"):
                    raise RuntimeError(r.get("msg") or "ComfyUI 未能启动，请检查设置里的路径")
                _upd(tid, stage="引擎已就绪，开始生成")
            mode = t["mode"]
            p = dict(t["params"])
            stamp = time.strftime("%m%d_%H%M%S")

            if mode == "04":
                _run_swap(tid, p, stamp)
            elif mode == "06":
                _run_natural(tid, p, stamp)
            elif mode == "05" and p.get("engine") == "h3_pipeline":
                import pose_pipeline
                pose_pipeline.run(sys.modules[__name__], tid, p, stamp)
            elif mode == "05" and (p.get("engine") or "h3") == "scail":
                _run_scail(tid, p, stamp)
            elif mode == "05" and (p.get("engine") or "h3") == "wan":
                _run_wan(tid, p, stamp)
            elif mode == "05" and p.get("segment"):
                _run_refseg(tid, p, stamp)
            else:
                p["tag"] = f"{mode}_{stamp}"
                p = prep_assets(p)
                api = build_api(mode, p)
                files = _run_one(tid, api, p["tag"], mode, p)
                _upd(tid, stage="导出成品")
                out_files = _export(files, mode, stamp, p.get("export_name"))
                if p.get("keep_audio") and p.get("video"):
                    _upd(tid, stage="挂原音轨")
                    _mux_original_audio(out_files, p["video"])
                _upd(tid, status="done", progress=100, stage="完成",
                     files=out_files, finished=time.time(), eta=0)
        except Exception as e:
            if (task_get(tid) or {}).get("status") == "canceled":
                continue
            _upd(tid, status="error", error=str(e)[:500], stage="失败",
                 finished=time.time(), eta=0)


def _run_natural_single(tid, p, stamp):
    """自然语言多目标替换：裁切时间范围，绑定两组角色参考图后运行 H3。"""
    src = p.get("video_abs") or ""
    if not src or not os.path.isfile(src):
        raise RuntimeError("源视频不存在，请重新选择")
    groups = p.get("target_groups") or []
    if not groups or any(not (g.get("images") or []) for g in groups):
        raise RuntimeError("请至少上传一组目标人物参考图")
    if any(not (g.get("description") or "").strip() for g in groups):
        raise RuntimeError("请填写每个目标人物的画面描述")
    info = probe_video(src)
    duration = float(info.get("duration") or 0)
    try:
        start = max(0.0, float(p.get("time_start") or 0))
        end = min(duration, float(p.get("time_end") or duration))
    except (TypeError, ValueError):
        raise RuntimeError("时间范围格式不正确")
    if end <= start:
        raise RuntimeError("结束时间必须大于开始时间")
    requested = max(22, int(round((end - start) * 24)))
    frames = snap_frames(requested)
    actual_end = min(duration, start + frames / 24.0)
    frames = max(22, int(round((actual_end - start) * 24)))
    frames = snap_frames(frames)
    actual_end = min(duration, start + frames / 24.0)
    if frames < 22:
        raise RuntimeError("时间范围太短，至少需要约 1 秒")
    work = os.path.join(DATA_DIR, "work", f"{tid}_natural")
    os.makedirs(work, exist_ok=True)
    crop = os.path.join(work, "source-range.mp4")
    _upd(tid, stage=f"准备时间范围 {start:.2f}–{actual_end:.2f} 秒", progress=2)
    run_ff([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{start:.4f}", "-i", src, "-t", f"{actual_end-start:.4f}",
            "-map", "0:v:0", "-map", "0:a:0?",
            "-vf", "fps=24,tpad=stop_mode=clone:stop_duration=1",
            "-frames:v", str(frames), "-r", "24",
            "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-af", "apad", "-t", f"{frames/24.0:.4f}", crop])
    staged_video = stage_asset(crop, sub=f"h3studio/{tid}_natural")
    refs = []
    staged_groups = []
    for group in groups[:2]:
        current = []
        for image in group.get("images") or []:
            staged = stage_asset(image, sub=f"h3studio/{tid}_natural")
            refs.append(staged)
            current.append(staged)
        staged_groups.append({"description": group["description"], "images": current})
    pp = dict(p)
    natural_w, natural_h = _h3_canvas(int(p.get("width") or 832), int(p.get("height") or 480))
    pp.update({"video": staged_video, "images": refs, "target_groups": staged_groups,
               "natural_scene": len(staged_groups) > 1,
               "natural_route": p.get("natural_route") or "reference",
               "char_count": 0, "frames": frames, "width": int(p.get("width") or 832),
               "height": int(p.get("height") or 480), "tag": f"06_{stamp}",
               "ref_size": p.get("ref_size") or "max"})
    pp["width"], pp["height"] = natural_w, natural_h
    api = build_api("06", pp)
    est = estimate_seconds("04", {"frames": frames, "width": 832, "height": 480,
                                  "steps": int(p.get("steps") or 4)})
    _upd(tid, stage=f"H3 多目标替换中 · {start:.2f}–{actual_end:.2f} 秒", progress=4, eta=est)
    entry = _run_one(tid, api, pp["tag"], "04", pp)
    files = [x for x in entry if x.lower().endswith(".mp4")]
    if not files:
        raise RuntimeError("自然语言替换没有生成视频")
    _upd(tid, stage="导出自然语言替换结果", progress=94)
    outputs = _export(files, "06", stamp, p.get("export_name") or "06_自然语言替换")
    if p.get("keep_audio", True):
        _mux_original_audio(outputs, staged_video)
    shutil.rmtree(work, ignore_errors=True)
    _upd(tid, status="done", progress=100, stage="完成",
         files=outputs, finished=time.time(), eta=0)


def _run_natural_two_phase(tid, p, stamp):
    """一键两阶段替换：先重拍场景，再只替换人物。"""
    src = p.get("video_abs") or ""
    groups = p.get("target_groups") or []
    if not src or not os.path.isfile(src):
        raise RuntimeError("源视频不存在，请重新选择")
    if len(groups) < 2 or any(not (g.get("images") or []) for g in groups[:2]):
        raise RuntimeError("两阶段模式需要角色参考图和场景参考图")
    if any(not (g.get("description") or "").strip() for g in groups[:2]):
        raise RuntimeError("请填写角色和场景参考图用途")

    info = probe_video(src)
    duration = float(info.get("duration") or 0)
    try:
        start = max(0.0, float(p.get("time_start") or 0))
        end = min(duration, float(p.get("time_end") or duration))
    except (TypeError, ValueError):
        raise RuntimeError("时间范围格式不正确")
    if end <= start:
        raise RuntimeError("结束时间必须大于开始时间")
    requested = max(22, int(round((end - start) * 24)))
    frames = snap_frames(requested)
    actual_end = min(duration, start + frames / 24.0)
    frames = max(22, int(round((actual_end - start) * 24)))
    frames = snap_frames(frames)
    actual_end = min(duration, start + frames / 24.0)
    if frames < 22:
        raise RuntimeError("时间范围太短，至少需要约 1 秒")

    work = os.path.join(DATA_DIR, "work", f"{tid}_natural_two_phase")
    os.makedirs(work, exist_ok=True)
    crop = os.path.join(work, "source-range.mp4")
    _upd(tid, stage=f"准备两阶段时间范围 {start:.2f}–{actual_end:.2f} 秒", progress=2)
    run_ff([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{start:.4f}", "-i", src, "-t", f"{actual_end-start:.4f}",
            "-map", "0:v:0", "-map", "0:a:0?",
            "-vf", "fps=24,tpad=stop_mode=clone:stop_duration=1",
            "-frames:v", str(frames), "-r", "24",
            "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-af", "apad", "-t", f"{frames/24.0:.4f}", crop])
    staged_video = stage_asset(crop, sub=f"h3studio/{tid}_natural_two_phase")

    role_refs = []
    for image in groups[0].get("images") or []:
        role_refs.append(stage_asset(image, sub=f"h3studio/{tid}_natural_two_phase"))
    scene_refs = []
    for image in groups[1].get("images") or []:
        scene_refs.append(stage_asset(image, sub=f"h3studio/{tid}_natural_two_phase"))

    width, height = _h3_canvas(int(p.get("width") or 1280), int(p.get("height") or 720))
    ref_size = p.get("ref_size") or "max"
    common = {
        "video": staged_video, "frames": frames, "width": width, "height": height,
        "steps": int(p.get("steps") or 4), "turbo": bool(p.get("turbo", True)),
        "ref_size": ref_size, "keep_audio": False,
    }

    phase1_prompt = (
        "只执行场景重拍，不替换源视频人物。\n"
        "把源视频的整个环境替换为场景参考图中的屋主海景卧室，真实生成床、床垫、床单、枕头、床头背景、室内光线、遮挡关系、接触阴影和人物与床面的互动。\n"
        "保留源视频人物的外观、动作、姿势、镜头运动、构图、时间节奏和人物与环境的前后关系。清除源场景水印和原有房间物件，但不要改变人物身份。"
    )
    phase1 = dict(common)
    phase1.update({
        "images": scene_refs, "target_groups": [{"description": groups[1]["description"], "images": scene_refs}],
        "natural_scene": True, "natural_route": "video", "char_count": 0,
        "prompt": phase1_prompt, "tag": f"06_{stamp}_phase1_scene",
    })
    api1 = build_api("06", phase1)
    est1 = estimate_seconds("06", phase1)
    _upd(tid, stage="第 1/2 阶段：只替换场景", progress=4, eta=est1)
    entry1 = _run_one(tid, api1, phase1["tag"], "06", phase1, base_pct=4, span=43)
    files1 = [x for x in entry1 if x.lower().endswith(".mp4")]
    if not files1:
        raise RuntimeError("第一阶段场景重拍没有生成视频")
    scene_video = os.path.join(work, "scene-stage.mp4")
    scene_src = os.path.join(comfy_output(), files1[0])
    if not os.path.isfile(scene_src):
        raise RuntimeError("第一阶段输出文件不存在")
    shutil.move(scene_src, scene_video)

    # AddGuide 的输入沿用原视频画布更稳定。第一阶段输出通常已经是目标分辨率，
    # 但 H3 在部分尺寸上会因为引导视频与 latent 网格恰好重合而触发 patchify 形状错误。
    # 先把中间场景片恢复到源视频画布，再由第二阶段按目标分辨率生成。
    guide_video = scene_video
    src_w = int(info.get("width") or 0)
    src_h = int(info.get("height") or 0)
    scene_info = probe_video(scene_video)
    if src_w and src_h and (int(scene_info.get("width") or 0) != src_w
                            or int(scene_info.get("height") or 0) != src_h):
        guide_video = os.path.join(work, "scene-stage-guide.mp4")
        run_ff([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
                "-i", scene_video, "-vf", f"scale={src_w}:{src_h}:flags=lanczos",
                "-r", "24", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", guide_video])
    stage2_video = stage_asset(guide_video, sub=f"h3studio/{tid}_natural_two_phase")
    phase2_prompt = (
        "只替换源视频中的人物为角色参考图中的夏日黑土。\n"
        "人物短黑发、白蓝夏日服装、白蓝宽檐帽、黄色花饰、蓝色凉鞋、脸型和整体身份以角色参考图为准。\n"
        "保留第一阶段已经生成的卧室、床铺、床品、家具、光线、遮挡关系、镜头运动、人物动作、姿势和时间节奏，不重新设计背景，不恢复源视频人物，不添加水印。"
    )
    phase2 = dict(common)
    phase2.update({
        "video": stage2_video, "images": role_refs,
        "target_groups": [{"description": groups[0]["description"], "images": role_refs}],
        "natural_scene": False, "natural_route": "reference", "char_count": 0,
        "prompt": phase2_prompt, "tag": f"06_{stamp}_phase2_role",
    })
    api2 = build_api("06", phase2)
    est2 = estimate_seconds("04", phase2)
    _upd(tid, stage="第 2/2 阶段：只替换人物", progress=50, eta=est2)
    entry2 = _run_one(tid, api2, phase2["tag"], "04", phase2, base_pct=50, span=44)
    files2 = [x for x in entry2 if x.lower().endswith(".mp4")]
    if not files2:
        raise RuntimeError("第二阶段人物替换没有生成视频")
    _upd(tid, stage="导出两阶段成品", progress=95)
    outputs = _export(files2, "06", stamp, p.get("export_name") or "06_两阶段场景人物替换")
    if p.get("keep_audio", True):
        _mux_original_audio(outputs, staged_video)
    shutil.rmtree(work, ignore_errors=True)
    _upd(tid, status="done", progress=100, stage="完成",
         files=outputs, finished=time.time(), eta=0)


def _run_natural(tid, p, stamp):
    """自然语言替换入口，默认一键执行场景重拍后的人物替换。"""
    groups = p.get("target_groups") or []
    if p.get("two_phase", True) and len(groups) >= 2:
        return _run_natural_two_phase(tid, p, stamp)
    return _run_natural_single(tid, p, stamp)


def _run_swap(tid, p, stamp):
    """换人模式：整片自动分段 → 逐段生成 → 拼接 → 挂原音轨。"""
    p = dict(p)
    imgs = []
    for v in (p.get("images") or []):
        if v and os.path.isabs(v):
            imgs.append(stage_asset(v))
        elif v:
            imgs.append(v)
    if not imgs:
        for key in ("image", "image2"):
            if p.get(key) and os.path.isabs(p[key]):
                imgs.append(stage_asset(p[key]))
    p["images"] = imgs
    src_abs = p.get("video_abs")
    if not src_abs or not os.path.exists(src_abs):
        raise RuntimeError("源视频不存在，请重新选择")
    info = probe_video(src_abs)
    dur = float(info.get("duration") or 0)
    total = max(1, int(round(dur * 24)))
    fps = 24
    seg_len = int(p.get("frames") or 243)
    overlap = 49
    step = seg_len - overlap
    starts = list(range(0, max(1, total - overlap), step))
    if len(starts) > 12:
        starts = starts[:12]
    n = len(starts)

    work = os.path.join(DATA_DIR, "work", f"{tid}")
    os.makedirs(work, exist_ok=True)
    segs = []
    for i, s in enumerate(starts):
        tag = f"04_{stamp}_seg{i+1:02d}"
        dst = os.path.join(work, f"src{i+1:02d}.mp4")
        _upd(tid, stage=f"切分视频 {i+1}/{n}")
        seg_frames = snap_frames(min(seg_len, total - s))
        cut_segment_time(src_abs, s / 24.0, seg_frames / 24.0, dst)
        comfy_name = stage_asset(dst)
        pp = dict(p)
        pp["video"] = comfy_name
        pp["frames"] = seg_frames
        pp["tag"] = tag
        api = build_api("04", pp)
        base = i * (100 / n)
        seg_est = estimate_seconds("04", {"frames": seg_frames})
        _upd(tid, stage=f"第 {i+1}/{n} 段生成中 · 本段预计 {fmt_dur(seg_est)}",
             progress=round(base, 1))
        WATCHER.reset()
        pid = submit(api)
        entry = _wait_prompt(pid, tid, base_pct=base, span=100 / n,
                             est=seg_est, mode="04")
        outs = collect_outputs(entry or [])
        if not outs:
            raise RuntimeError(f"第 {i+1} 段没有输出")
        segs.append(os.path.join(comfy_output(), outs[0]))
        _upd(tid, progress=round(base + 100 / n, 1))

    _upd(tid, stage="拼接成片", progress=97)
    final = os.path.join(out_dir(), f"04_换人_{stamp}.mp4")
    concat_with_overlap(segs, overlap, fps, final, audio_src=src_abs)
    shutil.rmtree(work, ignore_errors=True)
    _upd(tid, status="done", progress=100, stage="完成",
         files=[{"name": os.path.basename(final), "path": final, "size": os.path.getsize(final)}],
         finished=time.time(), eta=0)


def _detect_beats(src_abs, max_sec=40.0):
    """粗粒度节拍检测（RMS 起音包络 + 自相关，不依赖第三方库）。

    返回拍点时间列表（秒）。视频没有音轨或检测失败时返回空列表，调用方退回固定步长。
    """
    try:
        import wave
        import numpy as np
        tmp = os.path.join(DATA_DIR, "work", "_beat.wav")
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        run_ff([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-i", src_abs,
                "-t", str(max_sec), "-ac", "1", "-ar", "16000", "-vn", tmp])
        with wave.open(tmp, "rb") as w:
            sr = w.getframerate()
            data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        os.remove(tmp)
        hop, win = 160, 512
        n = 1 + max(0, (len(data) - win) // hop)
        if n < 100:
            return []
        env = np.array([np.sqrt(np.mean(data[i * hop:i * hop + win] ** 2)) for i in range(n)])
        flux = np.maximum(0, np.diff(env))
        flux = (flux - flux.mean()) / (flux.std() + 1e-8)
        ac = np.correlate(flux, flux, mode="full")[len(flux) - 1:]
        lo, hi = int(0.30 / 0.01), min(int(1.20 / 0.01), len(ac) - 1)
        lag = lo + int(np.argmax(ac[lo:hi]))
        thr = flux.mean() + 0.8 * flux.std()
        beats, last = [], -99
        for i in range(1, len(flux) - 1):
            if flux[i] > thr and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1] and i - last >= lag * 0.6:
                beats.append(i * 0.01)
                last = i
        return beats
    except Exception:
        return []


def _beat_aligned_plan(src_abs, total, seg_len, overlap, snap_frames=12):
    """把分段起点吸附到最近拍点，返回 (starts, overlaps)。

    这样接缝落在节拍上，音乐与动作不会错开半拍；拍点不足或没有音轨时退回固定步长。
    """
    stride = seg_len - overlap
    starts = list(range(0, max(1, total - overlap), stride))[:16]
    beats = _detect_beats(src_abs)
    if len(beats) < 4 or len(starts) <= 1:
        return starts, [overlap] * (len(starts) - 1)
    bf = sorted({int(round(b * 24)) for b in beats})
    snapped = [0]
    for st in starts[1:]:
        cand = min(bf, key=lambda f: abs(f - st))
        if abs(cand - st) <= snap_frames and cand > snapped[-1] + 60:
            snapped.append(cand)
        else:
            snapped.append(st)
    # 每段重叠 = 上一段结束 - 本段开始
    overlaps = []
    for i in range(1, len(snapped)):
        ov = snapped[i - 1] + seg_len - snapped[i]
        overlaps.append(max(0, min(ov, seg_len - 48)))
    return snapped, overlaps


def _cut_wan_segment(src, t0, dur, dst, w, h):
    """Wan 用 16fps 输入：按时间切段并缩放到目标尺寸。"""
    run_ff([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{max(0.0, t0):.4f}", "-t", f"{dur:.4f}", "-i", src,
            "-vf", f"fps=16,scale={w}:{h}:flags=lanczos", "-an",
            "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", dst])


def _run_scail(tid, p, stamp):
    """⑤ 的 SCAIL-2 路线：按 65 帧分段 → SAM3 遮罩替换 → 去重叠拼接 → 补帧 24fps → 挂原音轨。

    SCAIL-2 本身是 16fps；输出统一补到 24fps 并挂原片音轨，观感与 H3 路线一致。
    每段独立跑 SAM3 跟踪，遮罩始终来自原始驱动视频，所以跨段身份不会漂。
    """
    p = dict(p)
    imgs = []
    for v in (p.get("images") or []):
        if v and os.path.isabs(v):
            imgs.append(stage_asset(v))
        elif v:
            imgs.append(v)
    p["images"] = imgs

    src_abs = p.get("video_abs")
    if not src_abs or not os.path.exists(src_abs):
        raise RuntimeError("源视频不存在，请重新选择")
    w, h = _scail_canvas(int(p.get("width") or 512), int(p.get("height") or 896))

    info = probe_video(src_abs)
    total16 = max(1, int(round(float(info.get("duration") or 0) * 16)))
    seg_len, overlap = 65, 5
    stride = seg_len - overlap
    starts = list(range(0, max(1, total16 - overlap), stride))[:24]

    work = os.path.join(DATA_DIR, "work", f"{tid}")
    os.makedirs(work, exist_ok=True)
    segs = []
    n = len(starts)
    for i, s0 in enumerate(starts):
        tag = f"05S_{stamp}_seg{i+1:02d}"
        dst = os.path.join(work, f"src{i+1:02d}.mp4")
        _upd(tid, stage=f"切分视频 {i+1}/{n}")
        seg_frames = _snap_scail_frames(min(seg_len, total16 - s0))
        _cut_wan_segment(src_abs, s0 / 16.0, seg_frames / 16.0, dst, w, h)
        comfy_name = stage_asset(dst)

        pp = dict(p)
        pp["engine"] = "scail"
        pp["video"] = comfy_name
        pp["frames"] = seg_frames
        pp["width"], pp["height"] = w, h
        pp["tag"] = tag
        api = build_api("05", pp)

        base = i * (90 / n)
        # 65 帧 6 步实测约 5 分钟（含 SAM3 跟踪），按帧数线性估
        seg_est = max(150, int(seg_frames / 65 * 300))
        _upd(tid, stage=f"第 {i+1}/{n} 段生成中（SCAIL-2 · 本段预计 {fmt_dur(seg_est)}）",
             progress=round(base, 1))
        WATCHER.reset()
        pid = submit(api)
        entry = _wait_prompt(pid, tid, base_pct=base, span=90 / n, est=seg_est, mode="05")
        outs = [f for f in collect_outputs(entry or []) if f.startswith("H3影栈/")]
        if not outs:
            raise RuntimeError(f"第 {i+1} 段没有输出")
        segs.append(os.path.join(comfy_output(), outs[0]))
        _upd(tid, progress=round(base + 90 / n, 1))

    _upd(tid, stage="拼接并补帧到 24fps", progress=94)
    merged = os.path.join(work, "merged.mp4")
    concat_with_overlap(segs, overlap, 16, merged, audio_src=None)
    final = os.path.join(out_dir(), f"05_SCAIL角色替换_{stamp}.mp4")
    vf, out_fps = _out_fps_filter(p, 16)
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-i", merged]
    if p.get("keep_audio", True):
        cmd += ["-i", src_abs, "-map", "0:v", "-map", "1:a?", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-vf", vf, "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", final]
    run_ff(cmd)
    shutil.rmtree(work, ignore_errors=True)
    _upd(tid, status="done", progress=100, stage="完成",
         files=[{"name": os.path.basename(final), "path": final,
                 "size": os.path.getsize(final)}],
         finished=time.time(), eta=0)


def _run_wan(tid, p, stamp):
    """⑤ 的 Wan-Animate 2 路线：16fps 分段生成 → 去重叠拼接 → 补帧到 24fps → 挂原音轨。"""
    p = dict(p)
    imgs = []
    for v in (p.get("images") or []):
        if v and os.path.isabs(v):
            imgs.append(stage_asset(v))
        elif v:
            imgs.append(v)
    p["images"] = imgs

    src_abs = p.get("video_abs")
    if not src_abs or not os.path.exists(src_abs):
        raise RuntimeError("源视频不存在，请重新选择")
    w = max(256, min(1280, (int(p.get("width") or 480) // 16) * 16))
    h = max(256, min(1280, (int(p.get("height") or 832) // 16) * 16))

    info = probe_video(src_abs)
    total16 = max(1, int(round(float(info.get("duration") or 0) * 16)))
    seg_len, overlap = 81, 9
    stride = seg_len - overlap
    starts = list(range(0, max(1, total16 - overlap), stride))[:24]

    work = os.path.join(DATA_DIR, "work", f"{tid}")
    os.makedirs(work, exist_ok=True)
    segs = []
    n = len(starts)
    for i, s0 in enumerate(starts):
        tag = f"05W_{stamp}_seg{i+1:02d}"
        dst = os.path.join(work, f"src{i+1:02d}.mp4")
        _upd(tid, stage=f"切分视频 {i+1}/{n}")
        seg_frames = min(seg_len, total16 - s0)
        _cut_wan_segment(src_abs, s0 / 16.0, seg_frames / 16.0, dst, w, h)
        comfy_name = stage_asset(dst)

        pp = dict(p)
        pp["engine"] = "wan"
        pp["video"] = comfy_name
        pp["frames"] = seg_frames
        pp["width"], pp["height"] = w, h
        pp["tag"] = tag
        api = build_api("05", pp)

        base = i * (90 / n)
        seg_est = max(120, int(seg_frames / 81 * 240))
        _upd(tid, stage=f"第 {i+1}/{n} 段生成中（Wan · 本段预计 {fmt_dur(seg_est)}）",
             progress=round(base, 1))
        WATCHER.reset()
        pid = submit(api)
        entry = _wait_prompt(pid, tid, base_pct=base, span=90 / n, est=seg_est, mode="05")
        outs = [f for f in collect_outputs(entry or []) if f.startswith("H3影栈/")]
        if not outs:
            raise RuntimeError(f"第 {i+1} 段没有输出")
        segs.append(os.path.join(comfy_output(), outs[0]))
        _upd(tid, progress=round(base + 90 / n, 1))

    _upd(tid, stage="拼接并补帧到 24fps", progress=94)
    merged = os.path.join(work, "merged.mp4")
    concat_with_overlap(segs, overlap, 16, merged, audio_src=None)
    final = os.path.join(out_dir(), f"05_Wan动作迁移_{stamp}.mp4")
    vf, out_fps = _out_fps_filter(p, 16)
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-i", merged]
    if p.get("keep_audio", True):
        cmd += ["-i", src_abs, "-map", "0:v", "-map", "1:a?", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-vf", vf, "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", final]
    run_ff(cmd)
    shutil.rmtree(work, ignore_errors=True)
    _upd(tid, status="done", progress=100, stage="完成",
         files=[{"name": os.path.basename(final), "path": final,
                 "size": os.path.getsize(final)}],
         finished=time.time(), eta=0)


def _run_refseg(tid, p, stamp):
    """⑤ 整段模式：长视频自动分段 → 逐段参考生成（表情跟随）→ 去重叠拼接 → 挂原音轨。

    复用 04 的分段/拼接工具，区别是把每段喂给 05 的参考图路线（ref_videos），
    角色图与场景图逐段复用，保证跨段的身份和背景一致。
    """
    p = dict(p)
    imgs = []
    for v in (p.get("images") or []):
        if v and os.path.isabs(v):
            imgs.append(stage_asset(v))
        elif v:
            imgs.append(v)
    p["images"] = imgs

    src_abs = p.get("video_abs")
    if not src_abs or not os.path.exists(src_abs):
        raise RuntimeError("源视频不存在，请重新选择")
    info = probe_video(src_abs)
    total = max(1, int(round(float(info.get("duration") or 0) * 24)))
    seg_len = int(p.get("frames") or 243)
    overlap = 49
    starts, overlaps = _beat_aligned_plan(src_abs, total, seg_len, overlap)
    n = len(starts)
    if n <= 1:
        raise RuntimeError("视频太短，直接选 5 秒或 10 秒即可")

    work = os.path.join(DATA_DIR, "work", f"{tid}")
    os.makedirs(work, exist_ok=True)
    segs = []
    for i, s0 in enumerate(starts):
        tag = f"05_{stamp}_seg{i+1:02d}"
        dst = os.path.join(work, f"src{i+1:02d}.mp4")
        _upd(tid, stage=f"切分视频 {i+1}/{n}")
        seg_frames = snap_frames(min(seg_len, total - s0))
        cut_segment_time(src_abs, s0 / 24.0, seg_frames / 24.0, dst)
        comfy_name = stage_asset(dst)

        pp = dict(p)
        pp["video"] = comfy_name
        pp["frames"] = seg_frames
        pp["width"] = p.get("width")
        pp["height"] = p.get("height")
        pp["tag"] = tag
        api = build_api("05", pp)
        base = i * (100 / n)
        seg_est = estimate_seconds("05", {"frames": seg_frames, "width": pp.get("width"),
                                          "height": pp.get("height"), "steps": p.get("steps") or 4})
        _upd(tid, stage=f"第 {i+1}/{n} 段生成中 · 本段预计 {fmt_dur(seg_est)}",
             progress=round(base, 1))
        WATCHER.reset()
        pid = submit(api)
        entry = _wait_prompt(pid, tid, base_pct=base, span=100 / n, est=seg_est, mode="05")
        outs = [f for f in collect_outputs(entry or []) if f.startswith("H3影栈/")]
        if not outs:
            raise RuntimeError(f"第 {i+1} 段没有输出")
        segs.append(os.path.join(comfy_output(), outs[0]))
        _upd(tid, progress=round(base + 100 / n, 1))

    _upd(tid, stage="拼接成片", progress=97)
    final = os.path.join(out_dir(), f"05_姿态控制_{stamp}.mp4")
    concat_with_overlap(segs, overlaps, 24, final,
                        audio_src=src_abs if p.get("keep_audio", True) else None)
    shutil.rmtree(work, ignore_errors=True)
    _upd(tid, status="done", progress=100, stage="完成",
         files=[{"name": os.path.basename(final), "path": final,
                 "size": os.path.getsize(final)}],
         finished=time.time(), eta=0)


def _export(files, mode, stamp, export_name=""):
    """把 ComfyUI 输出搬运到成品目录，返回给前端的文件信息。

    用「移动」而不是「复制」：默认 out_dir 就是 ComfyUI 的 H3影栈 输出目录，
    复制会让同一个视频留下两份（原文件 + 改名副本），看起来像超分产物。
    """
    res = []
    for f in files:
        src = os.path.join(comfy_output(), f)
        if not os.path.exists(src):
            continue
        base = (export_name or "").strip() or f"{mode}_{stamp}"
        if not base.lower().endswith(".mp4"):
            base += ".mp4"
        dst = os.path.join(out_dir(), base)
        i = 1
        while os.path.exists(dst):
            dst = os.path.join(out_dir(), base[:-4] + f"_{i}.mp4")
            i += 1
        if os.path.normcase(os.path.normpath(dst)) == os.path.normcase(os.path.normpath(src)):
            # 目标就是原文件本身（极少见的命名重合），直接沿用
            pass
        else:
            shutil.move(src, dst)
        res.append({"name": os.path.basename(dst), "path": dst,
                    "size": os.path.getsize(dst)})
    if not res:
        raise RuntimeError("没有找到输出文件")
    return res


def _out_fps_filter(p, src_fps):
    """按「输出帧率」生成 ffmpeg 滤镜串。

    模型原生帧率固定（SCAIL-2/Wan 16fps、H3 24fps），要高帧率只能插帧：
    - 目标 <= 源：直接 fps 重采样（只是标记/丢帧，零成本）
    - 目标 > 源：minterpolate 运动补偿插帧（实测 512x896 每 4 秒约 18 秒）
    """
    try:
        want = int(p.get("out_fps") or 60)
    except (TypeError, ValueError):
        want = 60
    want = max(12, min(120, want))
    if want <= src_fps:
        return f"fps={want},format=yuv420p", want
    vf = (f"minterpolate=fps={want}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
          f"format=yuv420p")
    return vf, want


def _mux_original_audio(out_files, video_rel):
    """「使用原音频」：用源视频的原音轨替换模型生成的音轨。

    05/03 这类以视频为驱动的模式，H3 会自己编一段音频；用户要求口型/节奏贴原片时，
    直接把源视频的音轨盖上去更稳（模式 04 在分段流程里已经这么做过）。
    """
    src = os.path.join(comfy_input(), str(video_rel).replace("\\", "/"))
    if not os.path.isfile(src):
        return
    for f in out_files:
        dst = f.get("path") or ""
        if not dst.lower().endswith(".mp4") or not os.path.isfile(dst):
            continue
        tmp = dst[:-4] + "_mux.mp4"
        try:
            run_ff([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
                    "-i", dst, "-i", src, "-map", "0:v", "-map", "1:a?",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", tmp])
            os.replace(tmp, dst)
            f["size"] = os.path.getsize(dst)
        except Exception:
            try:
                os.remove(tmp)
            except Exception:
                pass


def cancel_task(tid):
    task = task_get(tid) or {}
    _upd(tid, status="canceled", stage="已取消", finished=time.time())
    if task.get("params", {}).get("engine") == "h3_pipeline":
        # Only interrupt this task's active prompt; preserve other users' ComfyUI jobs.
        pid = task.get("prompt_id")
        if pid:
            try:
                detail = http_json("/queue", timeout=8)
                if any(item[1] == pid for item in detail.get("queue_running", [])):
                    http_json("/interrupt", {}, timeout=8)
                elif any(item[1] == pid for item in detail.get("queue_pending", [])):
                    http_json("/queue", {"delete": [pid]}, timeout=8)
            except Exception:
                pass
        return {"ok": True}
    try:
        http_json("/interrupt", {}, timeout=8)
    except Exception:
        pass
    return {"ok": True}


def boot():
    WATCHER.start()
    threading.Thread(target=_worker, daemon=True).start()
