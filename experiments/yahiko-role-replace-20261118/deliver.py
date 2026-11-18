import shutil,json
from pathlib import Path
root=Path(r"E:\Agent\projects\freetime_AI_Video_Comfyui")
work=root/"experiments/yahiko-role-replace-20261118"
src=work/"宗师弥彦_5至8秒_H3角色替换_原音轨.mp4"
dstroot=Path(r"E:\Agent\projects\freetime_AI_Draw\角色工坊库\Temp\生前弥彦视频替换-20261118")
dstroot.mkdir(parents=True,exist_ok=True)
dst=dstroot/src.name
shutil.copy2(src,dst)
report={"source_video":r"C:\Users\RoverFly\Downloads\kling_20261118_作品_保留_视频1_全部动_2630_0.mp4",
"source_range_seconds":[5,8.041667],"target":"画面中央、鸽子心形中的人物",
"reference":r"E:\Agent\projects\freetime_AI_Draw\角色工坊库\角色库\生前弥彦\参考图",
"workflow":"MiniMax H3 Ref2VA + AddGuide + Character Swap LoRA",
"output":str(dst),"resolution":"832x480","frames":73,"fps":24,
"audio":"5秒起原AAC片段","background":"原视频花田、砖墙和鸽子心形",
"visual_check":["源片左右人物未被批量替换","心形鸽群和砖墙保持","中央人物橙色头发、黑红边长外套与弥彦参考一致",
"手部和衣摆仍有H3生成式细节变化","远景人物细节受横屏小人物尺寸限制"]}
(work/"检查报告.md").write_text("# 生前弥彦 5–8 秒视频角色替换检查\n\n"+json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(dst)
