"""Standalone opening API: custom placement/size, seal binding, atomic refusal and wall ownership."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_model import Model, load
from nbt_openings import open_declared_openings


def room(thick=False, blocked=False, missing_floor=False):
    model=Model((16,12,16))
    model.box((1,1,0),(14,1,14),'stone_bricks')
    model.box((2,1,2),(13,10,13),'stone_bricks')
    model.box((3,2,3),(12,9,12),'air')
    model.put((6,4,2),'calcite')
    if thick:model.box((3,2,3),(12,9,3),'stone_bricks')
    if blocked:model.put((7,3,3),'stone')
    if missing_floor:model.put((7,1,1),'air')
    walls={p for p in model.blocks if p[0] in (2,13) or p[2] in ((2,3,13) if thick else (2,13))}
    model.check_sealed([(7,4,7)])
    return model,walls


ENTRY=dict(id='entry',lo=[6,2,2],hi=[8,5,2],facing='north')


class Openings(unittest.TestCase):
    def test_custom_internal_aperture_roundtrip_and_reclose_original_states(self):
        model,walls=room();original=dict(model.blocks);old_walls=set(walls);before=model.fingerprint()
        report=open_declared_openings(model,[ENTRY],walls)
        self.assertEqual(len(report['changes']),12)
        changed={p for p in original if original[p]!=model.get(p)}
        self.assertEqual(changed,{tuple(c['pos']) for c in report['changes']})
        self.assertEqual(walls,old_walls-changed)
        self.assertEqual(report['validation']['routes'],'not_checked')
        self.assertEqual(report['before_geometry_sha256'],before)
        with tempfile.TemporaryDirectory() as temporary:
            file=Path(temporary)/'standalone.nbt';model.save(file)
            self.assertEqual(load(file).blocks,model.blocks)
        reclosed=copy.deepcopy(model);reclosed.begin_redesign()
        for change in report['changes']:reclosed.put(change['pos'],change['before'])
        self.assertEqual(reclosed.fingerprint(),before)
        self.assertTrue(reclosed.check_sealed([(7,4,7)])['passed'])

    def test_thick_wall_and_four_facings(self):
        model,walls=room(thick=True)
        report=open_declared_openings(model,[dict(ENTRY,hi=[8,5,3])],walls)
        self.assertEqual(len(report['changes']),24)
        for facing,lo,hi in [('south',[6,2,13],[8,5,13]),('west',[2,2,6],[2,5,8]),('east',[13,2,6],[13,5,8])]:
            model,walls=room();report=open_declared_openings(model,[dict(id=facing,lo=lo,hi=hi,facing=facing)],walls)
            self.assertEqual(len(report['changes']),12)

    def test_invalid_later_opening_never_partially_carves_or_changes_mask(self):
        model,walls=room();before=model.fingerprint();old_walls=set(walls)
        with self.assertRaisesRegex(ValueError,'bounds'):
            open_declared_openings(model,[ENTRY,dict(id='invalid',lo=[20,2,2],hi=[22,5,2],facing='north')],walls)
        self.assertEqual(model.fingerprint(),before);self.assertEqual(walls,old_walls);self.assertEqual(model.stage,'sealed')
        with self.assertRaisesRegex(ValueError,'overlap'):
            open_declared_openings(model,[ENTRY,dict(ENTRY,id='duplicate')],walls)
        self.assertEqual(model.fingerprint(),before)

    def test_missing_landings_and_blocked_throat_refuse_unchanged(self):
        for args,reason in [(dict(blocked=True),'Blocked interior'),(dict(missing_floor=True),'exterior landing')]:
            model,walls=room(**args);before=model.fingerprint();old_walls=set(walls)
            with self.assertRaisesRegex(ValueError,reason):open_declared_openings(model,[ENTRY],walls)
            self.assertEqual(model.fingerprint(),before);self.assertEqual(walls,old_walls)

    def test_unsealed_changed_or_already_opened_source_refuses(self):
        model,walls=room();model.begin_redesign()
        with self.assertRaisesRegex(ValueError,'closed master'):open_declared_openings(model,[ENTRY],walls)
        model,walls=room();model.blocks[(1,11,1)]='minecraft:stone'
        with self.assertRaisesRegex(ValueError,'closed master'):open_declared_openings(model,[ENTRY],walls)
        model,walls=room();open_declared_openings(model,[ENTRY],walls)
        with self.assertRaisesRegex(ValueError,'closed master'):open_declared_openings(model,[ENTRY],walls)

    def test_model_boundary_exterior_is_explicitly_unchecked(self):
        model=Model((8,8,8));model.box((0,0,0),(7,7,7),'stone');model.box((1,1,1),(6,6,6),'air');model.check_sealed([(4,4,4)])
        report=open_declared_openings(model,[dict(id='edge',lo=[2,1,0],hi=[3,3,0],facing='north')])
        exterior=report['openings'][0]['adjacent_faces'][1]
        self.assertFalse(exterior['checked']);self.assertEqual(exterior['reason'],'outside_model_bounds')


if __name__=='__main__':unittest.main(verbosity=2)
