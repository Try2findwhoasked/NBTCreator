"""Resolve fixed entrance and corner spans before repeating windows."""

from nbt_building.architectural_bay import Writer, contacts, facade_materials, finish, full
from nbt_building.structural_members import generate, grain


def window_row(start, stop, window, pier, *, corner_first):
    """Pack fixed frames with a pier between them, using half-open X intervals."""
    available = stop - start
    count = (available + pier) // (window + pier)
    if not count:
        return [('infill', start, stop)] if available else []
    remainder = available - count * window - (count - 1) * pier
    padding = (remainder + int(corner_first)) // 2
    first_window = start + padding
    segments = [('infill', start, first_window)] if padding else []
    x = first_window
    for index in range(count):
        segments.append(('window', x, x + window))
        x += window
        if index + 1 < count:
            segments.append(('pier', x, x + pier))
            x += pier
    if x < stop:
        segments.append(('infill', x, stop))
    return segments


def fit_error(reason, **measurements):
    from nbt_composition.working_model import ModelConflict
    return ModelConflict('FACADE_FIT_FAILED', [dict(reason=reason, **measurements)])


def compile_contextual_facade(workspace, args):
    if 'bays' in args:
        raise ValueError('contextual 根据净面宽决定窗列数量，不能同时指定 bays')
    scope = args['contextual']
    width = scope['width']
    entry = scope['entry']
    entry_x, entry_width, entry_height = entry['x'], entry['width'], entry['height']
    pier = args.get('pier_width', 2)
    frame_start, frame_stop = entry_x - 1, entry_x + entry_width + 1
    left_available, right_available = frame_start, width - frame_stop
    if min(left_available, right_available) < pier:
        raise fit_error(
            '立面放不下固定入口跨与转角柱', width=width, minimum_width=entry_width + 2 + 2 * pier,
            entry_x=entry_x, entry_frame_x=[frame_start, frame_stop - 1], corner_width=pier,
            left_available=left_available, right_available=right_available,
            allowed_entry_x=[pier + 1, width - pier - entry_width - 1],
        )

    window_width, window_height = args.get('opening', [3, 4])
    sill_height = args.get('sill_height', 2)
    beam_height = args.get('lintel_height', 1)
    beam_y = sill_height + window_height + 1
    pitch = beam_y + beam_height
    storeys = args.get('storeys', 2)
    if entry_height >= beam_y:
        raise fit_error('入口横框须在连续梁下方', height=entry_height, maximum_height=beam_y - 1, beam_y=beam_y)
    if storeys * pitch > 64:
        raise fit_error('立面总高超过64格', storeys=storeys, storey_pitch=pitch, height=storeys * pitch, maximum_height=64)

    # Each window owns both jambs. Columns and infill meet frames at their edges.
    window_span = window_width + 2
    left = window_row(pier, frame_start, window_span, pier, corner_first=True)
    right = window_row(frame_stop, width - pier, window_span, pier, corner_first=False)
    segments = [('corner', 0, pier), *left, ('entry', frame_start, frame_stop),
                *right, ('corner', width - pier, width)]
    recess = args.get('recess', 1)
    depth = recess + 2
    glazing = args.get('glazing', True)
    material, trim, glass, sill = facade_materials(args)
    column = grain(full(scope.get('column_material', trim)), 'y')
    beam = full(scope.get('beam_material', trim))
    writer = Writer([width, storeys * pitch, depth])

    def emit(kind, form, size, origin, part, primary, *, wall=False, window_sill=None):
        def box(lo, hi, value):
            writer.box([a + b for a, b in zip(lo, origin)], [a + b for a, b in zip(hi, origin)],
                       value, part, wall)
        generate(kind, form, size, box, primary, trim, window_sill=window_sill)

    def infill(part, start, stop, bottom, top):
        if bottom <= top:
            writer.box([start, bottom, 1], [stop - 1, top, depth - 1], material, part, True)

    openings = [dict(id='entry', kind='entry', lo=[entry_x, 0, 0],
                     hi=[entry_x + entry_width - 1, entry_height - 1, depth - 1])]
    pairs = []
    for storey in range(storeys):
        base = storey * pitch
        top = base + beam_y - 1
        beam_part = f'beam_{storey}'
        emit('beam', {'profile': 'rectangular'}, [width, beam_height, depth],
             [0, top + 1, 0], beam_part, beam)
        parts = [f'{role}_{storey}_{index}' for index, (role, _, _) in enumerate(segments)]
        pairs.extend((part, beam_part) for part in parts)
        if storey:
            pairs.extend((part, f'beam_{storey - 1}') for part in parts)
        for index, (role, start, stop) in enumerate(segments):
            part = parts[index]
            if role in ('corner', 'pier'):
                writer.box([start, base, 0], [stop - 1, top, depth - 1], column, part)
            elif role == 'entry' and storey == 0:
                emit('frame', {'profile': 'doorway', 'frame_depth': depth},
                     [stop - start, entry_height + 1, depth], [start, base, 0], part, trim)
                infill(part, start, stop, base + entry_height + 1, top)
            elif role == 'window':
                bottom = base + sill_height
                infill(part, start, stop, base, bottom - 2)
                emit('frame', dict(profile='recessed_window', recess=recess, glazing=glazing, glass_material=glass),
                     [window_span, window_height + 2, depth], [start, bottom - 1, 0], part, trim,
                     wall=True, window_sill=sill)
                openings.append(dict(id=part, kind='window', lo=[start + 1, bottom, 0],
                                     hi=[stop - 2, bottom + window_height - 1, depth - 1]))
                pairs.extend(((part, parts[index - 1]), (part, parts[index + 1])))
            else:
                infill(part, start, stop, base, top)

    joints = [dict(first=a, second=b, face_contact=contacts(writer, a, b)) for a, b in pairs]
    missing = [f"{row['first']} / {row['second']}" for row in joints if not row['face_contact']]
    if missing:
        raise ValueError('立面构件未相接：' + ', '.join(missing))
    return finish(
        workspace, writer, args, '带入口跨的凹窗立面', kind='facade',
        openings=openings, front='north_-z', glazing=glazing,
        resolved_form=dict(width=width, bays=sum(role == 'window' for role, _, _ in segments),
                           storeys=storeys, opening=[window_width, window_height], pier_width=pier,
                           storey_pitch=pitch, recess=recess,
                           flank_widths=[left_available - pier, right_available - pier],
                           layout=[dict(role=role, x=[start, stop - 1]) for role, start, stop in segments]),
        construction_graph=dict(joints=joints, connectivity='actual_final_halfcube_faces'),
    )
