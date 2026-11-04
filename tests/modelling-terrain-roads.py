import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_tools import modelling_plan
class Terrain(unittest.TestCase):
 def setUp(self):
  self.m=Volume((20,16,20));self.m.box((0,0,0),(19,2,19),'dirt')
  self.op=dict(kind='terrain_road',lo=[0,0,0],hi=[19,15,19],start=[3,2,3],end=[15,2,3],width=1)
 def test_avoid_obstacle_and_pure(self):
  self.m.box((8,3,0),(8,5,8),'stone_bricks');before=self.m.fingerprint()
  e,r=modelling_plan(self.m,self.op);self.assertTrue(any(p[2]>8 for p in r['path']));self.assertTrue(r['walking_checked']);self.assertEqual(before,self.m.fingerprint())
 def test_incline(self):
  self.m.box((10,3,0),(19,3,19),'dirt')
  e,r=modelling_plan(self.m,dict(self.op,end=[15,3,3]));self.assertTrue(any('_stairs' in v for _,v in e))
 def test_no_path_budget_and_protection(self):
  for changes in [dict(max_writes=1),dict(end=[15,5,3])]:
   with self.assertRaises(ValueError):modelling_plan(self.m,dict(self.op,**changes))
  wall={(8,y,z) for y in range(16) for z in range(20)}
  with self.assertRaises(ValueError):modelling_plan(self.m,self.op,wall)
 def test_bridge_opt_in(self):
  for x in (8,9):
   for y in range(3):
    for z in range(20):self.m.put((x,y,z),'air')
  with self.assertRaises(ValueError):modelling_plan(self.m,self.op)
  e,r=modelling_plan(self.m,dict(self.op,max_bridge_span=2));self.assertEqual(len(r['bridge_cells']),2)
if __name__=='__main__':unittest.main()
