"""Shared operation switches: synthetic plans/candidates, never real approvals."""
from copy import deepcopy
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_detail_control import default_settings,compile_plan,preview_effect
from nbt_assembly import Volume
from nbt_refine import save_master,operation_candidates
from nbt_tools import modelling_plan

class OperationHistory(unittest.TestCase):
 def op(self,**extra):return dict(kind='box',label='候选柱',classification='body',lo=[5,2,5],hi=[5,3,5],state='stone_bricks',**extra)
 def test_legacy_default_active_and_disabled_drafts_are_retained_but_not_compiled(self):
  s=default_settings();a=self.op();b=self.op(enabled=False);b['lo']=[-9,0,0]
  s['operations']=[a,b];self.assertEqual(compile_plan(s,(12,8,12))['operations'],[a]);self.assertEqual(s['operations'][1],b)
  b['enabled']=True
  with self.assertRaises(ValueError):compile_plan(s,(12,8,12))
 def test_switches_are_strict_booleans_in_gui_and_direct_python_tools(self):
  m=Volume((12,8,12));s=default_settings()
  for value in [0,1,'false',None]:
   op=self.op(enabled=value);s['operations']=[op]
   with self.assertRaises(ValueError):compile_plan(s,m.size)
   with self.assertRaises(ValueError):operation_candidates(m,op)
   with self.assertRaises(ValueError):modelling_plan(m,dict(kind='replace',enabled=value))
  self.assertEqual(operation_candidates(m,self.op(enabled=False)),[])
  edits,stats=modelling_plan(m,dict(kind='replace',enabled=False));self.assertEqual(edits,[]);self.assertTrue(stats['skipped'])
 def test_order_switch_and_reenable_change_actual_candidate_without_source_write(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);m=Volume((12,8,12));m.box((0,0,0),(11,0,11),'stone_bricks');source=root/'source.master.json.gz';save_master(source,m,set());before=source.read_bytes()
   context=root/'context.json';context.write_text(json.dumps(dict(mode='standalone',openings=[],start=[1.5,1,1.5],targets={'end':[10.5,1,10.5]},interior_probes=[[3,2,3]],cameras=[dict(role='whole',eye=[18,15,18],target=[6,2,6]),dict(role='entry',eye=[1.5,2.62,1.5],target=[6,2,6])])),encoding='utf8')
   a=self.op();b=deepcopy(a);b.update(label='覆盖材质',state='gold_block');s=default_settings();s['operations']=[a,b]
   req=dict(source=str(source),source_sha256=hashlib.sha256(before).hexdigest(),context=str(context),settings=s)
   def candidate(name):
    result=preview_effect(req,root/name);data=json.loads(Path(result['snapshot']).read_text(encoding='utf8'));return {tuple(p):v for p,v in data['master_blocks']},result
   blocks,_=candidate('both');self.assertEqual(blocks[(5,2,5)],'minecraft:gold_block')
   b['enabled']=False;blocks,_=candidate('disabled');self.assertEqual(blocks[(5,2,5)],'minecraft:stone_bricks')
   a['enabled']=False;blocks,result=candidate('all-disabled');self.assertEqual(result['changed_blocks'],0);self.assertNotIn((5,2,5),blocks)
   a['enabled']=b['enabled']=True;s['operations']=[b,a];blocks,_=candidate('reordered');self.assertEqual(blocks[(5,2,5)],'minecraft:stone_bricks');self.assertEqual(source.read_bytes(),before)

if __name__=='__main__':unittest.main(verbosity=2)
