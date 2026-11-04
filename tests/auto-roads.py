import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_tools import modelling_plan
from nbt_detail_control import default_settings, compile_plan

class Roads(unittest.TestCase):
 def setUp(self):
  self.model=Volume((32,16,32))
  self.op=dict(kind='auto_road',label='道路',classification='body',lo=[0,0,0],hi=[31,15,31],start=[4,3,4],end=[20,3,20],width=1,depth=1,state='stone_bricks')
 def test_connected_diagonal_and_no_mutation(self):
  edits,report=modelling_plan(self.model,self.op);points={p for p,v in edits};seen={tuple(self.op['start'])};pending=list(seen)
  while pending:
   x,y,z=pending.pop()
   for p in ((x+1,y,z),(x-1,y,z),(x,y,z+1),(x,y,z-1)):
    if p in points and p not in seen:seen.add(p);pending.append(p)
  self.assertEqual(points,seen);self.assertIn(tuple(self.op['end']),seen);self.assertFalse(self.model.blocks)
 def test_width_depth_and_both_bends(self):
  for route,corner in [('x_first',(20,3,4)),('z_first',(4,3,20))]:
   edits,_=modelling_plan(self.model,dict(self.op,route=route,width=4,depth=2));points={p for p,v in edits};self.assertIn(corner,points);self.assertEqual({p[1] for p in points},{2,3});self.assertEqual(min(p[0] for p in points),3);self.assertEqual(max(p[0] for p in points),22)
 def test_bounds_protection_collision_budget_and_invalid_inputs(self):
  with self.assertRaisesRegex(ValueError,'保护'):modelling_plan(self.model,self.op,{(4,3,4)})
  for change in [dict(width=True),dict(width=17),dict(depth=9),dict(route='auto'),dict(overwrite='yes'),dict(state='air'),dict(end=[20,4,20]),dict(width=16),dict(max_writes=1)]:
   with self.subTest(change=change),self.assertRaises(ValueError):modelling_plan(self.model,dict(self.op,**change))
  self.model.put((4,3,4),'gold_block')
  with self.assertRaisesRegex(ValueError,'已有方块'):modelling_plan(self.model,self.op)
  self.assertTrue(modelling_plan(self.model,dict(self.op,overwrite=True))[0]);self.assertEqual(self.model.get((4,3,4)),'minecraft:gold_block')
 def test_shared_settings_plan(self):
  settings=default_settings();settings['operations']=[self.op]
  self.assertEqual(compile_plan(settings,self.model.size)['operations'][-1]['kind'],'auto_road')

if __name__=='__main__':unittest.main()
