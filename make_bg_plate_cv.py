import cv2, numpy as np
from pathlib import Path
from PIL import Image
root=Path(r'E:\Agent\projects\freetime_AI_Video_Comfyui')
img=np.array(Image.open(r'E:\Agent\projects\freetime_AI_Draw\角色工坊库\角色库\宗师雏田\图集\通用姿势_单手抬起招呼_宗师雏田_池塘廊桥庭园_池塘廊桥庭园_001.png').convert('RGB'))[:,:,::-1].copy()
mask=np.array(Image.open(root/'compare_exact_20261115'/'bgmask_compare_exact_20261115_00001_.png').convert('L'))
mask=(mask>20).astype(np.uint8)*255
k=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(11,11)); mask=cv2.dilate(mask,k,iterations=1)
cv2.imwrite(str(root/'compare_exact_20261115'/'target_character_mask_dilated.png'),mask)
for name,method in [('telea',cv2.INPAINT_TELEA),('ns',cv2.INPAINT_NS)]:
    out=cv2.inpaint(img,mask,15,method)
    Image.fromarray(out[:,:,::-1]).save(root/'compare_exact_20261115'/f'background_plate_{name}.png')
