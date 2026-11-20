import sys,tempfile,uuid,unittest,hashlib,json,shutil,subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_agent_protocol import ProtocolError
from nbt_agent_tasks import dispatch
from nbt_prompts import save,publish,task_action,read_task,tasks
from nbt_refine import save_master
from nbt_assembly import Volume
from nbt_machine import dispatch as machine
from nbt_task_client import TaskClient
from nbt_diagnostic_delta import delta
class Contracts(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.w=Path(self.tmp.name)
  self.source=self.w/'nbt_models/single/契约测试/v01/master/model.snbt';self.source.parent.mkdir(parents=True);m=Volume((8,6,8));m.box((0,0,0),(7,0,7),'stone_bricks');save_master(self.source,m,set())
 def request(self,**params):return dict(request_id=uuid.uuid4().hex,**params)
 def create(self):return dispatch(self.w,'create',self.request(source=str(self.source),source_sha256=hashlib.sha256(self.source.read_bytes()).hexdigest(),name='合成任务'))
 def test_create_retry_is_exact_and_different_payload_is_rejected(self):
  req=self.request(source=str(self.source),source_sha256=hashlib.sha256(self.source.read_bytes()).hexdigest(),name='合成任务');a=dispatch(self.w,'create',req);self.assertEqual(dispatch(self.w,'create',req),a)
  with self.assertRaises(ProtocolError) as caught:dispatch(self.w,'create',dict(req,name='不同请求'))
  self.assertEqual(caught.exception.code,'IDEMPOTENCY_CONFLICT')
 def test_claim_is_exclusive_and_expiry_fences_old_worker(self):
  task=self.create();req=self.request(id=task['id'],owner='one',ttl_seconds=60)
  with patch('nbt_agent_protocol.time.time',return_value=100):first=dispatch(self.w,'claim',req)
  self.assertNotIn('token',first['lease']);self.assertIn('lease_token',first)
  with patch('nbt_agent_protocol.time.time',return_value=110):
   self.assertEqual(dispatch(self.w,'claim',req),first)
   with self.assertRaises(ProtocolError):dispatch(self.w,'claim',self.request(id=task['id'],owner='two'))
  with patch('nbt_agent_protocol.time.time',return_value=161):second=dispatch(self.w,'claim',self.request(id=task['id'],owner='two'))
  self.assertGreater(second['lease']['fence'],first['lease']['fence'])
  with patch('nbt_agent_protocol.time.time',return_value=162):
   with self.assertRaises(ProtocolError):dispatch(self.w,'heartbeat',self.request(id=task['id'],lease_token=first['lease_token'],fence=first['lease']['fence']))
   renewed=dispatch(self.w,'heartbeat',self.request(id=task['id'],lease_token=second['lease_token'],fence=second['lease']['fence']))
   self.assertGreater(renewed['lease']['expires_at'],second['lease']['expires_at'])
 def test_prompt_claim_and_completion_require_ownership(self):
  saved=save(self.w,dict(session_id=uuid.uuid4().hex,document={'project':{'stage':'draft','name':'提示词契约','buildingShape':'single'}},text='synthetic',plan={},context={}))
  task=publish(self.w,saved['index'],saved['id'],saved['revision']);req=self.request(id=task['id'],owner='agent');lease=task_action(self.w,'claim',req);self.assertEqual(task_action(self.w,'claim',req),lease)
  self.assertNotIn('token',read_task(self.w,task['id'])['task']['lease'])
  with self.assertRaises(ProtocolError):task_action(self.w,'task-status',self.request(id=task['id'],status='completed'))
  params=dict(id=task['id'],status='completed',lease_token=lease['lease_token'],fence=lease['lease']['fence'])
  with self.assertRaises(ProtocolError) as missing:task_action(self.w,'task-status',self.request(**params))
  self.assertEqual(missing.exception.code,'EVIDENCE_REQUIRED')
  from nbt_refine import prepare,digest
  review=self.w/'nbt_models/review'
  cameras=[dict(role='whole',eye=[12,8,13],target=[3.5,0.5,3.5]),dict(role='entry',eye=[2.5,2.62,2.5],target=[5.5,0.5,5.5])]
  prepare(self.source,dict(mode='standalone',require_enclosure=False,openings=[],allow_empty_wall_mask=True,start=[2.5,1,2.5],targets={'other':[5.5,1,5.5]},cameras=cameras),review)
  preview=review/'thumbnails.png';original=preview.read_bytes();preview.write_bytes(b'changed')
  with self.assertRaises(ProtocolError) as changed:
   task_action(self.w,'task-status',self.request(**params,review=str(review),review_sha256=digest(review/'review.json')))
  self.assertEqual(changed.exception.code,'EVIDENCE_INVALID');preview.write_bytes(original)
  result=task_action(self.w,'task-status',self.request(**params,review=str(review),review_sha256=digest(review/'review.json')))
  self.assertEqual(result['status'],'completed');self.assertEqual(result['approval'],'not_granted_by_prompt')
  self.assertTrue(result['model_written']);self.assertEqual(result['acceptance'],'pending_user_review')
 def test_new_prompt_revision_supersedes_old_lease(self):
  session=uuid.uuid4().hex;document={'project':{'stage':'draft','name':'替代任务','buildingShape':'single'}}
  first=self.publish_prompt(session,document,'第一版')
  client=TaskClient(self.w,'superseded');client.start('prompts',first['id'],'agent',60)
  second=self.publish_prompt(session,document,'第二版')
  self.assertNotEqual(first['id'],second['id'])
  self.assertEqual(read_task(self.w,first['id'])['task']['status'],'superseded')
  self.assertEqual([item['id'] for item in tasks(self.w,status='pending')['items']],[second['id']])
  with self.assertRaises(ProtocolError) as failure:client.change('heartbeat')
  self.assertEqual(failure.exception.code,'TASK_SUPERSEDED')
 def test_prompt_index_capacity_failure_keeps_last_readable_state(self):
  from nbt_prompts import task_index
  task=self.publish_prompt(uuid.uuid4().hex,{'project':{'stage':'draft','name':'容量测试','buildingShape':'single'}},'测试任务')
  index=task_index(self.w);before=index.read_bytes()
  with patch('nbt_prompts.TASK_INDEX_BYTES',len(before)):
   with self.assertRaises(ProtocolError) as failure:
    task_action(self.w,'claim',self.request(id=task['id'],owner='agent'))
   self.assertEqual(failure.exception.code,'TASK_INDEX_LIMIT')
   self.assertEqual(index.read_bytes(),before)
   self.assertEqual(read_task(self.w,task['id'])['task']['status'],'pending')
 def test_expired_prompt_returns_to_pending_discovery_without_exposing_token(self):
  saved=save(self.w,dict(session_id=uuid.uuid4().hex,document={'project':{'stage':'draft','name':'超时任务','buildingShape':'single'}},text='synthetic',plan={},context={}))
  task=publish(self.w,saved['index'],saved['id'],saved['revision'])
  with patch('nbt_agent_protocol.time.time',return_value=100):claimed=task_action(self.w,'claim',self.request(id=task['id'],owner='agent',ttl_seconds=60))
  with patch('nbt_agent_protocol.time.time',return_value=161):
   pending=tasks(self.w,status='pending')['items'];self.assertEqual(len(pending),1);self.assertTrue(pending[0]['lease_expired']);self.assertNotIn('token',pending[0]['lease'])
   with self.assertRaises(ProtocolError) as failure:task_action(self.w,'task-status',self.request(id=task['id'],status='completed',lease_token=claimed['lease_token'],fence=claimed['lease']['fence']))
   self.assertEqual(failure.exception.code,'LEASE_EXPIRED')
 def test_machine_strict_envelope_and_separate_annotation_namespace(self):
  def call(method,params={},**extra):return machine(self.w,dict(protocol_version=1,method=method,params=params,**extra))
  for req,code in [(dict(protocol_version=9,method='tasks.list'),'PROTOCOL_VERSION_UNSUPPORTED'),(dict(protocol_version=1,method='tasks.review'),'METHOD_NOT_FOUND'),(dict(protocol_version=1,method='tasks.list',params={'execute':'anything'}),'INVALID_REQUEST')]:
   result=machine(self.w,req);self.assertFalse(result['ok']);self.assertEqual(result['error']['code'],code);self.assertIsNone(result['data'])
  self.assertEqual(call('tasks.claim',dict(id='test',owner='agent'))['error']['code'],'REQUEST_ID_REQUIRED')
  self.assertTrue(call('annotations.scan')['ok']);self.assertTrue(call('prompts.list')['ok'])
 def test_concurrent_process_claims_have_one_owner_and_release_reclaims(self):
  task=self.create();script=ROOT/'.agents/skills/minecraft-nbt-modeler/scripts/nbt_machine.py'
  def claim(owner):
   request=dict(protocol_version=1,request_id=uuid.uuid4().hex,method='tasks.claim',params=dict(id=task['id'],owner=owner))
   run=subprocess.run([sys.executable,'-B',str(script),'--workspace',str(self.w),'--request','-'],input=json.dumps(request),encoding='utf8',capture_output=True,timeout=15)
   return json.loads(run.stdout)
  with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(claim,['worker-one','worker-two']))
  self.assertEqual(sum(result['ok'] for result in results),1);success=next(result['data'] for result in results if result['ok'])
  self.assertEqual(next(result['error']['code'] for result in results if not result['ok']),'TASK_CLAIMED')
  dispatch(self.w,'release',self.request(id=task['id'],lease_token=success['lease_token'],fence=success['lease']['fence']))
  self.assertGreater(dispatch(self.w,'claim',self.request(id=task['id'],owner='next'))['lease']['fence'],success['lease']['fence'])
 def test_failed_primary_commit_does_not_make_retry_duplicate(self):
  req=self.request(source=str(self.source.relative_to(self.w)),source_sha256=hashlib.sha256(self.source.read_bytes()).hexdigest())
  with patch.object(Path,'replace',side_effect=OSError('simulated commit interruption')):
   with self.assertRaises(OSError):dispatch(self.w,'create',req)
  success=dispatch(self.w,'create',req);self.assertEqual(dispatch(self.w,'create',req),success);self.assertEqual(len(dispatch(self.w,'list',{})['tasks']),1)
 def test_receipts_relocate_and_corrupted_receipts_refuse_reexecution(self):
  req=self.request(source=str(self.source.relative_to(self.w)),source_sha256=hashlib.sha256(self.source.read_bytes()).hexdigest());first=dispatch(self.w,'create',req)
  moved=self.w/'relocated';shutil.copytree(self.w/'nbt_models',moved/'nbt_models')
  replayed=dispatch(moved,'create',req);self.assertEqual(replayed['id'],first['id']);self.assertEqual(Path(replayed['absolute_source']),(moved/req['source']).resolve())
  index=json.loads((moved/'nbt_models/_workspaces/agent_tasks/index.json').read_text(encoding='utf8'));file=moved/index['operation_receipts'][req['request_id']]['path'];file.write_text('tampered')
  with self.assertRaises(ProtocolError) as failure:dispatch(moved,'create',req)
  self.assertEqual(failure.exception.code,'RECEIPT_CHANGED')
 def test_record_retry_survives_lost_reply_and_finishes_lease(self):
  task=self.create();claimed=dispatch(self.w,'claim',self.request(id=task['id'],owner='agent'))
  target=self.source.parent.parent.parent/'v02/master/model.snbt';target.parent.mkdir(parents=True);target.write_bytes(self.source.read_bytes())
  req=self.request(id=task['id'],revision=claimed['revision'],new_source=str(target),new_source_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),summary='完成本次制作，等待人工审查',lease_token=claimed['lease_token'],fence=claimed['lease']['fence'])
  result=dispatch(self.w,'record',req);self.assertEqual(dispatch(self.w,'record',req),result);self.assertEqual(len(result['returns']),1);self.assertEqual(result['status'],'completed');self.assertNotIn('lease',result);self.assertEqual(result['returns'][0]['acceptance'],'pending_user_review')

 def publish_prompt(self, session, document, text, context=None):
  saved=save(self.w,dict(session_id=session,document=document,text=text,plan={'operations':[]},context=context or {}))
  return publish(self.w,saved['index'],saved['id'],saved['revision'])

 def test_compact_prompt_preserves_stage_constraints_and_verbatim_excerpts(self):
  from nbt_constraints import checksum
  session=uuid.uuid4().hex
  text='完整正文 '+('很长的模板文字 ' * 200)
  purpose='先收卷，再走到庭院。'
  constraint=dict(schema_version=1,id='constraint-'+uuid.uuid4().hex,revision=1,name='露天项目',
                  rules=dict(require_enclosure=False,openings_policy='none',requirements='庭院保留露天。'))
  constraint['sha256']=checksum(constraint)
  document={'project':{'stage':'draft','name':'院落','buildingShape':'single','purpose':purpose},'constraints':[constraint]}
  before=self.publish_prompt(session,document,text)
  protected=[dict(lo=[0,0,0],hi=[3,3,3])]
  after=self.publish_prompt(session,dict(document,project=dict(document['project'],purpose=purpose,extras='保留临街入口。'*50)),
                            text+' 新段落',dict(protected_boxes=protected))
  def get(**params):return machine(self.w,dict(protocol_version=1,method='prompts.get',params=dict(id=after['id'],**params)))
  full, compact=get()['data'],get(view='compact')['data']
  self.assertEqual(compact['brief']['purpose'],purpose)
  self.assertEqual(compact['task']['stage'],'draft')
  self.assertIs(compact['effective']['require_enclosure'],False)
  self.assertEqual(compact['effective']['openings_policy'],'none')
  self.assertEqual(compact['constraints'][0]['requirements'],'庭院保留露天。')
  self.assertEqual(compact['protected_boxes'],protected)
  self.assertIn('document.project.extras',compact['clipped'])
  self.assertEqual(compact['previous']['task_id'],before['id'])
  self.assertEqual(compact['previous']['project_fields'],['extras'])
  self.assertEqual(compact['previous']['context_fields'],['protected_boxes'])
  self.assertLess(len(json.dumps(compact,ensure_ascii=False)),len(json.dumps(full,ensure_ascii=False)))
  self.assertEqual(get(view='text')['data']['text'],full['text'])
  self.assertEqual(get(view='nope')['error']['code'],'INVALID_REQUEST')

 def test_task_client_resumes_lost_reply_and_registers_once(self):
  task=self.create()
  client=TaskClient(self.w,'return')
  def lost_response(workspace, encoded):
   data=machine(workspace,encoded)
   if encoded['method'] in ('tasks.claim','tasks.record'):
    self.assertTrue(data['ok']);raise OSError('simulated response lost')
   return data
  with patch('nbt_task_client.dispatch',side_effect=lost_response):
   with self.assertRaises(OSError):client.start('tasks',task['id'],'local-agent',60)
  session=TaskClient(self.w,'return')
  request_id=session.status()['pending']['request_id']
  with patch('nbt_task_client.dispatch',wraps=machine) as calls:
   answer=session.retry()
   self.assertEqual(calls.call_args_list[0].args[1]['request_id'],request_id)
  self.assertEqual(answer['phase'],'active');self.assertNotIn('lease_token',answer)
  renewed=session.change('heartbeat')
  self.assertGreater(renewed['revision'],answer['revision'])
  target=self.source.parent.parent.parent/'v02/master/model.snbt';target.parent.mkdir(parents=True);target.write_bytes(self.source.read_bytes())
  with patch('nbt_task_client.dispatch',side_effect=lost_response):
   with self.assertRaises(OSError):session.change('complete',new_source=str(target),summary='等待用户审查')
  completed=TaskClient(self.w,'return').retry()
  self.assertEqual(completed['phase'],'completed')
  self.assertEqual(completed['completion']['return']['source'],target.relative_to(self.w).as_posix())
  returned=dispatch(self.w,'get',dict(id=task['id']))['returns']
  self.assertEqual(len(returned),1);self.assertEqual(returned[0]['acceptance'],'pending_user_review')
  self.assertNotIn('lease_token',session.load())

 def test_task_sidecars_are_frozen_even_across_heartbeat(self):
  from nbt_refine import read_master
  from nbt_snbt import write_binary
  binary=self.source.with_suffix('.nbt');volume,_=read_master(self.source);write_binary(binary,volume,{(0,0,0)})
  context=self.source.parents[1]/'coordinates.json';context.write_text('{"mode":"standalone"}',encoding='utf8')
  for sidecar,replacement in ((context,b'{"mode":"standalone","reserved_boxes":[]}'),(binary.with_name('wall_mask.json'),b'{}')):
   task=dispatch(self.w,'create',self.request(source=str(binary),source_sha256=hashlib.sha256(binary.read_bytes()).hexdigest()))
   claim=dispatch(self.w,'claim',self.request(id=task['id'],owner='local-agent'))
   original=sidecar.read_bytes();sidecar.write_bytes(replacement)
   with self.assertRaises(ProtocolError) as failure:
    dispatch(self.w,'heartbeat',self.request(id=task['id'],lease_token=claim['lease_token'],fence=claim['lease']['fence']))
   self.assertEqual(failure.exception.code,'SOURCE_CHANGED');sidecar.write_bytes(original)

 def test_stale_worker_cannot_publish_and_return_rejects_an_ancestor(self):
  from nbt_working_model import WorkingModel
  from nbt_history import History
  context=dict(mode='standalone',require_enclosure=False,openings=[],allow_empty_wall_mask=True,start=[2.5,1,2.5],targets={'other':[5.5,1,5.5]})
  working=WorkingModel(self.w,[8,6,8],context=context)
  working.apply_operations([dict(kind='box',label='floor',classification='body',lo=[0,0,0],hi=[7,0,7],state='stone')]);working.open_declared()
  ancestor=working.save_draft('租约测试')
  def edit(model,position):
   model.apply_operations([dict(kind='box',label='edit',classification='body',lo=position,hi=position,state='gold_block')])
  edit(working,[1,1,1]);base=working.save_draft()
  task=dispatch(self.w,'create',self.request(source=base['source'],source_sha256=base['source_sha256']))
  with patch('nbt_agent_protocol.time.time',return_value=100):
   old=TaskClient(self.w,'old');old.start('tasks',task['id'],'old',60)
  first=WorkingModel.open(self.w,base['source']);second=WorkingModel.open(self.w,base['source']);edit(first,[1,1,2]);edit(second,[1,1,3])
  with patch('nbt_agent_protocol.time.time',return_value=200):
   new=TaskClient(self.w,'new');new.start('tasks',task['id'],'new',60)
   with self.assertRaises(ProtocolError) as stale:first.save_draft(task_session='old')
   self.assertEqual(stale.exception.code,'LEASE_NOT_OWNER')
   with self.assertRaises(ProtocolError) as missing:first.save_draft()
   self.assertEqual(missing.exception.code,'LEASE_REQUIRED')
   with self.assertRaises(ProtocolError) as previous:
    new.change('complete',new_source=ancestor['source'],summary='旧祖先不是成果')
   self.assertEqual(previous.exception.code,'RETURN_LINEAGE_MISMATCH')
   candidate=second.save_draft(task_session='new');edit(second,[1,1,4]);candidate=second.save_draft(task_session='new')
   with patch('nbt_history.record_produced_version',return_value=dict(recorded=False,error='synthetic history failure')):
    completed=new.change('complete',new_source=candidate['source'],summary='验证多次保存后回传')
   self.assertTrue(completed['completion']['history_pending']);self.assertIn('synthetic history failure',completed['completion']['history_error'])
   repaired=new.retry();self.assertFalse(repaired['completion']['history_pending'])
   second.save_draft()
  node=candidate['history']['version']['id']
  self.assertEqual(len(dispatch(self.w,'get',dict(id=task['id']))['returns']),1)
  self.assertIn('agent:'+task['id'],History(self.w).get(node)['version']['tasks'])

 def test_task_client_renews_then_stops_on_release(self):
  published=self.publish_prompt(uuid.uuid4().hex,{'project':{'stage':'draft','name':'续租','buildingShape':'single'}},'测试任务')
  client=TaskClient(self.w,'renewer')
  with patch('nbt_agent_protocol.time.time',return_value=100):initial=client.start('prompts',published['id'],'agent',60)
  with patch('nbt_agent_protocol.time.time',return_value=120),patch('nbt_task_client.time.sleep',side_effect=lambda _:client.change('release')):
   final=client.keepalive()
  self.assertEqual(final['phase'],'released');self.assertEqual(final['revision'],initial['revision']+2)
  self.assertEqual(tasks(self.w,status='pending')['items'][0]['id'],published['id'])

 def test_task_client_refuses_stale_source_and_expired_lease(self):
  task=self.create();client=TaskClient(self.w,'stale')
  with patch('nbt_agent_protocol.time.time',return_value=100):client.start('tasks',task['id'],'agent',60)
  with patch('nbt_agent_protocol.time.time',return_value=161):
   with self.assertRaises(ProtocolError) as expired:client.change('heartbeat')
  self.assertEqual(expired.exception.code,'LEASE_EXPIRED')
  with patch('nbt_agent_protocol.time.time',return_value=162):client.start('tasks',task['id'],'agent',60)
  self.source.write_bytes(b'changed')
  with self.assertRaises(ProtocolError) as stale:client.change('heartbeat')
  self.assertEqual(stale.exception.code,'SOURCE_CHANGED')
  self.assertEqual(client.status()['phase'],'blocked')

 def test_prompt_completion_checks_source_after_claim(self):
  task=self.publish_prompt(uuid.uuid4().hex,{'project':{'stage':'plan','name':'源绑定','source':str(self.source)}},'测试任务')
  client=TaskClient(self.w,'prompt-source');client.start('prompts',task['id'],'agent',60)
  self.source.write_bytes(b'changed')
  with self.assertRaises(ProtocolError) as stale:client.change('complete',summary='检查源模型')
  self.assertEqual(stale.exception.code,'SOURCE_CHANGED')
  self.assertEqual(read_task(self.w,task['id'])['task']['status'],'in_progress')

 def test_read_only_plan_completes_with_findings_and_no_model(self):
  task=self.publish_prompt(uuid.uuid4().hex,{'project':{'stage':'plan','name':'只读计划','source':str(self.source)}},'检查任务')
  client=TaskClient(self.w,'plan');client.start('prompts',task['id'],'agent',60)
  completed=client.change('complete',summary='仅检查源模型，未执行候选操作')
  self.assertEqual(completed['completion']['acceptance'],'pending_user_review')
  self.assertFalse(read_task(self.w,task['id'])['task']['model_written'])

 def test_client_stops_on_revision_conflict_without_replacing_lease(self):
  task=self.create();client=TaskClient(self.w,'conflict')
  client.start('tasks',task['id'],'agent',60)
  session=client.load()
  newer=dispatch(self.w,'heartbeat',self.request(id=task['id'],lease_token=session['lease_token'],fence=session['lease']['fence']))
  with self.assertRaises(ProtocolError) as changed:client.change('release')
  self.assertEqual(changed.exception.code,'REVISION_CONFLICT')
  self.assertEqual(client.status()['phase'],'blocked')
  self.assertEqual(dispatch(self.w,'get',dict(id=task['id']))['revision'],newer['revision'])

 def test_incremental_diagnostics_preserve_evidence_for_grouped_issues(self):
  landing=dict(name='stair_landing',feet=[5.5,5,19.5],reachable=False,reason='invalid_or_obstructed_feet_pose')
  def receipt(targets):return dict(ok=False,code='ROUTE_FAILED',conflicts=[dict(passed=False,targets=targets)])
  old,new=self.w/'old.json',self.w/'new.json'
  old.write_text(json.dumps(receipt([landing])),encoding='utf8')
  new.write_text(json.dumps(receipt([dict(landing,feet=[5.5,5,20.5]),landing,dict(landing,name='entry')])),encoding='utf8')
  value=delta('model',new,old)
  self.assertEqual(value['new'][0]['target'],'entry')
  self.assertEqual(value['ongoing'][0]['occurrences'],2)
  self.assertEqual(value['ongoing'][0]['evidence_pointer'],'/conflicts/0/targets/0')
  self.assertEqual(value['ongoing'][0]['evidence']['feet'],[5.5,5,20.5])
  self.assertEqual(value['report']['sha256'],hashlib.sha256(new.read_bytes()).hexdigest())
  new.write_text(json.dumps(dict(error='ROUTE_FAILED: '+json.dumps(receipt([landing])['conflicts']))),encoding='utf8')
  self.assertEqual(delta('model',new,old)['ongoing'][0]['evidence_pointer'],'/error')
  face=dict(part='return_desk',interface='intake',passed=False,reason='wrong_side',feet=[13.5,2,11.5])
  new.write_text(json.dumps(dict(ok=False,code='DESIGN_INVALID',conflicts=[dict(kind='activity_routes',id='file_books',passed=False,use_faces=[face],segments=[])])),encoding='utf8')
  issue=delta('model',new,old)['new'][0]
  self.assertEqual((issue['target'],issue['evidence']['reason']),('return_desk.intake','wrong_side'))
  new.write_text(json.dumps(dict(images={'entry':{},'roof':{}},observations=[dict(image='entry')],issues=[],delivery_summary=['1/2'])),encoding='utf8')
  self.assertEqual(delta('review',new)['review']['pending_views'],['roof'])

 def test_assembly_identity_and_review_candidate_evidence(self):
  old,new=self.w/'old.json',self.w/'new.json'
  tea=dict(instance='tea_table',object='body',passed=False,unknown_shapes=[dict(pos=[8,3,7],state='minecraft:red_carpet')])
  joint=dict(instance='post',object='top',interface='beam',passed=False,missing_faces_half=[[26,10,10]])
  def save(path,data):path.write_text(json.dumps(data),encoding='utf8')
  save(old,dict(ok=False,code='ASSEMBLY_INVALID',conflicts=[tea]))
  save(new,dict(ok=False,code='ASSEMBLY_INVALID',conflicts=[joint,tea]))
  result=delta('model',new,old)
  self.assertEqual(result['ongoing'][0]['scope'],'tea_table')
  self.assertEqual(result['ongoing'][0]['evidence']['unknown_shapes'][0]['pos'],[8,3,7])
  issue,=result['new']
  self.assertEqual((issue['scope'],issue['target'],issue['evidence_pointer']),('post','top.beam','/conflicts/0'))
  self.assertEqual(issue['evidence']['missing_faces_half'],[[26,10,10]])
  view=dict(view='joinery',passed=False,visibility=dict(failure='occluded',blocker=[13,5,5],
   target_cell=[14,6,5],target_state='minecraft:stripped_spruce_log[axis=x]',target_inside_solid=True))
  location=dict(id='joint',passed=False,position=[14,6.15,5.6],candidates=[view])
  save(old,dict(coverage=dict(views=[],review_locations=[location])))
  save(new,dict(coverage=dict(views=[],review_locations=[dict(location,candidates=[view,dict(view,view='roof')])])))
  result=delta('review',new,old)
  self.assertEqual(result['ongoing'][0]['evidence_pointer'],'/coverage/review_locations/0/candidates/0/visibility')
  self.assertEqual(result['new'][0]['evidence']['view'],'roof')
  self.assertEqual(result['new'][0]['evidence']['blocker'],[13,5,5])
if __name__=='__main__':unittest.main(verbosity=2)
