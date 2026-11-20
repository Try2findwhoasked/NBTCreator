"""Verified fine blocks are conservative obstacles, never synthetic floor support."""
from itertools import product
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_collision import BOUNDED_OBSTACLES,TALL_OBSTACLES,_Space,bounded_obstacle,check_routes,collision_cells
from nbt_model import Model
from nbt_registry import registry


class FineEnvelopes(unittest.TestCase):
    def test_verified_flowers_are_passable_and_never_provide_support(self):
        for value in ('allium', 'lilac[half=lower]', 'lilac[half=upper]'):
            self.assertEqual(collision_cells(value), ((), None))
            model=Model((5,5,5));model.box((0,0,0),(4,0,4),'dirt')
            model.put((2,1,2),value)
            self.assertTrue(check_routes(model,(1.5,1,2.5),[(3.5,1,2.5)],conservative_obstacles=False)['passed'])
            empty=Model((3,4,3));empty.put((1,0,1),value)
            self.assertFalse(_Space(empty).supported((1.5,1,1.5)))

    def test_all_whitelisted_state_combinations_are_valid_and_have_no_exact_collision_claim(self):
        for short in sorted(BOUNDED_OBSTACLES|TALL_OBSTACLES):
            entry=registry()['blocks']['minecraft:'+short];keys=sorted(entry['properties'])
            for values in product(*(entry['properties'][key] for key in keys)):
                value=short+('['+','.join(k+'='+v for k,v in zip(keys,values))+']' if keys else '')
                self.assertTrue(bounded_obstacle(value),value)
                self.assertIsNotNone(collision_cells(value)[1],value)
        for value in ('anvil','oak_door','example:stone_brick_wall','chain[axis=invalid]'):
            self.assertFalse(bounded_obstacle(value),value)

    def test_walls_and_all_fence_materials_keep_the_full_one_and_half_block_obstacle(self):
        for value in sorted(TALL_OBSTACLES):
            with self.subTest(value=value):
                model=Model((5,5,5));model.put((2,1,2),value);space=_Space(model)
                self.assertFalse(space.clear_box((2.3,2.1,2.3),(2.7,2.4,2.7)))
                self.assertTrue(space.clear_box((2.3,2.6,2.3),(2.7,2.8,2.7)))
                self.assertFalse(space.supported((2.5,2.5,2.5)))

    def test_routes_can_avoid_fine_details_without_hiding_collision_scope(self):
        model=Model((12,8,10));model.box((0,0,0),(11,0,9),'stone')
        values=('stone_brick_wall','oak_fence','white_stained_glass_pane','spruce_trapdoor',
                'end_rod','chain','snow[layers=8]','white_carpet','stone_pressure_plate')
        for x,value in enumerate(values,1):model.put((x,1,1),value)
        report=check_routes(model,(1.5,1,5.5),[(10.5,1,5.5)])
        self.assertTrue(report['passed'])
        self.assertFalse(report['exact_geometry_supported'])
        self.assertTrue(report['route_geometry_supported'])
        self.assertFalse(report['support_from_proxies_allowed'])
        strict=check_routes(model,(1.5,1,5.5),[(10.5,1,5.5)],conservative_obstacles=False)
        self.assertFalse(strict['passed'])
        self.assertTrue(strict['unknown_shapes'])

    def test_every_unit_proxy_cannot_hold_a_player_over_a_missing_floor(self):
        for value in sorted(BOUNDED_OBSTACLES):
            model=Model((3,4,3));model.put((1,0,1),value)
            self.assertFalse(_Space(model).supported((1.5,1,1.5)),value)

    def test_dry_walking_distinguishes_water_from_unsupported_shapes(self):
        model=Model((8,5,6));model.box((0,0,0),(7,0,5),'stone')
        model.box((1,1,1),(6,1,1),'water[level=0]')
        model.put((1,1,2),'water[level=7]')
        start=(1.5,1,4.5)
        targets={'dry':(6.5,1,4.5),'water':(3.5,1,1.5),'above_water':(3.5,2,1.5)}
        dry=check_routes(model,start,{'dry':targets['dry']})
        self.assertTrue(dry['passed'])
        self.assertFalse(dry['unknown_shapes'])
        self.assertEqual({row['state'] for row in dry['conservative_obstacles']},
                         {'minecraft:water[level=0]','minecraft:water[level=7]'})
        excluded=check_routes(model,start,targets)
        self.assertFalse(excluded['passed'])
        self.assertFalse(excluded['targets'][1]['standing'])
        self.assertFalse(excluded['targets'][2]['standing'])
        strict=check_routes(model,start,{'dry':targets['dry']},conservative_obstacles=False)
        self.assertFalse(strict['passed'])
        self.assertTrue(strict['unknown_shapes'])


if __name__=='__main__':unittest.main(verbosity=2)
