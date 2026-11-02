"""Conservative, explicit-scope connector resolution on a complete author model."""
from nbt_registry import effective, normalize, registry

DIRECTIONS = dict(north=(0, 0, -1), east=(1, 0, 0), south=(0, 0, 1), west=(-1, 0, 0))
# Only ordinary opaque full-side blocks; never infer this from a rendering model.
FULL_FACES = set('stone granite polished_granite diorite polished_diorite andesite polished_andesite '
                 'cobblestone mossy_cobblestone stone_bricks mossy_stone_bricks cracked_stone_bricks '
                 'chiseled_stone_bricks deepslate cobbled_deepslate polished_deepslate deepslate_bricks '
                 'deepslate_tiles bricks mud_bricks sandstone red_sandstone quartz_block smooth_quartz '
                 'blackstone polished_blackstone polished_blackstone_bricks nether_bricks red_nether_bricks '
                 'end_stone end_stone_bricks dirt grass_block bedrock obsidian'.split())
FULL_FACES.update(name.removeprefix('minecraft:') for name in registry()['blocks'] if name.endswith('_planks'))


def family(name):
    short = name.removeprefix('minecraft:')
    if short == 'iron_bars' or short == 'glass_pane' or short.endswith('_stained_glass_pane'):
        return 'pane'
    if short == 'nether_brick_fence':
        return 'nether_fence'
    if short.endswith('_fence'):
        return 'wood_fence'
    return None


def resolve_connections(model, wall_positions=()):
    """Fill missing connector fields only; explicit fields are retained as authored.

    Ambiguous neighbours require an explicit field or a game-backed extension.
    Plan all writes first so a failed resolution leaves source and wall mask intact.
    Run before sealing, after geometry; never independently on already-cut pieces.
    """
    if model.stage != 'design':
        raise ValueError('Resolve on the complete design before sealing/freezing')
    walls = set(map(tuple, wall_positions))
    changes, unresolved = [], []
    for p, value in sorted(model.blocks.items()):
        name, effective_props = effective(value)
        group = family(name)
        if group is None:
            continue
        _, _, tail = normalize(value).partition('[')
        authored = dict(item.split('=') for item in tail.rstrip(']').split(',') if item)
        props = dict(authored)
        for direction, delta in DIRECTIONS.items():
            if direction in authored:
                continue
            q = tuple(p[i] + delta[i] for i in range(3))
            other, _ = effective(model.get(q))
            other_group = family(other)
            short = other.removeprefix('minecraft:')
            if short in FULL_FACES or other_group == group:
                connected = True
            elif other_group is not None or short in ('air', 'cave_air', 'void_air', 'water', 'lava'):
                connected = False
            else:
                unresolved.append(dict(position=list(p), direction=direction, neighbour=other))
                continue
            props[direction] = str(connected).lower()
        props.setdefault('waterlogged', effective_props['waterlogged'])
        after = normalize(dict(Name=name, Properties=props))
        if after != value:
            changes.append(dict(position=list(p), before=value, after=after))
    if unresolved:
        raise ValueError('Unsupported neighbour connections; explicitly author these fields: ' + str(unresolved[:20]))
    for change in changes:
        model.put(change['position'], change['after'])
    # If WallMask is active, mark these same-owner state-only writes again.
    return dict(changed_blocks=len(changes), changes=changes,
                wall_positions=sorted(walls), explicit_fields_preserved=True,
                scope='missing horizontal pane/bar/fence fields; no stairs, walls, gates, fluids or runtime updates')
