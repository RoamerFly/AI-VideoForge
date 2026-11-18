from pathlib import Path
import sys,subprocess,json
from PIL import Image,ImageDraw,ImageFont
from run_trial import OUT,HERE,STAGE,core
name=sys.argv[1]
frames=[0,12,24,36,48,60,72]
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',20)
sheet=Image.new('RGB',(7*288,1100),(235,240,237));d=ImageDraw.Draw(sheet)
paths=[STAGE/'drive-73f.mp4',OUT/f'{name}-原音轨.mp4']
for row,path in enumerate(paths):
    for i,frame in enumerate(frames):
        p=HERE/f'{name}-r{row}-f{frame:03d}.png'
        subprocess.run([core.ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-i',str(path),'-vf',f'select=eq(n\,{frame})','-frames:v','1',str(p)],check=True)
        im=Image.open(p).convert('RGB');im.thumbnail((288,512));y=row*550+32
        sheet.paste(im,(i*288,y));d.text((i*288+8,row*550+5),f'{"源动作" if row==0 else "生成"} {16+frame/24:.1f}s',font=font,fill=(20,55,38))
sheet.save(OUT/f'{name}-动作关键帧对照.jpg',quality=96)
subprocess.run([core.ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-i',str(paths[0]),'-i',str(paths[1]),'-filter_complex','[0:v][1:v]hstack=inputs=2[v]','-map','[v]','-map','1:a:0','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','copy','-shortest',str(OUT/f'{name}-左右动作对比.mp4')],check=True)
probe=subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate,nb_frames,start_time','-of','json',str(paths[1])],encoding='utf-8')
(OUT/f'{name}-视频规格.json').write_text(probe,encoding='utf-8')
print('Saved keyframes, side-by-side video, ffprobe evidence')
