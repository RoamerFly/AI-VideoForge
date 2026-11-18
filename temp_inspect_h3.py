import sys,json
sys.path.insert(0,r'E:\Agent\projects\freetime_AI_Video_Comfyui\app')
import core
p={'images':['h3studio/compare/target.png'],'char_count':1,'video':'h3studio/compare/h3_src.mp4','width':640,'height':1120,'frames':73,'steps':20,'turbo':False,'swap_str':1.0,'seed':20261115,'tag':'compare_h3','prompt':'A full body young woman with long straight black hair, wearing the exact red Chinese halter outfit, silver belt, red wrist guards and red boots from <Picture 1>. Preserve the source video dance motion, camera framing and timing. Do not copy the original character appearance.','quality':'full body, sharp details, natural lighting, correct anatomy, consistent identity'}
a=core.build_api('04',p)
for nid,v in a.items(): print(nid,v['class_type'],json.dumps(v.get('inputs',{}),ensure_ascii=False)[:1000])
