"""Library discovery, real rail geometry, host policies and portable recipes."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from itertools import product
from pathlib import Path
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_structure_agent import dispatch, build
from nbt_object_library import library
from nbt_components import placement, paste_plan
from nbt_assembly import Volume
from nbt_snbt import save_snbt, read_snbt
from nbt_registry import effective
from nbt_collision import collision_cells


@lru_cache(maxsize=256)
def visible_boxes(value):
    """Static model boxes; bars/chain are visual envelopes, never support proof."""
    name,props=effective(value)
    if name=='minecraft:iron_bars':
        boxes=[(7,0,7,9,16,9)]
        for direction,(axis,sign) in {'north':(2,-1),'east':(0,1),'south':(2,1),'west':(0,-1)}.items():
            if props[direction]!='true':continue
            box=[7,0,7,9,16,9];box[axis]=8 if sign>0 else 0;box[axis+3]=16 if sign>0 else 8
            boxes.append(tuple(box))
        return tuple(boxes)
    if name=='minecraft:chain':
        axis={'x':0,'y':1,'z':2}[props['axis']];box=[6.5,6.5,6.5,9.5,9.5,9.5];box[axis]=0;box[axis+3]=16
        return (tuple(box),)
    if name.endswith('_trapdoor') and props['open']=='false':
        return ((0,0,0,16,3,16),) if props['half']=='bottom' else ((0,13,0,16,16,16),)
    if name.endswith(('_fence','_wall')):
        wall=name.endswith('_wall')
        boxes=[(4,0,4,12,16,12)] if wall else [(6,0,6,10,16,10)]
        for direction,(axis,sign) in {'north':(2,-1),'east':(0,1),'south':(2,1),'west':(0,-1)}.items():
            if props[direction] in ('false','none'):continue
            for bottom,top in ((0,14 if props[direction]=='low' else 16),) if wall else ((6,9),(12,15)):
                a,b=(5,11) if wall else (7,9)
                box=[a,bottom,a,b,top,b];box[axis]=8 if sign>0 else 0;box[axis+3]=16 if sign>0 else 8
                boxes.append(tuple(box))
        return tuple(boxes)
    if name=='minecraft:end_rod':
        from nbt_fit_shapes import end_rods
        return next(shape.boxes for shape in end_rods(name,'wall') if effective(shape.value)[1]['facing']==props['facing'])
    cells,reason=collision_cells(value)
    if reason:raise ValueError('No precise visual boxes for '+value)
    return tuple((x*8,y*8,z*8,x*8+8,y*8+8,z*8+8) for x,y,z in cells)


def visually_connected(voxels):
    remaining=set(voxels)
    first=remaining.pop();queue=[first]
    while queue:
        p=queue.pop()
        for axis in range(3):
            for sign in (-1,1):
                q=tuple(v+sign if i==axis else v for i,v in enumerate(p))
                if q not in remaining:continue
                a,b=(p,q) if sign>0 else (q,p)
                contact=any(one[axis+3]==16 and two[axis]==0 and all(min(one[i+3],two[i+3])>max(one[i],two[i]) for i in range(3) if i!=axis)
                            for one in visible_boxes(voxels[a]) for two in visible_boxes(voxels[b]))
                if contact:remaining.remove(q);queue.append(q)
    return not remaining


def box_volume(boxes):
    axes=[sorted({box[i] for box in boxes}|{box[i+3] for box in boxes}) for i in range(3)]
    intervals=[list(zip(axis,axis[1:])) for axis in axes]
    total=0
    for span in product(*intervals):
        midpoint=[(a+b)/2 for a,b in span]
        if any(all(box[i]<midpoint[i]<box[i+3] for i in range(3)) for box in boxes):
            total+=(span[0][1]-span[0][0])*(span[1][1]-span[1][0])*(span[2][1]-span[2][0])
    return total


def components(points):
    remaining = set(points)
    result = []
    while remaining:
        seed = remaining.pop()
        seen, queue = {seed}, [seed]
        while queue:
            p = queue.pop()
            for axis in range(3):
                for sign in (-1, 1):
                    q = tuple(v+sign if i == axis else v for i, v in enumerate(p))
                    if q in remaining:
                        remaining.remove(q); seen.add(q); queue.append(q)
        result.append(seen)
    return result


class ModularObjects(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.workspace = Path(directory.name)

    def call(self, tool='parametric_compile', **args):
        return dispatch(self.workspace, tool, args)

    def voxels(self, compiled):
        data = build(self.workspace, compiled['spec'])
        return {tuple(row[:3]): data['palette'][row[3]] for row in data['blocks']}

    def stair(self, profile, side='both', **rail):
        return dict(kind='stairs', size=[24, 16, 24], form=dict(profile=profile,
                    run_width=3, rise=8, landing=3, handrail=dict(side=side,
                    height=2,**rail)))

    def test_all_discoverable_recipes_are_real_deterministic_and_pure(self):
        listing = self.call('parametric_list')
        self.assertEqual(len(listing['kinds']), 16)
        rows = listing['object_library']
        self.assertEqual(rows, library())
        self.assertGreaterEqual(len(rows), 50)
        self.assertEqual(len({row['id'] for row in rows}), len(rows))
        for row in rows:
            with self.subTest(id=row['id']):
                a = self.call(**row['arguments'])
                self.assertEqual(a, self.call(**row['arguments']))
                self.assertEqual(a['block_count'], len(self.voxels(a)))
                self.assertFalse(a['model_modified'])
                self.assertFalse(a['approval_created'])
                self.assertEqual(a['verification']['routes'], 'not_checked')
        self.assertTrue(all(row['arguments']['kind'] == 'pillar' for row in self.call('parametric_list', kind='pillar')['object_library']))
        self.assertEqual(list(self.workspace.iterdir()), [])

    def test_four_stair_shapes_keep_clear_width_and_connected_guards_on_both_sides(self):
        for profile in ('straight', 'quarter_turn', 'switchback', 'spiral'):
            by_side = {}
            for side in ('left', 'right', 'both'):
                with self.subTest(profile=profile, side=side):
                    compiled = self.call(**self.stair(profile, side))
                    voxels = self.voxels(compiled)
                    receipt = compiled['construction']
                    self.assertEqual(receipt['clear_width'], 3)
                    footprint = {tuple(q) for q in receipt['footprint']}
                    rail_bases = receipt['rail_bases']
                    self.assertTrue(rail_bases)
                    self.assertTrue(all((x, z) not in footprint for x, _, z in rail_bases))
                    for x, y, z in receipt['walk_columns']:
                        self.assertIn((x, y, z), voxels)
                        self.assertTrue(all((x, y+k, z) not in voxels for k in (1, 2, 3)))
                    self.assertTrue(visually_connected(voxels))
                    self.assertEqual(receipt['rail_height'],2)
                    self.assertTrue(any('_slab[' in v or '_trapdoor[' in v for v in voxels.values()))
                    self.assertTrue(any('_fence[' in v or '_wall[' in v for v in voxels.values()))
                    self.assertEqual(len(components((x,0,z) for x,_,z in rail_bases)),2 if side=='both' else 1)
                    # Outside the walk footprint, no solid full-block retaining
                    # wall may extend from the floor to the railing anymore.
                    for (x,y,z),value in voxels.items():
                        if (x,z) not in footprint:
                            cells,reason=collision_cells(value)
                            self.assertFalse(reason is None and len(cells)==8)
                    by_side[side] = {(x,z) for x, _, z in rail_bases}
                    self.assertEqual(len(receipt['entrance']), 3)
                    self.assertEqual(len(receipt['exit']), 3)
            self.assertFalse(by_side['left'] & by_side['right'])
            self.assertEqual(by_side['both'], by_side['left'] | by_side['right'])

    def test_open_styles_have_real_voids_distinct_members_and_no_floating_details(self):
        receipts={};fractions={};fingerprints=set()
        for style in ('baluster','lattice','horizontal','panel'):
            result=self.call(**self.stair('quarter_turn',style=style))
            voxels=self.voxels(result);receipt=result['construction'];receipts[style]=receipt
            self.assertTrue(visually_connected(voxels),style)
            fingerprint=[];filled=0;available=0
            for x,base,z in receipt['rail_bases']:
                for y in range(max(1,base-1),base+1):
                    available+=4096
                    value=voxels.get((x,y,z))
                    if value is None:continue
                    filled+=box_volume(visible_boxes(value));fingerprint.append(((x,y,z),value))
            fractions[style]=filled/available
            fingerprints.add(tuple(fingerprint))
        self.assertEqual(len(fingerprints),4)
        for style in ('baluster','lattice','horizontal'):
            self.assertLess(fractions[style],.35,(style,fractions))
        self.assertGreater(fractions['panel'],.95)
        self.assertGreater(receipts['horizontal']['handrail']['horizontal_detail_blocks'],0)
        self.assertEqual(receipts['lattice']['rail_height'],2)
        # Keep all three request variants; recommend only the selected horizontal family.
        self.assertEqual({row['arguments']['form']['handrail']['style'] for row in library('stairs')},
                         {'baluster','lattice','horizontal'})
        self.assertEqual({row['arguments']['form']['handrail']['style'] for row in library('stairs') if row['status']=='recommended'},
                         {'horizontal'})

    def test_new_column_families_have_clean_shaft_bounds_and_keep_local_parts(self):
        for identifier in ('pillar-modern-flush','pillar-timber-post','pillar-classical-plain'):
            args=next(row['arguments'] for row in library('pillar') if row['id']==identifier)
            result=self.call(**args);voxels=self.voxels(result)
            self.assertTrue(visually_connected(voxels))
            self.assertEqual(set(result['parts']),{'base','shaft','capital'})
            self.assertEqual({i['id'] for i in result['interfaces']},{'base','capital_top'})
            if identifier!='pillar-classical-plain':
                w,h,d=args['size']
                self.assertEqual(set(voxels),set(product(range(w),range(h),range(d))))
            else:
                start=result['parts']['shaft']['lo'][1];end=result['parts']['shaft']['hi'][1]
                sections=[{(x,z) for x,y,z in voxels if y==level} for level in (start,(start+end)//2,end)]
                self.assertTrue(all(section==sections[0] for section in sections))
        with self.assertRaisesRegex(ValueError,'圆柱'):
            self.call(kind='pillar',size=[9,20,9],form=dict(section='round',shaft_inset=0))

    def test_each_thin_guard_is_connected_without_relying_on_the_stair_mass(self):
        for shape,style,side in product(('straight','quarter_turn','switchback','spiral'),
                                         ('baluster','lattice','horizontal'),('left','right')):
            compiled=self.call(**self.stair(shape,side,style=style));voxels=self.voxels(compiled)
            footprint={tuple(p) for p in compiled['construction']['footprint']}
            supports={(x,y-1,z) for x,y,z in compiled['construction']['handrail']['support_seats']}
            guard={p:v for p,v in voxels.items() if (p[0],p[2]) not in footprint and p not in supports}
            self.assertTrue(visually_connected(guard),(shape,style,side))

    def test_explicit_fence_and_slab_materials_and_full_block_interfaces(self):
        for style in ('baluster','lattice','horizontal'):
            compiled=self.call(**self.stair('quarter_turn',style=style,material='birch_fence',cap_material='stone_brick_slab'))
            voxels=self.voxels(compiled)
            self.assertTrue(any('birch_fence[' in value for value in voxels.values()))
            self.assertTrue(any(effective(value)[0]=='minecraft:stone_brick_slab' for value in voxels.values()))
            self.assertTrue(visually_connected(voxels),style)
        exact=self.call(kind='railing',size=[13,5,3],form=dict(profile='lattice',post_material='iron_block',rail_material='gold_block'))
        self.assertEqual({item['id'] for item in exact['interfaces']},{'start','end'})

    def test_platforms_and_entrances_stay_open_for_varied_run_widths(self):
        for profile in ('straight', 'quarter_turn', 'switchback', 'spiral'):
            for width, rise, landing in ((1,4,1), (2,5,4), (4,11,2)):
                args = self.stair(profile)
                args['size'] = [32, 20, 32]
                args['form'].update(run_width=width, rise=rise, landing=landing)
                compiled = self.call(**args)
                receipt = compiled['construction']
                voxels = self.voxels(compiled)
                for endpoint in ('entrance', 'exit'):
                    self.assertEqual(len(receipt[endpoint]), width)
                    for x,y,z in receipt[endpoint]:
                        self.assertTrue(all((x,y+k,z) not in voxels for k in (1,2)))
                self.assertTrue(visually_connected(voxels),(profile,width,rise,landing))

    def test_new_rails_reject_invalid_state_size_budget_and_irrelevant_fields(self):
        args = self.stair('straight')
        invalid = [dict(args, size=[3,3,3]), dict(args, max_changed_blocks=1)]
        for key, value in [('rail',True), ('border',1), ('tread','stone'),
                           ('tread','oak_stairs[half=top]'), ('tread','oak_stairs[facing=north]'),
                           ('tread','oak_stairs[shape=inner_left]'), ('tread','oak_stairs[waterlogged=true]'),
                           ('handrail',{}), ('handrail',dict(side='unknown')),
                           ('handrail',dict(height=1)), ('handrail',dict(material='short_grass')),
                           ('handrail',dict(material='oak_fence[waterlogged=true]')),
                           ('handrail',dict(cap_material='smooth_stone_slab[type=top]')),
                           ('handrail',dict(cap_material='air'))]:
            bad = copy.deepcopy(args); bad['form'][key] = value; invalid.append(bad)
        for bad in invalid:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.call('parametric_preview', **bad)
        self.assertEqual(list(self.workspace.iterdir()), [])

    def test_legacy_rail_true_retains_old_tread_and_side_coordinates(self):
        args = dict(kind='stairs', size=[7,8,10], form=dict(profile='straight',run_width=3,rise=4,rail=True))
        voxels = self.voxels(self.call(**args))
        self.assertNotIn('handrail', self.call(**args)['resolved_form'])
        for step in range(4):
            self.assertEqual(voxels[(0,step+1,step)], 'minecraft:polished_andesite')
            for x in range(3):
                self.assertIn('facing=south', voxels[(x,step,step)])

    def test_column_bands_preserve_section_occupancy_and_capital_regeneration(self):
        for section in ('square','cross','octagonal','bundled','round'):
            args = dict(kind='pillar', size=[9,18,9], form=dict(section=section,base_height=3,capital_height=3))
            plain = self.voxels(self.call(**args))
            args['form']['band_spacing'] = 3
            banded = self.voxels(self.call(**args))
            self.assertEqual(set(plain), set(banded))
            self.assertNotEqual(plain, banded)
        before = next(row['arguments'] for row in library() if row['id']=='pillar-bundled')
        compiled = self.call(**before)
        after = copy.deepcopy(before); after['form']['capital_material'] = 'gold_block'
        changed = self.call('parametric_regenerate', object_id='bundled', part='capital',
                            original=before,replacement=after,original_recipe_sha256=compiled['recipe_sha256'])
        cap = compiled['parts']['capital']['lo'][1]
        self.assertEqual({p:v for p,v in self.voxels(compiled).items() if p[1]<cap},
                         {p:v for p,v in self.voxels(changed).items() if p[1]<cap})

    def test_new_members_preserve_openings_and_have_connected_voxels(self):
        for kind in ('railing','beam','bracket','arch','frame','pedestal'):
            for row in library(kind):
                compiled = self.call(**row['arguments'])
                voxels = self.voxels(compiled)
                self.assertEqual(len(components(voxels)), 1, row['id'])
                from nbt_window_frames import PROFILES as WINDOW_PROFILES
                if kind in ('arch','frame') and row['arguments'].get('form',{}).get('profile') not in WINDOW_PROFILES:
                    w,h,d = compiled['spec']['size']
                    self.assertNotIn((2,1,d//2), voxels)
                if kind == 'railing':
                    if row['id']=='railing-panel':
                        self.assertEqual({i['id'] for i in compiled['interfaces']},{'start','end'})
                    else:
                        self.assertEqual(compiled['interfaces'],[])
                        self.assertEqual(compiled['interface_scope'],'fine_rail_faces_not_halfcell_certified')
                for interface in compiled['interfaces']:
                    points=product(*(range(a,b+1) for a,b in zip(interface['lo'],interface['hi'])))
                    self.assertTrue(all(p in voxels for p in points),row['id'])

    def test_rotation_state_roundtrip_and_host_protection_are_shared(self):
        compiled = self.call(**self.stair('spiral'))
        data = build(self.workspace, compiled['spec'])
        for turns,mirror in product(range(4),(None,'x','z')):
            placed = placement(data, [25,0,25], [64,24,64], turns,mirror)
            volume = Volume((64,24,64))
            edits, _ = paste_plan(volume, placed['operations'][0], set())
            for p,value in edits:volume.put(p,value)
            self.assertEqual(len(volume.blocks), compiled['block_count'])
            self.assertTrue(visually_connected(volume.blocks),(turns,mirror))
            path = self.workspace/f'rotated-{turns}-{mirror}.snbt'
            save_snbt(path,volume,set())
            disk, walls = read_snbt(path)
            self.assertEqual(disk.blocks, volume.blocks)
            self.assertEqual(walls,set())
            with self.assertRaisesRegex(ValueError,'保护'):
                paste_plan(Volume((64,24,64)), placed['operations'][0], {edits[0][0]})

    def test_object_scene_contract_and_cli_discovery_accept_new_modules(self):
        args = next(row['arguments'] for row in library('railing') if row['id']=='railing-lattice')
        graph = dict(schema_version=1,name='栏杆场景',size=[24,12,16],objects=[dict(id='rail',lo=[2,1,2],recipe=dict(tool='parametric_compile',arguments=args))])
        result = self.call('scene_compile',graph=graph)
        self.assertGreater(result['block_count'],0)
        contract = self.call('parametric_contract',constraints=dict(kind='railing',size=args['size']))
        self.assertIn('handrail',contract['response_schema']['properties']['form']['properties'])
        request = self.workspace/'list-stairs.json'
        request.write_text(json.dumps(dict(kind='stairs')),encoding='utf8')
        run = subprocess.run(['node',str(ROOT/'scripts/cli.mjs'),'--workspace',str(self.workspace),
                              'components','agent','--tool','parametric_list','--request',str(request)],
                              cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=60)
        self.assertEqual(run.returncode,0,run.stderr+run.stdout)
        self.assertEqual(len(json.loads(run.stdout)['result']['object_library']),12)


if __name__ == '__main__':
    unittest.main(verbosity=2)
