"""Discoverable recipes, not generated assets or authoring approvals."""
from copy import deepcopy


def library(kind=None):
    rows = []
    def add(identifier, name, category, object_kind, size, **parameters):
        rows.append(dict(id=identifier, name=name, category=category,
                         arguments=dict(kind=object_kind, size=size, name=name, **parameters)))

    for section, name in [('square', '方柱'), ('cross', '十字柱'),
                          ('octagonal', '八角柱'), ('bundled', '束柱')]:
        add('pillar-'+section, name, '柱与基座', 'pillar', [9, 18, 9],
            form=dict(section=section, base_height=3, capital_height=3,
                      base_profile='stepped', capital_profile='beveled'))
    add('pillar-banded', '分带石柱', '柱与基座', 'pillar', [9, 20, 9],
        form=dict(section='octagonal', base_height=3, capital_height=3, band_spacing=4))
    add('pillar-round', '素面圆柱', '柱与基座', 'pillar', [9, 20, 9],
        form=dict(section='round', base_height=3, capital_height=3, shaft_ratio=.9))
    for order, name in [('tuscan', '托斯卡纳启发柱'), ('roman_doric', '罗马多立克启发柱'),
                        ('ionic', '爱奥尼启发柱'), ('corinthian', '科林斯启发柱'), ('composite', '复合柱式启发柱')]:
        add('pillar-'+order.replace('_', '-'), name, '柱与基座', 'pillar', [13, 48, 13],
            material='quartz_block', accent='smooth_sandstone', form=dict(order=order))
    for shape, size, name in [('straight', [7, 12, 13], '直梯'),
                               ('quarter_turn', [15, 12, 12], '转角梯'),
                               ('switchback', [13, 12, 12], '折返梯'),
                               ('spiral', [18, 12, 15], '方形旋梯')]:
        for style, label in [('baluster', '立柱扶手'), ('panel', '实心栏板'), ('lattice', '格构扶手')]:
            add('stairs-'+shape.replace('_', '-')+'-'+style, name+' · '+label, '楼梯与护栏', 'stairs', size,
                form=dict(profile=shape, run_width=3, rise=8, landing=3,
                          handrail=dict(side='both', style=style, height=3 if style=='lattice' else 2, post_spacing=3)))
    for profile, name in [('baluster', '立柱栏杆'), ('panel', '实心栏板'),
                          ('lattice', '格构栏杆'), ('horizontal', '横档栏杆')]:
        add('railing-'+profile, name, '楼梯与护栏', 'railing', [13, 5, 3],
            form=dict(profile=profile, pitch=3))
    add('railing-sloped', '斜坡扶手段', '楼梯与护栏', 'railing', [13, 9, 3],
        form=dict(profile='baluster', slope=4, pitch=3))
    groups = [('beam', [13, 4, 5], '梁与承托', [('solid', '整梁'), ('coffered', '格构梁'), ('braced', '加腋梁')]),
              ('bracket', [5, 7, 7], '梁与承托', [('stepped', '叠涩托架'), ('curved', '弧形托架'), ('diagonal', '斜撑托架')]),
              ('arch', [13, 12, 3], '洞口与边框', [('round', '圆拱框'), ('pointed', '尖拱框'), ('flat', '平拱框')]),
              ('frame', [11, 13, 3], '洞口与边框', [('rectangular', '素面门窗框'), ('crosslight', '十字窗框'), ('mullioned', '竖梃窗框')]),
              ('pedestal', [9, 5, 9], '柱与基座', [('square', '方形基座'), ('stepped', '层叠基座'), ('round', '圆形基座')])]
    for object_kind, size, category, profiles in groups:
        for profile, name in profiles:
            add(object_kind+'-'+profile, name, category, object_kind, size, form=dict(profile=profile))
    for object_kind, size, name in [('table', [7, 4, 5], '工作桌'), ('bench', [9, 5, 4], '靠背长凳'),
                                   ('shelf', [9, 11, 4], '多层书架'), ('lantern', [5, 9, 5], '落地灯架')]:
        add(object_kind+'-classic', name, '家具与陈设', object_kind, size)
    for shape, name in [('upright', '直立盆栽'), ('trailing', '垂挂盆栽'), ('climbing', '攀援盆栽')]:
        add('plant-'+shape, name, '家具与陈设', 'plant', [7, 10, 7],
            form=dict(profile=shape, pot_height=2, crown_height=5, radius=2))
    add('planter-row', '连续花槽', '家具与陈设', 'planter', [15, 8, 5])
    for shape, name in [('grid', '井字吊顶'), ('parallel', '平行梁吊顶')]:
        add('ceiling-'+shape, name, '墙面与吊顶', 'ceiling', [13, 4, 13], form=dict(profile=shape, drop=2, pitch=4))
    add('wall-wainscot', '墙裙与檐口', '墙面与吊顶', 'wall', [15, 12, 3],
        form=dict(base_height=2, dado_height=5, cornice_height=2, panel_pitch=4))
    return deepcopy([row for row in rows if kind is None or row['arguments']['kind'] == kind])
