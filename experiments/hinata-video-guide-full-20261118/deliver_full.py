import shutil,json
from pathlib import Path
root=Path(r"E:\Agent\projects\freetime_AI_Video_Comfyui")
work=root/"experiments/hinata-video-guide-full-20261118"
target=Path(r"E:\Agent\projects\freetime_AI_Draw\角色工坊库\Temp\宗师雏田完整视频-20261118")
target.mkdir(parents=True,exist_ok=True)
src=work/"宗师雏田_申鹤扭身舞_MiniMaxH3_原灰棚_34秒.mp4"
dst=target/src.name
shutil.copy2(src,dst)
report={"方案":"MiniMax H3 Ref2VA + AddGuide + Character Swap LoRA",
"角色参考":"宗师雏田_参考01_全身_正面.png","身份参考":"宗师雏田_参考05_头部_正面.png",
"源动作":"申鹤站立扭身舞.mp4","背景":"角色参考图原有灰棚，未做独立场景替换或后景合成",
"原音轨":"复制源片AAC，音频包SHA256一致","输出":str(dst),
"技术结果":json.loads((work/"完整性核验.json").read_text(encoding="utf-8")),
"画面检查":json.loads((work/"画面质量核查.json").read_text(encoding="utf-8")),
"人工抽查":["开头抬手","约17.8秒转身背面","约28秒双臂上举","约31.7秒侧身收臂","全片脸眼0.5秒采样","13个接缝前后帧"],
"通过项":["826帧完整解码","24fps时间线","无黑帧","音视频起点为0","源AAC包一致","灰棚边角无明显蓝地纹"],
"仍需人工留意":["部分手指和衣摆会随生成帧产生细微变化","脸眼清晰度受576x1024原生输出限制，部分侧脸偏软","背景是H3生成后的稳定灰棚观感，不是逐像素锁定"]}
(work/"完整视频交付检查.md").write_text("# 宗师雏田完整34秒视频交付检查\n\n"+json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(dst)
