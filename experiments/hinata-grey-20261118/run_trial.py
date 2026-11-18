"""Local H3 motion/character/background trial using the user's exact front reference."""
from pathlib import Path
import argparse,hashlib,json,shutil,struct,subprocess,sys,time
import requests
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'app'))
import core
BASE=core.base_url()
CHAR=ROOT.parent/'freetime_AI_Draw/角色工坊库/角色库/宗师雏田/参考图/宗师雏田_参考01_全身_正面.png'
SOURCE=ROOT.parent/'AI视频模板/申鹤站立扭身舞.mp4'
OUT=ROOT.parent/'freetime_AI_Draw/角色工坊库/Temp/宗师雏田视频动作替换-20261118'
STAGE=Path(core.comfy_input())/'h3studio/hinata-grey-20261118'

def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def stage():
    STAGE.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    shutil.copy2(CHAR,STAGE/'character.png')
    command=[core.ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-ss','16.0','-i',str(SOURCE),'-vf','fps=24,scale=576:1024:flags=lanczos','-frames:v','73','-c:v','libx264','-crf','16','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-t',str(73/24),str(STAGE/'drive-73f.mp4')]
    subprocess.run(command,check=True)
    meta={'source':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'character':str(CHAR),'character_sha256':hashlib.sha256(CHAR.read_bytes()).hexdigest(),'start_seconds':16.0,'frames':73,'fps':24,'width':576,'height':1024,'character_background':'以用户指定参考01中的灰色棚拍渐变背景为权威，不采用旧庭园或源人物背景','ffmpeg_command':command}
    save(HERE/'inputs.json',meta);save(OUT/'输入与哈希.json',meta)
    shutil.copy2(STAGE/'drive-73f.mp4',OUT/'源动作片段_16秒起_73帧.mp4')

def resolve_weights(g):
    info=requests.get(BASE+'/object_info',timeout=90).json()
    records=[]
    fields={'UNETLoader':('unet_name','diffusion_models'),'CLIPLoader':('clip_name','text_encoders'),'VAELoader':('vae_name','vae'),'LoraLoaderModelOnly':('lora_name','loras')}
    for key,node in g.items():
        if node['class_type'] not in fields:continue
        field,category=fields[node['class_type']];old=node['inputs'][field]
        value=info[node['class_type']]['input']['required'][field]
        options=value[0] if isinstance(value[0],list) else value[1].get('options',[])
        stem=Path(old).stem
        matches=[n for n in options if n.replace('\\','/').split('/')[-1].startswith(stem) and n.endswith('.safetensors')]
        if old in options:matches=[old]
        if len(matches)!=1:raise ValueError((key,old,matches))
        selected=matches[0];node['inputs'][field]=selected
        candidates=[Path('F:/AI_Comfyui模型库/video')/category/selected,ROOT/'release/models'/category/selected]
        path=next((p for p in candidates if p.is_file()),None)
        if path is None:raise FileNotFoundError(candidates)
        with path.open('rb') as f:
            n=struct.unpack('<Q',f.read(8))[0]
            if n>128*1024*1024:raise ValueError('Invalid safetensors header size')
            header=json.loads(f.read(n));f.seek(-min(65536,path.stat().st_size),2);tail=f.read()
            quant_count=0
            for tensor,value in header.items():
                if tensor.endswith('.comfy_quant'):
                    lo,hi=value['data_offsets'];f.seek(8+n+lo);json.loads(f.read(hi-lo).decode('utf-8'));quant_count+=1
        end=max(v['data_offsets'][1] for k,v in header.items() if k!='__metadata__')
        expected=8+n+end
        record={'node':key,'old':old,'selected':selected,'path':str(path),'size':path.stat().st_size,'header_expected_size':expected,'tail_nonzero':sum(v!=0 for v in tail),'valid_quantization_configs':quant_count}
        if expected!=record['size'] or record['tail_nonzero']==0:raise ValueError(('Model integrity warning',record))
        records.append(record)
    save(HERE/'model-path-check.json',records);save(OUT/'模型路径与文件结构检查.json',records)
    missing=sorted({v['class_type'] for v in g.values()}-set(info))
    assert not missing,missing

def submit(name,steps=4,turbo=True,gray_background=False,flat_boots=False,swap_strength=1.0):
    p={'images':['h3studio/hinata-grey-20261118/character.png'],'char_count':1,'video':'h3studio/hinata-grey-20261118/drive-73f.mp4','width':576,'height':1024,'frames':73,'steps':steps,'turbo':turbo,'swap_str':1.0,'seed':20261118,'tag':'hinata-grey-20261118-'+name,
       'prompt':('Replace the person throughout the entire driving clip with the SAME adult woman from <Picture 1>. '
                 'Preserve the complete dance motion and its exact timing: torso twists, shoulder turns, arms, hands, '
                 'hips, knees, steps, head turns, full-body camera and framing. Her face, pale violet eyes, long BLACK '
                 'hair with bangs and the blue hair ribbon, red and burgundy asymmetric mandarin-collar dress, '
                 'silver tiger belt buckle, cyan knots and tassels, red arm guards and burgundy mid-calf boots '
                 'must follow <Picture 1> consistently through front, side and back views. '
                 'Use ONLY the plain soft GREY studio backdrop and grey floor from <Picture 1>. '
                 'Remove the original woman, her silver hair, ornaments, black outfit, long flowing sleeves, '
                 'source watermark, source floor graphic and source studio design. One person, no duplicates. '
                 'Natural photographic skin, physically correct hands and feet, same long-leg body proportions '
                 'as the reference, coherent clothing, stable lighting and background throughout.'),
       'quality':'full body including feet, temporally coherent identity and costume, stable camera, natural anatomy'}
    if gray_background:
        shutil.copy2(OUT/'gray-background-576x1024.png',STAGE/'gray-background.png')
        p['images'].append('h3studio/hinata-grey-20261118/gray-background.png')
        p['prompt']+=' Use <Picture 2> as the empty grey backdrop AND grey floor. No floor graphics, no blue paint, no watermark, no text; the background is a static seamless grey studio.'
    if flat_boots:
        p['prompt']+=' The burgundy mid-calf boots have LOW FLAT CONTINUOUS SOLES, with no elevated separate heel blocks. These are flat martial-arts boots, not the original dancer\'s high-heeled shoes. Preserve normal human foot length and change foot contact naturally for flat boots, keeping the same steps and timing.'
    p['swap_str']=swap_strength
    g=core.build_api('04',p)
    for node in g.values():
        if node['class_type']=='LoraLoaderModelOnly' and 'character_swap' in node['inputs'].get('lora_name',''):
            node['inputs']['strength_model']=swap_strength
    resolve_weights(g)
    guide=[n for n in g.values() if n['class_type']=='MiniMaxH3AddGuide']
    assert len(guide)==1 and guide[0]['inputs'].get('image'), 'All guide frames must be connected'
    save(HERE/f'{name}-api.json',g);save(OUT/f'{name}-实际参数.json',g)
    save(OUT/f'{name}-参数说明.json',p)
    r=requests.post(BASE+'/prompt',json={'prompt':g,'client_id':'hinata-grey-'+name},timeout=60)
    save(HERE/f'{name}-submit.json',r.json());print(r.status_code,r.text,flush=True);r.raise_for_status()

def status(name):
    pid=json.loads((HERE/f'{name}-submit.json').read_text(encoding='utf-8'))['prompt_id']
    entry=requests.get(BASE+'/history/'+pid,timeout=20).json().get(pid)
    if not entry:
        q=requests.get(BASE+'/queue',timeout=10).json()
        print(json.dumps({'prompt_id':pid,'running':[x[1] for x in q['queue_running']],'pending':[x[1] for x in q['queue_pending']]}));return
    save(HERE/f'{name}-result.json',entry);save(OUT/f'{name}-执行记录.json',entry)
    paths=[]
    for output in entry.get('outputs',{}).values():
        for kind in ['videos','gifs','images']:
            for item in output.get(kind,[]):
                if not item.get('filename','').endswith('.mp4'):continue
                if item.get('type')!='output':continue
                src=Path(core.comfy_output())/item.get('subfolder','')/item['filename']
                dst=OUT/f'{name}-原始输出.mp4';shutil.copy2(src,dst)
                with_audio=OUT/f'{name}-原音轨.mp4'
                subprocess.run([core.ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-i',str(dst),'-ss','16.0','-i',str(SOURCE),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','copy','-t',str(73/24),'-shortest',str(with_audio)],check=True)
                paths.append(str(with_audio))
    print(json.dumps({'prompt_id':pid,'status':entry.get('status'),'paths':paths},ensure_ascii=False))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('action',choices=['stage','submit','status']);a.add_argument('name',nargs='?',default='h3-turbo4');a.add_argument('--steps',type=int,default=4);a.add_argument('--hq',action='store_true');a.add_argument('--gray-background',action='store_true');a.add_argument('--flat-boots',action='store_true');a.add_argument('--swap-strength',type=float,default=1.0);v=a.parse_args()
    if v.action=='stage':stage()
    elif v.action=='submit':submit(v.name,v.steps,not v.hq,v.gray_background,v.flat_boots,v.swap_strength)
    else:status(v.name)
