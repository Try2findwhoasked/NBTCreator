"""NBT IO and seal-then-open regression probes; output only to --output."""
import argparse
import json
from pathlib import Path
from nbt_model import Model, load, ports


def closed():
    m=Model((48,16,48))
    m.box((0,0,0),(47,15,47),'stone_bricks')
    m.box((1,2,1),(46,13,46),'air')
    return m


def rejects(action):
    try:
        action()
    except AssertionError:
        return True
    return False


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path.cwd()/'nbt_models/_tests/toolkit_validation/io')
    out=parser.parse_args().output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    results={}
    m=closed()
    results['fractional_voxel_write_rejected']=rejects(lambda:m.put((1.5,3,3),'stone'))
    results['fractional_seal_probe_rejected']=rejects(lambda:m.check_sealed([(24.5,3,24.5)]))
    results['carve_before_seal_rejected']=rejects(lambda:m.open_ports(ports(['west'],2),2))
    m.put((12,2,12),'stone_brick_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]')
    m.put((14,2,12),'stone_brick_slab[type=top,waterlogged=false]')
    m.check_sealed([(24,2,24)])
    results['design_edit_after_seal_rejected']=rejects(lambda:m.put((4,3,4),'gold_block'))
    m.open_ports(ports(['east','west'],2),2)
    report=m.save(out/'stateful.nbt')
    recovered=load(out/'stateful.nbt')
    results['stateful_palette_roundtrip']=recovered.blocks==m.blocks
    results['two_standard_port_volumes']=len(m.opened)==60 and all(recovered.get(p)=='minecraft:air' for p in m.opened)
    m.put((5,3,5),'gold_block')
    results['post_validation_edit_blocks_export']=rejects(lambda:m.save(out/'invalid.nbt'))
    # Each outside direction must be floodable, including flush bounds and roof.
    leak_paths=[((0,3,3),(1,3,3)),((46,3,3),(47,3,3)),
                ((3,0,3),(3,2,3)),((3,13,3),(3,15,3)),
                ((3,3,0),(3,3,1)),((3,3,46),(3,3,47))]
    for n,(lo,hi) in enumerate(leak_paths):
        bad=closed()
        bad.box(lo,hi,'air')
        results[f'leak_face_{n}_rejected']=rejects(lambda:bad.check_sealed([(24,2,24)]))
    m=closed()
    m.check_sealed([(24,2,24)])
    malformed=ports(['west'],2)
    malformed[0]['max'][2]=25
    results['five_wide_port_rejected']=rejects(lambda:m.open_ports(malformed,2))
    assert all(results.values()),results
    (out/'results.json').write_text(json.dumps(dict(passed=True,results=results,fixture=report),indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(passed=True,checks=len(results),report=str(out/'results.json'))))


if __name__=='__main__':
    main()
