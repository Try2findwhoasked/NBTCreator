"""Offline perspective inspection of a Java 1.20.1 structure NBT.

This is a geometry inspection tool, not a Minecraft renderer. It reads the actual
NBT with nbt_model.load, ray traces half-block voxels, and records approximations
in <output>.json. Only numpy and Pillow are required beyond the authoring tools.

Example:
  python nbt_preview.py --nbt room.nbt --output entrance.png \
      --eye 24,6,-8 --target 24,6,24 --width 1280 --height 800
  python nbt_preview.py --nbt room.nbt --output cut.png \
      --eye 58,45,-18 --target 24,5,24 --cut-height 12
Coordinates are Minecraft structure coordinates: +Y up, north is -Z. A cut
position is a block boundary coordinate, not an inclusive block index.
Repeat --cut AXIS:POSITION:above|below to combine planes, for example
--cut z:44:above --cut x:44:above --cut y:40:above. All --cut planes,
the legacy --cut-axis/--cut-position plane, and --cut-height accumulate:
geometry in ANY removed half-space is discarded. --cut-side applies only to
the legacy axis plane; --cut-height always removes at/above its Y coordinate.
All cut positions must be finite multiples of 0.5 blocks.
"""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

from nbt_model import AIR_NAMES, load
from nbt_collision import FULL_CUBES as COLLISION_FULL_CUBES
from nbt_registry import effective


# Deliberately conservative: unfamiliar states are recorded as approximations.
FULL_BLOCKS = set("""stone cobblestone mossy_cobblestone smooth_stone granite
polished_granite diorite polished_diorite andesite polished_andesite deepslate
cobbled_deepslate polished_deepslate deepslate_bricks cracked_deepslate_bricks
deepslate_tiles cracked_deepslate_tiles reinforced_deepslate tuff calcite
dripstone_block stone_bricks mossy_stone_bricks cracked_stone_bricks
chiseled_stone_bricks bricks mud_bricks packed_mud dirt coarse_dirt rooted_dirt
grass_block podzol mycelium mud clay gravel sand red_sand sandstone
smooth_sandstone cut_sandstone chiseled_sandstone red_sandstone
smooth_red_sandstone cut_red_sandstone chiseled_red_sandstone bedrock obsidian
crying_obsidian netherrack soul_sand soul_soil basalt smooth_basalt polished_basalt
blackstone polished_blackstone polished_blackstone_bricks
cracked_polished_blackstone_bricks chiseled_polished_blackstone nether_bricks
red_nether_bricks cracked_nether_bricks chiseled_nether_bricks end_stone
end_stone_bricks purpur_block purpur_pillar quartz_block smooth_quartz
quartz_bricks chiseled_quartz_block quartz_pillar prismarine prismarine_bricks
dark_prismarine sea_lantern glowstone shroomlight magma_block dried_kelp_block
bone_block bookshelf chiseled_bookshelf melon pumpkin carved_pumpkin
jack_o_lantern hay_block honeycomb_block target crafting_table furnace
blast_furnace smoker dispenser dropper observer piston sticky_piston
redstone_lamp note_block jukebox lodestone respawn_anchor ancient_debris
raw_iron_block raw_copper_block raw_gold_block iron_block gold_block diamond_block
emerald_block lapis_block redstone_block coal_block netherite_block amethyst_block
budding_amethyst copper_block exposed_copper weathered_copper oxidized_copper
cut_copper exposed_cut_copper weathered_cut_copper oxidized_cut_copper
waxed_copper_block waxed_exposed_copper waxed_weathered_copper
waxed_oxidized_copper waxed_cut_copper waxed_exposed_cut_copper
waxed_weathered_cut_copper waxed_oxidized_cut_copper terracotta snow_block
ice packed_ice blue_ice sponge wet_sponge mushroom_stem brown_mushroom_block
red_mushroom_block sculk sculk_catalyst sculk_shrieker
""".split()) - {'sculk_shrieker', 'soul_sand', 'piston', 'sticky_piston'}
WOOD = ('oak', 'spruce', 'birch', 'jungle', 'acacia', 'dark_oak', 'mangrove',
        'cherry', 'bamboo', 'crimson', 'warped')
for _wood in WOOD:
    FULL_BLOCKS.update(f'{prefix}{_wood}_{suffix}' for prefix in ('', 'stripped_')
                       for suffix in ('log', 'wood', 'stem', 'hyphae', 'planks'))
for _color in ('white', 'orange', 'magenta', 'light_blue', 'yellow', 'lime',
               'pink', 'gray', 'light_gray', 'cyan', 'purple', 'blue', 'brown',
               'green', 'red', 'black'):
    FULL_BLOCKS.update(f'{_color}_{suffix}' for suffix in
                      ('wool', 'concrete', 'concrete_powder', 'terracotta', 'glazed_terracotta'))
# Reuse certified full-cube knowledge; visual-only shapes remain separately
# classified above (e.g. mud is visually full but has a 14/16 collision shape).
FULL_BLOCKS.update(COLLISION_FULL_CUBES)


def parse_state(state):
    name, props = effective(state)
    return name.removeprefix('minecraft:'), props


def geometry(state):
    """Return a 2x2x2 occupancy mask and any approximation reason."""
    name, props = parse_state(state)
    cells = np.ones((2, 2, 2), dtype=bool)
    reason = None
    if name.endswith('_slab') and props.get('type', 'bottom') in ('bottom', 'top', 'double'):
        kind = props.get('type', 'bottom')
        if kind != 'double':
            cells[:, 1 if kind == 'bottom' else 0, :] = False
    elif name.endswith('_stairs'):
        facing = props.get('facing', 'north')
        shape = props.get('shape', 'straight')
        half = props.get('half', 'bottom')
        if facing not in ('north', 'east', 'south', 'west') or half not in ('bottom', 'top') or shape not in (
                'straight', 'inner_left', 'inner_right', 'outer_left', 'outer_right'):
            reason = 'Invalid/unknown stair state; rendered as a full cube'
        else:
            masks = dict(north=np.array([[1, 0], [1, 0]], bool),
                         east=np.array([[0, 0], [1, 1]], bool),
                         south=np.array([[0, 1], [0, 1]], bool),
                         west=np.array([[1, 1], [0, 0]], bool))
            turn = ('north', 'east', 'south', 'west')
            side = turn[(turn.index(facing) + (-1 if shape.endswith('left') else 1)) % 4]
            upper = masks[facing].copy()
            if shape.startswith('inner_'):
                upper |= masks[side]
            elif shape.startswith('outer_'):
                upper &= masks[side]
            cells[:, 1 if half == 'bottom' else 0, :] = upper
    elif name not in FULL_BLOCKS and not name.endswith('_ore'):
        reason = 'Unsupported/uncertified geometry rendered as an opaque full cube'
    if props.get('waterlogged') == 'true':
        reason = (reason + '; ' if reason else '') + 'Waterlogged fluid is omitted'
    return cells, reason


def material_color(name):
    """Procedural diagnostic palette; never claims to be resource-pack textures."""
    categories = (
        (('sea_lantern', 'pearlescent_froglight'), (192, 223, 214)),
        (('ochre_froglight',), (229, 215, 160)),
        (('verdant_froglight',), (188, 221, 162)),
        (('oxidized',), (69, 151, 130)),
        (('weathered',), (102, 148, 112)),
        (('gold', 'yellow'), (207, 165, 58)),
        (('copper', 'orange', 'acacia'), (172, 103, 64)),
        (('oxidized', 'prismarine', 'warped', 'cyan'), (63, 131, 132)),
        (('redstone', 'red_', 'nether_brick', 'crimson'), (139, 61, 63)),
        (('emerald', 'moss', 'grass', 'green', 'leaves'), (79, 122, 76)),
        (('lapis', 'blue'), (65, 93, 150)),
        (('purple', 'purpur', 'amethyst'), (137, 105, 163)),
        (('black', 'obsidian', 'coal', 'sculk'), (51, 53, 64)),
        (('deepslate', 'basalt'), (91, 94, 103)),
        (('sand', 'birch', 'end_stone', 'bone'), (199, 186, 138)),
        (('white', 'quartz', 'snow', 'calcite', 'iron'), (204, 207, 204)),
        (('spruce', 'dark_oak'), (107, 80, 53)),
        (('oak', 'jungle', 'cherry', 'bamboo', 'mangrove'), (157, 119, 75)),
        (('wood', 'planks', 'log', 'barrel', 'chest', 'bookshelf'), (157, 119, 75)),
        (('dirt', 'mud', 'brown'), (122, 92, 68)),
        (('glass', 'ice', 'diamond'), (139, 183, 193)),
        (('glow', 'lantern', 'shroomlight'), (232, 203, 130)),
    )
    base = next((np.array(c, float) for keys, c in categories if any(k in name for k in keys)),
                np.array((151, 153, 154), float))
    jitter = int.from_bytes(hashlib.sha256(name.encode()).digest()[:2], 'big') % 17 - 8
    return np.clip(base + jitter, 0, 255)


def cut_definition(axis, position, side='above'):
    """Validate one plane; above removes >=position, below removes <position."""
    try:
        position = float(position)
    except (TypeError, ValueError) as exc:
        raise ValueError('Cut position must be a finite multiple of 0.5 blocks') from exc
    if axis not in ('x', 'y', 'z') or side not in ('above', 'below'):
        raise ValueError('Cut requires an x/y/z axis and an above/below removed side')
    if not math.isfinite(position) or abs(position * 2 - round(position * 2)) > 1e-8:
        raise ValueError('Cut positions must be finite multiples of 0.5 blocks')
    return dict(axis=axis, position=position, removed_side=side)


def combine_cuts(cut_axis=None, cut_position=None, cut_side='above', cuts=None):
    """Normalize dictionary or (axis, position, side) planes, plus the old plane."""
    result = []
    for plane in cuts or []:
        if isinstance(plane, dict):
            result.append(cut_definition(plane.get('axis'), plane.get('position'),
                                         plane.get('removed_side', plane.get('side', 'above'))))
        else:
            try:
                axis, position, side = plane
            except (ValueError, TypeError) as exc:
                raise ValueError('Each cut must be a plane dictionary or (axis, position, side) tuple') from exc
            result.append(cut_definition(axis, position, side))
    if (cut_axis is None) != (cut_position is None):
        raise ValueError('cut_axis and cut_position must be provided together')
    if cut_axis is not None:
        result.append(cut_definition(cut_axis, cut_position, cut_side))
    return result


def make_grid(model, cut_axis=None, cut_position=None, cut_side='above', cuts=None):
    """Build occupancy, applying all cuts cumulatively.

    Existing positional arguments retain their meaning. ``cuts`` additionally
    accepts a list of (axis, position, side) tuples or dictionaries with axis,
    position and removed_side (or side). Every specified plane removes its own
    half-space; the kept region is the intersection of the surviving regions.
    """
    planes = combine_cuts(cut_axis, cut_position, cut_side, cuts)
    states = sorted(set(model.blocks.values()))
    grid = np.zeros(tuple(n * 2 for n in model.size), dtype=np.int32)
    colors = [np.zeros(3)]
    approximations = []
    counts = Counter(model.blocks.values())
    masks = {}
    for index, state in enumerate(states, 1):
        masks[state], reason = geometry(state)
        if reason:
            approximations.append(dict(state=state, block_count=counts[state], reason=reason))
        colors.append(material_color(parse_state(state)[0]))
    ids = {state: i for i, state in enumerate(states, 1)}
    for p, state in model.blocks.items():
        if state.split('[')[0] in AIR_NAMES:
            continue
        x, y, z = (n * 2 for n in p)
        grid[x:x + 2, y:y + 2, z:z + 2] = masks[state] * ids[state]
    for plane in planes:
        axis = 'xyz'.index(plane['axis'])
        cut = int(round(plane['position'] * 2))
        side = plane['removed_side']
        selection = [slice(None)] * 3
        selection[axis] = slice(max(0, cut), None) if side == 'above' else slice(None, max(0, cut))
        if side == 'above' and cut <= 0 or side == 'below' and cut >= grid.shape[axis]:
            grid[:] = 0
        elif 0 <= cut <= grid.shape[axis]:
            grid[tuple(selection)] = 0
    return grid, np.array(colors), approximations


def trace(grid, eye, directions):
    """Vectorized exact DDA through axis-aligned half-block cells."""
    count = len(directions)
    bound = np.array(grid.shape, float) * 0.5
    inv = np.divide(1.0, directions, out=np.full_like(directions, np.inf), where=np.abs(directions) > 1e-12)
    # Finite replacement avoids 0*inf when the eye lies on a box boundary.
    safe_dir = np.where(np.abs(directions) > 1e-12, directions, 1e-30)
    t0, t1 = -eye / safe_dir, (bound - eye) / safe_dir
    near, far = np.minimum(t0, t1), np.maximum(t0, t1)
    entry = np.maximum(near.max(axis=1), 0)
    end = far.min(axis=1)
    valid = end > entry + 1e-7
    ids = np.zeros(count, np.int32)
    depth = np.full(count, np.inf)
    normals = np.zeros((count, 3), float)
    points = eye + (entry[:, None] + 1e-6) * directions
    cell = np.floor(points * 2).astype(np.int32)
    cell = np.maximum(0, np.minimum(cell, np.array(grid.shape) - 1))
    step = np.where(directions >= 0, 1, -1)
    next_edge = (cell + (step > 0)) * 0.5
    next_t = (next_edge - eye) / safe_dir
    next_t[np.abs(directions) < 1e-12] = np.inf
    delta_t = np.abs(inv) * 0.5
    normal = np.zeros((count, 3), float)
    axis = near.argmax(axis=1)
    normal[np.arange(count), axis] = -step[np.arange(count), axis]
    current = entry.copy()
    active = np.flatnonzero(valid)
    for _ in range(sum(grid.shape) + 3):
        if not len(active):
            break
        coords = cell[active]
        values = grid[coords[:, 0], coords[:, 1], coords[:, 2]]
        hit = values != 0
        found = active[hit]
        ids[found], depth[found], normals[found] = values[hit], current[found], normal[found]
        active = active[~hit]
        if not len(active):
            break
        axis = next_t[active].argmin(axis=1)
        current[active] = next_t[active, axis]
        cell[active, axis] += step[active, axis]
        normal[active] = 0
        normal[active, axis] = -step[active, axis]
        next_t[active, axis] += delta_t[active, axis]
        inside = ((cell[active] >= 0) & (cell[active] < np.array(grid.shape))).all(axis=1)
        active = active[inside & (current[active] <= end[active] + 1e-7)]
    return ids, depth, normals


def occupied(grid, points):
    coords = np.floor(points * 2).astype(np.int32)
    inside = ((coords >= 0) & (coords < np.array(grid.shape))).all(axis=1)
    result = np.zeros(len(points), bool)
    q = coords[inside]
    result[inside] = grid[q[:, 0], q[:, 1], q[:, 2]] != 0
    return result


def render(grid, colors, eye, target, width, height, fov=60):
    forward = target - eye
    forward /= np.linalg.norm(forward)
    up_reference = np.array((0., 1., 0.))
    if abs(forward @ up_reference) > .999:
        up_reference = np.array((0., 0., 1.))
    right = np.cross(forward, up_reference)
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    scale = math.tan(math.radians(fov) / 2)
    light = np.array((-.45, .82, -.35))
    light /= np.linalg.norm(light)
    result = np.empty((height, width, 3), np.uint8)
    visible = 0
    # Keep memory bounded even for large diagnostic images.
    rows_per_batch = max(1, 65536 // width)
    for y0 in range(0, height, rows_per_batch):
        y1 = min(height, y0 + rows_per_batch)
        xx, yy = np.meshgrid((np.arange(width) + .5) / width * 2 - 1,
                             1 - (np.arange(y0, y1) + .5) / height * 2)
        dirs = (forward + xx[..., None] * scale * width / height * right + yy[..., None] * scale * up).reshape(-1, 3)
        dirs /= np.linalg.norm(dirs, axis=1)[:, None]
        ids, depth, normals = trace(grid, eye, dirs)
        sky_factor = np.clip(dirs[:, 1] * .5 + .5, 0, 1)[:, None]
        background = (np.array((204, 213, 218)) * (1 - sky_factor) + np.array((143, 167, 185)) * sky_factor)
        rgb = background.copy()
        hits = np.flatnonzero(ids)
        visible += len(hits)
        if len(hits):
            p = eye + dirs[hits] * depth[hits, None]
            n = normals[hits]
            brightness = .49 + .45 * np.maximum(n @ light, 0)
            # Short-range directional occlusion is intentionally approximate;
            # it adds depth in enclosed rooms without requiring game lighting.
            origin = p + n * .025
            blocked = np.zeros(len(p), bool)
            for distance in (.3, .7, 1.3, 2.2, 3.5, 5.0):
                blocked |= occupied(grid, origin + light * distance)
            brightness *= np.where(blocked, .76, 1.)
            block = np.floor(p + n * -.001)
            grain = np.sin(block[:, 0] * 83.1 + block[:, 1] * 127.7 + block[:, 2] * 37.3) * .018
            # Thin procedural joints, only along the two axes of a visible face.
            fract = np.mod(p, 1.)
            edge = np.minimum(fract, 1 - fract)
            edge[np.abs(n) > .5] = 1
            brightness *= np.where(edge.min(axis=1) < .018, .88, 1.)
            shaded = colors[ids[hits]] * (brightness + grain)[:, None]
            fog = (1 - np.exp(-depth[hits] / 180))[:, None] * .36
            rgb[hits] = shaded * (1 - fog) + background[hits] * fog
        result[y0:y1] = np.clip(rgb.reshape(y1 - y0, width, 3), 0, 255).astype(np.uint8)
    image = Image.fromarray(result)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, height - 25, width, height), fill=(30, 36, 43))
    draw.text((9, height - 18), 'NBT GEOMETRY PREVIEW | procedural colors | +Y up', fill=(225, 231, 236))
    return image, visible


def vector(value):
    try:
        result = np.array([float(v) for v in value.split(',')])
        if result.shape != (3,) or not np.isfinite(result).all():
            raise ValueError
        return result
    except ValueError as exc:
        raise argparse.ArgumentTypeError('Expected three finite comma-separated coordinates: x,y,z') from exc


def cut_argument(value):
    try:
        axis, position, side = value.split(':')
        return cut_definition(axis, position, side)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('Expected AXIS:POSITION:above|below; ' + str(exc)) from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--nbt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='PNG image path; metadata is written to <output>.json')
    parser.add_argument('--eye', type=vector, required=True)
    parser.add_argument('--target', type=vector, required=True)
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--height', type=int, default=800)
    parser.add_argument('--fov', type=float, default=60, help='Vertical field of view in degrees')
    parser.add_argument('--cut-height', type=float, help='Remove geometry at/above this Y plane (half-block increments)')
    parser.add_argument('--cut', type=cut_argument, action='append', default=[], metavar='AXIS:POSITION:SIDE',
                        help='Repeatable plane, e.g. x:44:above; combines with every other cut')
    parser.add_argument('--cut-axis', choices=('x', 'y', 'z'))
    parser.add_argument('--cut-position', type=float, help='Plane coordinate, in half-block increments')
    parser.add_argument('--cut-side', choices=('above', 'below'), default='above', help='Side to remove for --cut-axis only')
    # argparse mistakes a vector beginning with negative X for an option.
    # Accept both "--eye -8,3,4" and the usual "--eye=-8,3,4" spelling.
    argv = sys.argv[1:]
    normalized = []
    index = 0
    while index < len(argv):
        if argv[index] in ('--eye', '--target') and index + 1 < len(argv) and ',' in argv[index + 1]:
            normalized.append(argv[index] + '=' + argv[index + 1])
            index += 2
        else:
            normalized.append(argv[index])
            index += 1
    args = parser.parse_args(normalized)
    if not (64 <= args.width <= 4096 and 64 <= args.height <= 4096):
        parser.error('Image width and height must each be between 64 and 4096')
    if not 10 <= args.fov <= 120:
        parser.error('--fov must be between 10 and 120 degrees')
    if np.linalg.norm(args.target - args.eye) < 1e-6:
        parser.error('--eye and --target must differ')
    if args.output.suffix.lower() != '.png':
        parser.error('--output must end with .png')
    try:
        planes = combine_cuts(args.cut_axis, args.cut_position, args.cut_side, args.cut)
        if args.cut_height is not None:
            planes.append(cut_definition('y', args.cut_height, 'above'))
    except ValueError as exc:
        parser.error(str(exc))
    source = args.nbt.read_bytes()
    model = load(args.nbt)
    if args.nbt.read_bytes() != source:
        parser.error('Source NBT changed while loading; retry against a stable file')
    grid, colors, approximations = make_grid(model, cuts=planes)
    image, visible = render(grid, colors, args.eye, args.target, args.width, args.height, args.fov)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output)
    warnings = [] if visible else ['No structure pixels are visible; check camera direction and clipping.']
    if occupied(grid, args.eye[None, :])[0]:
        warnings.append('Camera eye is inside solid rendered geometry; move the camera or apply a cut.')
    metadata = dict(
        renderer='nbt_preview_half_voxel_v1', source_nbt=str(args.nbt.resolve()),
        source_nbt_sha256=hashlib.sha256(source).hexdigest(), structure_size=list(model.size),
        camera=dict(eye=args.eye.tolist(), target=args.target.tolist(), up=[0, 1, 0],
                    projection='perspective', vertical_fov_degrees=args.fov, width=args.width, height=args.height),
        cut=planes[0] if len(planes) == 1 else None,
        cuts=planes, cut_combination='remove_union_of_half_spaces_keep_intersection',
        geometry=dict(resolution_blocks=0.5, occupied_half_cells=int(np.count_nonzero(grid)),
                      supported=['full opaque cubes', 'bottom/top/double slabs',
                                 'bottom/top stairs: straight, inner_left/right, outer_left/right'],
                      approximated_states=approximations),
        rendering_approximations=[
            'Geometry inspection only; not a Minecraft screenshot or resource-pack preview.',
            'All materials use deterministic procedural colors, grain, and joints; no Minecraft textures.',
            'All rendered geometry is opaque, including glass, leaves, ice, and fluids when present.',
            'Fixed ambient/directional light and sampled short-range occlusion; no Minecraft block/sky light, emission, or full shadows.',
            'Block entities, entity models, animation, biome tint, and connected/neighbour-dependent shape updates are not rendered.',
            'NBT block states are used as saved; stair shape is not recomputed from neighbours.'
        ], visible_structure_pixels=visible,
        warnings=warnings)
    metadata_path = Path(str(args.output) + '.json')
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + '\n', encoding='utf8')
    print(json.dumps(dict(image=str(args.output.resolve()), metadata=str(metadata_path.resolve()),
                          visible_structure_pixels=visible, approximated_states=len(approximations)), ensure_ascii=False))


if __name__ == '__main__':
    main()
