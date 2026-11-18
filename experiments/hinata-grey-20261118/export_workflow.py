"""Export via the real ComfyUI frontend and verify semantic inputs after reload."""
import json,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from run_trial import HERE,OUT,BASE
name=sys.argv[1]
graph=json.loads((HERE/f'{name}-api.json').read_text(encoding='utf-8'))
types=list({v['class_type'] for v in graph.values()})
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',headless=True)
    page=browser.new_page(viewport={'width':1600,'height':1000})
    page.goto(BASE,wait_until='domcontentloaded')
    page.wait_for_function('types=>window.comfyAPI?.app?.app?.isGraphReady && window.comfyAPI.app.app.extensionManager?.workflow?.tabsRestored && types.every(t=>window.LiteGraph?.registered_node_types?.[t]?.comfyClass)',arg=types,timeout=90000)
    result=page.evaluate('''async graph=>{
        const app=window.comfyAPI.app.app;
        await app.loadApiJson(graph);
        app.graph.updateExecutionOrder();
        await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
        const before=await app.graphToPrompt();
        const native=app.graph.serialize();
        await app.loadGraphData(native,true);
        app.graph.updateExecutionOrder();
        await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
        const after=await app.graphToPrompt();
        return {native,before:before.output,after:after.output};
    }''',graph)
    selected=['UNETLoader','CLIPLoader','VAELoader','LoraLoaderModelOnly','MiniMaxH3ReferenceToVideo','MiniMaxH3AddGuide','BasicScheduler','PrimitiveBoolean','PrimitiveInt','PrimitiveStringMultiline','LoadImage','LoadVideo','RandomNoise','BasicGuider','CheckpointLoaderSimple','CLIPTextEncode','SAM3_VideoTrack','SAM3_TrackToMask','ImageFromBatch','MaskToImage','GetVideoComponents','SaveImage']
    for phase in ['before','after']:
        for k,v in graph.items():
            if v['class_type'] not in selected:continue
            for field,value in v['inputs'].items():
                actual=result[phase][k]['inputs'].get(field)
                assert actual==value,(phase,k,field,actual,value)
    (OUT/f'{name}-ComfyUI原生工作流.json').write_text(json.dumps(result['native'],ensure_ascii=False,indent=2),encoding='utf-8')
    (HERE/f'{name}-browser-roundtrip.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'nodes':len(result['native']['nodes']),'links':len(result['native']['links']),'two_loads_semantically_equal':True}))
    browser.close()
