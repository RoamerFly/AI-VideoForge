import json,shutil,subprocess
from pathlib import Path
root=Path(r"E:\Agent\projects\freetime_AI_Video_Comfyui")
d=root/"experiments/natural-language-hutao-kurotsuchi-20261118"
state=json.loads((d/"task-current.json").read_text(encoding="utf-8"))
src=Path(state["files"][0]["path"])
dst=d/"夏日黑土_胡桃坐姿抬腿_卧室场景_480p.mp4"
shutil.copy2(src,dst)
meta=json.loads(subprocess.check_output([r"E:\A-Environment\FFmpeg\bin\ffprobe.exe","-v","error","-count_frames","-show_entries","stream=codec_type,width,height,r_frame_rate,nb_read_frames,duration,start_time","-of","json",str(dst)],text=True))
report={"source":r"E:\Agent\projects\AI视频模板\胡桃坐姿抬腿.mp4","character_reference":r"E:\Agent\projects\freetime_AI_Draw\角色工坊库\角色库\夏日黑土\参考图","scene_reference":r"E:\Agent\projects\freetime_AI_Draw\角色工坊库\公共素材\场景\S22-屋主海景卧室\S22-BED_主卧_01-前视-朝北.png","workflow":"自然语言替换 + H3 05v 视频参考路线","range_seconds":[0,8],"resolution":"480p vertical 480x832","audio":"source audio reused","scene_result":"卧室、床、床头、枕头和接触关系生成，源水印与原房间消失","quality_note":"动作和场景通过，角色衣装/脸部有少量跨帧生成变化，未做超分"}
(d/"检查报告-v2.json").write_text(json.dumps({"report":report,"technical":meta},ensure_ascii=False,indent=2),encoding="utf-8")
print(dst)
