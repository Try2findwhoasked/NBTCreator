"""Real shared-engine and portable CLI regressions for parametric objects."""
import json,sys,tempfile,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];SCRIPTS=ROOT/'.agents/skills/minecraft-nbt-modeler/scripts';sys.path.insert(0,str(SCRIPTS))
from nbt_structure_agent import dispatch,build
from nbt_components import paste_plan
from nbt_assembly import Volume
from nbt_building.parametric import KINDS

class Parametric(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
 def request(self,kind='pillar',**kw):return dict(kind=kind,size=[7,8,9],**kw)
 def test_all_kinds_styles_real_bounds_states_and_no_writes(self):
  for kind in KINDS:
   hashes=[]
   for style in ('classic','stepped','open'):
    with self.subTest(kind=kind,style=style):
     args=self.request(kind,style=style);result=dispatch(self.root,'parametric_compile',args);data=build(self.root,result['spec'])
     hashes.append(data['content_sha256']);self.assertFalse(result['model_modified']);self.assertFalse(result['approval_created'])
     self.assertEqual(result['verification']['routes'],'not_checked');self.assertGreater(result['block_count'],0)
     self.assertEqual(result,dispatch(self.root,'parametric_compile',args));self.assertEqual(result['content_sha256'],data['content_sha256'])
     self.assertEqual(all(b[4] for b in data['blocks']),kind=='wall')
   self.assertGreater(len(set(hashes)),1,kind)
  self.assertEqual(list(self.root.iterdir()),[])
 def test_parameters_change_geometry_and_small_boundaries(self):
  for kind in KINDS:
   for size in ([3,3,3],[8,9,12]):
    result=dispatch(self.root,'parametric_compile',dict(kind=kind,size=size));self.assertEqual(result['spec']['size'],size)
  a=dispatch(self.root,'parametric_compile',self.request('wall',spacing=2,thickness=1))
  b=dispatch(self.root,'parametric_compile',self.request('wall',spacing=4,thickness=2))
  self.assertNotEqual(a['content_sha256'],b['content_sha256'])
  for kind in ['plant','planter']:
   data=build(self.root,dispatch(self.root,'parametric_compile',self.request(kind,foliage='azalea_leaves[persistent=true]'))['spec'])
   self.assertTrue(any('azalea_leaves' in s for s in data['palette']))
 def test_invalid_parameters_and_budget_refuse_before_files(self):
  for patch in [dict(kind='exec'),dict(script='x'),dict(size=[3,2,3]),dict(size=[33,8,9]),dict(size=[7,True,9]),dict(material='air'),dict(material='tuff_bricks'),dict(spacing=1),dict(thickness=3,size=[3,8,9]),dict(max_changed_blocks=1),dict(kind='stairs',size=[7,9,3]),dict(kind='stairs',stair_material='stone'),dict(kind='stairs',stair_material='oak_stairs[facing=north]')]:
   with self.subTest(patch=patch),self.assertRaises(ValueError):dispatch(self.root,'parametric_preview',{**self.request(),**patch})
  self.assertEqual(list(self.root.iterdir()),[])
 def test_preview_save_place_and_protection_are_separate(self):
  preview=dispatch(self.root,'parametric_preview',self.request('wall'))
  self.assertTrue(Path(preview['thumbnail']).is_file());self.assertEqual(dispatch(self.root,'structure_list',{})['items'],[])
  item=dispatch(self.root,'structure_write',{k:preview[k] for k in ('preview_id','preview_sha256')})
  recipe=json.loads((self.root/'.nbtcreator/components/recipes'/(item['id']+'.json')).read_text(encoding='utf8'))
  self.assertEqual(recipe['parametric_recipe']['parameters'],self.request('wall'))
  self.assertEqual(recipe['parametric_recipe']['recipe_sha256'],preview['recipe_sha256'])
  placed=dispatch(self.root,'structure_place',dict(id=item['id'],content_sha256=item['content_sha256'],position=[8,1,8],size=[32,16,32],quarter_turns=1))
  self.assertFalse(placed['model_modified']);self.assertEqual(placed['operations'][0]['classification'],'wall')
  op=placed['operations'][0];model=Volume((32,16,32));edits,_=paste_plan(model,op,set());target=edits[0][0]
  with self.assertRaisesRegex(ValueError,'保护'):paste_plan(model,dict(op,overwrite=True),{target})
  with self.assertRaises(ValueError):dispatch(self.root,'structure_place',dict(id=item['id'],content_sha256=item['content_sha256'],position=[0,0,0],size=[3,3,3]))
 def test_ornament_profiles_motifs_and_query_filters(self):
  from nbt_ornament import PROFILES
  selected=dispatch(self.root,'parametric_list',dict(kind='wall',ornament_profile='gothic'))
  self.assertEqual(len(selected['kinds']),1);self.assertEqual(set(selected['ornament_profiles']),{'gothic'})
  hashes=[]
  for profile,info in PROFILES.items():
   if profile=='none':continue
   for motif in info['motifs']:
    for kind in KINDS:
     with self.subTest(profile=profile,motif=motif,kind=kind):
      args=dict(kind=kind,size=[13,13,15],ornament=dict(profile=profile,motif=motif,density=100,border_layers=0))
      result=dispatch(self.root,'parametric_compile',args);data=build(self.root,result['spec'])
      self.assertEqual(result['content_sha256'],data['content_sha256']);self.assertFalse(result['model_modified'])
      if kind=='wall':
       self.assertGreater(result['ornament']['added_or_recolored_blocks'],0);hashes.append(result['content_sha256'])
  self.assertGreater(len(set(hashes)),5)
 def test_ornament_density_depth_symmetry_and_budget(self):
  base=dict(kind='wall',size=[15,13,4],ornament=dict(profile='geometric',motif='lattice',density=100,border_layers=0,depth=2,scale=4))
  result=dispatch(self.root,'parametric_compile',base);data=build(self.root,result['spec'])
  op=result['spec']['operations'][-1];points={tuple(v[:3]) for v in op['voxels']}
  self.assertTrue(all((14-x,y,z) in points for x,y,z in points));self.assertTrue(all(z in (1,2) for x,y,z in points))
  empty=dispatch(self.root,'parametric_compile',{**base,'ornament':{**base['ornament'],'density':0}})
  self.assertEqual(empty['ornament']['added_or_recolored_blocks'],0)
  thinner=dispatch(self.root,'parametric_compile',{**base,'ornament':{**base['ornament'],'depth':1}})
  self.assertLess(thinner['ornament']['added_or_recolored_blocks'],result['ornament']['added_or_recolored_blocks'])
  for ornament in [dict(profile='exec'),dict(profile='none',depth=2),dict(profile='gothic',motif='vine'),dict(profile='gothic',depth=3,source='x'),dict(profile='gothic',material='air'),dict(profile='gothic',density=101)]:
   with self.subTest(ornament=ornament),self.assertRaises(ValueError):dispatch(self.root,'parametric_preview',{**base,'ornament':ornament})
  with self.assertRaises(ValueError):dispatch(self.root,'parametric_compile',{**base,'max_changed_blocks':1})
  small=dict(kind='wall',size=[3,3,3],ornament=dict(profile='gothic'))
  with self.assertRaisesRegex(ValueError,'过小'):dispatch(self.root,'parametric_compile',small)
 def test_stair_ornament_preserves_actual_treads(self):
  args=dict(kind='stairs',size=[7,8,12]);plain=build(self.root,dispatch(self.root,'parametric_compile',args)['spec'])
  decorated=build(self.root,dispatch(self.root,'parametric_compile',{**args,'ornament':dict(profile='art_deco',density=100)})['spec'])
  get=lambda data:{tuple(b[:3]):data['palette'][b[3]] for b in data['blocks']}
  before,after=get(plain),get(decorated)
  for p,value in before.items():
   if '_stairs[' in value:self.assertEqual(value,after[p])
  self.assertEqual(set(before),set(after))
 def test_trusted_contract_rejects_schema_defaults_and_semantic_escape(self):
  constraints=dict(kind='wall',size=[15,13,4],profiles=['gothic'],motifs=['pointed_arch'],max_depth=2,min_density=80,max_density=100,max_blocks=2048,max_operations=30,require_decoration=True)
  proposal=dict(kind='wall',size=[15,13,4],ornament=dict(profile='gothic',density=100,depth=2))
  contract=dispatch(self.root,'parametric_contract',dict(constraints=constraints))
  self.assertEqual(contract['response_schema']['properties']['kind']['enum'],['wall'])
  accepted=dispatch(self.root,'parametric_validate',dict(proposal=proposal,constraints=constraints));self.assertTrue(accepted['accepted']);self.assertFalse(accepted['approval_created']);self.assertFalse(accepted['model_modified']);self.assertEqual(accepted['constraints_sha256'],contract['constraints_sha256'])
  self.assertEqual(accepted['spec']['max_changed_blocks'],2048)
  for bad in [{**proposal,'kind':'table'},{**proposal,'size':[16,13,4]},{**proposal,'constraints':{}},{**proposal,'max_changed_blocks':65536},{**proposal,'ornament':dict(profile='art_deco',density=100)},{**proposal,'ornament':dict(profile='gothic',density=100,motif='tracery')},{**proposal,'ornament':dict(profile='gothic')},{**proposal,'ornament':dict(profile='gothic',density=100,depth=3)}]:
   with self.subTest(bad=bad),self.assertRaises(ValueError):dispatch(self.root,'parametric_validate',dict(proposal=bad,constraints=constraints))
  with self.assertRaises(ValueError):dispatch(self.root,'parametric_validate',dict(proposal=proposal,constraints={**constraints,'max_operations':1}))
  with self.assertRaises(ValueError):dispatch(self.root,'parametric_validate',dict(proposal=proposal,constraints={**constraints,'materials':['gold_block']}))
  with self.assertRaises(ValueError):dispatch(self.root,'parametric_contract',dict(constraints=dict(profiles=['gothic'],motifs=['vine'])))
  self.assertEqual(list(self.root.iterdir()),[])
 def test_forms_themes_and_furniture_composition(self):
  forms=[
   ('pillar',dict(base_height=2,capital_height=3,section='cross',taper=True,flutes=True)),
   ('ceiling',dict(profile='parallel',drop=3,pitch=5,border=2,light_strip=True)),
   ('wall',dict(base_height=2,dado_height=6,cornice_height=2,panel_pitch=4,relief_depth=3)),
   *[('stairs',dict(profile=profile,rise=8,run_width=3,landing=3,rail=True))
     for profile in ('straight','quarter_turn','switchback','spiral')],
   *[('plant',dict(profile=profile,radius=3,crown_height=4,density=100,seed=17))
     for profile in ('upright','trailing','climbing')],
  ]
  variants={}
  for kind,form in forms:
   with self.subTest(kind=kind,form=form):
    args=dict(kind=kind,size=[16,12,16],form=form,theme='timber_room')
    result=dispatch(self.root,'parametric_compile',args)
    self.assertEqual(result,dispatch(self.root,'parametric_compile',args))
    if kind=='wall':self.assertTrue(all(b[4] for b in build(self.root,result['spec'])['blocks']))
    variants.setdefault(kind,set()).add(result['content_sha256'])
  self.assertEqual(len(variants['stairs']),4)
  self.assertEqual(len(variants['plant']),3)
  custom=dispatch(self.root,'parametric_compile',dict(kind='pillar',size=[7,8,9],form={},theme='timber_room',material='stone'))
  self.assertIn('minecraft:stone',build(self.root,custom['spec'])['palette'])
  self.assertIn('minecraft:dark_oak_planks',build(self.root,custom['spec'])['palette'])
  with self.assertRaisesRegex(ValueError,'不适用'):
   dispatch(self.root,'parametric_compile',dict(kind='pillar',size=[7,8,9],form=dict(profile='spiral')))
  items=[dict(id='table',position=[4,0,4],object=dict(kind='table',size=[5,3,5])),
         dict(id='bench',position=[4,0,10],object=dict(kind='bench',size=[5,3,3]))]
  args=dict(name='dining',size=[16,8,16],objects=items)
  result=dispatch(self.root,'parametric_compose',args)
  self.assertEqual([item['id'] for item in result['objects']],['table','bench'])
  with self.assertRaisesRegex(ValueError,'占用'):
   dispatch(self.root,'parametric_compose',dict(args,reserved_boxes=[dict(lo=[4,2,4],hi=[4,2,4])]))
  with self.assertRaisesRegex(ValueError,'重叠'):
   dispatch(self.root,'parametric_compose',dict(args,objects=[items[0],dict(items[0],id='second')]))

 def test_four_stair_forms_connect_declared_platforms(self):
  from nbt_collision import check_routes
  from nbt_tools import transformed_state
  targets={'straight':(4,9,11),'quarter_turn':(10,9,8),'switchback':(7,9,2),'spiral':(5,9,4)}
  for profile,(x,y,z) in targets.items():
   with self.subTest(profile=profile):
    args=dict(kind='stairs',size=[16,12,16],form=dict(profile=profile,rise=8,run_width=3,landing=3,rail=True))
    compiled=dispatch(self.root,'parametric_compile',args)
    data=build(self.root,compiled['spec'])
    model=Volume((22,16,22));model.box([0,0,0],[21,0,21],'stone')
    for a,b,c,index,_ in data['blocks']:
     model.put((a+3,b+1,c+3),data['palette'][index])
    model.put((x,y-1,z),'stone')
    self.assertTrue(check_routes(model,[4.5,1,2.5],{'top':[x+.5,y,z+.5]},max_poses=50000)['passed'])
  self.assertIn('facing=west',transformed_state('stone_brick_stairs[facing=south]',1,None))
  with self.assertRaises(ValueError):
   transformed_state('stone_brick_stairs[facing=south,shape=outer_left]',1,None)

 def test_regenerate_locks_other_parts_and_binds_parent(self):
  original=dict(kind='pillar',size=[9,10,9],form=dict(capital_height=2))
  first=dispatch(self.root,'parametric_compile',original)
  replacement=dict(original,form=dict(capital_height=2,capital_material='gold_block'))
  args=dict(object_id='column-01',original=original,replacement=replacement,part='capital',original_recipe_sha256=first['recipe_sha256'])
  result=dispatch(self.root,'parametric_regenerate',args)
  self.assertEqual(result['parent_recipe_sha256'],first['recipe_sha256'])
  self.assertEqual(result['object_id'],'column-01')
  def lower(spec):
   data=build(self.root,spec)
   return {tuple(b[:3]):data['palette'][b[3]] for b in data['blocks'] if b[1]<8}
  self.assertEqual(lower(first['spec']),lower(result['spec']))
  with self.assertRaisesRegex(ValueError,'之外'):
   dispatch(self.root,'parametric_regenerate',dict(args,replacement=dict(replacement,material='stone')))
  with self.assertRaisesRegex(ValueError,'预算'):
   dispatch(self.root,'parametric_regenerate',dict(args,max_changed_blocks=1))
  with self.assertRaisesRegex(ValueError,'哈希'):
   dispatch(self.root,'parametric_regenerate',dict(args,original_recipe_sha256='0'*64))

 def test_sample_fit_noise_hash_and_ornate_highlights(self):
  from PIL import Image, ImageDraw
  from hashlib import sha256
  path=self.root/'sample.png'
  image=Image.new('L',(15,15),0)
  draw=ImageDraw.Draw(image)
  draw.rectangle((2,2,12,12),fill=136)
  draw.line([(2,7),(7,2),(12,7),(7,12),(2,7)],fill=255,width=1)
  image.save(path)
  sample=dict(path=path.name,sha256=sha256(path.read_bytes()).hexdigest(),
              noise_strength=0,threshold=50)
  ornament=dict(profile='geometric',density=100,border_layers=0,sample=sample)
  args=dict(kind='wall',size=[15,15,4],style='open',ornament=ornament)
  def run(**overrides):
   return dispatch(self.root,'parametric_compile',dict(args,ornament={**ornament,**overrides}))
  plain=run()
  self.assertEqual(plain['ornament']['sample_sha256'],sample['sha256'])
  self.assertEqual(plain,run())
  noisy=run(sample=dict(sample,noise_strength=40),seed=31)
  self.assertEqual(noisy,run(sample=dict(sample,noise_strength=40),seed=31))
  self.assertNotEqual(noisy['content_sha256'],plain['content_sha256'])
  self.assertNotEqual(noisy['content_sha256'],run(sample=dict(sample,noise_strength=40),seed=32)['content_sha256'])
  ornate=run(richness=3,highlight='gold_block')
  self.assertIn('minecraft:gold_block',build(self.root,ornate['spec'])['palette'])
  self.assertNotEqual(ornate['content_sha256'],plain['content_sha256'])
  with self.assertRaisesRegex(ValueError,'工作区'):
   run(sample=dict(sample,path='../sample.png'))
  with self.assertRaisesRegex(ValueError,'SHA256'):
   run(sample=dict(sample,sha256='0'*64))

 def test_color_reduction_preserves_silhouette_and_fits_half_blocks(self):
  from hashlib import sha256
  from PIL import Image
  path=self.root/'colors.png'
  image=Image.new('RGBA',(16,16))
  for x,y,color in [(4,11,'red'),(5,11,'red'),(6,11,'blue'),(7,11,'blue'),(7,10,'blue'),
                    (8,10,'red'),(9,10,'red'),(8,11,'red'),(9,11,'red')]:
   from PIL import ImageColor
   image.putpixel((x,y),ImageColor.getcolor(color,'RGBA'))
  image.save(path)
  sample=dict(path=path.name,sha256=sha256(path.read_bytes()).hexdigest(),channel='alpha',noise_strength=0)
  args=dict(kind='wall',size=[8,8,3],style='open',ornament=dict(profile='geometric',
      border_layers=0,density=100,sample=sample,sample_shape_fit=dict(slab='quartz_slab',stairs='quartz_stairs')))
  plain=dispatch(self.root,'parametric_compile',args)
  sample['colors']=[dict(rgb='#FF0000',material='red_wool'),dict(rgb='#0000FF',material='blue_wool')]
  colored=dispatch(self.root,'parametric_compile',args)
  self.assertEqual(plain['ornament']['sample_subcell_comparison'],colored['ornament']['sample_subcell_comparison'])
  self.assertEqual(colored['ornament']['sample_shape_counts'],dict(slab=1,stairs=1,full=1))
  self.assertIn('minecraft:red_wool',build(self.root,colored['spec'])['palette'])
  self.assertEqual(colored['ornament']['sample_color_count'],2)

 def test_architectural_sample_repeat_and_shaped_trim(self):
  from hashlib import sha256
  from PIL import Image,ImageDraw
  from nbt_tools import transformed_state
  path=self.root/'tile.png';image=Image.new('L',(16,16))
  ImageDraw.Draw(image).rectangle((4,4,11,11),fill=255);image.save(path)
  sample=dict(path=path.name,sha256=sha256(path.read_bytes()).hexdigest(),
              noise_strength=0,reference_id='bursa_vine_frieze')
  ornament=dict(profile='geometric',sample=sample,density=100,border_layers=0,depth=2)
  args=dict(kind='wall',size=[24,16,4],style='open',ornament=ornament)
  plain=dispatch(self.root,'parametric_compile',args)
  decorated=dispatch(self.root,'parametric_compile',dict(args,ornament=dict(
      ornament,sample_repeat=[3,1],edge_trim=dict(slab='stone_brick_slab',stairs='stone_brick_stairs'))))
  self.assertNotEqual(plain['content_sha256'],decorated['content_sha256'])
  report=decorated['ornament'];self.assertGreater(report['trimmed_blocks'],0)
  self.assertEqual(report['sample_reference']['rights'],'Public Domain')
  palette=build(self.root,decorated['spec'])['palette']
  for family in ('_slab','_stairs'):
   selected=next(value for value in palette if family in value)
   self.assertIn(family,transformed_state(selected,1,'x'))
  self.assertIn('kashan_star_cross',dispatch(self.root,'parametric_list',{})['architectural_samples'])

 def test_ornament_layout_preserves_center_and_limits_corner_motifs(self):
  args=dict(kind='wall',size=[15,15,4])
  base=dict(profile='geometric',motif='lattice',border_layers=0,density=100,scale=2)
  for layout in ('continuous','centerpiece','corners'):
   ornament=dict(base,layout=layout)
   if layout=='continuous':ornament['center_clear']=5
   result=dispatch(self.root,'parametric_compile',dict(args,ornament=ornament))
   coords=result['spec']['operations'][-1]['voxels']
   self.assertGreater(len(coords),0)
   for x,y,z,index in coords:
    dx,dy=abs(2*x-14),abs(2*y-14)
    if layout=='continuous':self.assertFalse(dx<5 and dy<5)
    elif layout=='centerpiece':self.assertTrue(dx<=7 and dy<=7)
    else:self.assertTrue(dx>=7 and dy>=7)

 def test_generated_facade_discovers_and_executes_without_electron(self):
  from nbt_exposure import apply
  apply(self.root)
  facade=self.root/'.agents/skills/nbtcreator-workspace/nbt.py'
  def run(*args):
   result=subprocess.run([sys.executable,str(facade),*args],cwd=self.root,capture_output=True,text=True,encoding='utf8');self.assertEqual(result.returncode,0,result.stdout+result.stderr);return json.loads(result.stdout)
  caps=run('capabilities','--agent-tool','parametric_compile');self.assertEqual(set(caps['agent_tools']),{'parametric_compile'})
  request=self.root/'params.json';request.write_text(json.dumps(self.request('ceiling')))
  result=run('components','agent','--tool','parametric_compile','--request',str(request))['result']
  self.assertEqual(result['spec']['anchor'][1],7);self.assertIn('capabilities --agent-tool',(facade.parent/'SKILL.md').read_text(encoding='utf8'))
  request.write_text(json.dumps(dict(kind='wall',ornament_profile='gothic')));listed=run('components','agent','--tool','parametric_list','--request',str(request))['result'];self.assertEqual(len(listed['kinds']),1);self.assertIn('gothic',listed['ornament_profiles'])
  request.write_text(json.dumps(dict(kind='wall',size=[15,13,4],ornament=dict(profile='gothic',depth=2))))
  decorated=run('components','agent','--tool','parametric_compile','--request',str(request))['result'];self.assertGreater(decorated['ornament']['added_or_recolored_blocks'],0)
  request.write_text(json.dumps(dict(proposal=dict(kind='wall',size=[15,13,4],ornament=dict(profile='gothic',density=100)),constraints=dict(kind='wall',profiles=['gothic'],require_decoration=True))))
  accepted=run('components','agent','--tool','parametric_validate','--request',str(request))['result'];self.assertTrue(accepted['accepted'])

if __name__=='__main__':unittest.main(verbosity=2)
