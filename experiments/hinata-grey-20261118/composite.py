"""Preserve generated character pixels; use SAM3 masks and the reference-derived grey plate."""
import argparse,json,subprocess
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
from run_trial import HERE,OUT,core,save

a=argparse.ArgumentParser();a.add_argument('name');args=a.parse_args();name=args.name
mask_paths=sorted((OUT/f'{name}-masks').glob('*.png'))
assert len(mask_paths)==73,('Expected exactly 73 masks',len(mask_paths))
source=OUT/f'{name}-原音轨.mp4'
capture=cv2.VideoCapture(str(source));W=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH));H=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
plate=np.asarray(Image.open(OUT/'gray-background-576x1024.png').convert('RGB').resize((W,H),Image.Resampling.LANCZOS)).astype(np.float32)
dest=OUT/f'{name}-固定灰背景-原音轨.mp4'
video_only=HERE/f'{name}-composite-video-only.mp4'
# Encode the complete raw stream before muxing audio. With a live rawvideo pipe,
# -shortest can flush the encoder before its last buffered frames are written.
command=[core.ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r','24','-i','pipe:0','-an','-c:v','libx264','-crf','17','-pix_fmt','yuv420p','-frames:v','73',str(video_only)]
log=(HERE/f'{name}-composite-ffmpeg.log').open('wb');encoder=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=log)
Y,X=np.mgrid[0:H,0:W];records=[];posters=[]
try:
    for index,path in enumerate(mask_paths):
        ok,frame=capture.read();assert ok,('Missing generated frame',index)
        rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB).astype(np.float32)
        mask=np.asarray(Image.open(path).convert('L').resize((W,H),Image.Resampling.BILINEAR)).astype(np.float32)/255
        alpha=cv2.GaussianBlur(mask,(3,3),.55).clip(0,1)
        ys,xs=np.where(mask>.5);assert len(xs)>W*H*.04,('Empty or tiny person mask',index,len(xs))
        # Explicit synthetic soft contact shadow; the backdrop itself stays fixed.
        ground_y=int(ys.max());feet_x=xs[ys>=ground_y-14]
        center=float(np.median(feet_x));radius=float(np.clip((feet_x.max()-feet_x.min())*.65+18,25,95))
        shadow=.13*np.exp(-((X-center)/radius)**2-((Y-(ground_y+2))/8.0)**2)
        background=plate*(1-shadow[:,:,None])
        result=(rgb*alpha[:,:,None]+background*(1-alpha[:,:,None])).clip(0,255).astype(np.uint8)
        encoder.stdin.write(result.tobytes())
        records.append({'frame':index,'foreground_pixels':len(xs),'bbox':[int(xs.min()),int(ys.min()),int(xs.max()+1),ground_y+1],'contact_shadow_center':[center,ground_y+2]})
        if index in [0,12,24,36,48,60,72]:
            Image.fromarray(result).save(HERE/f'{name}-composited-f{index:03d}.png')
            posters.append((index,Image.fromarray(result),Image.fromarray((mask*255).astype(np.uint8))))
finally:
    encoder.stdin.close();capture.release();encoder.wait();log.close()
assert encoder.returncode==0,('ffmpeg failed',encoder.returncode)
subprocess.run([core.ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-i',str(video_only),'-i',str(source),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','copy','-t',str(73/24),str(dest)],check=True)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(dest)],encoding='utf-8'))
video=next(s for s in probe['streams'] if s['codec_type']=='video')
assert int(video['nb_frames'])==73,('Muxed video lost frames',video)
save(OUT/f'{name}-固定灰背景-视频规格.json',probe)
areas=np.array([r['foreground_pixels'] for r in records]);assert areas.min()>.45*np.median(areas),('Possible mask collapse',areas.tolist())
save(OUT/f'{name}-灰底合成记录.json',{'method':'SAM3逐帧人物遮罩+参考01边缘拟合的固定灰背景板+轻微合成接触阴影','background_center_estimated':True,'frames':len(records),'resolution':[W,H],'records':records,'foreground_pixel_policy':'只做遮罩混合，不对角色进行拉伸或换脸','ffmpeg_command':command})
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',19)
sheet=Image.new('RGB',(7*240,900),(238,242,239));d=ImageDraw.Draw(sheet)
for col,(index,im,mask) in enumerate(posters):
    im.thumbnail((240,426));mask=mask.convert('RGB');mask.thumbnail((240,426));sheet.paste(im,(240*col,30));sheet.paste(mask,(240*col,474));d.text((240*col+5,5),f'{16+index/24:.1f}s / 灰底合成',font=font,fill=(20,55,40))
sheet.save(OUT/f'{name}-灰背景与遮罩检查.jpg',quality=95)
print(str(dest))
