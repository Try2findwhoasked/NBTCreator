"""Two rough circulations for the same reading-loft programme."""

from plan import reading_loft


def reading_loft_layouts():
    plan = reading_loft()
    plan['envelope']['glazing'] = []
    plan['parts'] = [part for part in plan['parts']
                     if part['id'] in ('threshold', 'loft', 'return_desk', 'archive_cabinet')]
    loft = next(part for part in plan['parts'] if part['id'] == 'loft')
    arguments = loft['recipe']['arguments']
    operations = arguments['operations']
    arguments['size'][0] = 9
    for operation in operations:
        for key in ('lo', 'hi'):
            operation[key][0] = min(operation[key][0], 8)
    # Leave a three-block side landing for comparing a second approach.
    for operation in operations.copy():
        if operation['label'] in ('平台东侧矮护墙', '护墙压顶'):
            operations.remove(operation)
            for lo, hi in ((0, 1), (5, 6)):
                operations.append(dict(operation, lo=[8, operation['lo'][1], lo],
                                       hi=[8, operation['hi'][1], hi]))
    plan['views'] = [view for view in plan['views'] if view['id'] in ('outside', 'entry_player', 'counter')]
    plan.pop('review_locations')
    plan['requirements'][0].pop('review_locations')
    plan.pop('quality')

    front_foot = [5.5, 2, 5.5]
    plan['spaces'][0].update(lo=[2, 2, 5], samples=[[13.5, 2, 8.5], front_foot])
    plan['spaces'][1]['hi'][0] = 10
    plan['spaces'].append(dict(id='entry_bay', purpose='从门槛进入收卷厅', lo=[9, 2, 3], hi=[11, 9, 4],
                               feet_y=2, samples=[[10.5, 2, 4.5]]))
    plan['activities'][0]['stops'][1]['feet'] = front_foot
    plan['stairs'][0]['operation'].update(lo=[3, 1, 5], start=[5, 2, 5])

    desk, stair_foot, landing = [6.5, 2, 10.5], [17.5, 2, 22.5], [7.5, 5, 22.5]
    return dict(plan=plan, graph=dict(edges=[
        dict(id='entry_to_hall', kind='adjacent', spaces=['entry_bay', 'hall']),
        dict(id='hall_to_loft', kind='vertical', spaces=['hall', 'loft'], activity='file_books', segment=1),
    ], variants=[
        dict(id='front'),
        dict(id='side',
             spaces=[dict(id='hall', hi=[18, 9, 25], samples=[desk, stair_foot]),
                     dict(id='loft', samples=[landing, [5.5, 5, 23.5]])],
             parts=[dict(id='return_desk', position=[8, 2, 9], quarter_turns=2)],
             stairs=[dict(id='archive_stair', lo=[8, 1, 20], hi=[17, 7, 24],
                          start=[17, 2, 22], end=[8, 5, 22], width=1)],
             stops=[dict(activity='file_books', index=i, feet=pose)
                    for i, pose in enumerate((desk, stair_foot, landing))],
             route_targets=[dict(id='return_desk', feet=desk), dict(id='stair_landing', feet=landing)]),
        dict(id='blocked', parts=[dict(id='archive_cabinet', position=[4, 5, 19])]),
        dict(id='wrong-side', stops=[dict(activity='file_books', index=0, feet=[13.5, 2, 11.5])]),
    ]), areas=[dict(space='hall', minimum=238, maximum=357), dict(space='loft', minimum=63, maximum=63)])
