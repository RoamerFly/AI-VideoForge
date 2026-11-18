import os, sys, subprocess, time
sys.path.insert(0, "app")
import core
print("引擎在线:", core.online(3), flush=True)
if not core.online(3):
    core.start_comfy(block=True)
    print("启动后在线:", core.online(30), flush=True)
else:
    print("已在运行", flush=True)
