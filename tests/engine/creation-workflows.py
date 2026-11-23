"""Exercise the frozen external Agent route with real geometry and PNG artifacts."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[2]
SKILL=ROOT/'.agents/skills/minecraft-nbt-modeler'
sys.path[:0]=[str(SKILL/'scripts'),str(SKILL/'assets/examples/reading-loft')]

from nbt_building.plan import build
from nbt_building.workflow import dispatch
from nbt_project.prompts import publish, save, read_task
from nbt_review.blind_review import _public
from plan import reading_loft


class CreationWorkflows(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='nbt-creation-')
        self.addCleanup(temp.cleanup)
        self.workspace=Path(temp.name).resolve()
        self.environment=dict(os.environ,PYTHONIOENCODING='utf-8')

    def cli(self, *args, failure=False, env=None):
        output=subprocess.run([sys.executable,'-B',str(self.entry),*args],cwd=self.workspace,
                              encoding='utf8',capture_output=True,env=env or self.environment,timeout=240)
        self.assertEqual(output.returncode,1 if failure else 0,output.stdout+output.stderr)
        return json.loads(output.stdout)

    def init(self, session, name, creation=None, settings=None, size=None):
        self.entry=SKILL/'scripts/nbt_exposure.py'
        if not (self.workspace/'.agents/skills/nbtcreator-workspace/nbt.py').is_file():
            self.cli('apply','--workspace',str(self.workspace))
        self.entry=self.workspace/'.agents/skills/nbtcreator-workspace/nbt.py'
        self.session=session
        payload=dict(session_id=uuid4().hex,document=dict(project=dict(name=name,stage='draft',
            buildingShape='standalone',size=size or [21,16,28],size_policy='fixed'),user_requirements='窗边收卷。\n管理员登梯归架。'),
            text='窗边收卷。\n管理员登梯归架。',plan={},context={'mode':'standalone'})
        saved=save(self.workspace,payload)
        task=publish(self.workspace,saved['index'],saved['id'],saved['revision'],creation=creation)
        inspected=self.cli('task-client','inspect','prompts',task['id'])['data']
        self.assertIn('creation',inspected['next']['after_claim'])
        self.cli('task-client','--session',session,'start','prompts',task['id'],'--owner','creation-test')
        return task, self.action('start',settings)

    def action(self, name, request=None, **options):
        args=[]
        if request is not None:
            file=self.workspace/f'{uuid4().hex}.json'
            file.write_text(json.dumps(request,ensure_ascii=False),encoding='utf8')
            args=['--request',str(file)]
        return self.cli('creation','--session',self.session,name,*args,**options)['data']

    def observations(self, target, slot):
        rows=[dict(image=image, note='自动化只验证真实 PNG 与观察协议的绑定。')
              for image in target['review']['awaiting_views']]
        by_view={row['image']:row for row in rows}
        for location in target['review']['required_locations']:
            by_view[location['views'][0]].setdefault('locations',[]).append(location['id'])
        return self.action('observe',dict(slot=slot,observations=rows))

    def comparison_options(self, plan):
        from PIL import Image
        from nbt_agent.creation_execution import Execution, reference, saved_binding
        from nbt_review.reference_camera import prepare_cameras
        from nbt_review.reference_views import register_reference

        inputs=self.workspace/'references'
        inputs.mkdir()
        views={}
        for name,u,v in [('front','x','-y'),('side','z','-y'),('top','x','z')]:
            image=inputs/(name+'.png')
            Image.new('RGB',(160,160),'white').save(image)
            origin=[12,120] if name!='top' else [12,12]
            views[name]=dict(image=str(image),sha256=reference(image)['sha256'],origin=origin,
                             pixels_per_block=4,u_axis=u,v_axis=v,origin_type='original',basis='合成登记用例')
        registered=register_reference(self.workspace,dict(output='nbt_models/_workspaces/reference-views/loft',
            views=views,assumptions=['背面推定'],anchors=[dict(id='door',part='hall',world=[10,2,2],basis='合成基点',
                confidence='measured',uncertainty=0,views={'front':[52,112],'side':[20,112],'top':[52,20]})]))
        old=build(self.workspace,dict(plan=plan,save_draft=dict(name_zh='留存参照阁')))['saved']
        cameras=prepare_cameras(self.workspace,dict(saved_binding(old),reference=registered['manifest'],
            reference_sha256=registered['manifest_sha256'],output='nbt_models/_workspaces/reference-cameras/loft'))
        front=cameras['views']['front']
        folder=self.workspace/'nbt_models/_workspaces/retained-evidence'
        folder.mkdir(parents=True)
        pack=dispatch(self.workspace,'review-prepare',dict(saved_binding(old),output=str(folder/'review')))
        rendered=Execution(self.workspace,folder,lambda:None).render(old,pack['cameras'])
        rows={view['id']:dict(image=view['id'],note='测试观察契约。') for view in pack['coverage']['views']}
        for location in pack['coverage']['review_locations']:
            selected=next(row['view'] for row in location['candidates'] if row['passed'])
            rows[selected].setdefault('locations',[]).append(location['id'])
        notes=dispatch(self.workspace,'review-record',dict(pack['review_record_bindings'],
            render_manifest=rendered['render']['path'],observations=list(rows.values()),
            issues=[dict(id='frame',layer='massing',text='比较前后框架材质的明暗层次。',images=['outside'])]))
        return dict(axes=['主材'], reference=dict(manifest=dict(path=registered['manifest'],sha256=registered['manifest_sha256']),
                         fixed=['保留画布尺寸'],explore=['框架材质'],canvas_size=plan['size']),
                    comparison=dict(cameras=dict(path=str(Path(cameras['bundle']).parent/front['file']),sha256=front['sha256']),
                        bundle=dict(path=cameras['bundle'],sha256=cameras['bundle_sha256']),width=front['width'],height=front['height']),
                    retained_review=dict(path=notes['path'],sha256=notes['sha256']))

    def test_economy_diagnostics_operational_retry_and_completed_review(self):
        task,brief=self.init('economy','测试归卷阁',{'quality_model':'test-strong','economy_model':'test-low'})
        self.assertEqual(brief['user_requirements'],'窗边收卷。\n管理员登梯归架。')
        self.assertEqual([row['model'] for row in brief['requests']],['test-low'])
        result=self.action('candidate',dict(slot='1',plan=reading_loft(blocked=True)),failure=True)
        self.assertEqual(result['category'],'design')
        self.assertTrue(any(row['target']=='stair_landing' for row in result['diagnostics']['new']))
        self.assertEqual(result['next_request']['model'],'test-strong')
        result=self.action('candidate',dict(slot='1',plan=reading_loft(wrong_side=True)),failure=True)
        self.assertEqual(result['category'],'design')
        self.assertTrue(any(row['target']=='return_desk.intake' and row['evidence']['reason']=='wrong_side'
                            for row in result['diagnostics']['new']))
        request=dict(slot='1',plan=reading_loft(),model_usage={'calls':1,'input_tokens':134,'output_tokens':57})
        missing=dict(self.environment,NBTCREATOR_PLAYWRIGHT_MODULE=str(self.workspace/'no-playwright'))
        stopped=self.action('candidate',request,failure=True,env=missing)
        self.assertEqual((stopped['category'],stopped['stage']),('local_execution','render'))
        self.assertIsNone(stopped['next_request'])
        self.assertEqual(self.action('brief')['requests'],[])
        self.assertTrue(self.action('brief')['local_retries'])
        advanced=self.action('retry',request)
        self.assertEqual(stopped['steps'][0],advanced['steps'][0])
        self.assertEqual(advanced['status'],'ready_for_review')
        self.assertTrue(all(Path(row['path']).read_bytes().startswith(b'\x89PNG') for row in advanced['review']['images']))
        self.action('select')
        completed=self.action('publish')
        self.assertNotIn('_workspaces',completed['source']['source'])
        self.action('finish',failure=True)
        record=self.observations(completed,'published')
        self.assertTrue(record['observed'])
        self.assertEqual(self.action('finish')['acceptance'],'pending_user_review')
        self.assertEqual(self.action('finish')['acceptance'],'pending_user_review')
        self.assertEqual(read_task(self.workspace,task['id'])['task']['status'],'completed')
        self.assertFalse(list(self.workspace.rglob('*.nbt')))
        status=self.action('status')
        self.assertEqual(status['metrics']['local_retries'],1)
        self.assertEqual(status['metrics']['reported_model_calls'],1)
        self.assertEqual(status['metrics']['usage_reports'],1)

    def test_maximum_alignment_blind_selection_and_retained_review(self):
        first=reading_loft()
        options=self.comparison_options(first)
        _task,brief=self.init('maximum','测试比选阁',{'mode':'maximum','quality_model':'test-strong'},
                             options)
        self.assertEqual([row['phase'] for row in brief['requests']],['global_design','global_design'])
        self.assertEqual([row['model'] for row in brief['requests']],['test-strong','test-strong'])
        a=self.action('candidate',dict(slot='1',plan=first,variation=dict(axis='主材',decision='浅色框架')))
        second=reading_loft()
        second['style']['materials']['frame']='stripped_dark_oak_log'
        b=self.action('candidate',dict(slot='2',plan=second,variation=dict(axis='主材',decision='深色框架')))
        self.assertNotEqual(a['geometry_sha256'],b['geometry_sha256'])
        self.assertNotIn('binding',blind:=self.action('prepare-blind'))
        public_path=Path(blind['public'])
        public=_public(self.workspace,public_path,blind['public_sha256'])
        self.assertTrue(all(set(row['images'])=={'A','B','diff'} for row in public['views']))
        self.assertTrue(all(row['settings']['camera']['projection']=='orthographic' for row in public['views']))
        self.assertTrue(all((public_path.parent/row['images']['A']['file']).is_file() for row in public['views']))
        self.action('select',failure=True)
        self.action('record-blind',dict(decision='B',actor='agent',
            observations=[dict(view=public['views'][0]['id'],note='自动化仅覆盖匿名审阅契约。',remaining='审美由实际审阅判断。')]))
        selected=self.action('select')
        self.assertIn(selected['candidate'],[a['candidate'],b['candidate']])
        self.assertTrue(self.action('retest',{'slot':selected['slot'],'against':'blind'})['observation_pending'])
        winner=a if selected['slot']=='1' else b
        self.assertTrue(self.observations(winner, selected['slot'])['observed'])
        old_retest=self.action('retest',{'slot':selected['slot']})
        self.assertTrue(old_retest['same_view_observation_pending'])
        self.assertEqual(old_retest['comparison']['issues'][0]['id'],'frame')
        published=self.action('publish')
        self.assertEqual(published['candidate'],selected['candidate'])
        self.assertTrue(self.observations(published,'published')['observed'])
        self.assertEqual(self.action('finish')['acceptance'],'pending_user_review')

    def scripted_gate(self):
        from nbt_creation import submit_working_model
        from nbt_working_model import WorkingModel
        model=WorkingModel(self.workspace,[14,9,18],dict(mode='standalone',require_enclosure=False,
             start=[7.5,1,1.5],targets={'court':[7.5,1,10.5]},require_routes=True))
        blocks=[
            ('碎石庭道','body',[2,0,1],[11,0,15],'gravel'),
            ('西木柱','wall',[4,1,5],[4,5,5],'stripped_spruce_log'),
            ('东木柱','wall',[10,1,5],[10,5,5],'stripped_spruce_log'),
            ('双层门楣','body',[3,6,5],[11,6,5],'dark_oak_planks'),
            ('下垂边缘','body',[2,5,5],[3,5,5],'dark_oak_planks'),
            ('飞出端头','body',[11,6,5],[12,6,5],'dark_oak_planks'),
        ]
        model.apply_operations([dict(kind='box',label=name,classification=classification,lo=lo,hi=hi,state=state)
                                for name,classification,lo,hi,state in blocks])
        model.open_declared()
        cameras=[dict(id='front',role='whole',eye=[24,13,-14],target=[7,3,8],fov=55),
                 dict(id='entry',role='entry',eye=[7.5,2.62,1.5],target=[7,4,5],fov=65),
                 dict(id='lintel',role='structure',eye=[14,9,1],target=[9,5.5,5],fov=50)]
        return submit_working_model(self.session,dict(slot='1',working_id='gate-1',view_overrides=cameras),model)

    def test_scripted_working_model_and_stale_prompt(self):
        _first,brief=self.init('scripted','测试庭院',size=[14,9,18])
        self.assertEqual(brief['workflow']['mode'],'economy')
        outcome=self.scripted_gate()
        self.assertEqual(outcome['status'],'ready_for_review',outcome)
        self.assertFalse(outcome['review']['architecture'])
        self.assertEqual(len(outcome['review']['images']),3)
        self.action('select')
        existing=self.action('publish')
        rows=[dict(image=image,text='自动化验证图片绑定。') for image in existing['review']['awaiting_views']]
        self.action('observe',dict(slot='published',observations=rows))
        self.assertEqual(self.action('finish')['acceptance'],'pending_user_review')
        task,_brief=self.init('conflict','测试庭院',size=[14,9,18])
        self.assertEqual(self.scripted_gate()['status'],'ready_for_review')
        self.action('select')
        failed=self.action('publish',failure=True)
        self.assertEqual((failed['category'],failed['code']),('stale','STALE_PARENT'))
        self.assertTrue(Path(existing['source']['source']).is_file())
        self.assertNotIn('published',self.action('status'))
        draft_attachment=self.workspace/task['files']['提示词.md']['path']
        draft_attachment.write_text('模拟任务源在制作期间发生变化。',encoding='utf8')
        failed=self.action('select',failure=True)
        self.assertEqual((failed['category'],failed['code']),('stale','TASK_EVIDENCE_CHANGED'))


if __name__=='__main__':
    unittest.main(verbosity=2)
