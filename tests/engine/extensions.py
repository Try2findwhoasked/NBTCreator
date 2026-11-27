"""Explicit extension registries preserve contracts, isolation and cache identity."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import BytesIO, StringIO
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_extensions import HandlerRegistry, RecipeCompilation, AGENT_TOOLS, RECIPE_COMPILERS, MODEL_ACTIONS, compile_recipe
from nbt_modeling_session import ModellingSession, engine_revision
from nbt_agent.structure import dispatch, definitions
from nbt_composition.working_model import WorkingModel, main as model_main


def cube_spec(material='stone'):
    return dict(name='扩展测试方块',size=[1,1,1],anchor=[0,0,0],operations=[dict(
        kind='box',label='扩展生成几何',classification='body',lo=[0,0,0],hi=[0,0,0],state=material)])


class Registries(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def replace(self, registry, name, handler):
        original = registry[name]
        registry.register(name,handler,replace=True)
        self.addCleanup(lambda: registry.register(name,original,replace=True))

    def register(self, registry, name, handler):
        registry.register(name,handler)
        self.addCleanup(lambda: registry.unregister(name))

    def test_registry_duplicates_explicit_replacement_and_stable_reads(self):
        registry = HandlerRegistry('test')
        @registry.register('example')
        def first(value):
            return value+1
        before = registry.revision()
        self.assertEqual(registry.resolve('example')(2),3)
        self.assertEqual(registry.revision(),before)
        with self.assertRaisesRegex(ValueError,'已注册'):
            registry.register('example',lambda x:x)
        with self.assertRaisesRegex(ValueError,'布尔开关'):
            registry.register('example',lambda x:x,replace='yes')
        registry.register('example',lambda x:x*2,replace=True)
        self.assertEqual(registry['example'](3),6)
        self.assertNotEqual(registry.revision(),before)
        registry.unregister('example')
        with self.assertRaisesRegex(ValueError,'未注册'):
            registry.resolve('example')
        for name in ('../module','',None):
            with self.assertRaises(ValueError):
                registry.register(name,first)
        with self.assertRaises(TypeError):
            registry.register('invalid',42)

    def test_builtin_registries_match_public_tools_and_action_contracts(self):
        from nbt_runtime.catalog import catalog
        self.assertEqual(set(AGENT_TOOLS),set(catalog()['agent_tools']))
        self.assertEqual(set(MODEL_ACTIONS),set(catalog()['working_model']['actions']))
        self.assertIn('pattern_repeat_detect', AGENT_TOOLS)
        recipe_tools = catalog()['working_model']['actions']['install']['properties']['recipe']['properties']['tool']['enum']
        self.assertEqual(set(RECIPE_COMPILERS), set(recipe_tools))
        self.assertIn('structure',RECIPE_COMPILERS)
        self.assertNotIn('structure_save',RECIPE_COMPILERS)

    def test_public_schema_validation_runs_before_an_overridden_handler(self):
        calls = []
        self.replace(AGENT_TOOLS,'parametric_compile',lambda workspace,args:calls.append(args) or {'registered':True})
        with self.assertRaises(ValueError):
            dispatch(self.root,'parametric_compile',dict(kind='pillar',size=[-1,5,3]))
        self.assertEqual(calls,[])
        self.assertEqual(dispatch(self.root,'parametric_compile',dict(kind='pillar',size=[3,5,3])),{'registered':True})
        self.assertEqual(len(calls),1)

    def test_unpublished_tool_registration_cannot_bypass_the_catalogue(self):
        self.register(AGENT_TOOLS,'unpublished_tool',lambda workspace,args:None)
        with self.assertRaisesRegex(ValueError,'目录与Python实现不一致'):
            definitions()

    def test_custom_recipe_is_shared_by_working_models_and_declared_scenes(self):
        calls=[]
        def compiler(workspace,args):
            calls.append(args)
            return RecipeCompilation(spec=cube_spec(args.get('material','stone')))
        self.register(RECIPE_COMPILERS,'extension_cube',compiler)
        working = WorkingModel(self.root,[16,8,16],kind='component')
        working.install('custom',dict(tool='extension_cube',arguments=dict(material='gold_block')),[4,1,4])
        self.assertEqual(working.model.get((4,1,4)),'minecraft:gold_block')
        graph = dict(schema_version=1,name='已声明扩展配方',size=[8,8,8],objects=[dict(id='custom',lo=[1,1,1],
            recipe=dict(tool='extension_cube',arguments={}))])
        with self.assertRaises(ValueError):
            dispatch(self.root,'scene_compile',dict(graph=graph))
        # Simulate the catalogue declaration required for public/JSON exposure.
        declared = definitions()
        declared['scene_compile']['parameters']['properties']['graph']['properties']['objects']['items']['properties']['recipe']['properties']['tool']['enum'].append('extension_cube')
        with patch('nbt_agent.structure._definitions',return_value=declared):
            result = dispatch(self.root,'scene_compile',dict(graph=graph))
        self.assertEqual(result['block_count'],1)
        self.assertEqual(len(calls),2)

    def test_custom_components_are_validated_and_still_obey_host_protection(self):
        component=dict(schema_version=1,name='直接方块',size=[1,1,1],anchor=[0,0,0],palette=['stone'],blocks=[[0,0,0,0,False]])
        self.register(RECIPE_COMPILERS,'direct_component',lambda workspace,args:RecipeCompilation(component=component,metadata={'custom':True}))
        first,metadata=compile_recipe(self.root,dict(tool='direct_component',arguments={}))
        self.assertEqual(metadata,{'custom':True})
        first['blocks'][0][0]=99
        second,_=compile_recipe(self.root,dict(tool='direct_component',arguments={}))
        self.assertEqual(second['blocks'][0][0],0)
        working=WorkingModel(self.root,[8,8,8],context=dict(mode='standalone',openings=[],protected_boxes=[dict(lo=[1,1,1],hi=[1,1,1])]))
        with self.assertRaisesRegex(ValueError,'保护'):
            working.install('protected',dict(tool='direct_component',arguments={}),[1,1,1])
        self.assertFalse(working.instances)
        component['blocks'].append([0,0,0,0,False])
        with self.assertRaisesRegex(ValueError,'重复'):
            compile_recipe(self.root,dict(tool='direct_component',arguments={}))

    def test_recipe_result_contract_rejects_ambiguous_or_invalid_returns(self):
        self.register(RECIPE_COMPILERS,'invalid_result',lambda workspace,args:None)
        with self.assertRaisesRegex(ValueError,'RecipeCompilation'):
            compile_recipe(self.root,dict(tool='invalid_result',arguments={}))
        self.replace(RECIPE_COMPILERS,'invalid_result',lambda workspace,args:RecipeCompilation(spec={},component={}))
        with self.assertRaisesRegex(ValueError,'二选一'):
            compile_recipe(self.root,dict(tool='invalid_result',arguments={}))
        with self.assertRaisesRegex(ValueError,'未注册'):
            compile_recipe(self.root,dict(tool='missing',arguments={}))
        with self.assertRaises(ValueError):
            compile_recipe(self.root,dict(tool='structure',arguments={},module='arbitrary'))

    def test_custom_model_actions_need_a_public_contract_before_cli_dispatch(self):
        calls=[]
        def paint(model,args):
            calls.append(args)
            return model.patch([dict(pos=[1,1,1],before=['minecraft:air',False],after=['minecraft:gold_block',False])])
        self.register(MODEL_ACTIONS,'paint_one',paint)
        request=self.root/'request.json'
        request.write_text(json.dumps(dict(size=[8,8,8],kind='component',actions=[dict(method='paint_one')],positions=[[1,1,1]])),encoding='utf8')
        argv=['model','--workspace',str(self.root),'--request',str(request)]
        with patch.object(sys,'argv',argv),redirect_stdout(StringIO()):
            self.assertEqual(model_main(),1)
        self.assertEqual(calls,[])
        from nbt_runtime.catalog import catalog
        declared=deepcopy(catalog())
        declared['working_model']['parameters']['properties']['actions']['items']['properties']['method']['enum'].append('paint_one')
        declared['working_model']['actions']['paint_one']=dict(type='object',additionalProperties=False,
            properties=dict(method=dict(type='string',enum=['paint_one'])),required=['method'])
        output=StringIO()
        with patch('nbt_runtime.catalog.catalog',return_value=declared),patch.object(sys,'argv',argv),redirect_stdout(output):
            self.assertEqual(model_main(),0)
        self.assertEqual(json.loads(output.getvalue())['result']['model']['samples'][0]['value'],['minecraft:gold_block',False])
        self.assertEqual(len(calls),1)

    def test_registry_changes_invalidate_warm_computation_results(self):
        from PIL import Image
        import nbt_pattern.micro_alignment as nbt_micro_alignment
        source=self.root/'pattern.png'
        Image.new('L',(16,16),255).save(source)
        args=dict(surface='wall',size_uv=[2,2],sample=dict(path='pattern.png',sha256=hashlib.sha256(source.read_bytes()).hexdigest(),noise_strength=0))
        original=RECIPE_COMPILERS['structure']
        with ModellingSession(self.root),patch.object(nbt_micro_alignment,'adaptive_fit',wraps=nbt_micro_alignment.adaptive_fit) as fit:
            dispatch(self.root,'pattern_microfit',args)
            dispatch(self.root,'pattern_microfit',args)
            self.assertEqual(fit.call_count,1)
            before=engine_revision()
            self.replace(RECIPE_COMPILERS,'structure',original)
            self.assertNotEqual(before,engine_revision())
            dispatch(self.root,'pattern_microfit',args)
            self.assertEqual(fit.call_count,2)

    def test_live_transport_rejects_registry_changes_without_executing_tool(self):
        from nbt_engine_session import serve
        outer=self
        class ChangedInput(BytesIO):
            def readline(self,*args):
                if self.tell()==0:
                    outer.replace(AGENT_TOOLS,'parametric_list',lambda workspace,args: {'must_not_run':True})
                return super().readline(*args)
        request=dict(id='one',method='agent',params=dict(tool='parametric_list',arguments={}))
        sink=BytesIO()
        serve(self.root,ChangedInput(json.dumps(request).encode()+b'\n'),sink)
        response=json.loads(sink.getvalue())
        self.assertFalse(response['ok'])
        self.assertEqual(response['code'],'STALE_ENGINE')

    def test_recipe_compilation_cannot_write_preview_artifacts(self):
        args = dict(surface='wall',size_uv=[2,2],preview=True)
        with self.assertRaisesRegex(ValueError,'纯配方'):
            compile_recipe(self.root,dict(tool='pattern_microfit',arguments=args))
        self.assertFalse((self.root/'nbt_models').exists())

    def test_registration_implementation_identity_is_stable_across_processes(self):
        import os
        import subprocess
        script = """from nbt_extensions import RECIPE_COMPILERS, RecipeCompilation
from nbt_composition.object_scene import engine_hash
RECIPE_COMPILERS.register('local', lambda workspace,args: RecipeCompilation(spec={'material':'MATERIAL'}))
print(engine_hash())
"""
        environment = dict(os.environ,PYTHONPATH=str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
        hashes = [subprocess.check_output([sys.executable,'-B','-c',script.replace('MATERIAL',material)],
            env=environment,text=True).strip() for material in ('stone','stone','gold_block')]
        self.assertEqual(hashes[0],hashes[1])
        self.assertNotEqual(hashes[0],hashes[2])
        registry = HandlerRegistry('versioned')
        handler = lambda value:value
        registry.register('local',handler,version='build-1')
        first = registry.revision()
        registry.register('local',handler,replace=True,version='build-2')
        self.assertNotEqual(first[-1],registry.revision()[-1])


if __name__=='__main__':
    unittest.main(verbosity=2)
