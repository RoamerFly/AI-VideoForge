import cv2, json, numpy as np
from pathlib import Path
p=Path(r"E:\Agent\projects\freetime_AI_Video_Comfyui\experiments\hinata-video-guide-full-20261118")
v=p/"宗师雏田_申鹤扭身舞_MiniMaxH3_原灰棚_34秒.mp4"
cap=cv2.VideoCapture(str(v)); n=0; black=[]; edge=[]; blue=[]; mean=[]
while True:
    ok, frame=cap.read()
    if not ok: break
    n+=1
    if frame.mean()<8: black.append(n-1)
    e=np.concatenate((frame[:,15:65],frame[:,-65:-15]),1).astype(np.float32)
    edge.append(float(np.abs(e[:,:,0]-e[:,:,1]).mean()+np.abs(e[:,:,1]-e[:,:,2]).mean()))
    b=frame[int(frame.shape[0]*.78):].astype(np.int16)
    blue.append(float(((b[:,:,0]>b[:,:,1]+14)&(b[:,:,0]>b[:,:,2]+8)).mean()))
    mean.append(float(frame.mean()))
cap.release()
metrics={"frames":n,"black_frames":black,"edge_channel_difference_median":float(np.median(edge)),
         "edge_channel_difference_max":float(max(edge)),"bottom_blue_ratio_median":float(np.median(blue)),
         "bottom_blue_ratio_max":float(max(blue)),"frame_mean_min":float(min(mean)),
         "frame_mean_max":float(max(mean)),
         "segment_boundary_indices":[x["frame"] for x in json.loads((p/"接缝.json").read_text(encoding="utf-8"))]}
(p/"画面质量核查.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(metrics,ensure_ascii=False,indent=2))
