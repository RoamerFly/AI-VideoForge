import json,cv2
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT.parent/'freetime_AI_Draw/角色工坊库/Temp/宗师雏田面部原生清晰度核验-20261118-身份主脸/局部人脸重建'
m=json.loads((BASE/'head-crop-mapping.json').read_text(encoding='utf-8'));r=json.loads((BASE/'合成记录.json').read_text(encoding='utf-8'))
c=cv2.VideoCapture(r['final']);frames=[]
for i in range(72):
 ok,im=c.read();assert ok
 frames.append(Image.fromarray(cv2.cvtColor(im,cv2.COLOR_BGR2RGB)))
assert not c.read()[0];c.release()
factor=1080/768;offset=(round(1376*factor)-1920)//2
for page in range(5):
 ids=list(range(page*16,min((page+1)*16,72)))
 if not ids:continue
 sheet=Image.new('RGB',(4*256,((len(ids)+3)//4)*278),'white');d=ImageDraw.Draw(sheet)
 for j,i in enumerate(ids):
  cx,cy,side=m['boxes'][i];side*=factor;cx*=factor;cy=cy*factor-offset
  crop=frames[i].crop((round(cx-side/2),round(cy-side/2),round(cx+side/2),round(cy+side/2))).resize((256,256),Image.Resampling.LANCZOS)
  x=j%4*256;y=j//4*278;sheet.paste(crop,(x,y+22))
  label=f'f{i}'+(' original:occluded' if r['frames'][i]['occlusion_fallback'] else '')
  d.text((x+5,y+3),label,fill='black')
 sheet.save(BASE/f'局部合成逐帧检查-{page+1}.png')
print('Complete decode:72 frames. Occluded frames:',[x['frame'] for x in r['frames'] if x['occlusion_fallback']])
