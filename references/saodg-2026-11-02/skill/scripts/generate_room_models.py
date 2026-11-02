"""Original block-aligned room models, OBJ meshes and Java 1.20.1 structures.

Run: python <skill-dir>/scripts/generate_room_models.py
Pillow is required only for the cutaway contact sheet. No reference assets used.
"""
import collections
import gzip
import json
import math
from pathlib import Path
import struct

OUT = Path(__file__).resolve().parents[1] / 'build/room_models'
SIZE = (48, 24, 48)
COLORS = dict(air=(0, 0, 0), stone_bricks=(117, 124, 131),
              deepslate_tiles=(51, 61, 73), chiseled_stone_bricks=(151, 156, 160),
              mossy_stone_bricks=(91, 118, 83), polished_deepslate=(67, 76, 89),
              sea_lantern=(167, 236, 223), waxed_cut_copper=(183, 109, 71),
              oak_planks=(159, 124, 76), amethyst_block=(143, 104, 190),
              calcite=(219, 215, 201))


def make_room(style, height):
    blocks = {(x, y, z): 'air' for y in range(height) for z in range(48) for x in range(48)}

    def box(x0, y0, z0, x1, y1, z1, material):
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                for z in range(z0, z1 + 1):
                    blocks[x, y, z] = material

    box(0, 0, 0, 47, 1, 47, 'deepslate_tiles')
    for x in range(48):
        for z in range(48):
            if x % 8 == 0 or z % 8 == 0:
                blocks[x, 1, z] = 'stone_bricks'
    for y in range(2, height - 3):
        for t in range(48):
            for p in ((0, y, t), (47, y, t), (t, y, 0), (t, y, 47)):
                blocks[p] = 'chiseled_stone_bricks' if y in (7, 15, 20) else 'stone_bricks'
    box(0, height - 3, 0, 47, height - 3, 47, 'polished_deepslate')
    for x in (7, 16, 31, 40):
        for z in (7, 16, 31, 40):
            box(x, height - 4, z, x + 1, height - 4, z + 1, 'sea_lantern')
    if style == 'arcade':
        for z in (9, 18, 29, 38):
            for x in (12, 35):
                box(x - 1, 2, z - 1, x + 1, 3, z + 1, 'polished_deepslate')
                box(x, 4, z, x, 15, z, 'chiseled_stone_bricks')
            for x in range(12, 36):
                y = 15 + round(4 * math.sin((x - 12) / 23 * math.pi))
                box(x, y, z, x, y + 1, z, 'stone_bricks')
    elif style == 'sanctum':
        for x in range(3, 45):
            for z in range(3, 45):
                r = math.hypot(x - 23.5, z - 23.5)
                if 12 < r < 15:
                    blocks[x, 1, z] = 'waxed_cut_copper'
        for i in range(8):
            a = (i + .5) * math.pi / 4
            x, z = round(23.5 + 16 * math.cos(a)), round(23.5 + 16 * math.sin(a))
            box(x - 1, 2, z - 1, x + 1, 12, z + 1, 'polished_deepslate')
            box(x - 1, 13, z - 1, x + 1, 13, z + 1, 'sea_lantern')
        for x in range(9, 39):
            for z in range(9, 39):
                r = math.hypot(x - 23.5, z - 23.5)
                if 13 < r < 15:
                    blocks[x, 17, z] = 'waxed_cut_copper'
    elif style == 'archive':
        for x in (7, 14, 33, 40):
            for z0 in (7, 29):
                box(x, 2, z0, x + 1, 7, z0 + 11, 'oak_planks')
                for y in (3, 5, 7):
                    box(x, y, z0, x + 1, y, z0 + 11, 'waxed_cut_copper')
        for x in (9, 38):
            box(x - 2, 2, 18, x + 2, 3, 20, 'polished_deepslate')
        for x in range(6, 43, 9):
            box(x, 17, 3, x, 18, 44, 'oak_planks')
    else:
        for cx, cz, height in ((9, 9, 13), (38, 9, 10), (9, 38, 8), (38, 38, 15)):
            for y in range(2, height):
                radius = max(0, (height - y) // 4)
                box(cx - radius, y, cz - radius, cx + radius, y, cz + radius,
                    'calcite' if y < 4 else 'amethyst_block')
            blocks[cx, height, cz] = 'sea_lantern'
        for x in range(4, 44):
            for z in range(4, 44):
                if (x * 7 + z * 11) % 19 < 3:
                    blocks[x, 1, z] = 'mossy_stone_bricks'
    # Clear internal arteries while preserving the sealed exterior for stage one.
    for x in range(1, 47):
        for z in range(1, 47):
            if 21 <= x <= 26 or 21 <= z <= 26:
                for y in range(2, 7):
                    blocks[x, y, z] = 'air'
    return blocks


def validate_before_opening(blocks, height):
    """Flood a padded exterior before any doorway is carved."""
    exterior = {(-1, -1, -1)}
    queue = collections.deque(exterior)
    while queue:
        x, y, z = queue.popleft()
        for p in ((x-1,y,z),(x+1,y,z),(x,y-1,z),(x,y+1,z),(x,y,z-1),(x,y,z+1)):
            if (-1 <= p[0] <= 48 and -1 <= p[1] <= height and -1 <= p[2] <= 48
                    and blocks.get(p, 'air') == 'air' and p not in exterior):
                exterior.add(p)
                queue.append(p)
    interior = {p for p,m in blocks.items() if m == 'air' and
                1 <= p[0] <= 46 and 2 <= p[1] < height-3 and 1 <= p[2] <= 46}
    assert interior and not interior.intersection(exterior), 'Leak before opening ports'
    return dict(passed=True, interior_air_blocks=len(interior), exterior_leaks=0)


def open_ports(blocks, definition):
    """Stage two: change only the declared boundary doorway volumes."""
    opened = set()
    for port in definition['ports']:
        lo, hi = port['min'], port['max']
        for x in range(lo[0], hi[0]+1):
            for y in range(lo[1], hi[1]+1):
                for z in range(lo[2], hi[2]+1):
                    opened.add((x,y,z))
    for p in opened:
        blocks[p] = 'air'
    return len(opened)


def i(n):
    return struct.pack('>i', n)


def s(v):
    b = v.encode('utf8')
    return struct.pack('>H', len(b)) + b


def tag(t, name, data):
    return bytes([t]) + s(name) + data


def export_nbt(path, blocks, size):
    palette = list(COLORS)
    data = b'\x0a\0\0' + tag(3, 'DataVersion', i(3465))
    data += tag(9, 'size', b'\x03' + i(3) + b''.join(map(i, size)))
    data += tag(9, 'palette', b'\x0a' + i(len(palette)) + b''.join(
        tag(8, 'Name', s('minecraft:' + p)) + b'\0' for p in palette))
    payload = bytearray()
    for p, material in blocks.items():
        payload += tag(9, 'pos', b'\x03' + i(3) + b''.join(map(i, p)))
        payload += tag(3, 'state', i(palette.index(material))) + b'\0'
    data += tag(9, 'blocks', b'\x0a' + i(len(blocks)) + payload)
    data += tag(9, 'entities', b'\x0a' + i(0)) + b'\0'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(data, mtime=0))


def export_obj(path, blocks):
    # Minecraft Y-up, one unit per block; only exposed faces are emitted.
    faces = [((-1, 0, 0), [(0,0,0),(0,0,1),(0,1,1),(0,1,0)]),
             ((1,0,0), [(1,0,1),(1,0,0),(1,1,0),(1,1,1)]),
             ((0,-1,0), [(0,0,1),(0,0,0),(1,0,0),(1,0,1)]),
             ((0,1,0), [(0,1,0),(0,1,1),(1,1,1),(1,1,0)]),
             ((0,0,-1), [(1,0,0),(0,0,0),(0,1,0),(1,1,0)]),
             ((0,0,1), [(0,0,1),(1,0,1),(1,1,1),(0,1,1)])]
    with path.open('w', encoding='utf8') as f:
        f.write('mtllib materials.mtl\n')
        n = 1
        for (x,y,z), material in blocks.items():
            if material == 'air':
                continue
            for (dx,dy,dz), vertices in faces:
                if blocks.get((x+dx,y+dy,z+dz), 'air') != 'air':
                    continue
                f.write('usemtl ' + material + '\n')
                for vx,vy,vz in vertices:
                    f.write(f'v {x+vx} {y+vy} {z+vz}\n')
                f.write('f ' + ' '.join(str(n+j) for j in range(4)) + '\n')
                n += 4


def validate(blocks, definition):
    assert len(blocks) == math.prod(definition['size'])
    walkable = {(x,z) for x in range(48) for z in range(48)
                if blocks[x,1,z] != 'air' and all(blocks[x,y,z] == 'air' for y in (2,3,4))}
    reached = {(24,24)}
    queue = collections.deque(reached)
    while queue:
        x,z = queue.popleft()
        for p in ((x-1,z),(x+1,z),(x,z-1),(x,z+1)):
            if p in walkable and p not in reached:
                reached.add(p)
                queue.append(p)
    for x,y,z in definition['spawns'] + [definition['arrival']]:
        assert (x,z) in reached
    for port in definition['ports']:
        lo, hi = port['min'], port['max']
        for x in range(lo[0],hi[0]+1):
            for z in range(lo[2],hi[2]+1):
                assert (x,z) in reached
                assert all(blocks[x,y,z] == 'air' for y in range(2,7))
    return dict(explicit_blocks=len(blocks), reachable_floor_cells=len(reached),
                ports=4, spawn_points=4, runtime_verified=False,
                size=definition['size'], floor_y=1, door_y=2, door_top_y=6, arrival_y=2)


def preview(rooms):
    from PIL import Image, ImageDraw
    sheet = Image.new('RGB', (1600,1200), '#101823')
    draw = ImageDraw.Draw(sheet)
    for index, (name, blocks) in enumerate(rooms.items()):
        ox, oy = (index % 2) * 800 + 400, (index // 2) * 600 + 150
        def project(x,y,z):
            return (ox + (x-z)*7, oy + (x+z)*3.5-y*7)
        # Roof, front walls and high beams hidden only in the illustration.
        roof_y = max(p[1] for p in blocks) - 2
        visible = {p:m for p,m in blocks.items() if m != 'air' and p[1] < roof_y
                   and not (p[1] >= 17 and (p[0] in (0,47) or p[2] in (0,47)))
                   and not (p[1] > 1 and (p[0] >= 46 or p[2] >= 46))}
        for (x,y,z), material in sorted(visible.items(), key=lambda v:(sum(v[0][::2]),v[0][1])):
            rgb = COLORS[material]
            for delta, verts, shade in (
                ((1,0,0),[(1,0,0),(1,0,1),(1,1,1),(1,1,0)],.64),
                ((0,0,1),[(0,0,1),(1,0,1),(1,1,1),(0,1,1)],.8),
                ((0,1,0),[(0,1,0),(1,1,0),(1,1,1),(0,1,1)],1.1)):
                if (x+delta[0],y+delta[1],z+delta[2]) not in visible:
                    draw.polygon([project(x+a,y+b,z+c) for a,b,c in verts],
                                 fill=tuple(min(255,int(c*shade)) for c in rgb))
        draw.text((index%2*800+35,index//2*600+30), name.upper(), fill='#e6ecef', font_size=25)
        height = max(p[1] for p in blocks) + 1
        draw.text((index%2*800+35,index//2*600+560), f'48 x {height} x 48 | floor Y=1 | door Y=2..6 | CUTAWAY', fill='#a8bbc9', font_size=16)
    sheet.save(OUT / 'preview.png')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'materials.mtl').write_text(''.join(
        f'newmtl {name}\nKd ' + ' '.join(f'{c/255:.4f}' for c in rgb) + '\n\n'
        for name,rgb in COLORS.items()), encoding='utf8')
    base = Path(__file__).resolve().parents[1]/'references/combat_room_base.json'
    rooms, report = {}, {}
    for name, height in (('arcade',24),('sanctum',28),('archive',24),('crystal',32)):
        blocks = make_room(name, height)
        definition = json.loads(base.read_text(encoding='utf8'))
        definition.update(schema_version=4, door_y=2, size=[48,height,48], template='saodg:models/'+name,
                          secrets=[], secret_scenes=[])
        sealed = validate_before_opening(blocks, height)
        opened = open_ports(blocks, definition)
        report[name] = validate(blocks, definition)
        report[name]['before_opening'] = sealed
        report[name]['after_opening'] = dict(port_air_blocks=opened, ports_and_routes_passed=True)
        export_nbt(OUT/f'data/saodg/structures/models/{name}.nbt', blocks, definition['size'])
        p = OUT/f'data/saodg/rooms/models/{name}.json'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(definition,indent=4)+'\n',encoding='utf8')
        export_obj(OUT/f'{name}.obj', blocks)
        rooms[name] = blocks
    preview(rooms)
    (OUT/'validation.json').write_text(json.dumps(report,indent=4)+'\n',encoding='utf8')
    print(json.dumps(report,indent=2))
    print(OUT)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path.cwd()/'build/room_models')
    args = parser.parse_args()
    OUT = args.output.resolve()
    main()
