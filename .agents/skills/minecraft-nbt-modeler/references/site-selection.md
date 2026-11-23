# 单栋建筑与接路联合选址

在创作工作区使用 `model --request <JSON>`，把 `site_selection` 写入 `actions`。用 `capabilities --model` 查看参数。宿主沿用工作模型顶层的 `source` 与 `source_sha256`，也可先用同一请求内的工作模型操作构造地形。建筑另用 `goal.building` 绑定已有粗案的 `source`、`source_sha256`，或使用编译配方的 `recipe`、`content_sha256`。已有粗案按完整方块和墙层刚性放置，配方采用后保留为普通工作模型实例。

```json
{
  "source": "terrain.snbt",
  "source_sha256": "<地形文件的 SHA256>",
  "actions": [{
    "method": "site_selection",
    "goal": {
      "building": {"source": "pavilion.snbt", "source_sha256": "<粗案文件的 SHA256>"},
      "region": {"lo": [0, 0, 0], "hi": [33, 15, 26]},
      "junction": [2, 2, 12],
      "entrance": {"floor": [0, 0, 3], "facing": "west"},
      "targets": [{"id": "workbench", "feet": [4.5, 1, 3.5]}],
      "anchor_xz": [[18, 9], [13, 9]],
      "floor_ys": [2, 3, 4],
      "quarter_turns": [0, 1],
      "roads": [{}, {"max_bridge_span": 3, "bridge_water": true}],
      "max_candidates": 24,
      "max_pad_cut": 2,
      "max_pad_fill": 1
    },
    "preview": {"output": "river/preview"}
  }]
}
```

- `region` 是宿主世界 XYZ 的包含端点范围，最多 4096 个水平格和 64 层。道路选项可用 `corridor` 在其中缩小范围。整栋、门外落脚平台和每次写入都受范围约束。联合预算是 XZ、首层 Y、转向和道路选项的笛卡尔积，最多 64 项；超额或重复组合报错。固定位置对照把前三个列表各缩为一项并保留相同的道路选项与预算。
- 粗案每轴最多 64 格，使用局部原点作为放置锚点，配方沿用其编译锚点。填写锚点世界 XZ、最低实体层的世界 Y、局部入口地板和向外方向。最低实体层下方的空层按模型边距处理。若建筑已有外廊，以建筑外缘的接路脚位作为入口锚点。工位使用建筑局部实际脚位，通常取要站立的整方块中心上方。回执列出变换后的放置锚点、原基底高度、整栋包围盒、入口方块和门外一格的平台。
- 基底和平台须接触已知的干燥整方块，允许有限填方。只有 `terrain_states` 中的方块可被当作可挖土层，默认为草方块、泥土和石头。报告逐柱的原有承托面、填方深度以及水面、障碍、保护、留白或范围冲突的坐标。宿主原有墙层、托管构件与既有路口保留。
- 接路复用 `terrain_road` 的单格宽路径和楼梯。起点和门外平台保留整方块路面，过高端点需要同高的相邻道路落脚。路由默认绕开水面和缺口。正的 `max_bridge_span` 允许静态跨空，另设 `bridge_water: true` 允许在既有路口路面高度跨过更低的水面，报告实际桥面格和水格。桥面保留水方块。路线必须通过实际碰撞与净空检查。
- 排序使用挖方格、填方格和水平路长的等权和。挖方包括被建筑地板替换或为建筑净空清除的可挖土层。填方计原空气中加入的承托和平台，不把建筑本体和桥面计入。普通路面换材通过实际状态差异核对。无解的回执保留 `problem`、可获得的地基检查与候选耗时；后续检查或排序只使用可行候选。
- 通路记录从既有路口沿候选道路、直接跨过门槛到每个工位的实际半格脚位。该证据适用于回执绑定的静态模型。游戏流体变化、桥梁荷载、通行宽度以外的交通能力均需另行检查。

搜索保留源绑定，默认返回排名和各候选证据。提供 `preview.output` 会在全新目录保存首选的 `candidate.snbt`、快照、相机和 `site-selection.json`。使用 `preview.candidate_id` 可指定其他候选。按[纹理出图流程](rendering.md)调用 `render` 并实际看图。用相同的 `goal`、`candidate_id` 和 `candidate_sha256` 调用 `adopt_site_selection`，在工作模型中复算并采用。追加 `save_draft` 可使用正常制作版本入口保存并继续编辑。制作版继承宿主上下文，粗案以方块和墙层放置时，其内部对象关系、建筑方案和审阅批准仍属于原稿。用户看图确认、精修和手动 NBT 定稿继续使用各自入口。

从软件仓库根运行合成对照，指定全新的隔离创作目录。

```powershell
mise run test -- terrain-site-selection --workspace <新隔离目录>
```

回执思路参考地形代价参与接路的加权路径和道路与建筑选址的相互影响。此处联合比较同一栋刚性建筑的有限体素变换与实际接路，范围为单栋。 [Galin 等，道路生成](https://doi.org/10.1111/j.1467-8659.2009.01612.x) [Emilien 等，地形聚落生成](https://doi.org/10.1007/s00371-012-0699-7)
