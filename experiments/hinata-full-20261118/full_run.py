"""Resumable complete-video generation, per-segment SAM3, grey compositing and timed stitching."""
from __future__ import annotations
import argparse,copy,hashlib,json,math,os,shutil,subprocess,sys,time,traceback
from datetime import datetime,timezone,timedelta
from pathlib import Path
import cv2,numpy as np,requests,websocket
from PIL import Image,ImageDraw,ImageFont

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'app'))
import core
BASE=core.base_url();FPS=24;W=576;H=1024;LENGTH=73;OVERLAP=12;STRIDE=LENGTH-OVERLAP
PREV=ROOT.parent/'freetime_AI_Draw/角色工坊库/Temp/宗师雏田视频动作替换-20261118'
OUT=ROOT.parent/'freetime_AI_Draw/角色工坊库/Temp/宗师雏田完整视频-20261118'
STATE=OUT/'完整视频运行状态.json'
STAGE=Path(core.comfy_input())/'h3studio/hinata-full-20261118'
SOURCE=ROOT.parent/'AI视频模板/申鹤站立扭身舞.mp4'
CHAR=ROOT.parent/'freetime_AI_Draw/角色工坊库/角色库/宗师雏田/参考图/宗师雏田_参考01_全身_正面.png'
FF=core.ffmpeg_exe();PROBE=str(Path(FF).with_name('ffprobe.exe'))
M={}

def now():return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    for attempt in range(10):
        try:tmp.replace(path);return
        except PermissionError:
            if attempt==9:raise
            time.sleep(.05)
def checkpoint():
    M['updated']=now();save(STATE,M)
def log(message):
    line=f'[{now()}] {message}';print(line,flush=True)
    with (OUT/'运行日志.txt').open('a',encoding='utf-8') as f:f.write(line+'\n')
def note(message):
    with (ROOT/'进度.md').open('a',encoding='utf-8') as f:f.write('\n- 完整片自动记录：'+message+'\n')
def run(command):subprocess.run(list(map(str,command)),check=True,stdout=subprocess.DEVNULL)
def probe(path,count=False):
    command=[PROBE,'-v','error']+(['-count_frames'] if count else [])
    return json.loads(subprocess.check_output(command+['-show_streams','-show_format','-of','json',str(path)],encoding='utf-8'))
def verify_video(path,frames):
    p=probe(path);v=next(s for s in p['streams'] if s['codec_type']=='video')
    assert int(v.get('nb_frames',0))==frames,(str(path),v)
    assert (v['width'],v['height'],v['avg_frame_rate'])==(W,H,'24/1'),v
    return p
def input_relative(path):return path.relative_to(Path(core.comfy_input())).as_posix()

def initialize():
    global M
    OUT.mkdir(parents=True,exist_ok=True);STAGE.mkdir(parents=True,exist_ok=True)
    for folder in ['raw','masks','grey','api','results','review']:(OUT/folder).mkdir(exist_ok=True)
    character_hash=hashlib.sha256(CHAR.read_bytes()).hexdigest();source_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if STATE.exists():
        M=json.loads(STATE.read_text(encoding='utf-8'))
        assert M['character_sha256']==character_hash and M['source_sha256']==source_hash,'Assets changed; do not mix runs'
    else:
        old=json.loads((PREV/'输入与哈希.json').read_text(encoding='utf-8'));assert old['character_sha256']==character_hash
        duration=float(probe(SOURCE)['format']['duration']);total=math.ceil(duration*FPS)
        starts=[0]
        while starts[-1]+LENGTH<total:starts.append(starts[-1]+STRIDE)
        M={'status':'preparing','created':now(),'source':str(SOURCE),'source_sha256':source_hash,'character':str(CHAR),'character_sha256':character_hash,'duration_source':duration,'total_frames':total,'fps':FPS,'size':[W,H],'segment_frames':LENGTH,'overlap':OVERLAP,'steps':4,'turbo':True,'swap_strength':1.15,'seed':20261118,'background':'参考01边缘拟合灰底，中心区域为估计，脚下接触阴影随脚步变化','segments':[{'index':i,'start':s,'valid_frames':min(LENGTH,total-s),'generation':'pending','segmentation':'pending','composite':'pending'} for i,s in enumerate(starts)]}
    M['worker_pid']=os.getpid();checkpoint()
    assert shutil.disk_usage(OUT).free>5*1024**3,'Insufficient working space (need >5GiB)'
    shutil.copy2(CHAR,STAGE/'character.png');shutil.copy2(PREV/'gray-background-576x1024.png',STAGE/'background.png');shutil.copy2(PREV/'gray-background-576x1024.png',OUT/'背景板.png')
    canonical=STAGE/'canonical-24fps.mp4'
    if not canonical.exists():
        log('Preparing the complete 24fps source timeline')
        run([FF,'-hide_banner','-loglevel','error','-y','-i',SOURCE,'-vf',f'fps=24,scale={W}:{H}:flags=lanczos,tpad=stop_mode=clone:stop_duration=0.1','-frames:v',M['total_frames'],'-c:v','libx264','-crf','16','-pix_fmt','yuv420p','-c:a','copy',canonical])
    verify_video(canonical,M['total_frames'])
    for seg in M['segments']:
        path=STAGE/f"drive-{seg['index']:03d}.mp4"
        if not path.exists():
            run([FF,'-hide_banner','-loglevel','error','-y','-ss',f"{seg['start']/FPS:.8f}",'-i',canonical,'-vf','tpad=stop_mode=clone:stop_duration=4','-af','apad=pad_dur=4','-frames:v',LENGTH,'-t',str(LENGTH/FPS),'-c:v','libx264','-crf','16','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k',path])
        verify_video(path,LENGTH);seg['drive']=str(path)
    # Only the known-good, explicitly preserved program models are used for H3.
    checks=json.loads((PREV/'模型路径与文件结构检查.json').read_text(encoding='utf-8'))
    for item in checks:
        path=Path(item['path']);assert path.exists() and path.stat().st_size==item['size'],item
        assert ROOT/'release/models' in path.parents,('Unexpected H3 model origin',path)
    save(OUT/'H3模型来源检查.json',checks)
    if M.get('status')!='complete':M['status']='generating'
    checkpoint();log(f"Prepared {len(M['segments'])} segments, {M['total_frames']} unique timeline frames")

def get_history(pid):return requests.get(BASE+'/history/'+pid,timeout=20).json().get(pid)
def recover_id(client):
    q=requests.get(BASE+'/queue',timeout=15).json()
    for item in q.get('queue_running',[])+q.get('queue_pending',[]):
        if item[3].get('client_id')==client:return item[1]
    history=requests.get(BASE+'/history',params={'max_items':200},timeout=30).json()
    for pid,item in history.items():
        p=item.get('prompt',[])
        if len(p)>3 and p[3].get('client_id')==client:return pid
    return None

def execute(graph,seg,phase):
    index=seg['index'];client=f'hinata-full-20261118-{phase}-{index:03d}'
    api_path=OUT/'api'/f'{phase}-{index:03d}.json';save(api_path,graph)
    connection=None
    try:
        connection=websocket.create_connection(BASE.replace('http:','ws:')+'/ws?clientId='+client,timeout=3);connection.settimeout(.7)
    except Exception:pass
    pid=seg.get(phase+'_id') or recover_id(client)
    if not pid:
        seg[phase]='submitting';checkpoint()
        response=requests.post(BASE+'/prompt',json={'prompt':graph,'client_id':client},timeout=60)
        save(OUT/'results'/f'{phase}-{index:03d}-submit.json',response.json());response.raise_for_status()
        pid=response.json()['prompt_id'];seg[phase+'_id']=pid;checkpoint()
    else:seg[phase+'_id']=pid;checkpoint()
    seg[phase]='running';M['current']={'phase':phase,'segment':index+1,'prompt_id':pid,'step':0,'steps':4 if phase=='generation' else LENGTH};checkpoint()
    log(f'{phase} segment {index+1}/{len(M["segments"])} prompt_id={pid}')
    last_history=0;last_log=0
    try:
        while True:
            if connection:
                try:
                    raw=connection.recv()
                    if isinstance(raw,str):
                        event=json.loads(raw);data=event.get('data',{})
                        if event.get('type')=='executing':M['current']['node']=data.get('node')
                        if event.get('type')=='progress' and (phase!='generation' or str(data.get('node'))=='125'):
                            M['current'].update(step=data.get('value'),steps=data.get('max'));checkpoint()
                except websocket.WebSocketTimeoutException:pass
                except Exception:connection.close();connection=None
            else:time.sleep(1)
            t=time.monotonic()
            if t-last_history>=2:
                try:
                    entry=get_history(pid)
                except requests.RequestException:
                    last_history=t;continue
                last_history=t
                if entry:
                    status=entry.get('status',{});save(OUT/'results'/f'{phase}-{index:03d}.json',entry)
                    if status.get('status_str')=='error':raise RuntimeError(json.dumps(status,ensure_ascii=False)[-8000:])
                    if status.get('completed') and status.get('status_str')=='success':
                        seg[phase]='complete';checkpoint();return entry
            if t-last_log>=30:
                c=M['current'];log(f'{phase} {index+1}: {c.get("step",0)}/{c.get("steps",0)}, node={c.get("node")}');last_log=t
    finally:
        if connection:connection.close()

def outputs(entry,extension):
    for node in entry.get('outputs',{}).values():
        for kind in ['images','videos','gifs']:
            for value in node.get(kind,[]):
                if value.get('type')=='output' and value.get('filename','').endswith(extension):
                    yield Path(core.comfy_output())/value.get('subfolder','')/value['filename']

def review_segment(path,tag):
    capture=cv2.VideoCapture(str(path));sheet=Image.new('RGB',(3*192,370),(238,242,239));draw=ImageDraw.Draw(sheet);font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
    for i,frame in enumerate([0,36,72]):
        capture.set(cv2.CAP_PROP_POS_FRAMES,frame);ok,im=capture.read();assert ok
        image=Image.fromarray(cv2.cvtColor(im,cv2.COLOR_BGR2RGB)).resize((192,341));sheet.paste(image,(192*i,26));draw.text((192*i+4,3),f'{tag} / {frame}',font=font,fill=(20,55,40))
    capture.release();sheet.save(OUT/'review'/f'{tag}.jpg',quality=94)

def generate_all():
    base=json.loads((PREV/'h3-hq20-gray-实际参数.json').read_text(encoding='utf-8'))
    character_id=base['136']['inputs']['ref_images.ref_image_0'][0]
    assert base[character_id]['class_type']=='LoadImage'
    base[character_id]['inputs']['image']=input_relative(STAGE/'character.png')
    # Locate the second role-independent background reference by its graph link.
    background_id=base['136']['inputs']['ref_images.ref_image_1'][0]
    assert base[background_id]['class_type']=='LoadImage'
    base[background_id]['inputs']['image']=input_relative(STAGE/'background.png')
    base['146']['inputs']['value']=True;base['144']['inputs']['value']=4
    base['147']['inputs']['strength_model']=1.15;base['129']['inputs']['noise_seed']=20261118
    assert base['153']['inputs']['value']==LENGTH
    for seg in M['segments']:
        dest=OUT/'raw'/f"seg-{seg['index']:03d}.mp4"
        if dest.exists():verify_video(dest,LENGTH);seg['generation']='complete';seg['raw']=str(dest);checkpoint();continue
        graph=copy.deepcopy(base);graph['150']['inputs']['file']=input_relative(Path(seg['drive']))
        graph['92']['inputs']['filename_prefix']=f"hinata-full-20261118/raw/seg-{seg['index']:03d}"
        result=execute(graph,seg,'generation');files=list(outputs(result,'.mp4'));assert len(files)==1,files
        shutil.copy2(files[0],dest);verify_video(dest,LENGTH);seg['raw']=str(dest);checkpoint();review_segment(dest,f"raw-{seg['index']:03d}")
        note(f"H3完整片第{seg['index']+1}/{len(M['segments'])}段完成，任务{seg['generation_id']}，时间线{seg['start']/FPS:.3f}秒起；输出{dest.name}。")
        log(f"GENERATION COMPLETE {seg['index']+1}/{len(M['segments'])}")
    M['status']='segmenting_and_compositing';checkpoint()

def compose(seg):
    dest=OUT/'grey'/f"seg-{seg['index']:03d}.mp4"
    if dest.exists():verify_video(dest,LENGTH);seg['grey']=str(dest);seg['composite']='complete';checkpoint();return
    masks=sorted(Path(seg['mask_dir']).glob('*.png'));assert len(masks)==LENGTH,len(masks)
    plate=np.asarray(Image.open(OUT/'背景板.png').convert('RGB')).astype(np.float32);Y,X=np.mgrid[0:H,0:W]
    capture=cv2.VideoCapture(seg['raw']);logfile=(HERE/f"encode-{seg['index']:03d}.log").open('wb')
    encoder=subprocess.Popen([FF,'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-an','-c:v','libx264','-crf','17','-pix_fmt','yuv420p','-frames:v',str(LENGTH),str(dest)],stdin=subprocess.PIPE,stderr=logfile)
    areas=[]
    try:
        for i,path in enumerate(masks):
            ok,frame=capture.read();assert ok
            rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB).astype(np.float32)
            mask=np.asarray(Image.open(path).convert('L').resize((W,H),Image.Resampling.BILINEAR)).astype(np.float32)/255
            alpha=cv2.GaussianBlur(mask,(3,3),.55).clip(0,1);ys,xs=np.where(mask>.5)
            assert len(xs)>W*H*.04,('Person mask missing',seg['index'],i)
            ground=int(ys.max());feet=xs[ys>=ground-14];center=float(np.median(feet));radius=float(np.clip((feet.max()-feet.min())*.65+18,25,95))
            shadow=.13*np.exp(-((X-center)/radius)**2-((Y-ground-2)/8.)**2)
            background=plate*(1-shadow[:,:,None]);image=np.clip(rgb*alpha[:,:,None]+background*(1-alpha[:,:,None]),0,255).astype(np.uint8)
            encoder.stdin.write(image.tobytes());areas.append(len(xs))
    finally:
        encoder.stdin.close();encoder.wait();capture.release();logfile.close()
    assert encoder.returncode==0
    assert min(areas)>.45*float(np.median(areas)),('Mask collapse',seg['index'],areas)
    verify_video(dest,LENGTH);seg.update(grey=str(dest),composite='complete',mask_area_min=min(areas),mask_area_max=max(areas));checkpoint()

def segment_all():
    template=json.loads((PREV/'h3-hq20-gray-分割工作流.json').read_text(encoding='utf-8'))
    for seg in M['segments']:
        folder=OUT/'masks'/f"seg-{seg['index']:03d}";folder.mkdir(exist_ok=True)
        if len(list(folder.glob('*.png')))==LENGTH:
            seg.update(mask_dir=str(folder),segmentation='complete');checkpoint();compose(seg);continue
        staged=STAGE/f"generated-{seg['index']:03d}.mp4";shutil.copy2(seg['raw'],staged)
        graph=copy.deepcopy(template);graph['1']['inputs']['file']=input_relative(staged)
        graph['9']['inputs']['filename_prefix']=f"hinata-full-20261118/masks/seg-{seg['index']:03d}"
        entry=execute(graph,seg,'segmentation');paths=list(outputs(entry,'.png'));assert len(paths)==LENGTH,len(paths)
        for i,path in enumerate(paths):shutil.copy2(path,folder/f'{i:05d}.png')
        seg['mask_dir']=str(folder);checkpoint();compose(seg)
        log(f"MASK AND GREY COMPLETE {seg['index']+1}/{len(M['segments'])}")
    M['status']='stitching';checkpoint();note('全部段生成、SAM3和固定灰底合成完成，开始按重叠区选择接缝并拼接。')

def load_window(path,start,count):
    cap=cv2.VideoCapture(str(path));cap.set(cv2.CAP_PROP_POS_FRAMES,start);frames=[]
    for _ in range(count):
        ok,im=cap.read();assert ok;frames.append(im)
    cap.release();return frames

def seam_cost(a,b,k):
    a=cv2.resize(a,(144,256)).astype(np.float32);b=cv2.resize(b,(144,256)).astype(np.float32)
    def fg(x):
        return ((x.max(2)-x.min(2)>28)|(x.mean(2)<145))&(np.indices(x.shape[:2])[0]<247)
    mask=fg(a)|fg(b)
    if mask.sum()<100:return 1e9
    color=np.abs(a-b).mean(2)
    ga=cv2.cvtColor(a.astype(np.uint8),cv2.COLOR_BGR2GRAY);gb=cv2.cvtColor(b.astype(np.uint8),cv2.COLOR_BGR2GRAY)
    edge=np.abs(cv2.Laplacian(ga,cv2.CV_32F)-cv2.Laplacian(gb,cv2.CV_32F))
    return float(color[mask].mean()+.12*edge[mask].mean()+.08*abs(k-OVERLAP/2))

def finish():
    segments=M['segments'];seams=[]
    for prev,cur in zip(segments,segments[1:]):
        offset=cur['start']-prev['start'];a=load_window(prev['grey'],offset,OVERLAP);b=load_window(cur['grey'],0,OVERLAP)
        costs=[seam_cost(a[k],b[k],k) for k in range(OVERLAP)];k=min(range(2,OVERLAP-2),key=lambda j:costs[j])
        seams.append({'from':prev['index'],'to':cur['index'],'global_frame':cur['start']+k,'overlap_index':k,'cost':costs[k],'candidate_costs':costs,'method':'same-global-time visual matching, hard cut; no repeated or omitted timeline frames'})
    M['seams']=seams;checkpoint();save(OUT/'接缝与时间线映射.json',seams)
    video_only=HERE/'complete-video-only.mp4'
    log_file=(HERE/'complete-encode.log').open('wb')
    encoder=subprocess.Popen([FF,'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-an','-c:v','libx264','-crf','17','-pix_fmt','yuv420p','-frames:v',str(M['total_frames']),str(video_only)],stdin=subprocess.PIPE,stderr=log_file)
    captures={};owner=0;switches=[s['global_frame'] for s in seams];mapping=[]
    try:
        for global_index in range(M['total_frames']):
            while owner<len(switches) and global_index>=switches[owner]:owner+=1
            seg=segments[owner];local=global_index-seg['start']
            if owner not in captures:
                cap=cv2.VideoCapture(seg['grey']);cap.set(cv2.CAP_PROP_POS_FRAMES,local);captures[owner]=cap
            ok,frame=captures[owner].read();assert ok,(global_index,owner,local)
            encoder.stdin.write(frame.tobytes());mapping.append([global_index,owner,local])
    finally:
        encoder.stdin.close();encoder.wait();log_file.close()
        for cap in captures.values():cap.release()
    assert encoder.returncode==0;verify_video(video_only,M['total_frames'])
    final=OUT/'宗师雏田_申鹤扭身舞_完整灰背景_34秒.mp4'
    run([FF,'-hide_banner','-loglevel','error','-y','-i',video_only,'-i',SOURCE,'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','copy','-t',str(M['total_frames']/FPS),'-movflags','+faststart',final])
    verification=probe(final,True);v=next(x for x in verification['streams'] if x['codec_type']=='video');a=next(x for x in verification['streams'] if x['codec_type']=='audio')
    assert int(v['nb_read_frames'])==M['total_frames'];assert float(v['start_time'])==0 and float(a['start_time'])==0
    save(OUT/'实际解码及音轨核验.json',verification);save(OUT/'逐帧来源映射.json',mapping)
    comparison=OUT/'完整对比_左原动作_右宗师雏田灰背景.mp4'
    run([FF,'-hide_banner','-loglevel','error','-y','-i',STAGE/'canonical-24fps.mp4','-i',final,'-filter_complex','[0:v][1:v]hstack=inputs=2[v]','-map','[v]','-map','1:a:0','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','copy','-frames:v',M['total_frames'],'-movflags','+faststart',comparison])
    M.pop('error',None);M.pop('traceback',None)
    M.update(status='complete',final=str(final),comparison=str(comparison),final_sha256=hashlib.sha256(final.read_bytes()).hexdigest(),completed=now());M['current']=None;checkpoint()
    note(f"完整片已输出{final.name}，实际解码{M['total_frames']}帧/24fps，原音轨起点0；等待逐秒与接缝视觉复核。")
    log('COMPLETE '+str(final))

def main():
    initialize()
    if M.get('status')=='complete' and Path(M.get('final','')).exists():return
    generate_all();segment_all();finish()

if __name__=='__main__':
    try:main()
    except Exception as exc:
        if M:
            M['status']='error';M['error']=str(exc);M['traceback']=traceback.format_exc();checkpoint()
        if OUT.exists():log('ERROR '+str(exc))
        traceback.print_exc();raise
