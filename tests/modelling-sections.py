import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_tools import modelling_plan
class Sections(unittest.TestCase):
 def setUp(self):self.m=Volume((24,24,24));self.op=dict(kind='geometry',lo=[0,0,0],hi=[23,23,23],state='stone')
 def plan(self,shape,**kwargs):return modelling_plan(self.m,dict(self.op,geometry=dict(shape=shape,**kwargs)))
 def test_revolve_hole_and_partial(self):
  args=dict(centre=[12,4,12],profile=[[3,0],[5,0],[5,8],[3,8]])
  full,_=self.plan('revolve',**args);half,_=self.plan('revolve',**args,sweep_angle=180)
  self.assertEqual(len(full),2*len(half));self.assertNotIn((12,4,12),dict(full));self.assertFalse(self.m.blocks)
 def test_loft_narrows(self):
  e,_=self.plan('loft',sections=[dict(y=2,vertices=[[2,2],[12,2],[12,12],[2,12]]),dict(y=12,vertices=[[5,5],[9,5],[9,9],[5,9]])]);p=[p for p,v in e]
  self.assertGreater(sum(y==2 for x,y,z in p),sum(y==11 for x,y,z in p))
 def test_sweep_vertical_with_explicit_frame(self):
  e,_=self.plan('section_sweep',vertices=[[-1,-1],[1,-1],[1,1],[-1,1]],points=[[10,2,10],[10,12,10]],up=[1,0,0]);self.assertEqual(len(e),40)
 def test_invalid_polygon_and_protection(self):
  with self.assertRaises(ValueError):self.plan('revolve',profile=[[1,0],[3,3],[1,3],[3,0]])
  with self.assertRaises(ValueError):self.plan('section_sweep',vertices=[[0,0],[1,0],[1,1]],points=[[2,2,2],[2,8,2]])
  op=dict(self.op,geometry=dict(shape='revolve',centre=[12,4,12],profile=[[0,0],[5,0],[5,8],[0,8]]))
  with self.assertRaises(ValueError):modelling_plan(self.m,op,[(12,4,12)])
if __name__=='__main__':unittest.main()
