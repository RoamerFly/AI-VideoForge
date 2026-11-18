import json,shutil,subprocess
from pathlib import Path
root=Path(r"E:\Agent\projects\freetime_AI_Video_Comfyui")
out=Path(r"E:\Agent\projects\freetime_AI_Draw\AI_Draw\ComfyUI-aki\ComfyUI-aki-v3\ComfyUI\output\H3影栈\06_自然语言替换.mp4")
d=root/"experiments/natural-language-two-target-20261118";d.mkdir(exist_ok=True)
copy=d/"自然语言替换_双目标_0至10秒.mp4";shutil.copy2(out,copy)
meta=json.loads(subprocess.check_output([r"E:\A-Environment\FFmpeg\bin\ffprobe.exe","-v","error","-count_frames","-show_entries","stream=codec_type,width,height,r_frame_rate,nb_read_frames,duration,start_time","-of","json",str(copy)],text=True))
report={"source":r"C:\Users\RoverFly\Downloads\kling_20261118_作品_保留_视频1_全部动_2630_0.mp4",
"requested_range_seconds":[0,10],"actual_video_seconds":float(next(x for x in meta["streams"] if x["codec_type"]=="video")["duration"]),
"resolution":"832x480","workflow":"mode06 natural language multi-target H3 Ref2VA + AddGuide + Character Swap LoRA",
"target_mapping":[{"description":"花田画面左侧、橙色头发、穿黑色长衣并向右伸手驱赶鸽子的人","role":"宗师雏田"},
{"description":"花田画面右侧、紫色头发、穿黑白服装、站在花田另一侧的人","role":"漂泊佩恩-萝莉道"}],
"technical":meta,
"observation":"任务成功，角色参考按两组送入H3，源场景和动作可见。多人全帧生成暂不能保证每组参考图稳定锁定到指定人物位置。"}
(d/"检查报告.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(copy)
