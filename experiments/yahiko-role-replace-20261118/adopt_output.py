import shutil,subprocess,json
from pathlib import Path
root=Path(r"E:\Agent\projects\freetime_AI_Video_Comfyui")
d=root/"experiments/yahiko-role-replace-20261118"
comfy=Path(r"E:\Agent\projects\freetime_AI_Draw\AI_Draw\ComfyUI-aki\ComfyUI-aki-v3\ComfyUI")
generated=comfy/"output/video/YahikoRoleReplace/5to8_00001_.mp4"
driver=comfy/"input/yahiko-role-replace-20261118/driver-5to8.mp4"
video=d/"宗师弥彦_5至8秒_H3角色替换_原音轨.mp4"
shutil.copy2(driver,d/"driver-5to8.mp4")
subprocess.run([r"E:\A-Environment\FFmpeg\bin\ffmpeg.exe","-y","-v","error","-i",str(generated),"-i",str(driver),"-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","copy","-movflags","+faststart",str(video)],check=True)
meta=subprocess.check_output([r"E:\A-Environment\FFmpeg\bin\ffprobe.exe","-v","error","-count_frames","-show_entries","stream=codec_type,width,height,r_frame_rate,nb_read_frames,duration,start_time","-of","json",str(video)],text=True)
(d/"技术核验.json").write_text(meta,encoding="utf-8")
(d/"run.json").write_text(json.dumps({"pid":"38585d22-fc39-40c3-a536-75d3d7cf204f","status":"done","output":str(video),"generated":str(generated)},ensure_ascii=False,indent=2),encoding="utf-8")
print(video)
