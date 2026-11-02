"""Inspect actual NBT void outlines at multiple heights and vertical planes.

These are block-index material slices, not pathfinding or collision maps.
"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from nbt_model import load, AIR_NAMES
from nbt_preview import material_color


def indices(value):
    try:
        return [int(n) for n in value.split(',') if n.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError('Use comma-separated integer layer indices') from exc


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nbt',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--ys',type=indices,default=[])
    parser.add_argument('--xs',type=indices,default=[])
    parser.add_argument('--zs',type=indices,default=[])
    parser.add_argument('--scale',type=int,default=8)
    args=parser.parse_args()
    planes=[(axis,n) for axis,nums in [('y',args.ys),('x',args.xs),('z',args.zs)] for n in nums]
    if not planes or not 2<=args.scale<=24:
        parser.error('Select at least one plane; scale must be 2..24')
    source=args.nbt.read_bytes();model=load(args.nbt)
    if args.nbt.read_bytes()!=source:parser.error('NBT changed during load')
    for axis,n in planes:
        if not 0<=n<model.size['xyz'.index(axis)]:parser.error(f'Out of bounds: {axis}={n}')
    scale=args.scale;side=max(model.size)*scale
    tilew,tileh=side+40,side+76
    cols=min(3,len(planes));rows=(len(planes)+cols-1)//cols
    image=Image.new('RGB',(cols*tilew,rows*tileh+60),'#111b26');draw=ImageDraw.Draw(image)
    font=ImageFont.load_default(size=17)
    palette={v:tuple(int(c) for c in material_color(v.partition('[')[0])) for v in set(model.blocks.values())}
    for i,(axis,n) in enumerate(planes):
        ox,oy=(i%cols)*tilew+20,(i//cols)*tileh+40
        # XZ plans: north at top. Vertical sections: up at top.
        horizontal=0 if axis in ('y','z') else 2
        vertical=2 if axis=='y' else 1
        draw.text((ox,oy-27),f'{axis.upper()}={n} | '+('north top, east right' if axis=='y' else 'Y up'),font=font,fill='#eff6fa')
        for u in range(model.size[horizontal]):
            for v in range(model.size[vertical]):
                p=[0,0,0];p['xyz'.index(axis)]=n;p[horizontal]=u;p[vertical]=v
                state=model.get(tuple(p))
                color=(20,44,66) if state in AIR_NAMES else palette[state]
                row=v if axis=='y' else model.size[vertical]-1-v
                x,y=ox+u*scale,oy+row*scale
                draw.rectangle((x,y,x+scale-1,y+scale-1),fill=color)
        draw.text((ox,oy+side+10),'dark blue = air | colored = saved block',font=font,fill='#acc3d4')
    draw.text((20,rows*tileh+18),'NBT block slices | no collision or walkability claims',font=font,fill='#acc3d4')
    args.output.parent.mkdir(parents=True,exist_ok=True);image.save(args.output)
    metadata=dict(source_nbt=str(args.nbt.resolve()),source_nbt_sha256=hashlib.sha256(source).hexdigest(),
                  size=list(model.size),planes=[dict(axis=a,block_index=n) for a,n in planes],
                  description='Actual block states; slabs/stairs colored by state, not sub-block air. No collision or route certification.')
    Path(str(args.output)+'.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(image=str(args.output.resolve()),planes=len(planes))))


if __name__=='__main__':main()
