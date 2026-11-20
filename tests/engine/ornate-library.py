"""Validate the authored collection through transforms and real SNBT roundtrips."""
import argparse,copy,json,sys,tempfile,unittest,threading
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_components import validate,placement,paste_plan
from nbt_tools import transformed_state
from nbt_registry import effective
from nbt_assembly import Volume
from nbt_snbt import save_snbt,read_snbt
from nbt_collision import collision_cells,check_routes

LIBRARY=ROOT.parent/'NBTCreator-AssetLibrary'


class OrnateLibrary(unittest.TestCase):
    def test_actual_registry_download_component_import_and_fully_offline_reads(self):
        from nbt_asset_libraries import dispatch as libraries
        from nbt_structure_agent import dispatch
        manifest=json.loads((LIBRARY/'library.json').read_text(encoding='utf8'))
        allowed={'/library.json','/registry.json'}|{'/'+r['path'] for r in manifest['assets']};requested=[]
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(LIBRARY),**kwargs)
            def log_message(self,*args):pass
            def do_GET(self):
                requested.append(self.path)
                if self.path not in allowed:self.send_error(404);return
                super().do_GET()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);worker=threading.Thread(target=lambda:server.serve_forever(poll_interval=.05),daemon=True);worker.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                workspace=Path(tmp);url=f'http://127.0.0.1:{server.server_port}/registry.json'
                discovered=libraries(workspace,'discover',dict(source=url))['items'][0]
                added=libraries(workspace,'add',dict(source=discovered['source'],manifest_sha256=discovered['manifest_sha256']))
                source_id=added['source']['id'];listing=libraries(workspace,'list',{})
                self.assertEqual(listing['errors'],[]);self.assertEqual(len(listing['items']),len(manifest['assets']))
                self.assertTrue(all(row['source_id']==source_id for row in listing['items']))
                self.assertTrue(allowed.issubset(set(requested)))
                for row in listing['items']:
                    if row['type']=='parametric_recipe':
                        compiled=dispatch(workspace,'parametric_compile',row['arguments'])
                        self.assertFalse(compiled['model_modified'])
                chosen=next(row for row in listing['items'] if row['asset_id']=='ornate-window-gothic-gilded-component')
                request=dict(id=chosen['id'],sha256=chosen['sha256'])
                imported=libraries(workspace,'import',request)
                self.assertFalse(imported['nbt_exported']);self.assertFalse(imported['approval_created'])
                self.assertEqual(imported['item']['review_status'],'pending_visual_review')
                server.shutdown();server.server_close();worker.join(timeout=2)
                offline=libraries(workspace,'list',{})
                self.assertEqual(offline['errors'],[]);self.assertEqual(len(offline['items']),len(manifest['assets']))
                self.assertTrue(all(row['source_id']==source_id for row in offline['items']))
                self.assertEqual(libraries(workspace,'read',request)['asset']['sha256'],request['sha256'])
        finally:
            server.shutdown();server.server_close();worker.join(timeout=2)

    def test_collection_covers_every_modular_kind_within_protocol_budget(self):
        from nbt_building.parametric import KINDS
        manifest=json.loads((LIBRARY/'library.json').read_text(encoding='utf8'))
        rows=[r for r in manifest['assets'] if r['id'].startswith('ornate-')]
        coverage={tag for row in rows for tag in row.get('tags',[]) if tag in KINDS}
        self.assertEqual(coverage,set(KINDS));self.assertGreaterEqual(len(rows),56)
        self.assertLessEqual(sum(row['bytes'] for row in manifest['assets']),32*1024*1024)

    def test_lantern_and_leaf_invariants_are_preserved(self):
        for value in ('lantern[hanging=true,waterlogged=false]',
                      'soul_lantern[hanging=false,waterlogged=false]',
                      'flowering_azalea_leaves[persistent=true,distance=2,waterlogged=false]'):
            expected=effective(value)[1]
            for turns in range(4):
                self.assertEqual(effective(transformed_state(value,turns,'x'))[1],expected)
        with self.assertRaises(ValueError):transformed_state('oak_door[facing=north]',1,None)

    def test_every_baked_component_transforms_without_mutating_library_data(self):
        manifest=json.loads((LIBRARY/'library.json').read_text(encoding='utf8'))
        rows=[r for r in manifest['assets'] if r['type']=='component']
        self.assertGreaterEqual(len(rows),45)
        for row in rows:
            raw=(LIBRARY/row['path']).read_bytes();data=validate(json.loads(raw));original=copy.deepcopy(data)
            plan=placement(data,[64,data['anchor'][1]+1,64],[128,80,128],1,'x')
            count=sum(len(op['voxels']) for op in plan['operations'])
            self.assertEqual(count,len(data['blocks']),row['id']);self.assertEqual(data,original)
            self.assertEqual((LIBRARY/row['path']).read_bytes(),raw)

    def test_baked_windows_match_the_current_parametric_engine(self):
        from nbt_structure_agent import dispatch
        manifest=json.loads((LIBRARY/'library.json').read_text(encoding='utf8'));rows={r['id']:r for r in manifest['assets']}
        for row in rows.values():
            if row['type']!='parametric_recipe' or not row['id'].startswith('ornate-window-'):continue
            recipe=json.loads((LIBRARY/row['path']).read_text(encoding='utf8'))
            result=dispatch(LIBRARY,'parametric_compile',recipe['arguments'])
            baked=validate(json.loads((LIBRARY/rows[row['id']+'-component']['path']).read_text(encoding='utf8')))
            self.assertEqual(result['content_sha256'],baked['content_sha256'],row['id'])

    def test_representative_assets_write_and_read_the_actual_transformed_states(self):
        examples=['ornate-window-gothic-gilded-component','ornate-plant-vessel','ornate-lantern-chandelier',
                  'ornate-table-inlaid','ornate-floor-star-eight','ornate-ceiling-coffer-rosette']
        manifest=json.loads((LIBRARY/'library.json').read_text(encoding='utf8'));rows={r['id']:r for r in manifest['assets']}
        with tempfile.TemporaryDirectory() as tmp:
            for identifier in examples:
                data=validate(json.loads((LIBRARY/rows[identifier]['path']).read_text(encoding='utf8')))
                plan=placement(data,[48,data['anchor'][1]+1,48],[96,80,96],3,'z');model=Volume((96,80,96))
                for op in plan['operations']:
                    edits,_=paste_plan(model,op,set())
                    for p,value in edits:model.put(p,value)
                file=Path(tmp)/(identifier+'.snbt');save_snbt(file,model,set());disk,_=read_snbt(file)
                self.assertEqual(model.blocks,disk.blocks,identifier)

    def test_mosaic_floors_are_flat_full_support_with_real_walking_clearance(self):
        manifest=json.loads((LIBRARY/'library.json').read_text(encoding='utf8'))
        rows=[r for r in manifest['assets'] if r['id'].startswith('ornate-floor-')]
        self.assertGreaterEqual(len(rows),4)
        for row in rows:
            data=validate(json.loads((LIBRARY/row['path']).read_text(encoding='utf8')));w,_,d=data['size']
            model=Volume((w,4,d));self.assertEqual(len(data['blocks']),w*d)
            for x,y,z,index,_ in data['blocks']:
                value=data['palette'][index];cells,reason=collision_cells(value)
                self.assertEqual(y,0);self.assertIsNone(reason);self.assertEqual(len(cells),8);model.put((x,y,z),value)
            route=check_routes(model,[.5,1,.5],[[w-.5,1,d-.5]],max_poses=20000)
            self.assertTrue(route['passed'],row['id'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--library',type=Path,default=LIBRARY);args,remaining=parser.parse_known_args()
    LIBRARY=args.library.resolve();unittest.main(argv=[sys.argv[0],*remaining],verbosity=2)
