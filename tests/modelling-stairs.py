import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_tools import modelling_plan
class Stairs(unittest.TestCase):
 def setUp(self):
  self.m=Volume((40,24,40));self.op=dict(kind='auto_stairs',lo=[0,0,0],hi=[39,23,39],start=[4,2,4],end=[24,6,4],width=1)
 def test_straight_and_no_mutation(self):
  e,r=modelling_plan(self.m,self.op);self.assertEqual(r['feet'][-1][1],6);self.assertTrue(r['route_segments']);self.assertFalse(self.m.blocks)
 def test_switchback(self):
  e,r=modelling_plan(self.m,dict(self.op,mode='switchback',end=[4,6,7],flight_length=12));self.assertEqual(r['feet'][-1],(4.5,6,7.5))
 def test_spiral(self):
  e,r=modelling_plan(self.m,dict(self.op,mode='spiral',centre=[10,2,10],radius=6,start=[4,2,4],end=[4,8,4]));self.assertEqual(r['feet'][-1][1],8)
 def test_head_obstruction_budget_and_bounds(self):
  for change in [dict(end=[6,10,4]),dict(max_writes=1),dict(hi=[8,23,8])]:
   with self.assertRaises(ValueError):modelling_plan(self.m,dict(self.op,**change))
  self.m.box((4,3,4),(24,4,4),'stone')
  with self.assertRaises(ValueError):modelling_plan(self.m,self.op)
if __name__=='__main__':unittest.main()
