"""归卷院：从街口经侧路、石门槛进入阅览室，西侧另设值房。"""
from plan import box, part, tiled_gable


def courtyard():
    street = [5.5, 2, 2.5]
    junction = [14.5, 2, 4.5]
    threshold = [14.5, 2, 15.5]
    desk = [16.5, 2, 19.5]
    guard = [6.5, 2, 8.5]
    parts = [
        part("grounds", "landscape", [1, 0, 1], [
            box("街道基床", [0, 0, 0], [26, 0, 2], "andesite"),
            box("院落草坡下缘", [0, 0, 3], [23, 0, 14], "grass_block"),
            box("阅览室基床", [7, 0, 15], [22, 0, 25], "grass_block"),
            box("东院草坪", [15, 1, 3], [22, 1, 12], "grass_block"),
            box("主路西侧草肩", [9, 1, 3], [11, 1, 6], "grass_block"),
            box("值房窗前草地", [1, 1, 3], [7, 1, 4], "grass_block"),
            box("值房后草台", [1, 1, 11], [10, 1, 13], "grass_block"),
            box("东院矮篱", [17, 2, 11], [21, 2, 11], "oak_leaves[persistent=true]"),
        ]),
        tiled_gable("hall_roof", [10, 16], [21, 24], 7, 4),
        tiled_gable("lodge_roof", [3, 6], [8, 11], 5, 2, axis="x", tile="spruce"),
        part("street", "road", [1, 1, 1], [box("石铺主街", [0, 0, 0], [26, 0, 2], "stone_bricks")]),
        part("junction", "road", [13, 1, 4], [box("转入院路的石带", [0, 0, 0], [2, 0, 0], "polished_andesite")]),
        part("lane", "road", [13, 1, 5], [box("院路至正门地槛", [0, 0, 0], [2, 0, 10], "smooth_stone")]),
        part("guard_path", "road", [9, 1, 8], [box("值房支路", [0, 0, 0], [3, 0, 1], "stone_bricks")]),
        part("guard_seat", "furniture", [4, 2, 7], [
            box("值守长凳", [0, 0, 0], [0, 0, 2], "spruce_stairs[facing=west,half=bottom]"),
        ]),
        part("sill", "frame", [18, 2, 14], [
            box("正窗挑台", [0, 0, 0], [2, 0, 0], "stone_brick_slab[type=top]"),
        ]),
        part("portal", "frame", [12, 1, 14], [
            box("西柱石座", [0, 0, 0], [0, 0, 0], "stone_bricks"),
            box("东柱石座", [4, 0, 0], [4, 0, 0], "stone_bricks"),
            box("西门柱", [0, 1, 0], [0, 4, 0], "stripped_spruce_log"),
            box("东门柱", [4, 1, 0], [4, 4, 0], "stripped_spruce_log"),
            box("门额", [0, 5, 0], [4, 5, 0], "stripped_spruce_log[axis=x]"),
        ]),
        part("desk", "furniture", [16, 2, 20], [
            box("案左脚", [0, 0, 0], [0, 0, 0], "spruce_planks"),
            box("案右脚", [2, 0, 0], [2, 0, 0], "spruce_planks"),
            box("收卷案面", [0, 1, 0], [2, 1, 0], "birch_slab[type=bottom]"),
        ], interfaces=[dict(id="intake", face="north", lo=[0, 1, 0], hi=[2, 1, 0])]),
    ]
    return dict(
        schema_version=1, name="归卷院", size=[30, 14, 27],
        style=dict(name="低值房与高山墙", materials=dict(wall="calcite")),
        context=dict(mode="standalone", start=street, targets=dict(junction=junction, threshold=threshold, desk=desk, guard=guard),
                     interior_probes=[[14, 4, 18], [6, 4, 8]], require_routes=True,
                     openings=[dict(id="hall_entry", facing="north", lo=[13, 2, 15], hi=[15, 5, 15]),
                               dict(id="guard_entry", facing="east", lo=[9, 2, 8], hi=[9, 4, 9])],
                     route_legs=[dict(name="public_lane_without_guard_room", start=street, targets=dict(desk=desk),
                                      validation_only_barriers=[dict(lo=[3, 2, 6], hi=[8, 6, 11])])]),
        spaces=[dict(id="yard", purpose="沿主街转入院路", lo=[1, 2, 1], hi=[27, 5, 15], feet_y=2, samples=[street, junction, threshold]),
                dict(id="hall", purpose="在案前交卷", lo=[10, 2, 16], hi=[21, 8, 24], feet_y=2, samples=[desk]),
                dict(id="lodge", purpose="值守", lo=[3, 2, 6], hi=[8, 5, 11], feet_y=2, samples=[guard])],
        envelope=dict(wall={"design_ref": "style.materials.wall"}, floor="smooth_stone", roof="deepslate_tiles",
                      volumes=[dict(id="reading_room", lo_xz=[10, 16], hi_xz=[21, 24], feet_y=2, eaves_y=7,
                                    roof=dict(kind="gable", rise=4, axis="z")),
                               dict(id="gate_lodge", lo_xz=[3, 6], hi_xz=[8, 11], feet_y=2, eaves_y=5,
                                    roof=dict(kind="gable", rise=2, axis="x"))],
                      glazing=[dict(lo=[18, 3, 15], hi=[20, 5, 15], state="glass"),
                               dict(lo=[4, 3, 5], hi=[6, 4, 5], state="glass")]),
        parts=parts, activities=[dict(id="visitor", actor="访客", purpose="从主街经门槛到案前交卷", stops=[
            dict(space="yard", feet=street), dict(space="yard", feet=junction), dict(space="yard", feet=threshold),
            dict(space="hall", feet=desk, use_face=dict(part="desk", interface="intake", height=1.25, max_distance=1))])],
        views=[dict(id="district", layer="massing", eye=[40, 27, -28], target=[14, 3, 13], fov=45),
               dict(id="turn", layer="structure", feet=[10.5, 2, 2.5], target_part="junction", fov=78),
               dict(id="entrance", layer="detail", feet=[14.5, 2, 10.5], target_part="portal", target=[14.5, 3.7, 15], fov=72),
               dict(id="intake", layer="detail", feet=[15.5, 2, 17.5], target_part="desk", fov=65)],
        review_locations=[dict(id="street_turn", purpose="主街与支路的接缝", position=[14.5, 2, 4.5], views=["turn"]),
                          dict(id="doorstep", purpose="院路与门内落脚处的高差", position=[14.5, 2.1, 15.5], views=["entrance"]),
                          dict(id="worktop", purpose="交卷一侧的台沿", position=[16.5, 3.25, 20], views=["intake"])],
    )
