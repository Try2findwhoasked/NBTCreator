from pathlib import Path
import json,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_refine import save_master
from nbt_room_score import score_room,VISUAL,PROFILES
class Scoring(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.source=self.root/'room.master.json.gz';self.m=Volume((10,7,10));self.m.box([0,0,0],[9,6,9],'stone');self.m.box([1,1,1],[8,5,8],'air');self.context=self.root/'coordinates.json';self.context.write_text(json.dumps(dict(mode='standalone',openings=[],start=[2.5,1,2.5],targets={'end':[7.5,1,7.5]})));self.request=dict(source=str(self.source),context=str(self.context));self.save()
 def save(self):save_master(self.source,self.m,set())
 def rating(self,kind,value):return dict(scores={key:value for key in VISUAL[kind]},evidence='按当前模型实际看图的测试评价',reviewer='human')
 def test_full_composite_and_optional_exterior_weights(self):
  original=self.source.read_bytes();a=score_room(dict(self.request,visual={'interior':self.rating('interior',0)}));b=score_room(dict(self.request,visual={'interior':self.rating('interior',100)}));self.assertEqual(a['gate'],'evaluated_static');self.assertAlmostEqual(b['total_score']-a['total_score'],35,places=2);self.assertEqual(len(a['metrics']),12);self.assertEqual(len(a['group_scores']),4);self.assertEqual(a['coverage_percent'],100);self.assertEqual(self.source.read_bytes(),original)
  low=score_room(dict(self.request,include_exterior=True,visual={'interior':self.rating('interior',75),'exterior':self.rating('exterior',0)}));high=score_room(dict(self.request,include_exterior=True,visual={'interior':self.rating('interior',75),'exterior':self.rating('exterior',100)}));self.assertAlmostEqual(high['total_score']-low['total_score'],20,places=2)
 def test_blocked_routes_cannot_be_compensated_by_visual_scores(self):
  self.m.box([5,1,1],[5,5,8],'stone');self.save();r=score_room(dict(self.request,visual={'interior':self.rating('interior',100)}));self.assertEqual(r['gate'],'blocked');self.assertIsNone(r['total_score']);self.assertLess(r['metrics']['connectivity']['score'],100);self.assertEqual(r['metrics']['routes']['score'],0)
 def test_missing_inputs_are_not_full_credit(self):
  r=score_room(self.request);self.assertIsNone(r['total_score']);self.assertIn('内部视觉评价',r['missing']);r=score_room(dict(source=str(self.source)));self.assertEqual(r['gate'],'incomplete');self.assertEqual(r['coverage_percent'],62)
  r=score_room(dict(self.request,include_exterior=True,visual={'interior':self.rating('interior',100)}));self.assertIn('外部外观评价',r['missing']);self.assertIsNone(r['total_score'])
 def test_low_ceiling_and_unknown_collision_gate_scores(self):
  self.m.box([1,2,1],[8,5,8],'stone');self.save();self.assertEqual(score_room(self.request)['gate'],'blocked');self.m.box([1,1,1],[8,5,8],'air');self.m.put((3,1,3),'chest');self.save();self.assertEqual(score_room(self.request)['gate'],'unsupported')
 def test_ledge_safety_responds_to_actual_floor_hole(self):
  base=score_room(self.request);self.assertEqual(base['metrics']['edge_safety']['score'],100);self.assertEqual(base['metrics']['stable_support']['score'],100);self.m.box([3,0,3],[6,0,6],'air');self.save();r=score_room(self.request);self.assertLess(r['metrics']['edge_safety']['score'],100);self.assertTrue(r['evidence']['edge_positions'])
 def test_detour_efficiency_and_hazard_neighborhood_are_measured(self):
  data=json.loads(self.context.read_text());data['targets']={'end':[7.5,1,2.5]};self.context.write_text(json.dumps(data));base=score_room(self.request);self.assertEqual(base['metrics']['route_directness']['score'],100)
  self.m.box([5,1,1],[5,5,6],'stone');self.save();detour=score_room(self.request);self.assertEqual(detour['gate'],'evaluated_static');self.assertLess(detour['metrics']['route_directness']['score'],base['metrics']['route_directness']['score'])
  self.m.put((3,0,3),'magma_block');self.save();hazard=score_room(self.request);self.assertLess(hazard['metrics']['hazard_safety']['score'],100);self.assertTrue(hazard['evidence']['hazard_positions'])
 def test_profiles_and_visual_function_counts(self):
  for weights in PROFILES.values():self.assertEqual(sum(weights.values()),100);self.assertEqual(len(weights),12)
  self.assertEqual(len(VISUAL['interior']),10);self.assertEqual(len(VISUAL['exterior']),8)
 def test_stale_geometry_and_invalid_visual_inputs_rejected(self):
  with self.assertRaises(ValueError):score_room(dict(self.request,source_sha256='0'*64))
  with self.assertRaises(ValueError):score_room(dict(self.request,visual={'interior':self.rating('interior',101)}))
  snapshot=self.root/'after.json';snapshot.write_text(json.dumps(dict(source_sha256='0'*64,size=[10,7,10],geometry_sha256=self.m.fingerprint())))
  with self.assertRaises(ValueError):score_room(self.request,snapshot)
if __name__=='__main__':unittest.main(verbosity=2)
