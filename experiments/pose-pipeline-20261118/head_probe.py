"""Face-region rendering experiment; no sharpening or face restoration GAN."""
import json,sys,time,uuid,subprocess
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'app'))
import core,pose_pipeline as pp
HQ=ROOT.parent/'freetime_AI_Draw/角色工坊库/Temp/宗师雏田面部原生清晰度核验-20261118-身份主脸'
BASE=HQ/'局部人脸重建';BASE.mkdir(exist_ok=True)
ht=json.loads((HQ/'task-current.json').read_text(encoding='utf-8'));source=Path(ht['files'][0]['path'])
face=Path(ht['params']['images'][1]);plate=Path(ht['work_dir'])/'背景板.png'
core.CFG=dict(core.CFG,out_dir=str(BASE));core.boot();print(core.start_comfy(block=True),flush=True)
haar=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
video=BASE/'face-drive-video-only.mp4';cap=cv2.VideoCapture(str(source));boxes=[];previous=None
cmd=[core.ffmpeg_exe(),'-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s','512x512','-r','24','-i','pipe:0','-an','-c:v','libx264','-crf','12','-pix_fmt','yuv420p',str(video)]
encoder=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000)
try:
 for i in range(72):
  ok,frame=cap.read();assert ok
  h,w=frame.shape[:2];gray=cv2.cvtColor(frame[:int(h*.32)],cv2.COLOR_BGR2GRAY)
  found=haar.detectMultiScale(gray,1.05,3,minSize=(40,40))
  found=[b for b in found if .2*w<b[0]+b[2]/2<.8*w and .04*h<b[1]+b[3]/2<.27*h and b[2]<.3*w]
  if found:
   b=min(found,key=lambda b:abs((b[0]+b[2]/2)/w-.5)+abs((b[1]+b[3]/2)/h-.16))
   current=np.array([b[0]+b[2]/2,b[1]+b[3]/2,max(b[2],b[3])*1.9],dtype=float)
  else:current=previous if previous is not None else np.array([w*.5,h*.17,w*.27])
  current=current if previous is None else previous*.7+current*.3;previous=current
  cx,cy,side=current;patch=cv2.getRectSubPix(frame,(round(side),round(side)),(float(cx),float(cy)))
  patch=cv2.resize(patch,(512,512),interpolation=cv2.INTER_LANCZOS4);encoder.stdin.write(patch.tobytes());boxes.append(current.tolist())
finally:
 encoder.stdin.close();err=encoder.stderr.read();encoder.wait();cap.release()
assert encoder.returncode==0,err
drive=BASE/'face-drive.mp4';core.run_ff([core.ffmpeg_exe(),'-v','error','-y','-i',str(video),'-i',str(source),'-map','0:v:0','-map','1:a:0?','-c:v','copy','-c:a','copy','-t','3',str(drive)])
pp.write_json(BASE/'head-crop-mapping.json',{'source':str(source),'boxes':boxes,'size':512,'fps':24})
params={'engine':'h3_pipeline','video_abs':str(drive),'images':[str(face),str(plate)],'char_count':1,
 'identity_ref_index':1,'width':512,'height':512,'pipeline_duration':3,'steps':4,'turbo':True,
 'seed':20261118,'swap_str':1.15,'ref_size':'max','background_mode':'image','keep_audio':True,
 'prompt':'This is a tight head-and-face region reconstruction. Keep the same head position, size, orientation, expression, eye gaze and mouth motion as the driving crop. The exact adult facial identity, natural eye shape, clear pupils, nose and lips come from Picture 1. Photographic human skin with natural texture. Keep the crop framing locked; no camera movement, no zoom out, no full-body view, no eye enlargement, no painted eyes, no beauty-filter smoothing. Preserve facial anatomy and temporal identity.'}
tid='head-'+uuid.uuid4().hex[:6];core.TASKS[tid]={'id':tid,'status':'running','progress':0,'stage':'准备局部人脸','params':params}
p=pp.Pipeline(core,tid,params,time.strftime('%m%d_%H%M%S'))
try:
 p.initialize();p.generate()
 raw=p.work/'raw/000.mp4';pp.write_json(BASE/'head-result.json',{'file':str(raw),'work':str(p.work),'params':params,'generation_id':p.m['segments'][0]['generation_job']['pid']})
 print('HEAD_CANDIDATE',raw,flush=True)
except Exception as e:
 pp.write_json(BASE/'head-error.json',{'error':str(e),'work':str(p.work)});raise
