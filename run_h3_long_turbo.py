# -*- coding: utf-8 -*-
"""Run the 8-second MiniMax H3 long-segment verification after the 3-second baseline."""
from __future__ import annotations
import argparse,json,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'app'))
import core
SRC=Path(r'E:\Agent\projects\AI视频模板\申鹤站立扭身舞.mp4')
CHAR=Path(r'E:\Agent\projects\freetime_AI_Draw\角色工坊库\角色库\宗师雏田\图集\通用姿势_单手抬起招呼_宗师雏田_池塘廊桥庭园_池塘廊桥庭园_001.png')
TAG='h3_long8_20261115_t16_turbo4'
START=16.0; DUR=8.0; FPS=24; FRAMES=192; W=640; H=1120
WORK=ROOT/'compare_exact_20261115'/'long8'; WORK.mkdir(parents=True,exist_ok=True)
INPUT_DIR=Path(core.comfy_input())/'h3studio'/TAG; INPUT_DIR.mkdir(parents=True,exist_ok=True)

def run(cmd):
    print('$',' '.join(map(str,cmd)),flush=True); subprocess.run(cmd,check=True)

def stage(background:Path|None):
    target=INPUT_DIR/'target_character.png'; shutil.copy2(CHAR,target)
    src=INPUT_DIR/'h3_src_24fps_640x1120_8s.mp4'
    run([core.ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-ss',f'{START:.6f}','-t',f'{DUR:.6f}','-i',str(SRC),'-vf',f'fps={FPS},scale={W}:{H}:flags=lanczos','-frames:v',str(FRAMES),'-c:v','libx264','-crf','16','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-shortest',str(src)])
    bg_rel=''
    if background:
        bg=INPUT_DIR/'optional_background.png'; shutil.copy2(background,bg); bg_rel=f'h3studio/{TAG}/optional_background.png'
    meta={'source':str(SRC),'character':str(CHAR),'background':str(background) if background else None,'start_sec':START,'duration_sec':DUR,'fps':FPS,'frames':FRAMES,'width':W,'height':H,'video_rel':f'h3studio/{TAG}/{src.name}','target_rel':f'h3studio/{TAG}/target_character.png'}
    (WORK/'inputs.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    return f'h3studio/{TAG}/target_character.png', f'h3studio/{TAG}/{src.name}', bg_rel

def wait(pid):
    t=time.time(); last=0
    while True:
        e=core.history(pid)
        if e:
            st=e.get('status') or {}
            if st.get('status_str')=='error': raise RuntimeError(json.dumps(st,ensure_ascii=False)[:4000])
            if st.get('completed') or e.get('outputs'):
                fs=[f for f in core.collect_outputs(e) if f.startswith('H3影栈/')]
                if not fs: raise RuntimeError('completed without output')
                return fs,time.time()-t
        if time.time()-last>60:
            print('running',round((time.time()-t)/60,1),'min',core.queue_info(),flush=True);last=time.time()
        time.sleep(8)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--background',type=Path,default=None);args=ap.parse_args()
    target,video,bg=stage(args.background)
    imgs=[target]
    prompt=('A full-body young woman with long straight black hair, wearing the exact red and burgundy Chinese halter outfit, silver belt, red arm guards, blue ribbon details and red boots from <Picture 1>. '
            'Preserve the source video dance motion, turning timing, camera framing and full-body composition. '
            'Use the covered wooden bridge, pond and garden environment visible in the character reference as the scene background. '
            'Do not copy the original character face, hair or clothes. Keep the background stable across the segment.')
    if bg:
        imgs.append(bg);prompt+=' Use <Picture 2> as the optional clean background reference while keeping the character identity from <Picture 1>.'
    p={'images':imgs,'char_count':1,'video':video,'width':W,'height':H,'frames':FRAMES,'steps':4,'turbo':True,'swap_str':1.0,'seed':20261115,'tag':TAG,'prompt':prompt,'quality':'full body, natural lighting, sharp details, correct anatomy, consistent identity'}
    api=core.build_api('04',p);(WORK/'h3_api.json').write_text(json.dumps(api,ensure_ascii=False,indent=2),encoding='utf-8')
    pid=core.submit(api);print('prompt_id',pid,flush=True);fs,elapsed=wait(pid);print('done',round(elapsed/60,1),'min',fs,flush=True)
    out=[]
    for f in fs:
        src=Path(core.comfy_output())/f;dst=WORK/(Path(f).name);shutil.copy2(src,dst);out.append(str(dst))
    (WORK/'results.json').write_text(json.dumps({'outputs':out,'elapsed_min':round(elapsed/60,2),'frames':FRAMES,'fps':FPS,'resolution':f'{W}x{H}'},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()

