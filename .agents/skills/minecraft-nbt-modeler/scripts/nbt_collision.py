"""Conservative static walking routes for nbt_model.Model (Minecraft 1.20.1).

check_routes(model, start, targets) takes actual player-feet coordinates, NOT
block indices: a block-centred player above block (2, 0, 3) is (2.5, 1, 3.5).
The 0.6 x 1.8 player AABB moves on a half-block horizontal/height graph. Swept
AABBs and continuous support checks handle ordinary walking and <=0.5 steps;
jumping, falling farther, swimming, climbing and special movement are omitted.

Full cubes use an explicit material allowlist; bottom/top/double slabs and all
five stair shapes are represented exactly as unions of half-block cubes. Other
blocks become full cubes for diagnostics and make passed=False. A small,
version-verified allowlist may instead use full-block obstacle supersets: these
proxies never provide floor support, and reports distinguish this conservative
route witness from exact shape support. All other unknown shapes still fail.
This is a geometric authoring check, not a substitute for an in-game walk test.
"""
from collections import Counter, deque
from functools import lru_cache
import math
from nbt_registry import effective


EPS = 1e-8
RADIUS = 0.3
PLAYER_HEIGHT = 1.8
AIR_NAMES = {'air', 'cave_air', 'void_air'}
FACING = {'east': (1, 0), 'west': (-1, 0),
          'south': (0, 1), 'north': (0, -1)}
# These collision shapes are full unit cubes. Do not broaden this to "anything
# not air": e.g. honey, soul sand, chests, panes and fences are not full cubes.
FULL_CUBES = set('''
stone granite polished_granite diorite polished_diorite andesite polished_andesite
deepslate cobbled_deepslate polished_deepslate calcite tuff dripstone_block
grass_block dirt coarse_dirt rooted_dirt podzol mycelium packed_mud
cobblestone mossy_cobblestone stone_bricks mossy_stone_bricks cracked_stone_bricks
chiseled_stone_bricks deepslate_bricks cracked_deepslate_bricks deepslate_tiles
cracked_deepslate_tiles chiseled_deepslate bricks mud_bricks bedrock obsidian
crying_obsidian netherrack nether_bricks red_nether_bricks cracked_nether_bricks
chiseled_nether_bricks basalt polished_basalt smooth_basalt blackstone
polished_blackstone polished_blackstone_bricks cracked_polished_blackstone_bricks
chiseled_polished_blackstone end_stone end_stone_bricks sandstone cut_sandstone
chiseled_sandstone smooth_sandstone red_sandstone cut_red_sandstone
chiseled_red_sandstone smooth_red_sandstone quartz_block quartz_bricks
chiseled_quartz_block quartz_pillar smooth_quartz smooth_stone prismarine
prismarine_bricks dark_prismarine sea_lantern glowstone glass tinted_glass
amethyst_block budding_amethyst gold_block iron_block diamond_block emerald_block
lapis_block coal_block netherite_block redstone_block raw_iron_block raw_gold_block
raw_copper_block copper_block exposed_copper weathered_copper oxidized_copper
cut_copper exposed_cut_copper weathered_cut_copper oxidized_cut_copper
waxed_copper_block waxed_exposed_copper waxed_weathered_copper waxed_oxidized_copper
waxed_cut_copper waxed_exposed_cut_copper waxed_weathered_cut_copper
waxed_oxidized_cut_copper terracotta packed_ice blue_ice ice snow_block clay
sand red_sand gravel sponge wet_sponge bone_block dried_kelp_block hay_block
melon pumpkin carved_pumpkin jack_o_lantern bookshelf chiseled_bookshelf
crafting_table target reinforced_deepslate moss_block shroomlight ochre_froglight
verdant_froglight pearlescent_froglight brown_mushroom_block red_mushroom_block
mushroom_stem nether_wart_block warped_wart_block sculk
'''.split())
WOODS = 'oak spruce birch jungle acacia dark_oak mangrove cherry bamboo crimson warped'.split()
COLORS = 'white orange magenta light_blue yellow lime pink gray light_gray cyan purple blue brown green red black'.split()
for _wood in WOODS:
    FULL_CUBES.add(_wood + '_planks')
    for _suffix in ('log', 'wood', 'stem', 'hyphae'):
        FULL_CUBES.update((_wood + '_' + _suffix, 'stripped_' + _wood + '_' + _suffix))
    FULL_CUBES.add(_wood + '_leaves')
FULL_CUBES.update(('bamboo_block', 'stripped_bamboo_block', 'bamboo_mosaic', 'azalea_leaves', 'flowering_azalea_leaves'))
for _color in COLORS:
    FULL_CUBES.update(_color + '_' + suffix for suffix in
                      ('wool', 'concrete', 'terracotta', 'glazed_terracotta', 'stained_glass'))
for _ore in ('coal', 'iron', 'gold', 'copper', 'lapis', 'redstone', 'emerald', 'diamond'):
    FULL_CUBES.update((_ore + '_ore', 'deepslate_' + _ore + '_ore'))
FULL_CUBES.update(('nether_gold_ore', 'nether_quartz_ore', 'ancient_debris'))

# Verified against the Java 1.20.1 server shape definitions. These classes have
# static collision contained within their own unit block, including dripstone's
# <=1/8 horizontal offset. This is NOT a full-cube collision/support allowlist.
# See references/collision-envelopes.md for the source and proof boundary.
BOUNDED_OBSTACLES = frozenset(('chain', 'iron_bars', 'iron_trapdoor',
                              'spruce_trapdoor', 'lever', 'pointed_dripstone',
                              'stone_button'))
# FenceBlock's collision is 24/16 blocks high, unlike IronBarsBlock. Never
# silently classify it as a unit-height obstacle or allow it to support a floor.
TALL_OBSTACLES = frozenset(('spruce_fence',))
ENVELOPE_VERSION = 'minecraft-java-1.20.1-bounded-obstacles-v2'


@lru_cache(maxsize=4096)
def bounded_obstacle(value):
    """Whether the state has an explicitly verified obstacle envelope.

    Registry normalization remains mandatory. A name resembling a supported
    class, an unknown mod block, or an invalid state must not enter this path.
    """
    try:
        name, _ = effective(value)
    except ValueError:
        return False
    return name.removeprefix('minecraft:') in BOUNDED_OBSTACLES | TALL_OBSTACLES


@lru_cache(maxsize=4096)
def collision_cells(value):
    """Return occupied local (x,y,z) half-cubes and unsupported-shape reason.

    Stairs face their raised half. inner_left/right adds the corresponding side
    quadrant; outer_left/right retains only that quarter. Top stairs reflect the
    vertical half, without reflecting facing or left/right in the horizontal plane.
    """
    full = tuple((x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1))
    try:
        name, props = effective(value)
    except ValueError:
        return full, 'invalid_minecraft_1_20_1_state'
    name = name.removeprefix('minecraft:')
    if name in AIR_NAMES:
        return (), None
    if name.endswith('_slab'):
        kind = props.get('type', 'bottom')
        if kind not in ('bottom', 'top', 'double'):
            return full, 'invalid_slab_type'
        return tuple(p for p in full if kind == 'double' or p[1] == (kind == 'top')), None
    if name.endswith('_stairs'):
        facing = props.get('facing', 'north')
        half = props.get('half', 'bottom')
        shape = props.get('shape', 'straight')
        if (facing not in FACING or half not in ('bottom', 'top') or
                shape not in ('straight', 'inner_left', 'inner_right', 'outer_left', 'outer_right')):
            return full, 'invalid_stair_properties'
        dx, dz = FACING[facing]
        lx, lz = dz, -dx
        base_y = 0 if half == 'bottom' else 1
        cells = []
        for x, y, z in full:
            front = (2*x-1)*dx + (2*z-1)*dz > 0
            side = (2*x-1)*lx + (2*z-1)*lz > 0
            if shape.endswith('_right'):
                side = not side
            raised = front if shape == 'straight' else (front or side) if shape.startswith('inner') else (front and side)
            if y == base_y or raised:
                cells.append((x, y, z))
        return tuple(cells), None
    if name in FULL_CUBES:
        return full, None
    return full, 'unsupported_collision_shape'


class _Space:
    def __init__(self, model, conservative_obstacles=True):
        self.size = tuple(model.size)
        self.sx, self.sy, self.sz = (2*n for n in model.size)
        # Each y,z row is an X bitset; a player query usually touches only 8 rows.
        self.rows = [0] * (self.sy*self.sz)
        # An upper collision envelope cannot prove any supporting surface.
        # Keep exact support cells independent from obstacle rasterization.
        self.support_rows = [0] * (self.sy*self.sz)
        self.unknown = Counter()
        self.conservative = Counter()
        for (x, y, z), value in model.blocks.items():
            cells, reason = collision_cells(value)
            if reason:
                if (conservative_obstacles and reason == 'unsupported_collision_shape'
                        and bounded_obstacle(value)):
                    self.conservative[value] += 1
                    name, _ = effective(value)
                    height = 3 if name.removeprefix('minecraft:') in TALL_OBSTACLES else 2
                    cells = tuple((dx,dy,dz) for dx in (0,1) for dy in range(height) for dz in (0,1))
                else:
                    self.unknown[(value, reason)] += 1
            for dx, dy, dz in cells:
                # Only poses inside model bounds are considered. Tall envelope
                # cells above the model top cannot affect any accepted pose.
                if 2*y+dy >= self.sy:
                    continue
                row = (2*y+dy)*self.sz+2*z+dz
                bit = 1 << (2*x+dx)
                self.rows[row] |= bit
                if not reason:
                    self.support_rows[row] |= bit

    @staticmethod
    def _span(lo, hi):
        return math.floor(2*lo+EPS), math.ceil(2*hi-EPS)

    def clear_box(self, lo, hi):
        if any(a < -EPS or b > n+EPS for a, b, n in zip(lo, hi, self.size)):
            return False
        x0, x1 = self._span(lo[0], hi[0])
        y0, y1 = self._span(lo[1], hi[1])
        z0, z1 = self._span(lo[2], hi[2])
        mask = ((1 << (x1-x0))-1) << x0
        for y in range(y0, y1):
            for z in range(z0, z1):
                if self.rows[y*self.sz+z] & mask:
                    return False
        return True

    def clear_player_sweep(self, a, b):
        return self.clear_box((min(a[0], b[0])-RADIUS, min(a[1], b[1]), min(a[2], b[2])-RADIUS),
                              (max(a[0], b[0])+RADIUS, max(a[1], b[1])+PLAYER_HEIGHT, max(a[2], b[2])+RADIUS))

    def supported(self, p):
        x, y, z = p
        if abs(2*y-round(2*y)) > EPS or not 0 < y <= self.size[1]:
            return False
        below = round(2*y)-1
        x0, x1 = self._span(x-RADIUS, x+RADIUS)
        z0, z1 = self._span(z-RADIUS, z+RADIUS)
        if x0 < 0 or x1 > self.sx or z0 < 0 or z1 > self.sz:
            return False
        mask = ((1 << (x1-x0))-1) << x0
        return any(self.support_rows[below*self.sz+zz] & mask for zz in range(z0, z1))

    def standing(self, p):
        return self.clear_player_sweep(p, p) and self.supported(p)

    def support_along(self, a, b):
        """Exact union of support intervals along a cardinal horizontal move.

        On a step, support may occur at either endpoint's floor height. There
        must be continuous floor contact in horizontal projection, so stepping
        cannot become a miniature flight across an unsupported gap.
        """
        axis = 0 if abs(a[0]-b[0]) > EPS else 2
        other = 2-axis
        lower, upper = sorted((a[axis], b[axis]))
        cross0, cross1 = self._span(a[other]-RADIUS, a[other]+RADIUS)
        along0 = max(0, math.floor(2*(lower-RADIUS)))
        along1 = min((self.sx if axis == 0 else self.sz), math.ceil(2*(upper+RADIUS)))
        intervals = []
        for foot in {a[1], b[1]}:
            yy = round(2*foot)-1
            if yy < 0 or yy >= self.sy:
                continue
            for along in range(along0, along1):
                for cross in range(cross0, cross1):
                    xx, zz = (along, cross) if axis == 0 else (cross, along)
                    if 0 <= zz < self.sz and 0 <= xx < self.sx and self.support_rows[yy*self.sz+zz] & (1 << xx):
                        intervals.append((along*.5-RADIUS, (along+1)*.5+RADIUS))
                        break
        end = lower
        for lo, hi in sorted(intervals):
            if hi <= end+EPS:
                continue
            # Only touching two expanded edges leaves zero support area there.
            if lo >= end-EPS:
                return False
            if hi > end:
                end = hi
            if end > upper+EPS:
                return True
        return False

    def move(self, a, b):
        if abs(a[0]-b[0]) > EPS and abs(a[2]-b[2]) > EPS:
            return False
        if max(abs(a[0]-b[0]), abs(a[2]-b[2])) > .5+EPS or abs(a[1]-b[1]) > .5+EPS:
            return False
        if not self.standing(b):
            return False
        if a == b:
            return True
        if abs(a[0]-b[0])+abs(a[2]-b[2]) < EPS:
            return False  # No levitation between stacked platforms.
        top = max(a[1], b[1])
        raised_a, raised_b = (a[0], top, a[2]), (b[0], top, b[2])
        return (self.clear_player_sweep(a, raised_a) and
                self.clear_player_sweep(raised_a, raised_b) and
                self.clear_player_sweep(raised_b, b) and self.support_along(a, b))

    def connector(self, a, b):
        """Axis-aligned short connector for exact off-grid endpoint coordinates."""
        if a == b:
            return [a] if self.standing(a) else None
        if any(abs(a[i]-b[i]) > .5+EPS for i in (0, 1, 2)):
            return None
        if not self.standing(a) or not self.standing(b):
            return None
        for axis in (0, 2):
            for middle_y in {a[1], b[1]}:
                middle = list(a)
                middle[axis] = b[axis]
                middle[1] = middle_y
                middle = tuple(middle)
                if self.move(a, middle) and self.move(middle, b):
                    return [a, middle, b]
        return None


def _position(value):
    p = tuple(float(v) for v in value)
    if len(p) != 3 or not all(math.isfinite(v) for v in p):
        raise ValueError('Player feet must be three finite x,y,z coordinates')
    return p


def check_routes(model, start, targets, *, conservative_obstacles=True):
    """Return a JSON-serializable report; failed routes do not raise assertions.

    Half-block graph sampling is conservative and can miss narrow/off-grid
    manoeuvres. A successful report certifies only the listed static walking
    routes within the model bounds under exact shapes or verified enclosing
    obstacles with exact support only. Set conservative_obstacles=False for a
    strict exact-shape-only report; unknown shapes always prevent certification.
    Targets may be a list of positions or a name -> position dictionary.
    """
    start = _position(start)
    named = list(targets.items()) if isinstance(targets, dict) else [(str(i), p) for i, p in enumerate(targets)]
    named = [(str(name), _position(p)) for name, p in named]
    space = _Space(model, conservative_obstacles=conservative_obstacles)
    report = dict(passed=False, method='half_block_graph_swept_player_aabb',
                  size=list(model.size), geometry_sha256=model.fingerprint(),
                  player_width=.6, player_height=1.8, horizontal_grid=.5,
                  maximum_step_up=.5, maximum_step_down=.5, jumps_allowed=False,
                  runtime_verified=False, registry_verified=False,
                  unknown_shapes=[dict(state=s, reason=r, count=n) for (s, r), n in sorted(space.unknown.items())],
                  conservative_obstacles=[dict(state=s, count=n) for s, n in sorted(space.conservative.items())],
                  obstacle_envelope_version=ENVELOPE_VERSION if space.conservative else None,
                  collision_mode='bounded_obstacles_exact_support' if space.conservative else 'exact_half_cells',
                  geometry_supported=not space.unknown and not space.conservative,
                  exact_geometry_supported=not space.unknown and not space.conservative,
                  route_geometry_supported=not space.unknown,
                  support_from_proxies_allowed=False, start=list(start),
                  limitations=['Static collision only; fluids, damage, friction, entities and dynamic block updates are not simulated.',
                               'No jumps, long falls, swimming, climbing, crawling or special movement.',
                               'Half-block sampling may reject a route that requires a finer horizontal manoeuvre.',
                               'Unverified shapes are solid diagnostic proxies and prevent a passing report.',
                               'Verified bounded obstacles use solid supersets for clearance only, never for support; routes through real thin gaps may be missed.'])

    @lru_cache(maxsize=None)
    def standing(node):
        return space.standing(tuple(v*.5 for v in node))

    def anchors(p, forward):
        choices = []
        for i in (0, 2):
            choices.append(sorted({math.floor(p[i]*2+EPS), math.ceil(p[i]*2-EPS)}))
        out = {}
        for x in choices[0]:
            for z in choices[1]:
                for y in (round(p[1]*2), round(p[1]*2)-1, round(p[1]*2)+1):
                    node = (x, y, z)
                    if not standing(node):
                        continue
                    position = tuple(v*.5 for v in node)
                    path = space.connector(p, position) if forward else space.connector(position, p)
                    if path:
                        out[node] = path
        return out

    start_ok = space.standing(start)
    report['start_standing'] = start_ok
    starts = anchors(start, True) if start_ok else {}
    target_anchors = [anchors(p, False) if space.standing(p) else {} for _, p in named]
    parent = {node: None for node in starts}
    source = {node: node for node in starts}
    queue = deque(starts)
    found = {}
    desired = {}
    for i, candidates in enumerate(target_anchors):
        for node in candidates:
            desired.setdefault(node, []).append(i)
    while queue:
        node = queue.popleft()
        for i in desired.get(node, ()):
            found.setdefault(i, node)
        if len(found) == len(named):
            break
        x, y, z = node
        a = (x*.5, y*.5, z*.5)
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (0, 1, -1):
                next_node = (x+dx, y+dy, z+dz)
                if next_node in parent or not standing(next_node):
                    continue
                b = tuple(v*.5 for v in next_node)
                if space.move(a, b):
                    parent[next_node] = node
                    source[next_node] = source[node]
                    queue.append(next_node)
    target_reports = []
    for i, (name, p) in enumerate(named):
        item = dict(name=name, feet=list(p), standing=space.standing(p), reachable=i in found)
        if i in found:
            node = found[i]
            chain = []
            while node is not None:
                chain.append(tuple(v*.5 for v in node))
                node = parent[node]
            chain.reverse()
            path = starts[source[found[i]]][:-1]+chain+target_anchors[i][found[i]][1:]
            # Connector choices can repeat the same pose; remove those duplicates.
            item['path'] = [list(v) for j, v in enumerate(path) if not j or v != path[j-1]]
        else:
            item['reason'] = ('invalid_or_obstructed_feet_pose' if not item['standing'] else
                              'no_safe_half_grid_connector' if not target_anchors[i] else
                              'unreachable_with_walking_and_half_block_steps')
        target_reports.append(item)
    report.update(targets=target_reports, reachable_poses=len(parent),
                  passed=bool(start_ok and starts and len(found) == len(named) and not space.unknown))
    if not start_ok:
        report['failure'] = 'Start has collision, no support, or extends outside model bounds.'
    elif not starts:
        report['failure'] = 'Start cannot safely connect to the half-block sampling grid.'
    elif space.unknown:
        report['failure'] = 'Unsupported collision shapes prevent certification; inspect unknown_shapes.'
    return report
