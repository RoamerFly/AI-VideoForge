import json,sys
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[2];BASE=Path(__file__).parent
HQ=ROOT.parent/'freetime_AI_Draw/角色工坊库/Temp/宗师雏田面部原生清晰度核验-20261118-身份主脸'
task=json.loads((HQ/'task-current.json').read_text(encoding='utf-8'))
if task['status']!='done':raise RuntimeError('The native quality candidate has not finished')
work=Path(task['work_dir']);candidate=Path(task['files'][0]['path'])
old=json.loads((BASE/'task-current.json').read_text(encoding='utf-8'))
oldnative=Path(old['work_dir'])/'composite/000.mp4';oldsr=Path(old['files'][0]['path'])
face_ref=Path(task['params']['images'][1])
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
haar=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')

def read(path,index):
 cap=cv2.VideoCapture(str(path));cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,bgr=cap.read();cap.release()
 if not ok:raise RuntimeError((path,index))
 return Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB))

def crop(im):
 rgb=np.asarray(im);h,w=rgb.shape[:2]
 gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
 boxes=haar.detectMultiScale(gray[:int(h*.45)],scaleFactor=1.05,minNeighbors=3,minSize=(28,28))
 if len(boxes):
  x,y,bw,bh=min(boxes,key=lambda b:abs((b[0]+b[2]/2)/w-.5)+abs((b[1]+b[3]/2)/h-.13))
  side=max(bw,bh)*1.45;cx=x+bw/2;cy=y+bh/2
 else:
  side=w*.29;cx=w*.5;cy=h*.125
 box=(round(cx-side/2),round(cy-side/2),round(cx+side/2),round(cy+side/2))
 return im.crop(box).resize((256,256),Image.Resampling.LANCZOS),box

ref=Image.open(face_ref).convert('RGB')
# The reference is already a headshot; detect over the whole photo rather than top45%.
boxes=haar.detectMultiScale(cv2.cvtColor(np.asarray(ref),cv2.COLOR_RGB2GRAY),1.05,3,minSize=(80,80))
if len(boxes):
 x,y,w,h=max(boxes,key=lambda b:b[2]*b[3]);side=max(w,h)*1.3;cx=x+w/2;cy=y+h/2
 refcrop=ref.crop((round(cx-side/2),round(cy-side/2),round(cx+side/2),round(cy+side/2))).resize((256,256),Image.Resampling.LANCZOS)
else:refcrop=ref.resize((256,256),Image.Resampling.LANCZOS)
sheet=Image.new('RGB',(4*256,310),(238,240,237));draw=ImageDraw.Draw(sheet)
sheet.paste(refcrop,(0,45));draw.text((5,7),'参考05主脸',font=font,fill='black')
records=[]
for i,(path,title) in enumerate([(oldnative,'576原生 / 4步'),(oldsr,'576生成后超分'),(candidate,'768原生 / 20步')],1):
 image=read(path,36);imagecrop,box=crop(image);sheet.paste(imagecrop,(i*256,45));draw.text((i*256+5,7),title,font=font,fill='black');records.append({'file':str(path),'frame':36,'box':box})
sheet.save(HQ/'主脸对照_参考_旧原生_旧超分_新原生.png')
for page in range(5):
 indices=list(range(page*16,min((page+1)*16,72)))
 if not indices:continue
 sheet=Image.new('RGB',(4*256,((len(indices)+3)//4)*284),(238,240,237));draw=ImageDraw.Draw(sheet)
 for j,index in enumerate(indices):
  imagecrop,box=crop(read(candidate,index));x=j%4*256;y=j//4*284
  sheet.paste(imagecrop,(x,y+27));draw.text((x+5,y+3),f'f{index} / {index/24:.2f}s',font=font,fill='black')
 sheet.save(HQ/f'逐帧人脸核验-{page+1}.png')
read(candidate,36).save(HQ/'原生完整帧_1.5秒.png')
(HQ/'裁切对照记录.json').write_text(json.dumps({'method':'仅裁切与等尺度Lanczos显示，无超分、锐化、修脸或身份替换','records':records},ensure_ascii=False,indent=2),encoding='utf-8')
print(candidate)
