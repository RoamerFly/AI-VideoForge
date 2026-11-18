import json,sys,re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'app'))
import core,server
BASE=Path(__file__).parent
core.UPLOAD_DIR=str(BASE/'ui-uploads');Path(core.UPLOAD_DIR).mkdir(exist_ok=True)
core.CFG=dict(core.CFG,out_dir=str(BASE/'outputs'))
http=server.serve(8799)
captured=[];errors=[]
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(channel='msedge',headless=True,args=['--disable-gpu'])
  page=browser.new_page(viewport={'width':1440,'height':1080})
  page.on('pageerror',lambda e:errors.append(str(e)))
  def generate(route):
   captured.append(route.request.post_data_json)
   route.fulfill(json={'task':{'id':'ui-only'},'autostart':False})
  page.route('**/api/generate',generate)
  page.goto('http://127.0.0.1:8799/#05');page.wait_for_timeout(1200)
  assert page.get_by_role('button',name='H3 · 固定流程',exact=False).count()==1
  assert not page.get_by_text('动作逐帧复刻',exact=True).count()
  assert page.evaluate("MODES['05'].family")=='ref2v'
  page.evaluate('''() => {
    setAssets('05',{k:'video'},[{path:'E:/test/source.mp4',name:'source.mp4'}]);
    setAssets('05',{k:'chars',multi:3},[{path:'E:/test/character.png',name:'character.png'}]);
    setAssets('05',{k:'faces',multi:1},[{path:'E:/test/main-face.png',name:'main-face.png'}]);
    setAssets('05',{k:'angles',multi:2},[{path:'E:/test/left-face.png',name:'left-face.png'}]);
    renderStage();
  }''')
  page.locator('#btnGenerate').click();page.wait_for_timeout(300)
  p=captured[-1]['params'];assert p['engine']=='h3_pipeline' and p['native_short']==768
  assert p['steps']==4 and p['turbo'] and p['pipeline_duration']==3 and p['char_count']==3
  assert p['identity_ref_index']==2 and p['images'][1]=='E:/test/main-face.png'
  assert p['ref_size']=='match' and p['keep_audio'] is True
  page.get_by_role('button',name='1080p超分',exact=False).click()
  page.get_by_role('button',name=re.compile(r'^整段')).click()
  page.locator('#btnGenerate').click();page.wait_for_timeout(300)
  assert captured[-1]['params']['upscale'] is True
  assert captured[-1]['params']['pipeline_duration'] is None
  page.screenshot(path=str(BASE/'pipeline-form.png'),full_page=True)
  page.get_by_role('button',name='流程记录 / 断点续接').click()
  page.locator('dialog.pose-runs').wait_for(state='visible')
  page.screenshot(path=str(BASE/'pipeline-ui.png'),full_page=True)
  page.get_by_role('button',name='指定片段返修',exact=True).first.click()
  page.locator('dialog.pose-runs textarea').fill('keep facing front')
  page.get_by_role('button',name='开始返修',exact=True).click();page.wait_for_timeout(300)
  assert captured[-1]['params']['repair_segments']==[1]
  assert captured[-1]['params']['repair_prompt']=='keep facing front'
  page.get_by_role('button',name='SCAIL-2 · 角色替换',exact=False).click()
  assert not page.get_by_role('button',name='1080p超分',exact=False).count()
  assert page.get_by_text('输出帧率',exact=True).count()==1
  assert not errors,errors
  browser.close()
 (BASE/'ui-check.json').write_text(json.dumps({'errors':errors,'captured':captured,'status':'pass'},ensure_ascii=False,indent=2),encoding='utf-8')
 print('UI preset, payload, legacy mode isolation and run dialog passed')
finally:http.shutdown()
