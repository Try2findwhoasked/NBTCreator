"""Synthetic checks for shared catalogue, relocation and non-destructive migration."""
import hashlib,json,sys,tempfile,unittest,shutil,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ENGINE=ROOT/'.agents/skills/minecraft-nbt-modeler';sys.path.insert(0,str(ENGINE/'scripts'))
from nbt_capabilities import capabilities
from nbt_exposure import MISE_TASK,apply as expose,import_knowledge
from nbt_workspace import migrate
from nbt_project.request_paths import read_request,metadata_path
from nbt_detail_control import default_settings,compile_plan,preview_effect
from nbt_refine import save_master
from nbt_assembly import Volume

class Contracts(unittest.TestCase):
 def run_mise(self,root,*args):
  mise=shutil.which('mise.exe') or shutil.which('mise')
  if not mise:self.skipTest('mise is unavailable on PATH')
  env=dict(os.environ,PATH=str(Path(sys.executable).parent)+os.pathsep+os.environ.get('PATH',''))
  run=subprocess.run([mise,'run',*args],cwd=root,capture_output=True,text=True,encoding='utf8',env=env,timeout=30)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr)
  return run.stdout.strip()
 def test_mise_uses_the_moved_creative_workspace_even_with_a_parent_task(self):
  with tempfile.TemporaryDirectory() as temp:
   parent=Path(temp);(parent/'mise.toml').write_text('[tasks.nbt]\nrun = "echo parent-nbt"\n',encoding='utf8')
   root=parent/'创作 项目';root.mkdir();user_config=root/'mise.toml'
   user_bytes=b'[tasks.local-check]\nrun = "echo my-project"\n';user_config.write_bytes(user_bytes)
   result=expose(root)
   self.assertEqual(result['launcher'],'mise run nbt --');self.assertEqual(user_config.read_bytes(),user_bytes)
   self.assertTrue((root/MISE_TASK).is_file())
   (root/'请求 & 样例.json').write_text(json.dumps(dict(workflow='prompt',query='石拱'),ensure_ascii=False),encoding='utf8')
   moved=parent/'移动 后';root.rename(moved);subdir=moved/'sub';subdir.mkdir()
   paths=json.loads(self.run_mise(subdir,'nbt','--','paths'))
   self.assertEqual(Path(paths['workspace']),moved.resolve())
   self.assertTrue((Path(paths['scripts'])/'nbt_knowledge/saved_references.py').is_file())
   found=json.loads(self.run_mise(subdir,'nbt','--','retrieve','search','--request','请求 & 样例.json'))
   self.assertEqual(found['query'],'石拱')
   self.assertEqual(self.run_mise(subdir,'nbt','--','task','--help'),
                    self.run_mise(subdir,'nbt','--','prompts','task','--help'))

 def test_mise_preserves_a_user_owned_nbt_task_and_points_to_the_exact_launcher(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);expose(root)
   config=root/'mise.toml';original=b'[tasks.nbt]\nrun = "echo own-nbt"\n';config.write_bytes(original)
   result=expose(root)
   self.assertEqual(config.read_bytes(),original);self.assertFalse((root/MISE_TASK).exists())
   self.assertEqual(self.run_mise(root,'nbt'),'own-nbt')
   path='./.agents/skills/nbtcreator-workspace/nbt.py'
   self.assertEqual(result['launcher'],f'mise run {path} --')
   text=(root/'.agents/skills/nbtcreator-workspace/SKILL.md').read_text(encoding='utf8')
   self.assertIn(f'mise run {path} -- <命令>',text)
   self.assertEqual(Path(json.loads(self.run_mise(root,path,'--','paths'))['workspace']),root.resolve())

 def test_software_source_root_does_not_regenerate_an_authoring_facade(self):
  with self.assertRaisesRegex(ValueError,'软件源码或安装目录'):expose(ROOT)
 def test_exposed_paths_are_callable_after_relocation_and_locate_importable_api(self):
  with tempfile.TemporaryDirectory() as temp:
   old=Path(temp)/'old';new=Path(temp)/'new';expose(old)
   shutil.copytree(old,new);shutil.rmtree(old)
   command=[sys.executable,str(new/'.agents/skills/nbtcreator-workspace/nbt.py'),'paths']
   run=subprocess.run(command,cwd=new,capture_output=True,text=True,encoding='utf8')
   self.assertEqual(run.returncode,0,run.stderr);data=json.loads(run.stdout)
   self.assertTrue(Path(data['engine']).is_relative_to(new.resolve()))
   self.assertTrue((Path(data['scripts'])/'nbt_openings.py').is_file())
   self.assertEqual(Path(data['workspace']),new.resolve());self.assertEqual(len(data['runtime_bundle_sha256']),64)
   imported=subprocess.run([sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);from nbt_openings import open_declared_openings;print(callable(open_declared_openings))',data['scripts']],capture_output=True,text=True)
   self.assertEqual(imported.returncode,0,imported.stderr);self.assertEqual(imported.stdout.strip(),'True')
 def test_catalogue_and_generic_gui_operations(self):
  c=capabilities();self.assertEqual(set(c['tools']),set(json.loads((ENGINE/'tool-catalog.json').read_text(encoding='utf8'))['tools']))
  s=default_settings();s['operations']=[dict(kind='box',label='same engine',classification='body',lo=[4,4,4],hi=[4,5,4],state='stone')]
  self.assertEqual(compile_plan(s,(48,16,48))['operations'],s['operations'])
  s['operations'][0]['kind']='run_python'
  with self.assertRaises(ValueError):compile_plan(s,(48,16,48))
 def test_exposure_keeps_core_and_does_not_remove_knowledge(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);result=expose(root,dict(schema_version=1,enabled_groups=['architecture']))
   self.assertIn('core',result['enabled_groups'])
   text=(root/'.agents/skills/nbtcreator-workspace/knowledge.md').read_text(encoding='utf8')
   self.assertIn('architecture-knowledge-base.md',text);self.assertNotIn('micro-props.md',text)
   self.assertTrue((ENGINE/'references/micro-props.md').is_file())
   self.assertNotIn(str(ENGINE),text)
 def test_request_relative_survives_whole_workspace_move(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);old=root/'old';new=root/'new';(old/'nbt_models/room').mkdir(parents=True)
   (old/'nbt_models/room/model.nbt').write_bytes(b'fixture')
   request=dict(path_base='workspace',source='nbt_models/room/model.nbt',context='',settings={})
   (old/'request.json').write_text(json.dumps(request),encoding='utf8');shutil.copytree(old,new)
   loaded=read_request(new/'request.json',workspace=new);self.assertEqual(Path(loaded['source']).read_bytes(),b'fixture');self.assertTrue(Path(loaded['source']).is_relative_to(new.resolve()))
 def test_legacy_paths_remain_accepted(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);f=root/'request.json';f.write_text(json.dumps({'source':str(root/'master.gz')}),encoding='utf8')
   self.assertEqual(read_request(f)['source'],str((root/'master.gz').resolve()))
 def test_migration_verified_and_metadata_rebased(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);old=root/'old';new=root/'agent';room=old/'nbt_models/single/房间/v01';room.mkdir(parents=True)
   master=room/'master.json.gz';master.write_bytes(b'unchanged')
   (room/'room_description.json').write_text(json.dumps({'master':str(master)}),encoding='utf8')
   cache=old/'nbt_models/_workspaces';cache.mkdir();(cache/'approval.json').write_text('synthetic evidence',encoding='utf8')
   result=migrate(old,new);self.assertEqual(result['status'],'complete');self.assertEqual(result['files'],3)
   description=new/'nbt_models/single/房间/v01/room_description.json';data=json.loads(description.read_text(encoding='utf8'));self.assertEqual(metadata_path(description,data['master']).read_bytes(),b'unchanged')
   self.assertEqual(master.read_bytes(),b'unchanged');self.assertEqual(migrate(old,new),result)
 def test_migration_refuses_conflict_before_copy(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);old=root/'old';new=root/'new';(old/'nbt_models').mkdir(parents=True);(new/'nbt_models').mkdir(parents=True)
   (old/'nbt_models/a.nbt').write_bytes(b'old');(new/'nbt_models/a.nbt').write_bytes(b'new')
   with self.assertRaises(ValueError):migrate(old,new)
   self.assertEqual((old/'nbt_models/a.nbt').read_bytes(),b'old');self.assertEqual((new/'nbt_models/a.nbt').read_bytes(),b'new')
 def test_exposed_skill_moves_with_workspace_and_runs_without_old_directory(self):
  with tempfile.TemporaryDirectory() as temp:
   old=Path(temp)/'old';new=Path(temp)/'new';expose(old,dict(schema_version=1,enabled_groups=['props']))
   shutil.copytree(old,new);shutil.rmtree(old)
   run=subprocess.run([sys.executable,str(new/'.agents/skills/nbtcreator-workspace/nbt.py'),'capabilities'],cwd=new,capture_output=True,text=True,encoding='utf8')
   self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(set(json.loads(run.stdout)['tools']),set(capabilities()['tools']))
   text=(new/'.agents/skills/nbtcreator-workspace/SKILL.md').read_text(encoding='utf8');self.assertIn('.nbtcreator/runtimes',text);self.assertNotIn(str(ROOT),text)
 def test_custom_knowledge_copied_selected_and_portable(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);workspace=root/'project';doc=root/'建筑规范.md';doc.write_text('梁端需要承托。',encoding='utf8')
   result=import_knowledge(workspace,[doc]);item=result['custom_knowledge'][0];self.assertTrue((workspace/'.nbtcreator'/item['path']).is_file());self.assertIn('建筑规范',(workspace/'.agents/skills/nbtcreator-workspace/knowledge.md').read_text(encoding='utf8'))
   item['enabled']=False;expose(workspace,dict(schema_version=1,enabled_groups=['core'],custom_knowledge=[item]));self.assertNotIn('建筑规范',(workspace/'.agents/skills/nbtcreator-workspace/knowledge.md').read_text(encoding='utf8'));self.assertTrue(doc.is_file());self.assertTrue((workspace/'.nbtcreator'/item['path']).is_file())
 def test_task_entry_and_selected_inventory_have_separate_filtered_responsibilities(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);expose(root,dict(schema_version=1,enabled_groups=['modelling']))
   facade=root/'.agents/skills/nbtcreator-workspace'
   entry=(facade/'SKILL.md').read_text(encoding='utf8');index=(facade/'knowledge.md').read_text(encoding='utf8')
   for name in ('pattern-fitting.md','pattern-authoring.md','surface-mounting.md','modeling-sessions.md'):
    self.assertIn(name,index)
   self.assertNotIn('pattern-fitting.md',entry);self.assertIn('knowledge.md',entry)
   for route in ('task-client inspect prompts <id>','task-client inspect tasks <id>'):
    self.assertLess(entry.index(route),entry.index('capabilities --routes'))
   self.assertIn('asset-libraries browse --request <JSON文件>',entry);self.assertIn('{"query":"尖拱","limit":4}',entry)
   for hint in ('architect plan-build --request <JSON文件>','capabilities --architect-action plan-build',
                'model --request <JSON文件>','selection-edit context --request <JSON文件>',
                'selection-edit.md','result.passed','report.path'):
    self.assertIn(hint,entry)
   self.assertNotIn('micro-props.md',entry);self.assertNotIn('micro-props.md',index)
   self.assertNotIn(str(ENGINE),entry+index)
   marker=json.loads((root/'.nbtcreator/facade-manifest.json').read_text(encoding='utf8'))
   self.assertEqual(set(marker),{'SKILL.md','knowledge.md','nbt.py'})
   self.assertLess(len(entry),2400)

 def test_resynchronizing_backs_up_a_user_edited_generated_inventory(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);config=dict(schema_version=1,enabled_groups=['core']);expose(root,config)
   index=root/'.agents/skills/nbtcreator-workspace/knowledge.md'
   edited=index.read_text(encoding='utf8')+'\n用户补充的索引注记\n';index.write_text(edited,encoding='utf8')
   expose(root,config)
   backups=list((root/'.nbtcreator/skill-backups').glob('*/knowledge.md'))
   self.assertEqual(len(backups),1);self.assertEqual(backups[0].read_text(encoding='utf8'),edited)
   self.assertNotIn('用户补充的索引注记',index.read_text(encoding='utf8'))

 def test_facade_manifest_matches_disk_and_resync_accepts_legacy_windows_newlines(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);config=dict(schema_version=1,enabled_groups=['core']);expose(root,config)
   facade=root/'.agents/skills/nbtcreator-workspace'
   marker=root/'.nbtcreator/facade-manifest.json'
   for name,checksum in json.loads(marker.read_text(encoding='utf8')).items():
    file=facade/name
    self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),checksum)
    file.write_bytes(file.read_text(encoding='utf8').replace('\n','\r\n').encode('utf8'))
   expose(root,dict(config,enabled_groups=['core','props']))
   self.assertFalse((root/'.nbtcreator/skill-backups').exists())
   entry=(facade/'knowledge.md').read_text(encoding='utf8')
   self.assertIn('render --help',entry);self.assertIn('仅在启用或用户明确指定',entry)
   self.assertNotIn('rendering.md',entry)
   self.assertEqual(sum(line.startswith('| 验证、看图') for line in entry.splitlines()),1)
   self.assertIn('查看实际图片',entry)
   expose(root,dict(config,enabled_groups=['core','rendering']))
   entry=(facade/'knowledge.md').read_text(encoding='utf8')
   route,=[line for line in entry.splitlines() if line.startswith('| 验证、看图')]
   self.assertIn('/references/diagnostic-guidance.md',route)
   self.assertIn('/references/rendering.md',route)
   self.assertIn('查看实际图片',route)

 def test_authoring_entry_keeps_pattern_tools_and_loads_maintenance_only_when_enabled(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);expose(root,dict(schema_version=1,enabled_groups=['core']))
   entry=(root/'.agents/skills/nbtcreator-workspace/knowledge.md').read_text(encoding='utf8')
   self.assertNotIn('state-and-maintenance.md',entry)
   self.assertNotIn('extensions.md',entry)
   self.assertIn('capabilities --agent-tool pattern_microfit',entry)
   self.assertIn('retrieve architecture --library',entry)
   run=subprocess.run([sys.executable,str(root/'.agents/skills/nbtcreator-workspace/nbt.py'),'capabilities','--agent-tool','pattern_microfit'],cwd=root,capture_output=True,text=True,encoding='utf8')
   self.assertEqual(run.returncode,0,run.stderr)
   self.assertIn('pattern_microfit',run.stdout)
   expose(root,dict(schema_version=1,enabled_groups=['core','maintenance']))
   maintenance=(root/'.agents/skills/nbtcreator-workspace/knowledge.md').read_text(encoding='utf8')
   self.assertIn('state-and-maintenance.md',maintenance)
   self.assertIn('extensions.md',maintenance)

 def test_frozen_entry_exposes_compact_tool_routes_without_running_tools(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);expose(root,dict(schema_version=1,enabled_groups=['core']))
   facade=root/'.agents/skills/nbtcreator-workspace'
   self.assertIn('capabilities --routes',(facade/'SKILL.md').read_text(encoding='utf8'))
   command=[sys.executable,str(facade/'nbt.py'),'capabilities']
   before=set(root.rglob('*'))
   for flag in ('-h','--help'):
    help_run=subprocess.run([*command[:-1],flag],cwd=root,capture_output=True,text=True,encoding='utf8')
    self.assertEqual(help_run.returncode,0,help_run.stderr)
    self.assertIn('capabilities --routes',help_run.stdout)
   unknown=subprocess.run([*command[:-1],'part-search'],cwd=root,capture_output=True,text=True,encoding='utf8')
   self.assertEqual(unknown.returncode,1)
   self.assertIn('capabilities --routes',unknown.stderr)
   run=subprocess.run([*command,'--routes'],cwd=root,capture_output=True,text=True,encoding='utf8')
   self.assertEqual(run.returncode,0,run.stderr)
   self.assertEqual(set(root.rglob('*')),before)
   routes=json.loads(run.stdout)
   self.assertEqual(set(routes),{'tool_routes','capabilities_sha256','gui_required'})
   self.assertEqual(routes['tool_routes'],capabilities()['tool_routes'])
   self.assertEqual(routes['capabilities_sha256'],capabilities()['capabilities_sha256'])
   groups=routes['tool_routes']
   self.assertEqual(list(groups)[:3],['创作起步','局部修改','找素材与复用'])
   for group,first_call,contract,next_field in (
       ('创作起步','architect plan-build','capabilities --architect-action plan-build','next.request'),
       ('局部修改','selection-edit context','selection-edit.md','geometry_sha256'),
       ('找素材与复用','asset-libraries browse','asset-libraries --help','content_sha256')):
    route=groups[group][0]
    self.assertTrue(route['call'].startswith(first_call))
    self.assertIn(contract,(route.get('contract'),route['guide']))
    self.assertIn(next_field,route['next'])
   output=subprocess.check_output([*command,'--operations'],cwd=root,text=True,encoding='utf8')
   operations=json.loads(output)['operations']
   self.assertEqual(set(operations),set(capabilities()['tools']))
   self.assertEqual(set(operations['box']),{'title','hint'})
   invalid=subprocess.run([*command,'--routes','--model'],cwd=root,capture_output=True,text=True,encoding='utf8')
   self.assertEqual(invalid.returncode,2)

 def test_core_facade_exposes_both_draft_routes_and_the_blocked_landing_example(self):
  with tempfile.TemporaryDirectory() as temp:
   root = Path(temp).resolve()
   expose(root, dict(schema_version=1, enabled_groups=['core']))
   facade = root / '.agents/skills/nbtcreator-workspace'
   entry = (facade / 'SKILL.md').read_text(encoding='utf8')
   index = (facade / 'knowledge.md').read_text(encoding='utf8')
   self.assertIn('整栋初稿：纯文字', index)
   self.assertIn('整栋初稿：有参考图', index)
   self.assertIn('architect layout-check', entry)
   self.assertIn('references/whole-building-planning.md', index)
   for reference in ('design-grammar.md','architecture-knowledge-base.md','structure-atlas.md',
                     'organic-spaces.md','linked-spaces.md'):
    self.assertNotIn(reference,entry)
    self.assertNotIn(reference,index)
   paths = subprocess.check_output([sys.executable, str(facade / 'nbt.py'), 'paths'], cwd=root)
   example = Path(json.loads(paths)['engine']) / 'assets/examples/reading-loft'
   self.assertIn(os.path.relpath(example / 'README.md', facade).replace(os.sep, '/'), entry)
   planning = example.parent / 'whole-building-planning.json'
   checked = subprocess.check_output([sys.executable, str(facade / 'nbt.py'), 'architect',
                                      'layout-check', '--request', str(planning)], cwd=root)
   self.assertTrue(json.loads(checked)['passed'])
   result = subprocess.run([sys.executable, '-B', str(example / 'run.py'), 'blocked'], cwd=root, capture_output=True)
   self.assertEqual(result.returncode, 1)
   receipt, = root.glob('nbt_models/_workspaces/examples/*/plan-build-result.json')
   error = json.loads(receipt.read_bytes())['error']
   code, payload = error.split(': ', 1)
   self.assertEqual(code, 'ROUTE_FAILED')
   targets = {row['name']: row for row in json.loads(payload)[0]['targets']}
   self.assertTrue(targets['return_desk']['reachable'])
   self.assertEqual(targets['stair_landing']['feet'], [5.5, 5, 19.5])
   self.assertEqual(targets['stair_landing']['reason'], 'invalid_or_obstructed_feet_pose')
   self.assertFalse(targets['archive_shelf']['reachable'])
   self.assertFalse(list(root.rglob('model.snbt')))

if __name__=='__main__':unittest.main(verbosity=2)
