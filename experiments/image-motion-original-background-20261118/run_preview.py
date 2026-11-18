import json
from pathlib import Path
import shutil
import sys
import time
import traceback
from urllib.error import HTTPError

directory = Path(__file__).resolve().parent
sys.path.insert(0, str(directory.parents[1] / "app"))
import core

core.CFG = dict(core.CFG, port=8193, comfy_root=core.DEFAULT_CONFIG["comfy_root"])
api_path = Path(sys.argv[1]) if len(sys.argv) > 1 else next(directory.glob("*_API.json"))
state_path = api_path.with_suffix(".run.json")
api = json.loads(api_path.read_text(encoding="utf-8"))
state = {"api": api_path.name, "port": core.CFG["port"], "status": "starting"}
job_key = f"image-motion:{api_path.stem}"

def save(**fields):
    state.update(fields)
    temporary = state_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(state_path)

try:
    if state_path.exists():
        raise RuntimeError("Run record exists; inspect it before submitting another prompt.")
    save()
    result = core.start_comfy(block=True)
    if not result.get("online"):
        raise RuntimeError(result)
    if not core._proc:
        raise RuntimeError("Experiment port is already in use by another ComfyUI server.")
    save(server_pid=core._proc.pid)
    q = core.http_json("/queue")
    if q["queue_running"] or q["queue_pending"]:
        raise RuntimeError("Experiment queue is not empty.")
    core.WATCHER.start()
    try:
        result = core.http_json("/prompt", {"prompt": api, "client_id": core.CLIENT_ID,
                                          "extra_data": {"experiment": job_key}}, timeout=60)
    except HTTPError as exc:
        raise RuntimeError(exc.read().decode("utf-8", "replace")) from exc
    prompt_id = result["prompt_id"]
    save(status="queued", prompt_id=prompt_id)
    print("prompt", prompt_id, flush=True)
    missing = 0
    while True:
        try:
            history = core.http_json(f"/history/{prompt_id}", timeout=12).get(prompt_id)
            if history:
                break
            q = core.http_json("/queue", timeout=12)
            running = any(row[1] == prompt_id for row in q["queue_running"])
            pending = any(row[1] == prompt_id for row in q["queue_pending"])
            missing = 0 if running or pending else missing + 1
            if missing >= 4:
                raise RuntimeError("Prompt disappeared from both history and queue.")
            save(status="running" if running else "queued", progress={
                "steps": core.WATCHER.value, "total": core.WATCHER.max,
                "node": getattr(core.WATCHER, "node_id", None)})
        except (OSError, TimeoutError) as exc:
            if core._proc.poll() is not None:
                raise RuntimeError(f"ComfyUI exited, code {core._proc.returncode}") from exc
            print(f"Read failed: {exc}", flush=True)
        time.sleep(8)
    api_path.with_suffix(".history.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    if not history["status"]["completed"]:
        raise RuntimeError(history["status"])
    output = next(item for slot in history["outputs"].values()
                  for key in ("images", "videos", "gifs") for item in slot.get(key, [])
                  if item.get("type") == "output" and item["filename"].endswith(".mp4"))
    source = Path(core.comfy_output()) / output["subfolder"] / output["filename"]
    destination = api_path.with_suffix(".mp4")
    shutil.copy2(source, destination)
    save(status="done", output=str(destination), output_bytes=destination.stat().st_size)
    print("done", destination, flush=True)
except Exception as exc:
    if state_path.exists() and state.get("server_pid"):
        save(status="error", error=str(exc))
    traceback.print_exc()
    raise
finally:
    if core._proc and core._proc.poll() is None:
        try:
            remaining = core.http_json("/queue", timeout=8)
            if not remaining["queue_running"] and not remaining["queue_pending"]:
                core.stop_owned()
        except OSError:
            pass
