import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_tools import modelling_plan
class Roofs(unittest.TestCase):
 def setUp(self):self.m=Volume((24,24,24));self.op=dict(kind='auto_roof',lo=[2,4,2],hi=[21,20,21],rise=5)
 def test_all_profiles_and_pure(self):
  for roof in ('gable','hip','gambrel','dome'):
   with self.subTest(roof=roof):
    e,r=modelling_plan(self.m,dict(self.op,roof=roof));self.assertTrue(e);self.assertFalse(r['structural_support_verified'])
  self.assertFalse(self.m.blocks)
 def test_symmetry_and_hollow_interior(self):
  e,_=modelling_plan(self.m,self.op);p=dict(e)
  self.assertEqual(set(p),{(23-x,y,z) for x,y,z in p});self.assertNotIn((12,4,12),p)
 def test_stair_direction_and_hip_corners(self):
  e,_=modelling_plan(self.m,dict(self.op,finish='stairs',roof='hip'))
  self.assertTrue(any('outer_' in v for _,v in e));self.assertTrue(any('facing=east' in v for _,v in e))
 def test_eaves_protection_budget_and_height(self):
  for change in [dict(eaves=1),dict(max_writes=1),dict(rise=100),dict(thickness=8)]:
   with self.assertRaises(ValueError):modelling_plan(self.m,dict(self.op,**change))
  e,_=modelling_plan(self.m,self.op)
  with self.assertRaises(ValueError):modelling_plan(self.m,self.op,[e[0][0]])
if __name__=='__main__':unittest.main()
