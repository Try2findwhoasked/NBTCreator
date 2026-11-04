import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_recipes import translate_operation
from nbt_operation_parameters import validate_operation
class Parameters(unittest.TestCase):
 def test_mode_requirements_and_integer_points(self):
  base=dict(kind='align_region',lo=[0,0,0],hi=[2,2,2],mode='anchor')
  with self.assertRaises(ValueError):validate_operation(base)
  validate_operation(dict(base,source_anchor=[0,0,0],target_anchor=[4,0,0]))
  with self.assertRaises(ValueError):validate_operation(dict(base,source_anchor=[True,0,0],target_anchor=[4,0,0]))
 def test_anchor_path_and_profile_translation(self):
  offset=[10,20,30]
  op=dict(kind='array_region',lo=[0,0,0],hi=[2,2,2],source_anchor=[1,1,1],centre=[5,2,5],points=[[1,2,3],[4,5,6]],radius=4)
  result=translate_operation(op,offset)
  self.assertEqual(result['source_anchor'],[11,21,31]);self.assertEqual(result['points'][1],[14,25,36]);self.assertEqual(result['radius'],4)
  sweep=translate_operation(dict(geometry=dict(shape='section_sweep',points=[[0,0,0],[2,0,0]],vertices=[[-1,-1],[1,-1],[1,1]],up=[0,1,0])),offset)
  self.assertEqual(sweep['geometry']['vertices'],[[-1,-1],[1,-1],[1,1]]);self.assertEqual(sweep['geometry']['up'],[0,1,0])
  loft=translate_operation(dict(geometry=dict(shape='loft',sections=[dict(y=2,vertices=[[1,3],[4,3],[4,6]])])),offset)
  self.assertEqual(loft['geometry']['sections'][0],dict(y=22,vertices=[[11,33],[14,33],[14,36]]))
 def test_external_structure_agent_radial_and_anchor(self):
  import tempfile
  from nbt_structure_agent import build
  seed=dict(kind='box',label='seed',classification='body',lo=[2,2,2],hi=[2,2,2],state='stone')
  radial=dict(kind='array_region',label='ring',classification='body',lo=[2,2,2],hi=[2,2,2],mode='radial',source_anchor=[2,2,2],centre=[16,2,16],radius=5,count=4)
  anchor=dict(kind='align_region',label='anchor',classification='body',lo=[2,2,2],hi=[2,2,2],mode='anchor',source_anchor=[2,2,2],target_anchor=[25,2,25])
  with tempfile.TemporaryDirectory() as workspace:
   result=build(workspace,dict(name='parameter integration',size=[32,16,32],operations=[seed,radial,anchor]))
  self.assertEqual(len(result['blocks']),6)
 def test_nested_types_and_limits(self):
  base=dict(kind='array_region',lo=[0,0,0],hi=[2,2,2],mode='path',points=[[0,0,0],[4,0,0]])
  validate_operation(base)
  for patch in [dict(points=[[0,0],[1,2]]),dict(spacing=0),dict(end_margins=[0,-1]),dict(points=[[0,False,0],[4,0,0]])]:
   with self.assertRaises(ValueError):validate_operation(dict(base,**patch))
if __name__=='__main__':unittest.main()
