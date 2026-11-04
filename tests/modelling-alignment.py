import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_tools import modelling_plan
class Alignment(unittest.TestCase):
 def setUp(self):
  self.m=Volume((24,20,24));self.m.box((2,3,2),(3,4,3),'stone')
  self.op=dict(kind='align_region',lo=[2,3,2],hi=[3,4,3],mode='anchor',source_anchor=[2,3,2],target_anchor=[10,3,10])
 def test_anchor_and_pure(self):
  before=self.m.fingerprint();e,r=modelling_plan(self.m,self.op);self.assertEqual(len(e),8);self.assertIn(((10,3,10),'minecraft:stone'),e);self.assertEqual(self.m.fingerprint(),before)
 def test_centers_reject_half_grid(self):
  with self.assertRaises(ValueError):modelling_plan(self.m,dict(self.op,mode='align',target_lo=[10,3,10],target_hi=[12,4,12]))
 def test_ground_and_uneven_or_unknown_support(self):
  self.m.box((10,0,10),(11,0,11),'stone');op=dict(self.op,mode='ground',destination=[10,10,10])
  e,r=modelling_plan(self.m,op);self.assertEqual(r['offset'],[8,-2,8])
  self.m.put((10,1,10),'stone')
  with self.assertRaises(ValueError):modelling_plan(self.m,op)
 def test_move_clears_source_and_guards(self):
  e,_=modelling_plan(self.m,dict(self.op,move=True));self.assertEqual(sum(v=='minecraft:air' for _,v in e),8)
  for kwargs in [dict(max_writes=1),dict(target_anchor=[25,3,10]),dict(move='yes')]:
   with self.assertRaises(ValueError):modelling_plan(self.m,dict(self.op,**kwargs))
  with self.assertRaises(ValueError):modelling_plan(self.m,self.op,[(10,3,10)])
if __name__=='__main__':unittest.main()
