"""Library discovery, real rail geometry, host policies and portable recipes."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_structure_agent import dispatch, build
from nbt_object_library import library
from nbt_components import placement, paste_plan
from nbt_assembly import Volume
from nbt_snbt import save_snbt, read_snbt


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
                    material='iron_block', cap_material='gold_block', **rail)))

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

    def test_four_stair_shapes_keep_clear_width_and_connected_caps_on_both_sides(self):
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
                    for x, y, z in rail_bases:
                        self.assertEqual(voxels[(x, y+2, z)], 'minecraft:gold_block')
                    # Only the top band, excluding the decorative bottom rail.
                    top_levels = {(x, z): y+2 for x, y, z in rail_bases}
                    caps = set()
                    for (x, z), top in top_levels.items():
                        low = min([top, *[top_levels[q] for q in ((x-1,z),(x+1,z),(x,z-1),(x,z+1)) if q in top_levels]])
                        for y in range(low, top+1):
                            self.assertEqual(voxels[(x,y,z)], 'minecraft:gold_block')
                            caps.add((x,y,z))
                    self.assertEqual(len(components(caps)), 2 if side == 'both' else 1)
                    by_side[side] = {(x,z) for x, _, z in rail_bases}
                    self.assertEqual(len(receipt['entrance']), 3)
                    self.assertEqual(len(receipt['exit']), 3)
            self.assertFalse(by_side['left'] & by_side['right'])
            self.assertEqual(by_side['both'], by_side['left'] | by_side['right'])

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
                self.assertEqual(len(components(voxels)), 1)

    def test_new_rails_reject_invalid_state_size_budget_and_irrelevant_fields(self):
        args = self.stair('straight')
        invalid = [dict(args, size=[3,3,3]), dict(args, max_changed_blocks=1)]
        for key, value in [('rail',True), ('border',1), ('tread','stone'),
                           ('tread','oak_stairs[half=top]'), ('tread','oak_stairs[facing=north]'),
                           ('tread','oak_stairs[shape=inner_left]'), ('tread','oak_stairs[waterlogged=true]'),
                           ('handrail',{}), ('handrail',dict(side='unknown')),
                           ('handrail',dict(height=1)), ('handrail',dict(material='oak_fence')),
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
                if kind in ('arch','frame'):
                    w,h,d = compiled['spec']['size']
                    self.assertNotIn((2,1,d//2), voxels)
                if kind == 'railing':
                    self.assertEqual({i['id'] for i in compiled['interfaces']}, {'start','end'})
                for interface in compiled['interfaces']:
                    points=product(*(range(a,b+1) for a,b in zip(interface['lo'],interface['hi'])))
                    self.assertTrue(all(p in voxels for p in points),row['id'])

    def test_rotation_state_roundtrip_and_host_protection_are_shared(self):
        compiled = self.call(**self.stair('spiral'))
        data = build(self.workspace, compiled['spec'])
        for turns in range(4):
            placed = placement(data, [25,0,25], [64,24,64], turns)
            volume = Volume((64,24,64))
            edits, _ = paste_plan(volume, placed['operations'][0], set())
            for p,value in edits:volume.put(p,value)
            self.assertEqual(len(volume.blocks), compiled['block_count'])
            path = self.workspace/f'rotated-{turns}.snbt'
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
