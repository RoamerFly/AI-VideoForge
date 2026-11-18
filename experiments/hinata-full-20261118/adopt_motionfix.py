import copy,json,shutil
from pathlib import Path
import full_run as f

f.M=json.loads(f.STATE.read_text(encoding='utf-8'));seg=f.M['segments'][3]
folder=f.OUT/'repair';candidate=folder/'seg-003-motionfix-raw.mp4'
f.verify_video(candidate,73)
staged=f.STAGE/'motionfix-generated-003.mp4';shutil.copy2(candidate,staged)
graph=json.loads((f.PREV/'h3-hq20-gray-分割工作流.json').read_text(encoding='utf-8'))
graph['1']['inputs']['file']=f.input_relative(staged)
graph['9']['inputs']['filename_prefix']='hinata-full-20261118/repair/masks-003-motionfix'
f.M['status']='segmenting_motionfix';f.checkpoint()
result=f.execute(graph,seg,'motionfix-seg');paths=list(f.outputs(result,'.png'));assert len(paths)==73
newmasks=folder/'motionfix-masks';newmasks.mkdir(exist_ok=True)
for i,path in enumerate(paths):shutil.copy2(path,newmasks/f'{i:05d}.png')
archive=folder/'seg-003-original';archive.mkdir(exist_ok=True)
f.save(archive/'manifest-before-adoption.json',f.M)
for path,dest in [(f.OUT/'raw/seg-003.mp4',archive/'raw.mp4'),(f.OUT/'grey/seg-003.mp4',archive/'grey.mp4'),(f.OUT/'masks/seg-003',archive/'masks')]:
    assert path.resolve().is_relative_to(f.OUT.resolve()) and dest.resolve().is_relative_to(f.OUT.resolve())
    assert not dest.exists(),str(dest)
    path.rename(dest)
shutil.copy2(candidate,f.OUT/'raw/seg-003.mp4')
shutil.copytree(newmasks,f.OUT/'masks/seg-003')
seg['original_generation_id']=seg['generation_id'];seg['generation_id']=seg['motionfix_id']
seg['generation_adopted_phase']='motionfix';seg['seed_adopted']=20261119
seg['original_segmentation_id']=seg['segmentation_id'];seg['segmentation_id']=seg['motionfix-seg_id']
seg.update(raw=str(f.OUT/'raw/seg-003.mp4'),mask_dir=str(f.OUT/'masks/seg-003'),composite='pending')
f.compose(seg);f.review_segment(Path(seg['grey']),'motionfix-grey-003')
final=Path(f.M['final']);shutil.copy2(final,folder/'complete-before-motionfix.mp4')
f.finish()
f.note('第4段已采用新种子20261119和正面朝向约束返修，移除约10.4秒的背面突变，重做该段SAM3并重拼完整片；待复查全部接缝和完整解码。')
