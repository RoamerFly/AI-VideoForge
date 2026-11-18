import cv2,json,numpy as np
from pathlib import Path
p=Path(r"E:\Agent\projects\freetime_AI_Video_Comfyui\experiments\hinata-video-guide-full-20261118")
cap=cv2.VideoCapture(str(p/"宗师雏田_申鹤扭身舞_MiniMaxH3_原灰棚_34秒.mp4")); ratios=[]; 
while True:
 ok,f=cap.read()
 if not ok:break
 b=np.concatenate((f[int(f.shape[0]*.78):, :80], f[int(f.shape[0]*.78):, -80:]),1).astype(np.int16)
 ratios.append(float(((b[:,:,0]>b[:,:,1]+14)&(b[:,:,0]>b[:,:,2]+8)).mean()))
cap.release()
d=json.loads((p/"画面质量核查.json").read_text(encoding="utf-8"));d["bottom_corner_blue_ratio_median"]=float(np.median(ratios));d["bottom_corner_blue_ratio_max"]=float(max(ratios));(p/"画面质量核查.json").write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8");print(d["bottom_corner_blue_ratio_median"],d["bottom_corner_blue_ratio_max"])
