import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_tools import modelling_plan
from nbt_arrays import array_placements
class Arrays(unittest.TestCase):
 def setUp(self):
  self.m=Volume((32,20,32));self.m.put((2,2,2),'stone');self.op=dict(kind='array_region',lo=[2,2,2],hi=[2,2,2],mode='path',points=[[10,2,10],[14,2,10],[14,2,14]],spacing=2)
 def test_arc_length_and_snapshot(self):
  e,r=modelling_plan(self.m,self.op);self.assertEqual(len(e),5);self.assertIn(((14,2,12),'minecraft:stone'),e);self.assertEqual(len(self.m.blocks),1)
 def test_radial_cardinal(self):
  p=array_placements(dict(self.op,mode='radial',centre=[16,2,16],radius=5,count=4,orientation='cardinal'))
  self.assertEqual([v for _,v in p],[0,1,2,3]);self.assertEqual(len(set(v for v,_ in p)),4)
 def test_guards(self):
  for patch in [dict(spacing=.1),dict(max_writes=1),dict(points=[[30,2,30],[35,2,30]]),dict(end_margins=[20,20])]:
   with self.assertRaises(ValueError):modelling_plan(self.m,dict(self.op,**patch))
  with self.assertRaises(ValueError):modelling_plan(self.m,self.op,[(10,2,10)])
 def test_turns_use_existing_conservative_transform(self):
  self.m.put((2,2,2),'oak_stairs')
  with self.assertRaises(ValueError):modelling_plan(self.m,dict(self.op,orientation='cardinal'))
if __name__=='__main__':unittest.main()
