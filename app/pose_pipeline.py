"""Persistent H3 short-segment transfer, foreground compositing and optional upscale.

The host supplies task updates and ComfyUI access through core. No character-specific
assets, experimental output paths or credentials are embedded in the pipeline.
"""
import copy
import hashlib
import json
import math
import os
import shutil
import subprocess
import time
import uuid
import urllib.error
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

FPS, LENGTH, OVERLAP = 24, 73, 12


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    for attempt in range(10):
        try:os.replace(tmp,path);return
        except PermissionError:
            if attempt==9:raise
            time.sleep(.05)


def plan_frames(total):
    starts = [0]
    while starts[-1] + LENGTH < total:
        starts.append(starts[-1] + LENGTH - OVERLAP)
    return [{'index': i, 'start': start, 'valid': min(LENGTH, total-start)}
            for i, start in enumerate(starts)]


def timeline(segments, cuts, total):
    owner = 0
    for index in range(total):
        while owner < len(cuts) and index >= cuts[owner]:
            owner += 1
        local = index - segments[owner]['start']
        if not 0 <= local < LENGTH:
            raise ValueError('片段时间线不完整')
        yield index, owner, local


def outputs(core, result, suffix):
    found = []
    for node in result.get('outputs', {}).values():
        for key in ('images', 'videos', 'gifs'):
            for item in node.get(key, []):
                if item.get('type') == 'output' and item.get('filename', '').endswith(suffix):
                    found.append(Path(core.comfy_output()) / item.get('subfolder', '') / item['filename'])
    return found


def prepare_repair(work, manifest, selection, token, prompt):
    """Invalidate selected segments once, preserving previous media and task records."""
    if not selection or manifest.get('repair_token')==token:return
    if not isinstance(token,str) or len(token)!=32 or any(c not in '0123456789abcdef' for c in token):
        raise ValueError('返修任务标识无效')
    indices=sorted({int(n)-1 for n in selection})
    if any(n<0 or n>=len(manifest['segments']) for n in indices):
        raise ValueError('返修片段编号超出范围')
    work=Path(work);archive=work/'返修备份'/token
    archive.mkdir(parents=True,exist_ok=True)
    write_json(archive/'原状态.json',manifest)
    final=manifest.get('final')
    if final and Path(final).is_file():shutil.copy2(final,archive/'原成片.mp4')
    for i in indices:
        for phase in ('generation','segmentation','upscale'):
            for kind in ('api','results'):
                source=work/kind/f'{phase}-{i:03d}.json'
                if source.is_file():shutil.copy2(source,archive/f'{kind}-{phase}-{i:03d}.json')
        for kind,extension in [('raw','.mp4'),('masks',''),('composite','.mp4'),('enhanced','.mp4')]:
            source=work/kind/f'{i:03d}{extension}';dest=archive/f'{kind}-{i:03d}{extension}'
            if source.exists():
                if not source.resolve().is_relative_to(work.resolve()) or not dest.resolve().is_relative_to(work.resolve()):
                    raise ValueError('返修文件不在本任务过程目录内')
                source.rename(dest)
        seg=manifest['segments'][i]
        for key in ['generation_job','segmentation_job','upscale_job','mask_area']:seg.pop(key,None)
        seg['repair_prompt']='\n'.join(x for x in [seg.get('repair_prompt',''),prompt] if x)
        seg['repair_seed']=uuid.uuid4().int%(2**32)
    manifest['repair_token']=token


def make_background(reference, destination, size):
    """Estimate a neutral studio plate from outer edges; never reconstruct a furnished room."""
    im = np.asarray(Image.open(reference).convert('RGB').resize(size)).astype(np.float32)
    h, w = im.shape[:2]
    y, x = np.mgrid[-1:1:complex(h), -1:1:complex(w)]
    basis = np.stack([np.ones_like(x), x, y, x*x, x*y, y*y], -1)
    edge = (np.abs(x) > .92) | (y < -.94)
    values = im[edge]
    # A neutral estimate is also usable when clothes intrude into the outer edge.
    median = np.median(values, 0)
    keep = np.linalg.norm(values-median, axis=1) < 40
    if keep.sum() < 30:
        rgb = np.full((h, w, 3), 190, np.uint8)
    else:
        coef = np.linalg.lstsq(basis[edge][keep], values[keep], rcond=None)[0]
        rgb = np.clip(basis @ coef, median-30, median+30).clip(0, 255).astype(np.uint8)
    Image.fromarray(rgb).save(destination)


def composite(raw, masks, plate, destination, core, check_cancel):
    background = np.asarray(Image.open(plate).convert('RGB')).astype(np.float32)
    h, w = background.shape[:2]
    y, x = np.mgrid[0:h, 0:w]
    cap = cv2.VideoCapture(str(raw))
    args = [core.ffmpeg_exe(), '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
            '-s', f'{w}x{h}', '-r', '24', '-i', 'pipe:0', '-an', '-c:v', 'libx264',
            '-crf', '16', '-pix_fmt', 'yuv420p', '-frames:v', str(LENGTH), str(destination)]
    log = Path(str(destination)+'.log').open('wb')
    encoder = subprocess.Popen(args, stdin=subprocess.PIPE, stderr=log,
                               creationflags=0x08000000 if os.name == 'nt' else 0)
    areas = []
    try:
        for i, path in enumerate(masks):
            check_cancel()
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError(f'人物合成缺少第{i+1}帧')
            mask = np.asarray(Image.open(path).convert('L').resize((w,h))).astype(np.float32)/255
            yy, xx = np.where(mask > .5)
            if len(xx) < w*h*.04:
                raise RuntimeError(f'人物遮罩异常：第{i+1}帧，请返修该段')
            alpha = cv2.GaussianBlur(mask, (3,3), .55).clip(0,1)
            ground = yy.max(); feet = xx[yy >= ground-14]
            radius = np.clip((feet.max()-feet.min())*.65+18,25,95)
            shadow = .13*np.exp(-((x-np.median(feet))/radius)**2-((y-ground-2)/8)**2)
            rgb = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
            result = rgb*alpha[:,:,None]+background*(1-shadow[:,:,None])*(1-alpha[:,:,None])
            encoder.stdin.write(result.clip(0,255).astype(np.uint8).tobytes())
            areas.append(len(xx))
    finally:
        encoder.stdin.close(); encoder.wait(); cap.release(); log.close()
    if encoder.returncode or min(areas) < .45*np.median(areas):
        raise RuntimeError('人物合成失败或遮罩面积突变，请检查该段')
    return {'min':int(min(areas)), 'max':int(max(areas))}


def choose_cuts(segments, files):
    cuts, records = [], []
    for i in range(1, len(segments)):
        ca, cb = cv2.VideoCapture(str(files[i-1])), cv2.VideoCapture(str(files[i]))
        ca.set(cv2.CAP_PROP_POS_FRAMES,segments[i]['start']-segments[i-1]['start'])
        costs = []
        for k in range(OVERLAP):
            oka,a=ca.read();okb,b=cb.read()
            if not oka or not okb:
                raise RuntimeError('重叠区缺帧')
            a=cv2.resize(a,(144,256)).astype(np.float32);b=cv2.resize(b,(144,256)).astype(np.float32)
            mask=((a.max(2)-a.min(2)>28)|(b.max(2)-b.min(2)>28)|(a.mean(2)<145)|(b.mean(2)<145))
            cost=float(np.abs(a-b).mean(2)[mask].mean()) if mask.any() else 0
            costs.append(cost+.08*abs(k-OVERLAP/2))
        ca.release();cb.release()
        k=min(range(2,OVERLAP-2),key=lambda j:costs[j]);cut=segments[i]['start']+k
        cuts.append(cut);records.append({'frame':cut,'second':cut/FPS,'cost':costs[k]})
    return cuts, records


class Pipeline:
    def __init__(self, core, tid, params, stamp):
        self.c,self.tid,self.p,self.stamp=core,tid,dict(params),stamp
        root=Path(core.out_dir())/'过程'
        resume=params.get('resume_work')
        self.work=Path(resume) if resume else root/f'H3流程_{stamp}_{tid}'
        if resume and not self.work.resolve().is_relative_to(root.resolve()):
            raise ValueError('续接目录不在当前成品目录的过程文件夹中')
        self.work.mkdir(parents=True,exist_ok=True)
        self.state_path=self.work/'流程状态.json'
        self.m=json.loads(self.state_path.read_text(encoding='utf-8')) if self.state_path.exists() else {}
        self.stage=Path(core.comfy_input())/'h3studio'/self.work.name
        self.stage.mkdir(parents=True,exist_ok=True)
        for d in ('raw','masks','composite','enhanced','api','results','review'):
            (self.work/d).mkdir(exist_ok=True)
        core._upd(tid,work_dir=str(self.work))

    def save(self):
        self.m['updated']=time.time();write_json(self.state_path,self.m)

    def canceled(self):
        t=self.c.task_get(self.tid)
        if t and t.get('status')=='canceled':
            raise RuntimeError('已取消；已完成片段保留，可继续任务')

    def update(self,stage,progress):
        self.canceled();self.c._upd(self.tid,stage=stage,progress=round(progress,1),eta=0)

    def ff(self,*args):
        self.canceled();return self.c.run_ff([self.c.ffmpeg_exe(),'-hide_banner','-loglevel','error','-y',*map(str,args)])

    def probe(self,path,count=False):
        exe=Path(self.c.ffmpeg_exe()).with_name('ffprobe.exe' if os.name=='nt' else 'ffprobe')
        args=[str(exe),'-v','error']+(['-count_frames'] if count else [])
        return json.loads(self.c.run_ff(args+['-show_streams','-show_format','-of','json',str(path)]))

    def valid_video(self,path,frames=LENGTH):
        if not Path(path).exists():return False
        v=next(s for s in self.probe(path)['streams'] if s['codec_type']=='video')
        return int(v.get('nb_frames',0))==frames and v['avg_frame_rate']=='24/1'

    def relative(self,path):return Path(path).relative_to(Path(self.c.comfy_input())).as_posix()

    def read(self,path):
        while True:
            self.canceled()
            try:return self.c.http_json(path,timeout=30)
            except urllib.error.HTTPError:raise
            except (TimeoutError,OSError):
                self.c._upd(self.tid,stage='引擎连接暂时超时，保留原任务等待恢复',eta=0)
                time.sleep(2)

    def model(self,node,field,keyword):
        schema=self.c.http_json('/object_info/'+node)
        if node not in schema:raise RuntimeError('缺少ComfyUI节点：'+node)
        field_spec=schema[node]['input']['required'][field]
        choices=field_spec[0]
        if choices=='COMBO':choices=field_spec[1].get('options',[])
        hit=[x for x in choices if keyword.lower() in x.lower() and '.scail_chunks' not in x.lower()]
        if not hit:raise RuntimeError('模型未找到：'+keyword+'，请在ComfyUI配置模型路径')
        return hit[0]

    def execute(self,graph,seg,phase,base,span):
        self.canceled();key=phase+'_job';job=seg.setdefault(key,{'token':uuid.uuid4().hex})
        self.c.WATCHER.reset()
        pid=job.get('pid')
        q=self.read('/queue');queue=q.get('queue_running',[])+q.get('queue_pending',[])
        if not pid:
            # Recover a POST whose response was lost; never blindly submit it twice.
            for item in queue:
                if item[3].get('h3pose_job')==job['token']:pid=item[1]
            if not pid:
                for item_id,item in self.read('/history?max_items=200').items():
                    prompt=item.get('prompt',[])
                    if len(prompt)>3 and prompt[3].get('h3pose_job')==job['token']:pid=item_id
        if pid:
            h=self.read('/history/'+pid).get(pid)
            if h and h.get('status',{}).get('status_str')=='error':pid=None
            elif not h and not any(item[1]==pid for item in queue):pid=None
            elif h and len(h.get('prompt',[]))>2:
                graph=copy.deepcopy(h['prompt'][2])
            else:
                running=next((item for item in queue if item[1]==pid),None)
                if running:graph=copy.deepcopy(running[2])
        write_json(self.work/'api'/f'{phase}-{seg["index"]:03d}.json',graph)
        if not pid:
            self.save();self.c.WATCHER.reset()
            res=self.c.http_json('/prompt',{'prompt':graph,'client_id':self.c.CLIENT_ID,
                                           'extra_data':{'h3pose_job':job['token']}},timeout=60)
            if 'prompt_id' not in res:raise RuntimeError('工作流被拒绝：'+json.dumps(res,ensure_ascii=False)[:700])
            pid=res['prompt_id'];job['pid']=pid;self.save()
        job['pid']=pid;self.save()
        self.c.WATCHER.prompt_id=pid
        self.c._upd(self.tid,prompt_id=pid)
        last_queue=0;missing=0
        while True:
            self.canceled()
            h=self.read('/history/'+pid).get(pid)
            if h:
                status=h.get('status',{})
                if status.get('status_str')=='error':
                    write_json(self.work/'results'/f'{phase}-{seg["index"]:03d}.json',h)
                    job['failed']=True;self.save()
                    raise RuntimeError('片段执行失败：'+str(status.get('messages',[]))[-650:])
                if status.get('completed'):
                    write_json(self.work/'results'/f'{phase}-{seg["index"]:03d}.json',h)
                    job['complete']=True;self.save();return h
            elif time.monotonic()-last_queue>15:
                last_queue=time.monotonic();q=self.read('/queue')
                present=any(item[1]==pid for item in q.get('queue_running',[])+q.get('queue_pending',[]))
                missing=0 if present else missing+1
                if missing>=3:raise RuntimeError('原任务已从引擎队列和历史中消失；可从断点继续该段')
            watch=self.c.WATCHER
            v,mx=watch.value,watch.max
            sampling=watch.prompt_id==pid and mx and str(watch.node_id)=='125' and phase=='generation'
            ratio=v/mx if sampling else 0
            suffix=f' · 采样 {v}/{mx} 步' if sampling else ' · 引擎处理中'
            label={'generation':'生成','segmentation':'人物分割','upscale':'超分增强'}.get(phase,phase)
            self.update(f'{label} {seg["index"]+1}/{len(self.m["segments"])}'+suffix,base+span*ratio)
            time.sleep(1)

    def initialize(self):
        p=self.p;source=Path(p.get('video_abs') or '')
        images=[Path(x) for x in p.get('images',[])];char_count=int(p.get('char_count') or len(images))
        if not source.is_file() or not images or not images[0].is_file():
            raise ValueError('请上传动作视频和角色全身参考图')
        source_meta=self.probe(source)
        duration=float(source_meta['format']['duration']);limit=p.get('pipeline_duration')
        if limit:duration=min(duration,float(limit))
        total=math.ceil(duration*FPS);w=int(p.get('width') or 576);h=int(p.get('height') or 1024)
        if p.get('native_short'):
            v=next(s for s in source_meta['streams'] if s['codec_type']=='video')
            scale=int(p['native_short'])/min(v['width'],v['height'])
            w,h=[max(32,round(v[k]*scale/32)*32) for k in ('width','height')]
        if w%32 or h%32:raise ValueError('生成宽高需为32的倍数')
        signature={'source':hashlib.sha256(source.read_bytes()).hexdigest(),
                   'images':[hashlib.sha256(x.read_bytes()).hexdigest() for x in images],
                   'width':w,'height':h,'frames':total,'steps':p.get('steps',4),
                   'turbo':p.get('turbo',True),'background':p.get('background_mode','grey'),
                   'upscale':p.get('upscale',False),'seed':p.get('seed',20261118),
                   'ref_size':p.get('ref_size','match'),'swap_str':p.get('swap_str',1.15),
                   'char_count':char_count,'keep_audio':p.get('keep_audio',True),
                   'identity_ref_index':int(p.get('identity_ref_index') or 1),
                   'models':p.get('pipeline_models',self.c.CFG.get('models') or {}),
                   'prompt':p.get('prompt',''),'quality':p.get('quality','')}
        if self.m:self.m['signature'].setdefault('identity_ref_index',1)
        if self.m and self.m['signature']!=signature:
            raise ValueError('输入或参数已改变，请创建新任务；续接只用于相同素材和设置')
        if not self.m:
            self.m={'created':time.time(),'params':p,'signature':signature,'segments':plan_frames(total),
                    'total_frames':total,'source_duration':duration,'seed':p.get('seed',20261118)}
        prepare_repair(self.work,self.m,p.get('repair_segments'),p.get('repair_token') or uuid.uuid4().hex,p.get('repair_prompt',''))
        self.m.pop('error',None);self.m['status']='running';self.save()
        self.source,self.images,self.char_count=source,images,char_count
        self.size=(w,h);self.total=total
        self.update('检查模型与输入',1)
        self.sam=self.model('CheckpointLoaderSimple','ckpt_name','sam3')
        if p.get('upscale'):self.upscaler=self.model('UpscaleModelLoader','model_name','RealESRGAN_x2plus')
        for node in ('MiniMaxH3AddGuide','SAM3_VideoTrack'):
            if node not in self.c.http_json('/object_info/'+node):raise RuntimeError('缺少节点：'+node)
        self.plate=self.work/'背景板.png'
        if p.get('background_mode')=='image':
            if char_count>=len(images):raise ValueError('固定背景图模式需要上传一张独立场景图')
            ImageOps.fit(Image.open(images[char_count]).convert('RGB'),self.size,Image.Resampling.LANCZOS).save(self.plate)
        else:make_background(images[0],self.plate,self.size)
        self.staged_images=[self.c.stage_asset(str(x),sub='h3studio/'+self.work.name) for x in images[:char_count]]
        self.staged_images.append(self.c.stage_asset(str(self.plate),sub='h3studio/'+self.work.name))
        canonical=self.stage/'canonical.mp4'
        if not self.valid_video(canonical,total):
            self.update('转换完整24fps时间线',2)
            self.ff('-i',source,'-vf',f'fps=24,scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=gray,setsar=1,tpad=stop_mode=clone:stop_duration=1',
                    '-frames:v',total,'-an','-c:v','libx264','-crf','16','-pix_fmt','yuv420p',canonical)
        for seg in self.m['segments']:
            path=self.stage/f'drive-{seg["index"]:03d}.mp4'
            if not self.valid_video(path):
                self.ff('-ss',f'{seg["start"]/24:.8f}','-i',canonical,
                        '-ss',f'{seg["start"]/24:.8f}','-i',source,'-map','0:v:0','-map','1:a:0?',
                        '-vf','tpad=stop_mode=clone:stop_duration=4','-af','apad=pad_dur=4',
                        '-frames:v',LENGTH,'-t',LENGTH/FPS,'-c:v','libx264','-crf','16','-pix_fmt','yuv420p',
                        '-c:a','aac','-b:a','128k',path)

    def generate(self):
        p=self.p;base=self.c.load_template('05p')
        gen=next(v for v in base.values() if v['class_type']=='MiniMaxH3ReferenceToVideo')
        self.c._wire_ref_images(base,gen,self.staged_images,p.get('ref_size') or 'match')
        for k,n in base.items():
            ct=n['class_type'];inp=n['inputs']
            if ct=='PrimitiveBoolean':inp['value']=bool(p.get('turbo',True))
            if ct=='PrimitiveStringMultiline':
                inp['value']=('Replace the person in the driving clip with the SAME person from <Picture 1>. '
                    f'Pictures 1 through {self.char_count} show the same character: use the first for full-body costume and proportions, and the others for identity and clothing details. '
                    f'Use Picture {int(p.get("identity_ref_index") or 1)} as the facial identity authority, preserving its eye shape, pupils, nose, lips and face contour. '
                    'Preserve the driving motion, timing, body proportions, camera framing and orientation. '
                    'Keep the reference identity, hairstyle, costume, accessories and shoe design consistent. '
                    f'Use <Picture {len(self.staged_images)}> as the static background and floor. '
                    'One person, coherent hands and feet, no extra spin or duplicated limbs. '
                    'Preserve the reference shoe type instead of copying the source dancer footwear.\n'
                    +(p.get('prompt') or '')+'\n'+(p.get('quality') or ''))
            if ct=='RandomNoise':inp['noise_seed']=int(self.m['seed'])
            if ct=='MiniMaxLowVRAMAttention':inp['head_chunks']=int(p.get('head_chunks') or (8 if self.size[0]*self.size[1]>800000 else 4))
            if ct=='MiniMaxChunkFeedForward':inp['chunks']=int(p.get('ff_chunks') or (4 if self.size[0]*self.size[1]>800000 else 2))
            if ct=='UNETLoader':inp['unet_name']=(p.get('pipeline_models',self.c.CFG.get('models')) or {}).get('unet_ref2v') or inp['unet_name']
            if ct=='LoraLoaderModelOnly':
                selected=p.get('pipeline_models',self.c.CFG.get('models')) or {}
                if 'character_swap' in inp.get('lora_name',''):
                    inp['strength_model']=float(p.get('swap_str') or 1.15)
                    inp['lora_name']=selected.get('lora_swap') or inp['lora_name']
                elif 'turbo' in inp.get('lora_name',''):
                    inp['lora_name']=selected.get('lora_ref2v') or inp['lora_name']
        for key,value in [('width',self.size[0]),('height',self.size[1]),('length',LENGTH)]:self.c._set_scalar(base,gen,key,value)
        turbo,quality=self.c._step_prims(base)
        selected=turbo if p.get('turbo',True) else quality
        if selected:selected['inputs']['value']=int(p.get('steps') or 4)
        for seg in self.m['segments']:
            i=seg['index'];dest=self.work/'raw'/f'{i:03d}.mp4'
            if self.valid_video(dest):continue
            graph=copy.deepcopy(base)
            for n in graph.values():
                if n['class_type']=='PrimitiveStringMultiline' and seg.get('repair_prompt'):
                    n['inputs']['value']+='\nThis segment repair requirement: '+seg['repair_prompt']
                if n['class_type']=='RandomNoise' and 'repair_seed' in seg:
                    n['inputs']['noise_seed']=seg['repair_seed']
                if n['class_type']=='LoadVideo':n['inputs']['file']=self.relative(self.stage/f'drive-{i:03d}.mp4')
                if n['class_type']=='SaveVideo':n['inputs']['filename_prefix']=f'H3影栈/{self.work.name}/raw-{i:03d}'
            result=self.execute(graph,seg,'generation',4+60*i/len(self.m['segments']),60/len(self.m['segments']))
            files=outputs(self.c,result,'.mp4')
            if len(files)!=1:raise RuntimeError('生成结果缺少唯一视频')
            shutil.copy2(files[0],dest)
            if not self.valid_video(dest):raise RuntimeError('生成片段帧数不完整')

    def masks(self):
        for seg in self.m['segments']:
            i=seg['index'];folder=self.work/'masks'/f'{i:03d}';folder.mkdir(exist_ok=True)
            paths=sorted(folder.glob('*.png'));dest=self.work/'composite'/f'{i:03d}.mp4'
            if len(paths)!=LENGTH:
                graph=self.c.load_template('05m');staged=self.c.stage_asset(str(self.work/'raw'/f'{i:03d}.mp4'),sub='h3studio/'+self.work.name)
                graph['1']['inputs']['file']=staged;graph['4']['inputs']['ckpt_name']=self.sam
                graph['9']['inputs']['filename_prefix']=f'H3影栈/{self.work.name}/mask-{i:03d}'
                result=self.execute(graph,seg,'segmentation',64+20*i/len(self.m['segments']),20/len(self.m['segments']))
                found=outputs(self.c,result,'.png')
                if len(found)!=LENGTH:raise RuntimeError('遮罩未覆盖整个片段')
                for j,path in enumerate(found):shutil.copy2(path,folder/f'{j:05d}.png')
                paths=sorted(folder.glob('*.png'))
            if not self.valid_video(dest):
                self.update(f'合成固定背景 {i+1}/{len(self.m["segments"])}',64+20*(i+.5)/len(self.m['segments']))
                seg['mask_area']=composite(self.work/'raw'/f'{i:03d}.mp4',paths,self.plate,dest,self.c,self.canceled)
                self.save()

    def enhance(self):
        self.files=[self.work/'composite'/f'{s["index"]:03d}.mp4' for s in self.m['segments']]
        if not self.p.get('upscale'):return
        for seg in self.m['segments']:
            i=seg['index'];dest=self.work/'enhanced'/f'{i:03d}.mp4'
            if not self.valid_video(dest):
                src=self.c.stage_asset(str(self.files[i]),sub='h3studio/'+self.work.name)
                graph={'1':{'class_type':'LoadVideo','inputs':{'file':src}},
                    '2':{'class_type':'GetVideoComponents','inputs':{'video':['1',0]}},
                    '3':{'class_type':'UpscaleModelLoader','inputs':{'model_name':self.upscaler}},
                    '4':{'class_type':'ImageUpscaleWithModel','inputs':{'upscale_model':['3',0],'image':['2',0]}},
                    '5':{'class_type':'CreateVideo','inputs':{'images':['4',0],'fps':24}},
                    '6':{'class_type':'SaveVideo','inputs':{'video':['5',0],'format':'auto','codec':'auto','filename_prefix':f'H3影栈/{self.work.name}/upscale-{i:03d}'}}}
                result=self.execute(graph,seg,'upscale',84+10*i/len(self.m['segments']),10/len(self.m['segments']))
                files=outputs(self.c,result,'.mp4')
                if len(files)!=1:raise RuntimeError('超分结果缺少视频')
                shutil.copy2(files[0],dest)
                if self.c.queue_info()=={'running':0,'pending':0}:
                    # A decoded 73-frame enlarged batch occupies gigabytes of RAM.
                    # Everything needed for continuation is already persisted.
                    self.c.http_json('/free',{'free_memory':True},timeout=15)
            self.files[i]=dest

    def finish(self):
        self.update('选择重叠区接缝',95)
        # Match at native resolution; enlarged texture should not determine pose alignment.
        native=[self.work/'composite'/f'{s["index"]:03d}.mp4' for s in self.m['segments']]
        cuts,seams=choose_cuts(self.m['segments'],native);write_json(self.work/'接缝.json',seams)
        first=next(s for s in self.probe(self.files[0])['streams'] if s['codec_type']=='video');w,h=first['width'],first['height']
        video=self.work/'video-only.mp4';log=(self.work/'encode.log').open('wb')
        proc=subprocess.Popen([self.c.ffmpeg_exe(),'-v','error','-y','-f','rawvideo','-pix_fmt','bgr24',
            '-s',f'{w}x{h}','-r','24','-i','pipe:0','-an','-c:v','libx264','-crf','16',
            '-pix_fmt','yuv420p','-frames:v',str(self.total),str(video)],stdin=subprocess.PIPE,stderr=log,
            creationflags=0x08000000 if os.name=='nt' else 0)
        caps={};mapping=[]
        try:
            for index,owner,local in timeline(self.m['segments'],cuts,self.total):
                self.canceled()
                if owner not in caps:
                    caps[owner]=cv2.VideoCapture(str(self.files[owner]));caps[owner].set(cv2.CAP_PROP_POS_FRAMES,local)
                ok,frame=caps[owner].read()
                if not ok:raise RuntimeError('拼接缺帧')
                proc.stdin.write(frame.tobytes());mapping.append([index,owner,local])
        finally:
            proc.stdin.close();proc.wait();log.close()
            for cap in caps.values():cap.release()
        if proc.returncode:raise RuntimeError('拼接编码失败')
        final=Path(self.c.out_dir())/f'05_H3固定流程_{self.work.name}.mp4'
        args=['-i',video]
        if self.p.get('keep_audio',True):args+=['-i',self.source,'-map','0:v:0','-map','1:a:0?','-c:a','copy']
        else:args+=['-map','0:v:0','-an']
        if self.p.get('upscale'):
            # Preserve aspect ratio while exporting a 1080-long-short-side equivalent.
            nw,nh=(1080,round(1080*h/w/2)*2) if w<=h else (round(1080*w/h/2)*2,1080)
            args+=['-vf',f'scale={nw}:{nh}:flags=lanczos','-c:v','libx264','-crf','16']
        else:args+=['-c:v','copy']
        self.ff(*args,'-t',self.total/FPS,'-movflags','+faststart',final)
        meta=self.probe(final,True);v=next(s for s in meta['streams'] if s['codec_type']=='video')
        if int(v['nb_read_frames'])!=self.total:raise RuntimeError('成片帧数不完整')
        if abs(float(v['duration'])-self.total/FPS)>1/FPS:raise RuntimeError('成片时长异常')
        if abs(float(v.get('start_time',0)))>1/FPS:raise RuntimeError('成片起点异常')
        if self.p.get('keep_audio',True):
            source_audio=[s for s in self.probe(self.source)['streams'] if s['codec_type']=='audio']
            final_audio=[s for s in meta['streams'] if s['codec_type']=='audio']
            if source_audio and not final_audio:raise RuntimeError('原音轨未写入成片')
            if final_audio and abs(float(final_audio[0].get('start_time',0)))>1/FPS:
                raise RuntimeError('音频起点异常')
            if source_audio and not self.p.get('pipeline_duration'):
                def digest(path):return self.ff('-i',path,'-map','0:a:0','-c:a','copy','-f','hash','-hash','sha256','-').strip()
                expected=digest(self.source);actual=digest(final)
                if expected!=actual:raise RuntimeError('完整片原音轨数据校验失败')
                meta['audio_packet_hash']=actual
        write_json(self.work/'完整性核验.json',meta);write_json(self.work/'时间线映射.json',mapping)
        cap=cv2.VideoCapture(str(final));sheet=Image.new('RGB',(6*144,math.ceil((len(seams)+2)/6)*282),(235,240,237));draw=ImageDraw.Draw(sheet)
        frames=[0]+[x['frame'] for x in seams]+[self.total-1]
        for j,index in enumerate(frames):
            cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,frame=cap.read()
            if ok:
                x,y=j%6*144,j//6*282;sheet.paste(Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)).resize((144,256)),(x,y+24));draw.text((x+3,y+3),f'{index/24:.2f}s / {index}',fill=(20,50,35))
        cap.release();sheet.save(self.work/'review/接缝预览.jpg',quality=95)
        self.m.pop('error',None)
        self.m.update(status='complete',final=str(final),seams=seams,finished=time.time());self.save()
        (self.work/'检查说明.md').write_text('完整性核验通过；请人工检查脸、衣装、鞋型、手脚、动作和接缝。\n灰棚背景依据参考图边缘估计；独立背景图按画幅缩放。\n超分仅改善观感，不保证恢复原片细节；本预设固定输出24fps。\n',encoding='utf-8')
        self.c._upd(self.tid,status='done',progress=100,stage='完成 · 待画面验收',eta=0,finished=time.time(),
                    files=[{'name':final.name,'path':str(final),'size':final.stat().st_size}])

    def run(self):
        try:self.initialize();self.generate();self.masks();self.enhance();self.finish()
        except Exception as exc:
            self.m.update(status='interrupted',error=str(exc));self.save();raise


def run(core,tid,params,stamp):Pipeline(core,tid,params,stamp).run()


def runs(core):
    root=Path(core.out_dir())/'过程';result=[]
    for path in root.glob('H3流程_*/流程状态.json'):
        try:
            d=json.loads(path.read_text(encoding='utf-8'))
            result.append({'work':str(path.parent),'status':d.get('status'),'updated':d.get('updated',0),
                           'error':d.get('error',''),'params':d.get('params',{}),'final':d.get('final',''),
                           'segments':[{'number':x['index']+1,'start':x['start']/24,
                               'end':min(x['start']+LENGTH,d.get('total_frames',0))/24} for x in d.get('segments',[])]})
        except (OSError,ValueError):continue
    return sorted(result,key=lambda x:x['updated'],reverse=True)[:30]
