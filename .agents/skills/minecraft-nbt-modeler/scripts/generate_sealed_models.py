"""Generate original sealed Java 1.20.1 NBT architecture and cutaway previews.

Run with Python and Pillow: python <skill-dir>/scripts/generate_sealed_models.py
No reference assets, world edits or active content registration.
"""
from collections import deque
import json
import math
from pathlib import Path

from generate_room_models import COLORS, export_nbt

OUT = Path(__file__).resolve().parents[1] / 'build/sealed_models'
COLORS.update(tinted_glass=(78, 130, 155), gold_block=(220, 173, 58),
              quartz_block=(224, 220, 209), dark_prismarine=(44, 97, 92))
SPECS = {
    'domed_sanctuary': (48, 40, 48),
    'terraced_crypt': (48, 40, 48),
    'astral_tower': (40, 48, 40),
}


def generate(name, size):
    w,h,d = size
    cx,cz = (w-1)/2,(d-1)/2

    def inside(x,y,z):
        r = math.hypot(x-cx,z-cz)
        if name == 'domed_sanctuary':
            return 2 <= y <= 36 and r <= (21 if y <= 14 else 21*math.sqrt(max(0,1-((y-14)/23)**2)))
        if name == 'terraced_crypt':
            radius = 22 - max(0,(y-7)//5)*3
            return 2 <= y <= 36 and max(abs(x-cx),abs(z-cz)) <= radius
        radius = 16 if y < 9 else 13 if y < 31 else 16 if y < 39 else max(2,16-(y-38)*2)
        return 1 <= y <= 45 and r <= radius

    region = {(x,y,z) for x in range(w) for y in range(h) for z in range(d) if inside(x,y,z)}
    directions = ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))
    shell = {p for p in region if any(tuple(p[i]+v[i] for i in range(3)) not in region for v in directions)}
    blocks = {(x,y,z):'air' for y in range(h) for z in range(d) for x in range(w)}
    for x,y,z in shell:
        mat = 'deepslate_tiles'
        if y % 6 == 0:
            mat = 'waxed_cut_copper'
        if name == 'domed_sanctuary':
            mat = 'quartz_block' if y < 15 else 'dark_prismarine'
            if y >= 16 and (x % 7 == 0 or z % 7 == 0):
                mat = 'tinted_glass'
            if y in (3,13,14):
                mat = 'waxed_cut_copper'
        elif name == 'terraced_crypt':
            mat = 'stone_bricks' if y % 5 else 'chiseled_stone_bricks'
            if (x+z)%9 == 0:
                mat = 'mossy_stone_bricks'
        elif 9 < y < 39 and (x%8 in (3,4) or z%8 in (3,4)) and y%10 in range(3,8):
            mat = 'tinted_glass'
        blocks[x,y,z] = mat

    def put(x,y,z,m):
        # Interior decoration can never remove or breach the exterior envelope.
        p=(x,y,z)
        if p in region and p not in shell:
            blocks[p]=m

    if name == 'domed_sanctuary':
        for x,y,z in region-shell:
            r = math.hypot(x-cx,z-cz)
            if y==3:
                put(x,y,z,'waxed_cut_copper' if 11<r<13 or r<4 else 'polished_deepslate')
            for px,pz in ((12,12),(35,12),(12,35),(35,35)):
                if abs(x-px)<=1 and abs(z-pz)<=1 and 4<=y<=14:
                    put(x,y,z,'sea_lantern' if y==14 else 'chiseled_stone_bricks')
            if 18<=y<=21 and 12<r<14:
                put(x,y,z,'waxed_cut_copper')
            if y in (4,5,6) and r <= 5-(y-4):
                put(x,y,z,'quartz_block')
    elif name == 'terraced_crypt':
        for x,y,z in region-shell:
            r=max(abs(x-cx),abs(z-cz))
            if y==3:
                put(x,y,z,'polished_deepslate')
            if y in (10,17,24) and r>=7 and not (21<=x<=26):
                put(x,y,z,'stone_bricks')
            if x in (10,11,36,37) and z in (10,11,36,37) and y<=22:
                put(x,y,z,'chiseled_stone_bricks')
            if y in (8,15,22,29) and r<3:
                put(x,y,z,'sea_lantern')
        # Three successive stair flights through the central floor opening.
        for start_y,reverse in ((3,False),(10,True),(17,False)):
            for step in range(8):
                z=19+step if not reverse else 26-step
                for x in range(22,26):
                    put(x,start_y+step,z,'waxed_cut_copper')
                    for dy in (1,2,3):
                        put(x,start_y+step+dy,z,'air')
    else:
        for x,y,z in region-shell:
            r=math.hypot(x-cx,z-cz)
            if y in (2,12,22,32) and r>5:
                put(x,y,z,'polished_deepslate' if y%20==2 else 'quartz_block')
            if r<2 and y<37:
                put(x,y,z,'sea_lantern' if y%5==0 else 'waxed_cut_copper')
            if y==39 and 7<r<10:
                put(x,y,z,'gold_block')
        # Broad helical stepped ribbon, rising through the open atrium.
        for y in range(3,34):
            angle=(y-3)*math.pi/10
            for x in range(w):
                for z in range(d):
                    r=math.hypot(x-cx,z-cz)
                    a=math.atan2(z-cz,x-cx)
                    delta=abs((a-angle+math.pi)%(2*math.pi)-math.pi)
                    if 6<=r<=10 and delta<.27:
                        put(x,y,z,'waxed_cut_copper')
                        for dy in (1,2,3):
                            put(x,y+dy,z,'air')
    return blocks, region, shell


def validate(blocks,size,region,shell):
    w,h,d=size
    assert len(blocks)==w*h*d
    assert all(blocks[p]!='air' for p in shell)
    # Flood fill all exterior air from the complete six-sided bounding surface.
    seeds={p for p,m in blocks.items() if m=='air' and
           (p[0] in (0,w-1) or p[1] in (0,h-1) or p[2] in (0,d-1))}
    visited=set(seeds)
    q=deque(seeds)
    while q:
        x,y,z=q.popleft()
        for p in ((x+1,y,z),(x-1,y,z),(x,y+1,z),(x,y-1,z),(x,y,z+1),(x,y,z-1)):
            if blocks.get(p) == 'air' and p not in visited:
                visited.add(p)
                q.append(p)
    interior={p for p in region if blocks[p]=='air'}
    assert interior and not interior.intersection(visited), 'Exterior leak'
    return dict(size=list(size), local_y=[0,h-1], occupied_y=[min(p[1] for p in region),max(p[1] for p in region)],
                sealed_air_blocks=len(interior), exterior_leaks=0, shell_blocks=len(shell),
                explicit_volume=len(blocks), runtime_verified=False)


def render(name,blocks,size,cutaway):
    from PIL import Image, ImageDraw
    w,h,d=size
    image=Image.new('RGB',(900,900),'#101923')
    draw=ImageDraw.Draw(image)
    def project(x,y,z):
        return (450+(x-z)*7,350+(x+z)*3.5-y*6)
    visible={p:m for p,m in blocks.items() if m!='air' and
             (not cutaway or p[0]+p[2] < w-2)}
    for (x,y,z),m in sorted(visible.items(),key=lambda v:(v[0][0]+v[0][2],v[0][1])):
        for delta,verts,shade in (
            ((1,0,0),[(1,0,0),(1,0,1),(1,1,1),(1,1,0)],.65),
            ((0,0,1),[(0,0,1),(1,0,1),(1,1,1),(0,1,1)],.82),
            ((0,1,0),[(0,1,0),(1,1,0),(1,1,1),(0,1,1)],1.12)):
            if (x+delta[0],y+delta[1],z+delta[2]) not in visible:
                draw.polygon([project(x+a,y+b,z+c) for a,b,c in verts],
                             fill=tuple(min(255,int(c*shade)) for c in COLORS[m]))
    draw.text((30,28),name.replace('_',' ').upper(),fill='white',font_size=25)
    draw.text((30,835),f'{w} x {h} x {d} | LOCAL Y 0..{h-1} | '+('CUTAWAY' if cutaway else 'SEALED EXTERIOR'),fill='#bacbd5',font_size=19)
    return image


def main():
    from PIL import Image
    OUT.mkdir(parents=True,exist_ok=True)
    report={}
    sheet=Image.new('RGB',(1800,2700))
    for index,(name,size) in enumerate(SPECS.items()):
        blocks,region,shell=generate(name,size)
        report[name]=validate(blocks,size,region,shell)
        path=OUT/(name+'.nbt')
        export_nbt(path,blocks,size)
        # Independently decode written NBT, then validate the actual saved volume.
        decoded=read_nbt(path)
        assert decoded['DataVersion']==3465
        assert tuple(decoded['size'])==size and decoded['entities']==[]
        palette=[p['Name'].removeprefix('minecraft:') for p in decoded['palette']]
        saved={tuple(b['pos']):palette[b['state']] for b in decoded['blocks']}
        assert len(decoded['blocks'])==len(saved)==math.prod(size) and saved==blocks
        validate(saved,size,region,shell)
        for col,cut in enumerate((False,True)):
            img=render(name,blocks,size,cut)
            img.save(OUT/(name+('_cutaway' if cut else '_exterior')+'.png'))
            sheet.paste(img,(col*900,index*900))
    sheet.save(OUT/'preview.png')
    (OUT/'coordinates.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,indent=2))


def read_nbt(path):
    """Minimal independent reader for the standard tags emitted by this exporter."""
    import gzip
    import io
    import struct
    f=io.BytesIO(gzip.decompress(path.read_bytes()))
    def number(fmt):
        return struct.unpack(fmt,f.read(struct.calcsize(fmt)))[0]
    def string():
        return f.read(number('>H')).decode('utf8')
    def payload(t):
        if t==3:
            return number('>i')
        if t==8:
            return string()
        if t==9:
            element=number('>B')
            return [payload(element) for _ in range(number('>i'))]
        if t==10:
            result={}
            while True:
                kind=number('>B')
                if kind==0:
                    return result
                name=string()
                result[name]=payload(kind)
        raise ValueError(t)
    assert number('>B')==10
    string()
    result=payload(10)
    assert f.read()==b''
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path.cwd()/'build/sealed_models')
    args=parser.parse_args()
    OUT=args.output.resolve()
    main()
