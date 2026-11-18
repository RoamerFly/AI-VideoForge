import copy,json,shutil
from pathlib import Path
import full_run as f

f.M=json.loads(f.STATE.read_text(encoding='utf-8'))
seg=f.M['segments'][3]
f.M['status']='repairing_motion_segment_004';f.checkpoint()
folder=f.OUT/'repair';folder.mkdir(exist_ok=True)
graph=json.loads((f.OUT/'api/generation-003.json').read_text(encoding='utf-8'))
graph['129']['inputs']['noise_seed']=20261119
graph['138']['inputs']['value']+='\nSEGMENT-SPECIFIC MOTION REQUIREMENT: throughout this short clip she faces the camera or is in a slight front three-quarter view. Do not invent a full turn. Never show her back in this segment. Follow the driving clip arm gestures and head tilts exactly, while maintaining front-facing shoulders and chest. Preserve the same direction and placement as the original driving dancer on every frame. No extra spin, no rear view, no floating detached strands or sleeves.'
graph['92']['inputs']['filename_prefix']='hinata-full-20261118/repair/seg-003-motionfix'
result=f.execute(graph,seg,'motionfix')
paths=list(f.outputs(result,'.mp4'));assert len(paths)==1
dest=folder/'seg-003-motionfix-raw.mp4';shutil.copy2(paths[0],dest);f.verify_video(dest,73)
f.review_segment(dest,'motionfix-003')
f.M['status']='motionfix_candidate_ready';f.M['current']=None;f.checkpoint()
f.note('完整片10.4秒接缝发现不符合源片的背面转正面突变，定点重做第4段，候选生成后人工抽帧再替换；其他段保留。')
print(dest,flush=True)
