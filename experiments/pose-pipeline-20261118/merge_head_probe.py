import json,subprocess
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'app'))
import core
HQ=ROOT.parent/'freetime_AI_Draw/角色工坊库/Temp/宗师雏田面部原生清晰度核验-20261118-身份主脸'
BASE=HQ/'局部人脸重建';r=json.loads((BASE/'head-result.json').read_text(encoding='utf-8'));mapping=json.loads((BASE/'head-crop-mapping.json').read_text(encoding='utf-8'))
body=cv2.VideoCapture(mapping['source']);head=cv2.VideoCapture(r['file']);haar=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
out=BASE/'regional-video-only.mp4';log=(BASE/'merge.log').open('wb')
proc=subprocess.Popen([core.ffmpeg_exe(),'-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s','1080x1920','-r','24','-i','pipe:0','-an','-c:v','libx264','-crf','14','-pix_fmt','yuv420p',str(out)],stdin=subprocess.PIPE,stderr=log,creationflags=0x08000000)
Y,X=np.mgrid[0:512,0:512];previous=None;previous_target=None;records=[];gain=1.
def face_box(frame,is_head):
 h,w=frame.shape[:2];roi=frame if is_head else frame[:int(h*.32)]
 found=haar.detectMultiScale(cv2.cvtColor(roi,cv2.COLOR_BGR2GRAY),1.05,3,minSize=(40,40))
 found=[b for b in found if (.2*w<b[0]+b[2]/2<.8*w and ((.15 if is_head else .04)*h < b[1]+b[3]/2 < (.85 if is_head else .27)*h))]
 if not found:return None
 return min(found,key=lambda b:abs((b[0]+b[2]/2)/w-.5)+abs((b[1]+b[3]/2)/h-(.52 if is_head else .17)))
try:
 for i,(cx,cy,side) in enumerate(mapping['boxes']):
  ok,base=body.read();ok2,detail=head.read();assert ok and ok2
  hb=face_box(detail,True);bb=face_box(base,False)
  if bb is not None:
   bx,by,bw,bh=bb;tcx=(bx+bw/2-(cx-side/2))/side*512;tcy=(by+bh/2-(cy-side/2))/side*512;target_size=max(bw,bh)/side*512
   target=np.array([tcx,tcy,target_size])
  else:target=previous_target if previous_target is not None else np.array([256,256,512/1.9])
  target=target if previous_target is None else previous_target*.5+target*.5;previous_target=target
  tcx,tcy,target_size=target
  if hb is not None:
   hx,hy,hw,hh=hb;scale=np.clip(target_size/max(hw,hh),.65,1.5);transform=np.array([scale,tcx-scale*(hx+hw/2),tcy-scale*(hy+hh/2)])
  else:transform=previous if previous is not None else np.array([1,0,0])
  transform=transform if previous is None else previous*.6+transform*.4;previous=transform
  scale,tx,ty=transform;aligned=cv2.warpAffine(detail,np.array([[scale,0,tx],[0,scale,ty]],np.float32),(512,512),flags=cv2.INTER_LANCZOS4,borderMode=cv2.BORDER_REFLECT)
  radius_x=target_size*.45;radius_y=target_size*.54
  oval=(((X-tcx)/radius_x)**2+((Y-tcy-target_size*.04)/radius_y)**2<1).astype(np.float32)
  alpha=cv2.GaussianBlur(oval,(0,0),8).clip(0,1)
  body_hand=np.asarray(Image.open(BASE/'hand-masks/body-hand'/f'{i:05d}.png').convert('L')).astype(np.float32)/255
  body_hand=cv2.resize(cv2.getRectSubPix(body_hand,(round(side),round(side)),(float(cx),float(cy))),(512,512))
  detail_hand=np.asarray(Image.open(BASE/'hand-masks/head-hand'/f'{i:05d}.png').convert('L')).astype(np.float32)/255
  detail_hand=cv2.warpAffine(detail_hand,np.array([[scale,0,tx],[0,scale,ty]],np.float32),(512,512),flags=cv2.INTER_LINEAR)
  occlusion=np.maximum(cv2.dilate(body_hand,np.ones((25,25),np.uint8)),cv2.dilate(detail_hand,np.ones((9,9),np.uint8)))
  alpha*=1-cv2.GaussianBlur(occlusion,(0,0),2).clip(0,1)
  core_region=(((X-tcx)/(target_size*.25))**2+((Y-tcy)/(target_size*.22))**2<1)
  blocked=float((body_hand[core_region]>.4).mean())>.18 if core_region.any() else False
  gain=0. if blocked else min(1.,gain+.2)
  alpha*=gain
  # Match broad colour gently; do not sharpen, restore, or recolour the eyes.
  old=cv2.resize(cv2.getRectSubPix(base,(round(side),round(side)),(float(cx),float(cy))),(512,512))
  skin=(oval>.5)&(aligned[:,:,2]>aligned[:,:,1])&(aligned[:,:,1]>aligned[:,:,0]*.8)
  shift=np.clip(np.median(old[skin].astype(float)-aligned[skin].astype(float),axis=0),-10,10) if skin.any() else np.zeros(3)
  aligned=(aligned.astype(float)+shift).clip(0,255).astype(np.uint8)
  h,w=base.shape[:2];factor=1080/w;newheight=round(h*factor);canvas=cv2.resize(base,(1080,newheight),interpolation=cv2.INTER_LANCZOS4);crop_y=(newheight-1920)//2;canvas=canvas[crop_y:crop_y+1920].copy()
  region_side=round(side*factor);left=round((cx-side/2)*factor);top=round((cy-side/2)*factor)-crop_y
  refined=cv2.resize(aligned,(region_side,region_side),interpolation=cv2.INTER_LANCZOS4);mask=cv2.resize(alpha,(region_side,region_side))
  x0=max(0,left);y0=max(0,top);x1=min(1080,left+region_side);y1=min(1920,top+region_side)
  patch=refined[y0-top:y1-top,x0-left:x1-left];a=mask[y0-top:y1-top,x0-left:x1-left,None]
  canvas[y0:y1,x0:x1]=(patch*a+canvas[y0:y1,x0:x1]*(1-a)).clip(0,255).astype(np.uint8)
  proc.stdin.write(canvas.tobytes());records.append({'frame':i,'head_detected':hb is not None,'body_detected':bb is not None,'occlusion_fallback':blocked,'refinement_gain':gain,'transform':transform.tolist()})
  if i in [0,24,36,48,60,71]:Image.fromarray(cv2.cvtColor(canvas,cv2.COLOR_BGR2RGB)).save(BASE/f'局部合成完整帧-{i}.png')
finally:
 proc.stdin.close();proc.wait();body.release();head.release();log.close()
assert proc.returncode==0
final=BASE/'宗师雏田_3秒_局部人脸重建试验_1080p.mp4'
core.run_ff([core.ffmpeg_exe(),'-v','error','-y','-i',str(out),'-i',mapping['source'],'-map','0:v:0','-map','1:a:0?','-c:v','copy','-c:a','copy','-t','3','-movflags','+faststart',str(final)])
(BASE/'合成记录.json').write_text(json.dumps({'final':str(final),'method':'身体768原生输出按比例放大；脸部512独立生成，经跟踪、缩放平移对齐及椭圆羽化合成；未超分或锐化。','frames':records},ensure_ascii=False,indent=2),encoding='utf-8')
print(final)
