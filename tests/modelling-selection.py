import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_tools import modelling_plan
from nbt_selection import select_voxels

class Selection(unittest.TestCase):
 def setUp(self):
  self.m=Volume((20,20,20));self.m.box((3,3,3),(7,7,7),'stone');self.m.put((12,3,3),'stone')
  self.op=dict(kind='selection_replace',lo=[0,0,0],hi=[19,19,19],seed_position=[3,3,3],state='andesite')
 def test_connected_excludes_disconnected_and_is_pure(self):
  before=self.m.fingerprint();edits,r=modelling_plan(self.m,self.op)
  self.assertEqual(len(edits),125);self.assertEqual(before,self.m.fingerprint())
 def test_real_surface_and_thickness(self):
  op=dict(self.op,selection='surface',faces=['up'],lo=[3,3,3],hi=[7,6,7])
  self.assertEqual(select_voxels(self.m,op),[])
  op['hi']=[7,7,7];self.assertEqual(len(select_voxels(self.m,op)),25)
  op['thickness']=2;self.assertEqual(len(select_voxels(self.m,op)),50)
 def test_protection_budget_and_bad_seed(self):
  for changes in [dict(max_writes=1),dict(seed_position=[0,0,0]),dict(faces=['bad']),dict(thickness=True)]:
   with self.assertRaises(ValueError):modelling_plan(self.m,dict(self.op,**changes))
  with self.assertRaises(ValueError):modelling_plan(self.m,self.op,[(3,3,3)])
 def test_connected_surface_stays_on_surface(self):
  points=select_voxels(self.m,dict(self.op,selection='connected_surface'))
  self.assertEqual(len(points),98);self.assertNotIn((5,5,5),points)

if __name__=='__main__':unittest.main()
