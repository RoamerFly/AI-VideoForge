"""CPU-only DWPose keyframe assistance; never a visual/anatomical acceptance score."""
import os
os.environ['OMP_NUM_THREADS']='2'
from pathlib import Path
import sys,json
import numpy as np,cv2,onnxruntime as ort,torch
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[2]
COMFY=ROOT.parent/'freetime_AI_Draw/AI_Draw/ComfyUI-aki/ComfyUI-aki-v3/ComfyUI'
AUX=COMFY/'custom_nodes/comfyui_controlnet_aux'
sys.path.insert(0,str(AUX/'src'))
import custom_controlnet_aux.dwpose.wholebody as module

torch.set_num_threads(2)
options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
original_session=ort.InferenceSession
ort.InferenceSession=lambda path,providers=None:original_session(path,sess_options=options,providers=['CPUExecutionProvider'])
module.get_ort_providers=lambda:['CPUExecutionProvider']
module.get_model_type=lambda *a:'ort'
ckpt=AUX/'ckpts/yzd-v/DWPose'
detector=module.Wholebody(str(ckpt/'yolox_l.onnx'),str(ckpt/'dw-ll_ucoco_384.onnx'),torchscript_device='cpu')
name=sys.argv[1];HERE=Path(__file__).parent
OUT=ROOT.parent/'freetime_AI_Draw/角色工坊库/Temp/宗师雏田视频动作替换-20261118'
frames=[0,12,24,36,48,60,72]
edges=[(1,2),(2,3),(3,4),(1,5),(5,6),(6,7),(1,8),(8,9),(9,10),(1,11),(11,12),(12,13),(8,11)]
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',17)
sheet=Image.new('RGB',(7*216,2*420),(239,242,239));draw=ImageDraw.Draw(sheet)
records=[]
for row in range(2):
    for column,index in enumerate(frames):
        prefix='h3-turbo4' if row==0 else name
        path=HERE/f'{prefix}-r{row}-f{index:03d}.png'
        image=np.asarray(Image.open(path).convert('RGB'));prediction=detector(cv2.cvtColor(image,cv2.COLOR_RGB2BGR))
        points=prediction[0,:18,:3] if prediction is not None else np.zeros((18,3))
        records.append({'kind':'source' if row==0 else 'generated','frame':index,'absolute_source_time':16+index/24,'points_openpose18_xy_confidence':points.tolist()})
        im=Image.fromarray(image).resize((216,384),Image.Resampling.LANCZOS);d=ImageDraw.Draw(im)
        sx=216/image.shape[1];sy=384/image.shape[0]
        for i,j in edges:
            if points[i,2]>.55 and points[j,2]>.55:
                d.line((points[i,0]*sx,points[i,1]*sy,points[j,0]*sx,points[j,1]*sy),fill=(80,255,170),width=2)
        sheet.paste(im,(column*216,row*420+30));draw.text((column*216+5,row*420+4),f'{"源动作" if row==0 else "生成"} {16+index/24:.1f}s',font=font,fill=(20,55,40))
sheet.save(OUT/f'{name}-骨架辅助检查.jpg',quality=94)
(OUT/f'{name}-关键帧骨架.json').write_text(json.dumps({'note':'CPU DWPose辅助，只记录可见高置信关节，背向/遮挡可能误判，不代表人体或动作验收通过','providers':['CPUExecutionProvider'],'records':records},ensure_ascii=False,indent=2),encoding='utf-8')
print('Saved CPU keypoint evidence; no GPU inference was used')
