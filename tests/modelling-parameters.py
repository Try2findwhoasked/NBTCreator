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
 def test_geometry_nested_contract(self):
  base=dict(kind='geometry',lo=[0,0,0],hi=[15,15,15])
  valid=dict(shape='section_sweep',vertices=[[-1,-1],[1,-1],[1,1]],points=[[2,4,2],[10,4,2]],up=[0,1,0])
  validate_operation(dict(base,geometry=valid))
  for shape in [dict(valid,points=[[1,2],[3,4]]),dict(valid,vertices=[[0,0],[1,1]]),dict(valid,script='x'),dict(shape='loft',sections=[dict(y=2,vertices=[[0,0],[1,0],[1,1]])]),dict(shape='revolve',profile=[[0,0],[4,0],[4,4]],sweep_angle=0)]:
   with self.assertRaises(ValueError):validate_operation(dict(base,geometry=shape))
 def test_external_agent_stair_roof_and_section_modes(self):
  import tempfile
  from nbt_structure_agent import build
  cases=[dict(kind='auto_stairs',mode='straight',start=[4,2,4],end=[24,6,4]),dict(kind='auto_stairs',mode='switchback',start=[4,2,4],end=[4,6,7],flight_length=12),dict(kind='auto_stairs',mode='spiral',start=[4,2,4],end=[4,8,4],centre=[10,2,10],radius=6)]
  cases += [dict(kind='auto_roof',roof=roof,rise=4,footprint=[[4,4],[20,20]],break_fraction=.4,break_height=.7) for roof in ('gable','hip','gambrel','dome')]
  cases += [dict(kind='geometry',geometry=dict(shape='section_sweep',vertices=[[-1,-1],[1,-1],[1,1],[-1,1]],points=[[4,8,4],[20,8,4]])),dict(kind='geometry',geometry=dict(shape='loft',sections=[dict(y=4,vertices=[[4,4],[16,4],[16,16],[4,16]]),dict(y=12,vertices=[[7,7],[13,7],[13,13],[7,13]])])),dict(kind='geometry',geometry=dict(shape='revolve',centre=[16,4,16],profile=[[2,0],[4,0],[4,8],[2,8]]))]
  with tempfile.TemporaryDirectory() as workspace:
   for case in cases:
    with self.subTest(case=case):
     op=dict(label='integration',classification='body',lo=[0,0,0],hi=[31,23,31],**case)
     result=build(workspace,dict(name='integration',size=[32,24,32],operations=[op]))
     self.assertTrue(result['blocks'])
 def test_external_agent_selection_ground_path_and_terrain(self):
  import tempfile
  from nbt_structure_agent import build
  def box(lo,hi,state='stone'):return dict(kind='box',label='base',classification='body',lo=lo,hi=hi,state=state)
  cases=[
   [box([2,2,2],[3,3,3]),dict(kind='selection_replace',seed_position=[2,2,2],from_states=['stone'],state='andesite')],
   [box([2,4,2],[3,5,3]),box([12,0,12],[13,0,13]),dict(kind='align_region',mode='ground',lo=[2,4,2],hi=[3,5,3],destination=[12,10,12])],
   [box([2,2,2],[2,2,2]),dict(kind='array_region',mode='path',lo=[2,2,2],hi=[2,2,2],points=[[10,2,10],[20,2,10]],spacing=4,end_margins=[1,1])],
   [box([0,0,0],[31,1,31],'dirt'),dict(kind='terrain_road',start=[3,1,3],end=[24,1,24],terrain_states=['dirt'])]]
  with tempfile.TemporaryDirectory() as workspace:
   for steps in cases:
    with self.subTest(kind=steps[-1]['kind']):
     steps[-1]=dict(dict(label='integration',classification='body',lo=[0,0,0],hi=[31,23,31]),**steps[-1])
     result=build(workspace,dict(name='integration',size=[32,24,32],operations=steps));self.assertTrue(result['blocks'])
 def test_nonzero_selection_anchor_and_lathe_actual_candidate(self):
  import tempfile,hashlib
  from nbt_assembly import Volume
  from nbt_refine import save_master
  from nbt_selection_edit import dispatch
  from nbt_detail_control import simulate_plan
  with tempfile.TemporaryDirectory() as folder:
   source=Path(folder)/'source.master.json.gz';model=Volume((48,32,48));model.put((12,6,12),'stone');save_master(source,model,set())
   request=dict(source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),lo=[10,4,10],hi=[35,27,35],geometry_sha256=model.fingerprint(),allow_overwrite=True)
   operations=[dict(kind='align_region',label='anchor',classification='body',lo=[2,2,2],hi=[2,2,2],mode='anchor',source_anchor=[2,2,2],target_anchor=[20,2,20]),dict(kind='geometry',label='lathe',classification='body',lo=[0,0,0],hi=[25,23,25],geometry=dict(shape='revolve',centre=[12,4,12],profile=[[2,0],[4,0],[4,6],[2,6]]),state='andesite')]
   compiled=dispatch('compile',dict(request,operations=operations))['operations']
   candidate,_,_=simulate_plan(model,set(),dict(operations=compiled),dict(protected_boxes=[],protected_paths=[],max_changed_blocks=65536))
   self.assertEqual(candidate.get((30,6,30)),'minecraft:stone');self.assertEqual(model.get((30,6,30)),'minecraft:air')
   changed=[p for p,v in candidate.blocks.items() if model.get(p)!=v]
   self.assertTrue(all(10<=x<=35 and 4<=y<=27 and 10<=z<=35 for x,y,z in changed))
   self.assertEqual(candidate.get((22,8,22)),'minecraft:air')
 def test_new_engine_fields_are_exposed(self):
  import ast,json
  root=Path(__file__).resolve().parents[1]/'.agents/skills/minecraft-nbt-modeler'
  catalog=json.loads((root/'tool-catalog.json').read_text(encoding='utf8'))
  files={'selection_replace':'nbt_selection.py','align_region':'nbt_alignment.py','array_region':'nbt_arrays.py','auto_stairs':'nbt_stairs.py','terrain_road':'nbt_terrain_roads.py','auto_roof':'nbt_roofs.py'}
  for kind,file in files.items():
   keys=set()
   for node in ast.walk(ast.parse((root/'scripts'/file).read_text(encoding='utf8'))):
    if isinstance(node,ast.Subscript) and isinstance(node.value,ast.Name) and node.value.id in ('op','operation') and isinstance(node.slice,ast.Constant):keys.add(node.slice.value)
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id in ('op','operation') and node.func.attr=='get' and node.args and isinstance(node.args[0],ast.Constant):keys.add(node.args[0].value)
   self.assertFalse(keys-set(catalog['operation_parameters'][kind]['properties'])-{'kind'},kind)
if __name__=='__main__':unittest.main()
