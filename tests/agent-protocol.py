import sys,tempfile,uuid,unittest,hashlib,json,shutil,subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_agent_protocol import ProtocolError
from nbt_agent_tasks import dispatch
from nbt_prompts import save,publish,task_action,read_task,tasks
from nbt_refine import save_master
from nbt_assembly import Volume
from nbt_machine import dispatch as machine
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
  result=task_action(self.w,'task-status',self.request(id=task['id'],status='completed',lease_token=lease['lease_token'],fence=lease['lease']['fence']))
  self.assertEqual(result['status'],'completed');self.assertEqual(result['approval'],'not_granted_by_prompt')
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
if __name__=='__main__':unittest.main(verbosity=2)
