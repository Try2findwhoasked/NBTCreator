"""Disjoint sparse wall/interior layers preserve states without clearing peers."""
import argparse,json
from pathlib import Path
from nbt_model import Model
from nbt_wall_layers import export_wall_layers,read_sparse,WallMask
from generate_sealed_models import read_nbt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path.cwd()/'nbt_models/_tests/wall_layer_validation')
    out=parser.parse_args().output.resolve()
    m=Model((8,8,8));m.box((0,0,0),(7,7,7),'stone_bricks');m.box((1,1,1),(6,6,6),'air')
    mask={(x,y,z) for x in range(8) for y in range(1,7) for z in range(8) if x in (0,7) or z in (0,7)}
    # Same stone material in a free-standing interior object must stay interior.
    m.put((3,1,3),'stone_bricks')
    m.put((4,1,3),'stone_brick_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]')
    m.put((0,2,3),'air');mask.add((2,2,2))
    original=dict(m.blocks)
    report=export_wall_layers(m,mask,out,'fixture')
    walls=read_sparse(out/'fixture_walls.nbt');interior=read_sparse(out/'fixture_interior.nbt')
    checks=dict(no_overlap=not bool(walls.blocks.keys()&interior.blocks.keys()),
                exact_reconstruction={**walls.blocks,**interior.blocks}==original,
                omitted_door=(0,2,3) not in walls.blocks,
                same_material_interior=(3,1,3) in interior.blocks and (3,1,3) not in walls.blocks,
                state_properties_preserved=interior.get((4,1,3))==m.get((4,1,3)),
                roof_floor_not_wall=(0,0,0) not in walls.blocks and (0,7,0) not in walls.blocks,
                source_not_mutated=m.blocks==original)
    for label in ['walls','interior']:
        raw=read_nbt(out/f'fixture_{label}.nbt')
        checks[label+'_no_air_erasers']=all(raw['palette'][b['state']]['Name']!='minecraft:air' for b in raw['blocks'])
        checks[label+'_sparse']=len(raw['blocks'])<8**3
    try:export_wall_layers(m,[(99,1,1)],out,'invalid')
    except AssertionError:checks['out_of_bounds_mask_rejected']=True
    else:checks['out_of_bounds_mask_rejected']=False
    tracked=Model((8,8,8));tracked.box((0,0,0),(7,7,7),'stone_bricks')
    guard=WallMask(tracked,[(0,2,3),(0,3,3),(0,4,3),(0,5,3)])
    tracked.put((0,2,3),'stone_bricks')  # Same material, now part of an overlay.
    tracked.box((0,3,3),(0,3,3),'sea_lantern')
    tracked.put((0,4,3),'air')
    guard.mark([(0,3,3)])  # An explicitly reclassified wall lamp is intentional.
    final=guard.finish()
    checks['same_material_postwrite_reclassified']=(0,2,3) not in final
    checks['box_writes_tracked_and_explicit_mark_kept']=(0,3,3) in final
    checks['door_air_removed_from_tracked_wall']=(0,4,3) not in final
    checks['untouched_wall_retained']=(0,5,3) in final
    cave=Model((8,8,8));cave.box((0,0,0),(7,7,7),'stone')
    owner=WallMask(cave,cave.blocks)
    cave.box((2,2,2),(5,5,5),'air')
    cave.put((1,3,3),'stone')  # Authored later object, even with same geology material.
    skin=owner.finish_vertical_skin()
    checks['vertical_cave_skin_detected']=(1,4,3) in skin
    checks['skin_excludes_floor_roof']=all(2<=p[1]<6 for p in skin)
    checks['same_material_later_object_not_skin']=(1,3,3) not in skin
    assert all(checks.values()),checks
    (out/'results.json').write_text(json.dumps(dict(passed=True,checks=checks,layers=report),indent=2)+'\n')
    print(json.dumps(dict(passed=True,checks=len(checks),report=str(out/'results.json'))))


if __name__=='__main__':main()
