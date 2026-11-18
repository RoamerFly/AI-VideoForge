import math,sys,unittest,tempfile,copy,json
from types import SimpleNamespace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'app'))
import core
import pose_pipeline as p

class PipelineTests(unittest.TestCase):
    def test_timeline_has_no_gaps_or_repeats(self):
        for n in [1,12,72,73,74,124,826,2000]:
            seg=p.plan_frames(n);cuts=[s['start']+6 for s in seg[1:]]
            frames=list(p.timeline(seg,cuts,n))
            self.assertEqual([x[0] for x in frames],list(range(n)))
            self.assertTrue(all(0<=x[2]<73 for x in frames))
        self.assertEqual(len(p.plan_frames(math.ceil(34.411995*24))),14)

    def test_input_preview_is_not_generated_output(self):
        class C:
            def comfy_output(self):return 'output'
        result={'outputs':{'1':{'images':[{'filename':'source.mp4','type':'input'},
              {'filename':'generated.mp4','type':'output','subfolder':'run'}]}}}
        self.assertEqual(p.outputs(C(),result,'.mp4'),[Path('output/run/generated.mp4')])

    def test_real_template_uses_ref2va_and_video_guide(self):
        g=core.load_template('05p');classes=[n['class_type'] for n in g.values()]
        self.assertIn('MiniMaxH3AddGuide',classes)
        self.assertEqual(g['127']['inputs']['unet_name'],'minimax_h3_ref2va_pruned_int8_convrot.safetensors')
        self.assertEqual(g['153']['inputs']['value'],73)
        self.assertEqual(core.load_template('05m')['6']['class_type'],'SAM3_VideoTrack')

    def test_old_and_new_combo_model_schemas(self):
        for spec in [[['RealESRGAN_x2plus.pth'],{}],['COMBO',{'options':['RealESRGAN_x2plus.pth']}]]:
            class C:
                def http_json(self,path):return {'UpscaleModelLoader':{'input':{'required':{'model_name':spec}}}}
            pipeline=object.__new__(p.Pipeline);pipeline.c=C()
            self.assertEqual(pipeline.model('UpscaleModelLoader','model_name','RealESRGAN_x2plus'),'RealESRGAN_x2plus.pth')

    def test_resume_does_not_queue_same_work_twice(self):
        core.TASKS.clear()
        while not core.JOB_QUEUE.empty():core.JOB_QUEUE.get_nowait()
        params={'engine':'h3_pipeline','resume_work':str(Path('test-run').resolve())}
        a=core.new_task('05','test',params);b=core.new_task('05','test',params)
        self.assertEqual(a['id'],b['id']);self.assertEqual(core.JOB_QUEUE.qsize(),1)

    def test_cancel_preserves_other_comfy_jobs(self):
        core.TASKS['cancel-test']={'params':{'engine':'h3_pipeline'},'prompt_id':'ours'}
        calls=[];original=core.http_json
        def request(path,data=None,**kw):
            calls.append((path,data))
            return {'queue_running':[[1,'somebody-else',{},{}]],'queue_pending':[[2,'ours',{},{}]]}
        core.http_json=request
        try:core.cancel_task('cancel-test')
        finally:core.http_json=original
        self.assertNotIn(('/interrupt',{}),calls)
        self.assertIn(('/queue',{'delete':['ours']}),calls)

    def test_resume_path_stays_inside_output_work(self):
        with self.assertRaises(ValueError):p.Pipeline(core,'test',{'resume_work':'C:/not-a-pipeline'},'test')

    def test_repair_only_invalidates_selected_segment_and_is_idempotent(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            work=Path(tmp)
            for kind in ['raw','composite','enhanced','masks']:
                (work/kind).mkdir()
                for i in [0,1]:
                    target=work/kind/f'{i:03d}'
                    if kind=='masks':target.mkdir();(target/'mask.png').write_bytes(b'mask')
                    else:target.with_suffix('.mp4').write_bytes(b'video')
            manifest={'segments':[{'index':i,'generation_job':{'pid':str(i)}} for i in [0,1]]}
            token='a'*32;p.prepare_repair(work,manifest,[2],token,'keep facing front')
            self.assertTrue((work/'raw/000.mp4').exists());self.assertFalse((work/'raw/001.mp4').exists())
            self.assertTrue((work/'返修备份'/token/'raw-001.mp4').exists())
            self.assertNotIn('generation_job',manifest['segments'][1])
            before=copy.deepcopy(manifest);p.prepare_repair(work,manifest,[2],token,'ignored duplicate')
            self.assertEqual(before,manifest)

    def test_transient_read_timeout_preserves_task(self):
        calls=[]
        class C:
            def task_get(self,tid):return {'status':'running'}
            def _upd(self,*args,**kwargs):pass
            def http_json(self,path,**kwargs):
                calls.append(path)
                if len(calls)==1:raise TimeoutError('temporary')
                return {'queue_running':[]}
        pipeline=object.__new__(p.Pipeline);pipeline.c=C();pipeline.tid='test'
        original=p.time.sleep;p.time.sleep=lambda _:None
        try:self.assertEqual(pipeline.read('/queue'),{'queue_running':[]})
        finally:p.time.sleep=original
        self.assertEqual(calls,['/queue','/queue'])

    def test_running_prompt_resume_retains_actual_graph_without_post(self):
        actual={'1':{'class_type':'ActualRunningGraph','inputs':{}}};count=[]
        class C:
            WATCHER=SimpleNamespace(reset=lambda:None,prompt_id='')
            def task_get(self,tid):return {'status':'running'}
            def _upd(self,*a,**kw):pass
            def http_json(self,path,data=None,**kw):
                selftest.assertIsNone(data,'Resume must not POST another generation')
                if path=='/queue':return {'queue_running':[[0,'original',actual,{}]],'queue_pending':[]}
                if path=='/history/original':
                    count.append(path)
                    if len(count)==1:return {}
                    return {'original':{'status':{'status_str':'success','completed':True},'outputs':{}}}
                raise AssertionError(path)
        selftest=self
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            work=Path(tmp);self.assertTrue(work.resolve().is_relative_to(Path(__file__).parent.resolve()))
            pipeline=object.__new__(p.Pipeline);pipeline.c=C();pipeline.tid='test';pipeline.work=work
            pipeline.state_path=work/'state.json';pipeline.m={'segments':[{'index':0}]}
            seg={'index':0,'generation_job':{'pid':'original','token':'stable'}}
            pipeline.execute({'1':{'class_type':'NewCodeGraph','inputs':{}}},seg,'generation',0,1)
            self.assertEqual(json.loads((work/'api/generation-000.json').read_text(encoding='utf-8')),actual)

if __name__=='__main__':unittest.main(verbosity=2)
