"""Make contact sheets and independently validate the complete output timeline."""
import hashlib,json,subprocess,sys
from pathlib import Path
import cv2
from PIL import Image,ImageDraw,ImageFont
sys.path.insert(0,str(Path(__file__).parent))
import full_run as f

out=f.OUT
state=json.loads(f.STATE.read_text(encoding='utf-8'))
assert state['status']=='complete'
video=Path(state['final'])
meta=f.probe(video,True)
vs=next(x for x in meta['streams'] if x['codec_type']=='video')
audio=next(x for x in meta['streams'] if x['codec_type']=='audio')
mapping=json.loads((out/'逐帧来源映射.json').read_text(encoding='utf-8'))
assert [x[0] for x in mapping]==list(range(state['total_frames']))
assert all(x[2]==x[0]-state['segments'][x[1]]['start'] and 0<=x[2]<73 for x in mapping)
assert int(vs['nb_read_frames'])==826
assert abs(float(vs['duration'])-state['duration_source'])<1/24
assert float(vs['start_time'])==float(audio['start_time'])==0

def audio_hash(path):
    return subprocess.check_output([f.FF,'-v','error','-i',str(path),'-map','0:a:0','-c:a','copy','-f','hash','-hash','sha256','-'],encoding='utf-8').strip()

ah=audio_hash(video);source_ah=audio_hash(f.SOURCE)
assert ah==source_ah,(ah,source_ah)
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',16)
cap=cv2.VideoCapture(str(video))

def frame(index,size):
    cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,im=cap.read();assert ok,index
    return Image.fromarray(cv2.cvtColor(im,cv2.COLOR_BGR2RGB)).resize(size,Image.Resampling.LANCZOS)

for page in range(2):
    indices=list(range(page*18,min((page+1)*18,35)))
    rows=(len(indices)+5)//6
    sheet=Image.new('RGB',(6*144,rows*282),(235,240,237));draw=ImageDraw.Draw(sheet)
    for j,second in enumerate(indices):
        idx=min(round(second*24),825);x=(j%6)*144;y=(j//6)*282
        sheet.paste(frame(idx,(144,256)),(x,y+24));draw.text((x+3,y+2),f'{second}s / f{idx}',font=font,fill=(15,52,38))
    sheet.save(out/'review'/f'full-seconds-{page+1}.jpg',quality=96)

for page in range(3):
    seams=state['seams'][page*5:(page+1)*5]
    if not seams:continue
    sheet=Image.new('RGB',(4*144,len(seams)*284),(235,240,237));draw=ImageDraw.Draw(sheet)
    for row,seam in enumerate(seams):
        c=seam['global_frame']
        for col,idx in enumerate([c-2,c-1,c,c+1]):
            x=col*144;y=row*284
            sheet.paste(frame(idx,(144,256)),(x,y+25))
            draw.text((x+2,y+2),f'{idx/24:.2f}s f{idx}',font=font,fill=(15,52,38))
    sheet.save(out/'review'/f'seams-{page+1}.jpg',quality=96)
cap.release()
report={'file':str(video),'seconds':float(vs['duration']),'frames_decoded':int(vs['nb_read_frames']),'fps':vs['avg_frame_rate'],'size':[vs['width'],vs['height']],'source_seconds':state['duration_source'],'timeline_exactly_0_to_825':True,'audio_packet_sha256':ah,'source_audio_packet_sha256':source_ah,'audio_packets_identical':True,'start_time_video':vs['start_time'],'start_time_audio':audio['start_time'],'seams':len(state['seams']),'visual_review':'Contact sheets generated; manual visual review recorded separately','file_sha256':hashlib.sha256(video.read_bytes()).hexdigest()}
f.save(out/'独立完整性核验.json',report)
print(json.dumps(report,ensure_ascii=False,indent=2))
