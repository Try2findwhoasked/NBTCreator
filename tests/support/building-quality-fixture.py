"""Prepare the loft control group and independent buildings for rendered assessment."""
from copy import deepcopy
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / '.agents/skills/minecraft-nbt-modeler'
sys.path[:0] = [str(SKILL / 'scripts'), str(SKILL / 'assets/examples/reading-loft')]

from courtyard import courtyard
from plan import box, part, reading_loft
from nbt_building.workflow import dispatch


def loft_variants():
    plan = reading_loft()
    variants = {name: deepcopy(plan) for name in ('palette', 'joint', 'rear')}
    variants['palette']['envelope']['wall'] = 'white_terracotta'
    cabinet = next(row for row in variants['joint']['parts'] if row['id'] == 'archive_cabinet')
    cabinet['recipe']['arguments']['operations'][-1]['hi'][0] = 1
    roof = next(row for row in variants['rear']['parts'] if row['id'] == 'tiled_roof')
    for operation in roof['recipe']['arguments']['operations']:
        if operation['label'] == '山面封檐木' and operation['lo'][2] > 2:
            operation['state'] = 'calcite'
    return dict(open=plan, **variants)


def quantitative_style_variants():
    plan = reading_loft()
    members = []
    for n, z in enumerate((4, 10, 16), 1):
        name = f'ceiling_beam_{n}'
        plan['parts'].append(part(name, 'frame', [9, 8, z], [
            box('量化验证横梁', [0, 0, 0], [2, 0, 0], 'stripped_spruce_log[axis=x]')
        ]))
        target = dict(lo=[9, 8, z], hi=[11, 8, z])
        members.append(dict(part=name, roles=['frame'], boxes=[target]))
    members[-1]['variants'] = [dict(id='extended_end', boxes=[dict(lo=[9, 8, 18], hi=[11, 8, 18])])]
    plan['quality'].update(revision='longitudinal-beams-1', style=[
        dict(id='beam_rhythm', goal='由低厅向后保持木梁节奏，末跨可加宽', sites=[
            dict(id='ceiling', goal='横梁按六格节距排列，末跨允许移至 Z 18',
                 target=dict(part='ceiling_beam_2'), quantitative=dict(
                    region=dict(lo=[8, 7, 1], hi=[12, 9, 24]), members=members,
                    bands=[dict(kind='lowpass', high=.10), dict(kind='highpass', low=.25),
                           dict(kind='bandpass', low=.15, high=.18)])),
        ])
    ])
    shifted, allowed, material = (deepcopy(plan) for _ in range(3))
    shifted['parts'][-2]['position'][2] += 1
    allowed['parts'][-1]['position'][2] = 18
    for beam in material['parts'][-3:]:
        beam['recipe']['arguments']['operations'][0]['state'] = 'polished_andesite'
    return dict(reference=plan, shifted=shifted, allowed_end=allowed, wrong_material=material)


def held_out():
    def criterion(identifier, goal, *views):
        return dict(id=identifier, goal=goal, views=list(views))

    def leg(identifier, turn, way, purpose, *views):
        return dict(id=identifier, criteria=[
            criterion('turning_stops', turn, *views),
            criterion('wayfinding', way, *views),
            criterion('purpose_fit', purpose, *views),
        ])

    def details(identifier, part, view, relation, joint, use):
        return dict(id=identifier, target=dict(part=part), criteria=[
            criterion('relationships', relation, view),
            criterion('joints', joint, view),
            criterion('legibility', use, view),
        ])

    def aesthetic(identifier, goal, part, *views):
        return dict(criterion(identifier, goal, *views), target=dict(part=part))

    yard = courtyard()
    yard['requirements'] = [
        dict(id='visitor_delivery', text='访客由主街进院，在阅览室案前交卷', origin='design',
             reason='主次建筑应各有入口，访客走主路', spaces=['yard', 'hall'], parts=['lane', 'portal', 'desk']),
        dict(id='lodge_rest', text='值房提供独立落脚和坐具', origin='design',
             reason='设值房供人员短时值守', spaces=['lodge'], parts=['guard_seat']),
    ]
    yard['rules'] = [dict(id='lane_span', kind='extent', parts=['lane'], expected_size=[3, 1, 11])]
    yard['quality'] = dict(rubric='building-quality-v1', revision='courtyard-1', stage='draft',
        requirements=[
            dict(id='visitor_delivery', required=True, stage='draft', goal='主路连续，访客可以在案前交卷',
                 checks=[dict(id='visitor', kind='activity_routes'), dict(id='lane_span', kind='extent')],
                 views=['district', 'turn', 'entrance', 'intake']),
            dict(id='lodge_rest', required=False, stage='draft', goal='值房有落脚点及长凳',
                 checks=[dict(id='lodge', kind='space_samples'), dict(id='guard_seat', kind='part_presence')]),
        ],
        aesthetics=[
            aesthetic('massing', '值房低、正厅高，主路与两栋体量主次清楚', 'hall_roof', 'district', 'turn'),
            aesthetic('hierarchy', '院路汇向正厅入口，值房由分支进入', 'portal', 'district', 'entrance'),
        ],
        activities=[dict(id='visitor', required=True, requirements=['visitor_delivery'], segments=[
            leg('street_to_turn', '街边有横向转身空间', '石带标示院路入口', '访客沿街可直接转入院路', 'turn'),
            leg('turn_to_door', '入口前留有独立落脚点', '路面正对门跨', '主路避开值房绕行', 'turn', 'entrance'),
            leg('door_to_desk', '案前有等候与转身空间', '门内可识别案前方向', '越过石槛可在案前交卷', 'intake'),
        ])],
        style=[dict(id='stone_approach', goal='街道与主要入口之间保留显式石质分区', sites=[
            dict(id='lane', target=dict(part='lane'), goal='院路保留三格宽的石带', rule='lane_span'),
            dict(id='portal', target=dict(part='portal'), goal='对称石座支承木门柱', views=['entrance']),
        ])],
        details=[details('portal', 'portal', 'entrance', '石座、门柱及门额尺度明确',
                         '柱根与石座相接，石槛平整', '人站在院路上能明确识别门跨'),
                 details('intake', 'desk', 'intake', '浅色案面搭在两侧支脚上',
                         '两端案面齐平收口', '能辨认正面案沿与交卷站位')])

    factory = runpy.run_path(str(ROOT / 'tests/engine/architecture-workflow.py'))['plan']
    hall = factory()
    hall['name'] = '折角铜顶展馆'
    hall['envelope']['volumes'][0].update(polygon=[[2, 2], [26, 2], [26, 25], [20, 25], [20, 28], [2, 28]])
    hall['envelope']['volumes'][0]['roof'].update(kind='hip', rise=4)
    hall['envelope']['interfaces'][0].update(lo=[21, 11, 21], hi=[23, 16, 23])
    hall['style']['materials']['roof'] = 'oxidized_cut_copper'
    hall['stairs'][0]['railing'] = dict(state='stone_brick_wall', kerb_material='stone_bricks')
    hall['views'][2].update(id='bearing', feet=[18.5, 2, 13.5], target_part='right')
    hall['views'].append(dict(id='entry_player', layer='structure', feet=[15.5, 2, .5],
                              target=[15.5, 5, 12], fov=73, minimum_visible=.08))
    hall['requirements'] = [dict(id='exhibition_gallery', text='从展厅登高到阅览廊',
        origin='design', reason='首层展示及二层阅览采用连续观展动线', parts=['gallery_stair','platform'],
        spaces=['hall','gallery'])]
    hall['activities'] = [dict(id='visitor', actor='观展者', purpose='由厅内登阶到阅览廊',
        stops=[dict(space='hall', feet=[15.5, 2, 8.5]), dict(space='gallery', feet=[6.5, 5, 22.5])])]
    hall['quality'] = dict(rubric='building-quality-v1', revision='exhibition-1', stage='draft',
        requirements=[dict(id='exhibition_gallery', required=True, stage='draft', goal='阶梯与上层廊道连续可达',
            checks=[dict(id='gallery_stair', kind='stair_segments'), dict(id='visitor', kind='activity_routes')],
            views=['entry_player', 'bearing'])],
        aesthetics=[
            aesthetic('massing', '高铜顶下的折角展厅比例完整', 'envelope', 'overall', 'entry_player'),
            aesthetic('materials_light', '铜绿屋顶与石墙层次分明', 'envelope', 'overall', 'entry_player'),
        ],
        activities=[dict(id='visitor', required=True, requirements=['exhibition_gallery'],
            segments=[leg('hall_to_gallery', '楼梯两端留出停靠与转向空间', '入口跨可辨识登廊方向',
                          '动线允许观展者自主登廊', 'entry_player', 'beam')])],
        style=[dict(id='stone_and_copper', goal='厚石墙围护，铜顶统一收口', sites=[
            dict(id='roof', target=dict(part='envelope'), goal='折角上方铜绿屋盖连续', views=['overall']),
        ])],
        details=[details('support', 'right', 'bearing', '左右柱墩与高度错落的横梁有明确支承关系',
                         '石梁应落到柱墩实面', '从展厅中能读出木石构造的主支承')])
    return dict(courtyard=yard, exhibition=hall)


def prepare(workspace, variants):
    bindings = {}
    for label, candidate in variants.items():
        result = dispatch(workspace, 'plan-build', dict(plan=candidate, save_draft=dict(name_zh=candidate['name'] + '-' + label)))
        binding = {key: result['saved'][key] for key in ('source', 'source_sha256')}
        pack = dispatch(workspace, 'review-prepare', dict(binding, output='nbt_models/_workspaces/reviews/' + label))
        bindings[label] = dict(binding, render_command=pack['render_command'], **pack['review_record_bindings'])
    return bindings


if __name__ == '__main__':
    plans = quantitative_style_variants() if '--style' in sys.argv else held_out() if '--held-out' in sys.argv else loft_variants()
    print(json.dumps(prepare(Path(sys.argv[1]).resolve(), plans), ensure_ascii=True))
