import cv2, numpy as np
from pathlib import Path
base=Path(r'compare_exact_20261115'); out=base/'bg_plate_work'
vid=str(base/'outputs'/'h3_compare_exact_20261115_t16_h3_00001_.mp4')
cap=cv2.VideoCapture(vid); frames=[]
while True:
 ok,fr=cap.read()
 if not ok: break
 frames.append(fr)
cap.release()
mask_files=sorted(out.glob('h3_short_masks_*.png'))
assert len(frames)==len(mask_files),(len(frames),len(mask_files))
arr=np.stack(frames,axis=0).astype(np.uint16)
ms=np.stack([cv2.imread(str(p),cv2.IMREAD_GRAYSCALE)>127 for p in mask_files],axis=0)
valid=~ms
count=valid.sum(axis=0)
# median over background pixels; use a loop over channels to keep memory bounded
plate=np.zeros(frames[0].shape,dtype=np.uint8)
for c in range(3):
    x=np.where(valid,arr[:,:, :,c],np.nan)
    med=np.nanmedian(x,axis=0)
    med=np.nan_to_num(med,nan=0).astype(np.uint8)
    plate[:,:,c]=med
# low-coverage pixels fall back to first frame, then inpaint only holes.
low=(count<3).astype(np.uint8)*255
plate[low>0]=frames[0][low>0]
# dilate a little to remove mask halos, then inpaint residual missing areas.
hole=cv2.dilate(low,np.ones((9,9),np.uint8),iterations=1)
plate=cv2.inpaint(plate,hole,9,cv2.INPAINT_TELEA)
cv2.imwrite(str(base/'background_plate_h3_640x1120.png'),plate)
# diagnostics
cv2.imwrite(str(base/'background_plate_h3_low_coverage.png'),low)
print('frames',len(frames),'shape',frames[0].shape,'low_pct',round(float((count<3).mean()*100),2),'out',base/'background_plate_h3_640x1120.png')
