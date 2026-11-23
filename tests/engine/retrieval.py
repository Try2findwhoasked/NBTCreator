from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import shutil
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_knowledge.retrieval import dispatch, read_bundle
from unittest.mock import patch
from nbt_assets.components import store,load,update
from nbt_agent.structure import build

def strings(value):
 if isinstance(value,str):return [value]
 if isinstance(value,list):return [text for item in value for text in strings(item)]
 if isinstance(value,dict):return [text for item in value.values() for text in strings(item)]
 return []

class Retrieval(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.query=dict(workflow='component',query='水渠桥 支承',size=[4,6,10]);self.asset=store(self.root,dict(schema_version=1,name='水渠桥',tags=['支承','水渠'],size=[9,4,3],anchor=[4,0,1],palette=['stone_bricks'],blocks=[[x,0,1,0,False] for x in range(9)]));self.original=(self.root/'.nbtcreator/components'/f'{self.asset["id"]}.json').read_bytes()
  content='## 桥面支承\n水渠桥必须在两侧有支承；保留桥下排水空间。\n\n## 无关的仓库\n仓库储物架。\n';self.docid=hashlib.sha256(content.encode()).hexdigest();base=self.root/'.nbtcreator/internal-ai';(base/'knowledge').mkdir(parents=True);(base/'knowledge'/f'{self.docid}.md').write_bytes(content.encode('utf8'));self.config=dict(schema_version=1,documents=[dict(id=self.docid,label='桥梁规范',path=f'knowledge/{self.docid}.md')],workflows=dict(component=dict(knowledge=[self.docid]),prompt=dict(knowledge=[])));(base/'config.json').write_text(json.dumps(self.config),encoding='utf8')
 def call(self,operation,**request):return dispatch(self.root,operation,dict(self.query,**request))
 def bundle(self):
  found=self.call('search');return self.call('bundle',selected=[found['assets'][0]['id'],found['knowledge'][0]['id']])
 def test_external_scope_receipts_find_enabled_text_and_never_replay_search_for_bundle(self):
  from nbt_exposure import apply, import_knowledge
  note=self.root/'青弦工程.md';note.write_text(('# 青弦\n'+'其他工程行\n'*62+'\n## 节点\nzephyrquill 由两侧石墩承托。\n'+'后续门槛\n'*60),encoding='utf8')
  config=import_knowledge(self.root,[note]);document=config['custom_knowledge'][0]
  def external(action,**fields):return dispatch(self.root,action,dict(workflow='component',**fields),audience='external_agent')
  self.assertEqual(self.call('search',query='zephyrquill')['knowledge'],[])
  found=external('search',query='zephyrquill');hit,=found['knowledge']
  self.assertEqual(hit['ref'],'R1');self.assertNotIn('id',hit);self.assertIn('两侧石墩',hit['text'])
  with patch('nbt_knowledge.retrieval.search',side_effect=AssertionError('bundle re-ran search')):
   bundle=external('bundle',receipt=found['receipt'],selected=['R1'])
  receipt={key:bundle[key] for key in ('id','sha256')}
  checked=external('read',**receipt)
  self.assertEqual({key:checked[key] for key in receipt},receipt); self.assertEqual(checked['sources'][0]['citation'],'R1')
  with self.assertRaisesRegex(ValueError,'SHA256 不匹配'):external('read',id=bundle['id'],sha256='0'*64)
  self.assertEqual(read_bundle(self.root,dict(workflow='component',**receipt),audience=None)['sources'],bundle['sources'])
  with self.assertRaisesRegex(ValueError,'资料范围'):self.call('read',**receipt)
  with self.assertRaisesRegex(ValueError,'工作流'):dispatch(self.root,'source',dict(workflow='prompt',receipt=found['receipt'],ref='R1'),audience='external_agent')
  window=external('source',receipt=found['receipt'],ref='R1');full=external('source',receipt=found['receipt'],ref='R1',full=True)
  self.assertIn('两侧石墩',window['text']);self.assertLess(len(window['text']),len(full['text']));self.assertGreater(window['next_line'],window['line_end'])
  query_file=self.root/'.nbtcreator/retrieval/queries'/(found['receipt']+'.json');query_file.write_text('{}',encoding='utf8')
  with self.assertRaisesRegex(ValueError,'回执已变化'):external('bundle',receipt=found['receipt'],selected=['R1'])
  self.assertEqual(external('search',query='zephyrquill')['receipt'],found['receipt'])
  document['enabled']=False;apply(self.root,dict(schema_version=1,enabled_groups=['core'],custom_knowledge=[document]))
  with self.assertRaisesRegex(ValueError,'重新检索'):external('read',**receipt)
  self.assertIsNone(external('search',query='zephyrquill')['receipt'])
 def test_missing_external_document_is_reported_without_breaking_other_receipts(self):
  from nbt_exposure import edit_knowledge, import_knowledge, show
  notes=[]
  for name in ('testazimuth','testmeridian'):
   note=self.root/(name+'.md');note.write_text(name+' 是本地合成资料',encoding='utf8');notes.append(note)
  documents=import_knowledge(self.root,notes)['custom_knowledge']
  def external(action,**fields):
   return dispatch(self.root,action,dict(workflow='prompt',source_kind='skill',**fields),audience='external_agent')
  first=external('search',query='testazimuth')
  second=external('search',query='testmeridian')
  missing=documents[1]
  (self.root/'.nbtcreator'/missing['path']).unlink()
  lookup=external('search',query='testazimuth')
  self.assertEqual(lookup['receipt'],first['receipt'])
  self.assertEqual(lookup['knowledge_errors'][0]['id'],missing['id'])
  self.assertIn('testazimuth',external('source',receipt=first['receipt'],ref='R1')['text'])
  with self.assertRaisesRegex(ValueError,'testmeridian.*缺失'):
   external('source',receipt=second['receipt'],ref='R1')
  edit_knowledge(self.root,missing['id'],'disable')
  self.assertEqual(external('search',query='testazimuth')['knowledge_errors'],[])
  self.assertFalse(show(self.root)['custom_issues'][0]['enabled'])
  import_knowledge(self.root,[notes[1]])
  edit_knowledge(self.root,missing['id'],'enable')
  self.assertIn('testmeridian',external('source',receipt=second['receipt'],ref='R1')['text'])
  edit_knowledge(self.root,missing['id'],'remove')
  with self.assertRaisesRegex(ValueError,'取消'):
   external('source',receipt=second['receipt'],ref='R1')
  self.assertTrue((self.root/'.nbtcreator'/missing['path']).is_file())

 def test_public_cli_supports_stdin_and_explains_file_argument(self):
  invocation=[sys.executable,'-B',str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts/nbt_retrieval.py'),'search','--request']
  request=json.dumps(dict(workflow='prompt',query='zephyrquill',source_kind='library'))
  success=subprocess.run([*invocation,'-'],cwd=self.root,input=request,capture_output=True,encoding='utf8')
  self.assertEqual(success.returncode,0,success.stdout+success.stderr);self.assertIsNone(json.loads(success.stdout)['receipt'])
  error=subprocess.run([*invocation,request],cwd=self.root,capture_output=True,encoding='utf8')
  self.assertEqual(error.returncode,1);self.assertIn('JSON 文件路径',json.loads(error.stdout)['error'])
 def test_invalid_registration_is_isolated_recoverable_and_cannot_grant_read_access(self):
  from nbt_exposure import apply,edit_knowledge,import_knowledge,recover,show
  note=self.root/'azimuth.md';note.write_text('azimuthfixture',encoding='utf8')
  registered=import_knowledge(self.root,[note])['custom_knowledge'][0]
  file=self.root/'.nbtcreator/skill-exposure.json'
  def external(action,**fields):return dispatch(self.root,action,dict(workflow='prompt',source_kind='skill',**fields),audience='external_agent')
  receipt=external('search',query='精修')['receipt']
  raw=json.dumps(dict(schema_version=1,enabled_groups=['core'],custom_knowledge=[dict(registered,id='broken',enabled=False)])).encode()
  file.write_bytes(raw);state=apply(self.root)
  self.assertEqual(file.read_bytes(),raw);self.assertEqual(state['registration_issues'][0]['row'],0)
  self.assertTrue(external('source',receipt=receipt,ref='R1')['text'])
  self.assertIsNone(external('search',query='azimuthfixture')['receipt'])
  with self.assertRaisesRegex(ValueError,'登记已变化'):recover(self.root,'0'*64,'remove',0)
  restored=recover(self.root,state['config_sha256'],'restore',0)
  self.assertEqual((self.root/restored['backup']).read_bytes(),raw)
  self.assertFalse(restored['custom_knowledge'][0]['enabled'])
  edit_knowledge(self.root,registered['id'],'enable')
  self.assertTrue(external('search',query='azimuthfixture')['receipt'])
  self.assertEqual(self.call('search',workflow='prompt',query='azimuthfixture')['knowledge'],[])
  config=json.loads(file.read_bytes());config['custom_knowledge']*=2;file.write_text(json.dumps(config),encoding='utf8')
  duplicate=show(self.root);self.assertEqual(len(duplicate['registration_issues']),2)
  self.assertEqual(duplicate['custom_knowledge'],[])
  result=recover(self.root,duplicate['config_sha256'],'remove',0)
  self.assertFalse(result['custom_knowledge'][0]['enabled'])
 def test_broken_config_preserved_and_recovery_explicitly_selects_core(self):
  from nbt_exposure import CONFIG_BYTES,apply,inherit,recover,show
  folder=self.root/'.nbtcreator';file=folder/'skill-exposure.json';raw=b'{broken\xff'
  file.write_bytes(raw)
  state=show(self.root);self.assertTrue(state['config_error']);self.assertEqual(state['enabled_groups'],[])
  with self.assertRaises(ValueError):apply(self.root)
  self.assertEqual(file.read_bytes(),raw)
  self.assertEqual(inherit(self.root/'next',self.root)['enabled_groups'],['core'])
  result=recover(self.root,state['config_sha256'],'reset-core')
  self.assertEqual((self.root/result['backup']).read_bytes(),raw);self.assertEqual(result['enabled_groups'],['core'])
  file.write_bytes(b' '*(CONFIG_BYTES+1))
  with self.assertRaisesRegex(ValueError,'256 KiB'):show(self.root)
 def test_long_task_can_use_explicit_keywords_for_books_and_offline_asset_candidates(self):
  self.library('命中书库')
  query='描述环境 '*90+' 放射式 玫瑰窗'
  request=dict(workflow='prompt',query=query,source_kind='library')
  first=dispatch(self.root,'search',request,audience='external_agent')
  self.assertTrue(first['search_scope']['library_query_truncated'])
  with patch('urllib.request.urlopen',side_effect=AssertionError('offline retrieval opened a network connection')):
   found=dispatch(self.root,'search',dict(request,keywords='放射式 玫瑰窗',include_extension_assets=True),audience='external_agent')
   stairs=dispatch(self.root,'search',dict(request,keywords='螺旋楼梯',include_extension_assets=True),audience='external_agent')
  self.assertFalse(found['search_scope']['library_query_truncated'])
  self.assertTrue(found['knowledge'])
  self.assertTrue(stairs['extension_candidates'])
  candidate=stairs['extension_candidates'][0]
  self.assertEqual(candidate['review_status'],'pending_visual_review')
  self.assertIn('sha256',candidate)
  self.assertIsNone(stairs['receipt'])
  with self.assertRaisesRegex(ValueError,'仅用于外部'):
   dispatch(self.root,'search',dict(request,include_extension_assets=True))
 def test_search_suggests_actual_rotation_and_only_task_selected_references(self):
  result=self.call('search');self.assertEqual(result['assets'][0]['rotations'],[1]);self.assertEqual(result['assets'][0]['asset_id'],self.asset['id']);self.assertEqual(result['knowledge'][0]['label'],'桥梁规范');self.assertIn('桥下排水',result['knowledge'][0]['text']);self.assertEqual(self.call('search',size=[2,3,2])['assets'],[]);self.assertEqual(self.call('search',workflow='prompt')['knowledge'],[])
 def test_indexed_long_query_equivalence_and_explicit_windows_preserve_scope(self):
  self.library('masonry','# 柱头\n盘旋楼梯的踏步旁有 metasilicate 纹线。\n')
  def find(**fields):
   return dispatch(self.root,'search',{'workflow':'prompt','source_kind':'library',**fields},audience='external_agent')
  # Known construction in the middle, after the old first-300-character cut.
  prefix='abcdefgh '*80;tail='uvwxyz '*100
  with patch('urllib.request.urlopen',side_effect=AssertionError('offline search went online')):
   hit=find(query=prefix+'螺旋梯 '+tail)
   self.assertTrue(hit['receipt']);self.assertIn('盘旋楼梯',hit['search_scope']['indexed_query'])
   self.assertLessEqual(len(hit['search_scope']['indexed_query']),300)
   hidden=prefix+'metasilicate '+tail
   first=find(query=hidden);self.assertIsNone(first['receipt'])
   self.assertIn('当前工作流',first['search_scope']['no_knowledge_match'])
   offsets=[];page=first
   while not page['receipt']:
    offset=page['search_scope']['query_selection']['next_offset'];self.assertIsNotNone(offset)
    offsets.append(offset);page=find(query=hidden,query_offset=offset)
   self.assertEqual(offsets,[0,300,600])
   disabled=find(query=hidden,workflow='component',keywords='metasilicate')
   self.assertIsNone(disabled['receipt']);self.assertEqual(disabled['search_scope']['libraries_in_scope'],0)
   self.assertIn('没有已启用的书库',disabled['search_scope']['no_knowledge_match'])
   with self.assertRaisesRegex(ValueError,'择一'):find(query=hidden,keywords='metasilicate',query_offset=0)
   with self.assertRaisesRegex(ValueError,'字符位置'):find(query='short',query_offset=100)
   filtered=self.call('search',query='水渠桥',filters={'region':'Egypt'})
   self.assertFalse(filtered['assets']);self.assertFalse(filtered['knowledge'])
   self.assertEqual(filtered['search_scope']['skill_documents_searched'],0)
 def test_more_than_two_matching_passages_can_be_read_with_verified_receipt(self):
  from nbt_exposure import import_knowledge,edit_knowledge
  note=self.root/'circulation.md';note.write_text(''.join(f'## 第{n}处\nxyzaxle 节点{n}\n' for n in range(5)),encoding='utf8')
  identifier=import_knowledge(self.root,[note])['custom_knowledge'][0]['id']
  def external(action,**params):return dispatch(self.root,action,dict(workflow='component',**params),audience='external_agent')
  found=external('search',query='xyzaxle',source_kind='skill')
  self.assertEqual(len(found['knowledge']),2)
  next_read,=found['search_scope']['continued_passages']
  self.assertEqual(next_read['receipt'],found['receipt'])
  self.assertNotIn(next_read['line'],[item['line_start'] for item in found['knowledge']])
  result=external('source',**next_read);self.assertIn('xyzaxle',result['text'])
  self.assertFalse(self.call('search',query='xyzaxle')['knowledge'])
  with self.assertRaisesRegex(ValueError,'内置 AI'):self.call('source',**next_read)
  edit_knowledge(self.root,identifier,'disable')
  with self.assertRaisesRegex(ValueError,'取消'):external('source',**next_read)
 def test_bundle_is_hash_bound_and_sends_citable_fragments_without_local_paths_or_voxels(self):
  bundle=self.bundle();read=self.call('read',id=bundle['id'],sha256=bundle['sha256']);self.assertEqual(read['sources'][0]['citation'],'R1');self.assertEqual(read['sources'][1]['line_start'],1);self.assertTrue(all(str(self.root) not in text for text in strings(read)));self.assertNotIn('blocks',read['references'][0]);self.assertFalse(read['asset_written']);self.assertEqual(self.original,(self.root/'.nbtcreator/components'/f'{self.asset["id"]}.json').read_bytes())
 def test_revoked_knowledge_and_changed_content_refuse_old_bundle(self):
  bundle=self.bundle();self.config['workflows']['component']['knowledge']=[];(self.root/'.nbtcreator/internal-ai/config.json').write_text(json.dumps(self.config),encoding='utf8')
  with self.assertRaisesRegex(ValueError,'取消'):self.call('read',id=bundle['id'],sha256=bundle['sha256'])
 def test_archived_assets_and_wrong_workflow_or_tampered_bundle_are_rejected(self):
  bundle=self.bundle()
  with self.assertRaisesRegex(ValueError,'工作流'):self.call('read',workflow='prompt',id=bundle['id'],sha256=bundle['sha256'])
  with self.assertRaises(ValueError):self.call('read',id='../secret',sha256=bundle['sha256'])
  file=self.root/'.nbtcreator/retrieval/bundles'/f'{bundle["id"]}.json';original=file.read_bytes();file.write_bytes(original+b' ')
  with self.assertRaisesRegex(ValueError,'SHA256 不匹配'):self.call('read',id=bundle['id'],sha256=bundle['sha256'])
  file.write_bytes(original);update(self.root,self.asset['id'],archived=True)
  with self.assertRaisesRegex(ValueError,'回收'):self.call('read',id=bundle['id'],sha256=bundle['sha256'])
 def test_source_read_requires_current_selection_and_actual_hash(self):
  found=self.call('search');source=found['knowledge'][0];doc=self.call('source',document_id=source['document_id'],sha256=source['sha256']);self.assertIn('无关的仓库',doc['text'])
  with self.assertRaises(ValueError):self.call('source',workflow='prompt',document_id=self.docid,sha256=self.docid)
 def test_rotated_recolored_asset_reuse_generates_actual_geometry_and_preserves_original(self):
  result=build(self.root,dict(name='金色水渠桥',size=self.query['size'],placements=[dict(id=self.asset['id'],content_sha256=self.asset['content_sha256'],position=[1,0,4],quarter_turns=1,material_map={'minecraft:stone_bricks':'gold_block'})]));self.assertEqual(result['palette'],['minecraft:gold_block']);self.assertEqual(len(result['blocks']),9);self.assertEqual({b[2] for b in result['blocks']},set(range(9)));self.assertEqual(load(self.root,self.asset['id'])['palette'],['minecraft:stone_bricks']);self.assertEqual(self.original,(self.root/'.nbtcreator/components'/f'{self.asset["id"]}.json').read_bytes())
 def test_invalid_materials_and_unselected_or_empty_bundle_are_rejected(self):
  with self.assertRaises(ValueError):self.call('bundle',selected=[])
  with self.assertRaises(ValueError):self.call('bundle',selected=['asset:'+'0'*32])
  with self.assertRaises(ValueError):build(self.root,dict(name='无效',size=[4,6,10],placements=[dict(id=self.asset['id'],content_sha256=self.asset['content_sha256'],position=[1,0,4],quarter_turns=1,material_map={'stone_bricks':'not_a_block'})]))
 def test_relative_bundle_survives_relocation_and_forged_line_metadata_is_rejected(self):
  bundle=self.bundle();file=self.root/'.nbtcreator/retrieval/bundles'/f'{bundle["id"]}.json';self.assertTrue(all(str(self.root) not in text for text in strings(json.loads(file.read_bytes()))));destination=self.root/'relocated';shutil.copytree(self.root/'.nbtcreator',destination/'.nbtcreator');moved=dispatch(destination,'read',dict(workflow='component',id=bundle['id'],sha256=bundle['sha256']));self.assertEqual(moved['references'][0]['id'],self.asset['id']);forged=json.loads(file.read_bytes());forged['sources'][1]['line_start']+=1;raw=json.dumps(forged).encode();file.write_bytes(raw)
  with self.assertRaisesRegex(ValueError,'片段'):self.call('read',id=bundle['id'],sha256=hashlib.sha256(raw).hexdigest())

 def library(self, folder, text='# 窗饰\n立面采用玫瑰窗，窗饰沿圆环放射。\n', **fields):
  directory=self.root/folder;directory.mkdir(exist_ok=True);payload=text.encode('utf8');(directory/'window.md').write_bytes(payload)
  document=dict(id='window',file='window.md',bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest(),
                title='窗饰图录',region='France',styles=['gothic'],year=1920,author='Fixture Archive',
                source='https://example.org/catalogue',license='test fixture',**fields)
  manifest=dict(schema_version=1,id='windows',version='2026.1',documents=[document]);(directory/'knowledge.json').write_text(json.dumps(manifest),encoding='utf8')
  connection=self.call('library',workflow='prompt',action='add',path=folder)
  return directory,manifest,connection

 def test_library_is_opt_in_and_round_trips_exact_citation_through_provider_projection(self):
  original=self.bundle();directory,_,connection=self.library('参考书库')
  self.assertEqual(connection['status'],'ready');self.assertFalse((directory/'architecture.sqlite').exists())
  query=dict(query='放射式 玫瑰窗',workflow='prompt')
  hit,=self.call('search',**query)['knowledge'];self.assertEqual(hit['reference_type'],'architecture_library')
  self.assertEqual(self.call('search',query=query['query'],workflow='component')['knowledge'],[])
  self.assertEqual(self.call('search',filters={'year':[1900,1930],'style':'gothic'},**query)['knowledge'],[hit])
  self.assertEqual(self.call('search',filters={'region':'Egypt'},**query)['knowledge'],[])
  arguments={key:hit[key] for key in ('document_id','manifest_sha256','sha256')}
  source=self.call('source',line=2,**query,**arguments);self.assertIn('放射',source['text']);self.assertEqual(source['line_end'],2)
  bundle=self.call('bundle',selected=[hit['id']],**query);receipt={key:bundle[key] for key in ('id','sha256')}
  result=self.call('read',**query,**receipt);proof,=result['sources'];self.assertEqual(proof['citation'],'R1')
  self.assertEqual(proof['passage_sha256'],hashlib.sha256(result['knowledge'][0]['content'].encode()).hexdigest())
  self.assertEqual(proof['bibliography']['source_url'],'https://example.org/catalogue');self.assertEqual(proof['bibliography']['version'],'2026.1')
  self.assertTrue(all(str(self.root) not in value for value in strings(result)))
  moved=self.root/'moved';shutil.copytree(self.root/'.nbtcreator',moved/'.nbtcreator');shutil.copytree(directory,moved/directory.name)
  self.assertEqual(dispatch(moved,'read',dict(workflow='prompt',**receipt)),result)
  self.call('library',workflow='prompt',action='enable',id=connection['id'],enabled=False)
  with self.assertRaisesRegex(ValueError,'停用'):self.call('read',**query,**receipt)
  self.assertEqual(self.call('read',id=original['id'],sha256=original['sha256'])['sources'][1]['citation'],'R2')

 def test_changed_or_corrupt_library_leaves_other_sources_available_and_can_reindex(self):
  left,manifest,first=self.library('one');_,_,second=self.library('two','# 窗洞\n常见玫瑰窗使用石条和玻璃。\n')
  query=dict(query='玫瑰窗',workflow='prompt');initial=self.call('search',**query)['knowledge'];self.assertEqual(len(initial),2)
  hit=next(item for item in initial if item['library_name']=='one')
  bundle=self.call('bundle',selected=[hit['id']],**query);receipt={key:bundle[key] for key in ('id','sha256')}
  file=left/'window.md';content=file.read_bytes();file.write_bytes(content+b' ')
  with self.assertRaisesRegex(ValueError,'已变化'):self.call('read',**query,**receipt)
  failed=self.call('search',**query);self.assertEqual([item['library_name'] for item in failed['knowledge']],['two'])
  self.assertEqual(failed['library_errors'][0]['id'],first['id'])
  with self.assertRaisesRegex(ValueError,'size changed'):self.call('library',workflow='prompt',action='build',id=first['id'])
  file.write_bytes(content);self.assertEqual(len(self.call('search',**query)['knowledge']),2)
  manifest['version']='2026.2';(left/'knowledge.json').write_text(json.dumps(manifest),encoding='utf8')
  self.assertEqual(self.call('library',workflow='prompt')['libraries'][0]['status'],'stale')
  self.call('library',workflow='prompt',action='build',id=first['id'])
  self.assertEqual(len(self.call('search',**query)['knowledge']),2)
  with self.assertRaisesRegex(ValueError,'已变化'):self.call('read',**query,**receipt)
  self.call('library',workflow='prompt',action='remove',id=second['id'])
  self.assertEqual(len(self.call('search',**query)['knowledge']),1)

 def test_rejects_unregistered_external_paths_and_forged_source_fields(self):
  for path in ('https://example.org/books','../somewhere','//server/share'):
   with self.assertRaises(ValueError):self.call('library',workflow='prompt',action='add',path=path)
  self.library('catalogue');query=dict(query='窗饰',workflow='prompt');hit,=self.call('search',**query)['knowledge']
  bundle=self.call('bundle',selected=[hit['id']],**query);file=self.root/'.nbtcreator/retrieval/bundles'/f'{bundle["id"]}.json'
  record=json.loads(file.read_bytes());record['sources'][0]['bibliography']['source_url']='https://example.org/fake'
  raw=json.dumps(record).encode();file.write_bytes(raw)
  with self.assertRaisesRegex(ValueError,'出处'):self.call('read',id=bundle['id'],sha256=hashlib.sha256(raw).hexdigest(),**query)

if __name__=='__main__':unittest.main(verbosity=2)
