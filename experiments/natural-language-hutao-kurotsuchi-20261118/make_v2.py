from pathlib import Path
p=Path(r"E:\Agent\projects\freetime_AI_Video_Comfyui\experiments\natural-language-hutao-kurotsuchi-20261118\run_test.py")
s=p.read_text(encoding="utf-8").replace("title=\"夏日黑土 · 卧室场景 · 480p\"","title=\"夏日黑土 · 卧室场景 · 480p · 05v\"")
p.with_name("run_scene_test_v2.py").write_text(s,encoding="utf-8")
