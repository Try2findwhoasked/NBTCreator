"""窗边收卷，登梯归架。两个样例共用构造、脚位和审阅机位。"""
from math import ceil


def box(label, lo, hi, state):
    return dict(kind="box", label=label, classification="body", lo=lo, hi=hi, state=state)


def part(identifier, role, position, operations, interfaces=None):
    size = [max(op["hi"][axis] for op in operations) + 1 for axis in range(3)]
    result = dict(id=identifier, role=role, position=position, recipe=dict(
        tool="structure", arguments=dict(name=identifier, size=size, anchor=[0, 0, 0], operations=operations)))
    if interfaces:
        result["interfaces"] = interfaces
    return result


def tiled_gable(identifier, lo_xz, hi_xz, eaves, rise, axis="z", tile="deepslate_tile"):
    """Add a continuous half-step roof covering to a gabled enclosure."""
    cross_axis = 0 if axis == "z" else 1
    width = hi_xz[cross_axis] - lo_xz[cross_axis] + 1
    length = hi_xz[1 - cross_axis] - lo_xz[1 - cross_axis] + 1
    heights = [-1, 0] + [ceil(rise * (1 - abs(2 * x + 1 - width) / width)) for x in range(width)] + [0, -1]
    operations = []
    for x, height in enumerate(heights):
        inward = x + 1 if x < (len(heights) - 1) / 2 else x - 1
        state = f"{tile}_slab[type=bottom]"
        if heights[inward] > height:
            positive, negative = ("east", "west") if axis == "z" else ("south", "north")
            state = f"{tile}_stairs[facing={positive if inward > x else negative},half=bottom]"
        strips = [("瓦面", height + 2, 0, length + 3, state),
                  ("山面封檐木", height + 1, 0, 1, "dark_oak_planks"),
                  ("山面封檐木", height + 1, length + 2, length + 3, "dark_oak_planks")]
        if x in (0, len(heights) - 1):
            strips.append(("通长檐口", height + 1, 2, length + 1, "dark_oak_planks"))
        for label, y, start, end, material in strips:
            lo, hi = [x, y, start], [x, y, end]
            if axis == "x":
                lo, hi = lo[::-1], hi[::-1]
            operations.append(box(label, lo, hi, material))
    return part(identifier, "roof", [lo_xz[0] - 2, eaves - 1, lo_xz[1] - 2], operations)


def reading_loft(blocked=False, wrong_side=False):
    timber = {"design_ref": "style.materials.frame"}
    beam = "stripped_spruce_log[axis=x]"
    trim = "dark_oak_slab[type=bottom]"
    cabinet = [4, 5, 19] if blocked else [4, 5, 24]
    counter_feet = [13.5, 2, 8.5]
    stair_foot = [5.5, 2, 4.5]
    landing = [5.5, 5, 19.5]
    shelf_feet = [5.5, 5, 23.5]

    front = [box("门窗共用横枋", [0, 5, 0], [16, 5, 0], beam)]
    for x in (0, 5, 6, 10, 11, 16):
        front.append(box("窗边柱与门柱", [x, 0, 0], [x, 4, 0], timber))
    for x in (1, 12):
        front.append(box("窗下外挑石台", [x, 1, 0], [x + 3, 1, 0], "smooth_stone_slab[type=top]"))
    front.append(box("山面中柱", [8, 6, 0], [8, 10, 0], timber))
    for x in (3, 13):
        front.append(box("山面短柱", [x, 6, 0], [x, 8, 0], timber))

    parts = [
        part("threshold", "floor", [1, 1, 0], [
            box("门外踏面", [6, 0, 0], [12, 0, 0], "smooth_stone"),
            box("门柱窗柱石座", [0, 0, 1], [18, 0, 1], "smooth_stone"),
            box("门洞地面与正墙勒脚", [0, 0, 2], [18, 0, 2], "smooth_stone"),
            box("西墙勒脚", [0, 0, 3], [0, 0, 25], "smooth_stone"),
            box("东墙勒脚", [18, 0, 3], [18, 0, 25], "smooth_stone"),
            box("后墙勒脚", [0, 0, 26], [18, 0, 26], "smooth_stone"),
        ]),
        part("front_frame", "frame", [2, 2, 1], front),
        tiled_gable("tiled_roof", [2, 3], [18, 25], 9, 4),
        part("ridge_purlin", "frame", [10, 12, 3], [
            box("短柱上的纵向脊檩", [0, 0, 0], [0, 0, 22], "stripped_spruce_log[axis=z]"),
        ]),
        part("loft", "floor", [2, 2, 19], [
            box("夹层后柱", [0, 0, 5], [0, 1, 5], timber),
            box("夹层前柱", [9, 0, 0], [9, 1, 0], timber),
            box("平台前缘梁", [0, 1, 0], [8, 1, 0], beam),
            box("阅览平台", [0, 2, 0], [9, 2, 6], "spruce_planks"),
            box("平台东侧矮护墙", [9, 3, 0], [9, 3, 6], "spruce_planks"),
            box("护墙压顶", [9, 4, 0], [9, 4, 6], trim),
            box("梯口东侧护边", [5, 3, 0], [8, 3, 0], "spruce_planks"),
        ]),
        part("return_desk", "furniture", [12, 2, 9], [
            box("左端柜脚", [0, 0, 0], [0, 0, 1], "dark_oak_planks"),
            box("右端柜脚", [4, 0, 0], [4, 0, 1], "dark_oak_planks"),
            box("收卷薄台面", [0, 1, 0], [4, 1, 0], {"design_ref": "style.materials.counter"}),
            box("后排托板", [0, 1, 1], [4, 1, 1], "birch_planks"),
            box("左侧板", [0, 2, 1], [0, 2, 1], "spruce_planks"),
            box("分卷隔板", [2, 2, 1], [2, 2, 1], "spruce_planks"),
            box("右侧板", [4, 2, 1], [4, 2, 1], "spruce_planks"),
            box("两格共用层板", [0, 3, 1], [4, 3, 1], "spruce_slab[type=bottom]"),
        ], interfaces=[dict(id="intake", face="north", lo=[0, 1, 0], hi=[4, 1, 0])]),
        part("archive_cabinet", "furniture", cabinet, [
            box("书柜下层与上层", [0, 0, 0], [2, 1, 0], "bookshelf"),
            box("柜顶木压条", [0, 2, 0], [2, 2, 0], trim),
        ], interfaces=[dict(id="shelves", face="north", lo=[0, 0, 0], hi=[2, 1, 0])]),
    ]
    for z in (6, 14):
        parts.append(part(f"bent_{z}", "frame", [2, 2, z], [
            box("西柱", [0, 0, 0], [0, 6, 0], timber),
            box("东柱", [16, 0, 0], [16, 6, 0], timber),
            box("跨厅梁", [0, 7, 0], [16, 7, 0], beam),
            box("承脊短柱", [8, 8, 0], [8, 9, 0], timber),
            box("西柱托木", [1, 6, 0], [1, 6, 0], "spruce_stairs[facing=west,half=top]"),
            box("东柱托木", [15, 6, 0], [15, 6, 0], "spruce_stairs[facing=east,half=top]"),
        ]))
    windows = [dict(lo=[x, 4, 2], hi=[x + 3, 6, 2], state="glass") for x in (3, 14)]
    windows.extend(dict(lo=[19, 3, z], hi=[19, 6, z + 3], state="glass") for z in (7, 15))
    plan = dict(
        schema_version=1, name="归卷阁", size=[21, 16, 28],
        style=dict(name="木架灰瓦阅览阁", materials=dict(frame="stripped_spruce_log", counter="birch_slab[type=bottom]")),
        context=dict(mode="standalone", openings=[dict(id="entry", lo=[9, 2, 2], hi=[11, 5, 2], facing="north")],
                     interior_probes=[[10, 4, 8], [6, 7, 21]], start=[10.5, 2, 0.5], require_routes=True,
                     targets=dict(return_desk=counter_feet, stair_landing=landing, archive_shelf=shelf_feet)),
        envelope=dict(wall="calcite", floor="smooth_stone", roof="deepslate_tiles", glazing=windows,
                      volumes=[dict(id="hall", lo_xz=[2, 3], hi_xz=[18, 25], feet_y=2, eaves_y=9,
                                    roof=dict(kind="gable", rise=4, axis="z"))]),
        spaces=[dict(id="hall", purpose="进门收卷、转身上楼", lo=[2, 2, 3], hi=[18, 9, 18], feet_y=2,
                     samples=[counter_feet, stair_foot]),
                dict(id="loft", purpose="梯顶转身、近柜归架", lo=[2, 5, 19], hi=[11, 9, 25], feet_y=5,
                     samples=[landing, shelf_feet])],
        requirements=[dict(id="return_books", text="在窗边收卷，由管理员登梯归架", origin="user",
                           reason="示例任务给定的工作顺序", spaces=["hall", "loft"],
                           parts=["return_desk", "archive_cabinet"], review_locations=["desk_edge", "shelf_face", "stair_exit"])],
        activities=[dict(id="file_books", actor="管理员", purpose="从收卷台登梯到柜前",
                         stops=[dict(space="hall", feet=[13.5, 2, 11.5] if wrong_side else counter_feet,
                                     use_face=dict(part="return_desk", interface="intake", height=1.25, max_distance=1)),
                                dict(space="hall", feet=stair_foot), dict(space="loft", feet=landing),
                                dict(space="loft", feet=shelf_feet,
                                     use_face=dict(part="archive_cabinet", interface="shelves", height=1.25, max_distance=1))])],
        parts=parts,
        stairs=[dict(id="archive_stair", kind="stair_system", foundation_y=2, support_spacing=4, support_material=timber,
                     railing=dict(state="spruce_fence", kerb_material="spruce_planks"),
                     operation=dict(kind="auto_stairs", label="归架梯", classification="body", lo=[3, 1, 4],
                                    hi=[7, 7, 18], start=[5, 2, 4], end=[5, 5, 18], width=3,
                                    mode="straight", state="smooth_stone", slab_state="smooth_stone_slab[type=bottom]"))],
        views=[dict(id="outside", layer="massing", eye=[29, 17, -29], target=[10, 5, 12], fov=46),
               dict(id="window", layer="detail", eye=[1, 4.6, -6], target_part="front_frame", target=[5.8, 4.4, 2], fov=62),
               dict(id="frame", layer="structure", feet=[9.5, 2, 11.5], target_part="bent_14", target=[14.5, 8, 14], fov=78),
               dict(id="counter", layer="detail", feet=[10.5, 2, 6.5], target_part="return_desk", fov=65),
               dict(id="landing", layer="detail", feet=[5.5, 5, 22.5], target_part="archive_stair", target=[5.5, 4, 15], fov=75),
               dict(id="cabinet", layer="detail", feet=[7.5, 5, 21.5], target_part="archive_cabinet", fov=65)],
        review_locations=[dict(id="window_reveal", purpose="柱后窗洞与外挑窗台", position=[5.5, 4.5, 2], views=["window"]),
                          dict(id="beam_seat", purpose="柱头托木与跨厅梁交接", position=[17.8, 8.7, 14], views=["frame"]),
                          dict(id="desk_edge", purpose="台面薄边与台前站位", position=[13.5, 3.5, 9], views=["counter"]),
                          dict(id="stair_exit", purpose="梯顶与平台交接净空", position=[5.5, 5.1, 19.5], views=["landing"]),
                          dict(id="shelf_face", purpose="书格使用面与压顶", position=[5.5, 6.1, 24], views=["cabinet"])],
    )
    plan["views"].extend([
        dict(id="entry_player", layer="structure", feet=[10.5, 2, .5], target=[10.5, 4.5, 6.5], fov=75,
             minimum_visible=.1),
        dict(id="rear_eaves", layer="structure", eye=[27, 13, 35], target=[10, 9, 25], target_part="tiled_roof",
             fov=65, minimum_visible=.1),
    ])
    plan["quality"] = quality_checklist()
    return plan


def quality_checklist():
    def standard(name, goal, views):
        return dict(id=name, target=dict(position=[10.5, 5, 8]), goal=goal, views=views)

    def detail(identifier, position, view, relationship, joint, use):
        return dict(id=identifier, target=dict(position=position), criteria=[
            dict(id="relationships", goal=relationship, views=[view]),
            dict(id="joints", goal=joint, views=[view]),
            dict(id="legibility", goal=use, views=[view]),
        ])

    def leg(identifier, views, turn, wayfinding, purpose):
        return dict(id=identifier, criteria=[
            dict(id="turning_stops", goal=turn, views=views),
            dict(id="wayfinding", goal=wayfinding, views=views),
            dict(id="purpose_fit", goal=purpose, views=views),
        ])

    return dict(
        rubric="building-quality-v1", revision="reading-loft-2", stage="draft",
        requirements=[dict(id="return_books", required=True, stage="draft",
            goal="有完整收卷台、上楼停靠及归架柜，从三个适用机位可核对",
            views=["counter", "landing", "cabinet"])],
        aesthetics=[
            standard("massing", "屋顶和主体比例协调，入口整体可读", ["outside", "entry_player"]),
            standard("hierarchy", "山墙中跨入口和阅读窗构成主次", ["outside", "entry_player"]),
            standard("materials_light", "灰瓦、灰白墙面和木框形成稳定层次", ["outside", "frame"]),
            standard("view_coherence", "保留顶构，外部到展卷空间的主题连续", ["outside", "entry_player", "frame"]),
        ],
        activities=[dict(id="file_books", required=True, requirements=["return_books"], segments=[
            leg("desk_to_stair", ["counter", "entry_player"], "台前能转身并在梯前停靠",
                "从台前能辨识厅内楼梯", "收卷离台后可直接到梯脚"),
            leg("stair_to_landing", ["landing"], "梯顶能转向且出口净空",
                "登梯时可辨认平台边缘和护栏端头", "负卷步行可连续登梯并在夹层站稳"),
            leg("landing_to_shelf", ["landing", "cabinet"], "平台和柜前可停靠、转向",
                "从夹层出口可辨识柜面朝向", "归架者可沿平台走到书柜正面"),
        ])],
        style=[dict(id="continuous_eaves", goal="山面有明确深色封檐，沿边连续收口", sites=[
            dict(id="front", target=dict(position=[10, 12, 0]), goal="前山面灰瓦下连续深木封檐",
                 views=["outside"]),
            dict(id="rear", target=dict(position=[10, 12, 27]), goal="后山面封檐与前山面连续同色",
                 views=["rear_eaves"]),
        ])],
        details=[
            detail("entry", [10.5, 2, 2.5], "entry_player", "入口阔度与木柱、墙厚有清晰层次",
                   "墙边与地面交接平整", "从入口能识别厅内方向"),
            detail("stair_head", [5.5, 5.1, 19.5], "landing", "踏步与平台高度协调",
                   "梯顶护边干净止于平台", "保留梯顶出入口和转身位"),
            detail("archive", [5.5, 6.1, 24], "cabinet", "书格、柜身和压条尺度适合站立使用",
                   "压条与柜体端头收齐", "从平台可识别书柜操作侧"),
        ],
    )
