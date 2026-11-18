import cv2,numpy as np
from pathlib import Path
b=Path(r'compare_exact_20261115')
img=cv2.imread(r'compare_exact_20261115/target_source.png')
m=cv2.imread(str(b/'target_mask.png'),0)
m=cv2.resize(m,(img.shape[1],img.shape[0]),interpolation=cv2.INTER_NEAREST)
m=(m>127).astype(np.uint8)*255
m=cv2.dilate(m,np.ones((9,9),np.uint8),iterations=1)
for r in (3,7,15,25):
 out=cv2.inpaint(img,m,r,cv2.INPAINT_TELEA)
 cv2.imwrite(str(b/f'target_inpaint_r{r}.png'),out)
