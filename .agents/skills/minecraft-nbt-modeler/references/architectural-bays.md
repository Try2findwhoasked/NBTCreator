# 联动跨间、券顶与透空窗棂

当柱、拱、墙窗、顶构和地砖需要共用比例时，先做一个可辨识的单跨试件。`bay_compile` 是一种可选的石造回廊构造，不是所有建筑的默认布局；其他布局仍用对象图与自由几何。它不依据截图自动复原历史建筑，也不将二维花纹解释为承托结构。

这些工具通过 `components agent --tool <名称> --request <JSON>` 返回纯候选 spec。完整字段和范围查询 `capabilities --agent-tool <名称>`，示例尺寸供本次试搭调整。工作区使用冻结引擎时，先在 AI 知识设置同步这些工具，再由该工作区入口调用。

| 工具 | 实际生成的几何 | 主要参数 |
| --- | --- | --- |
| `bay_compile` | 四束柱、四面连续拱套、对角肋与凹格交叉券顶、低墙裙、后墙拱窗和齐平多色地砖 | span、depth、pier_width、spring_height、rise、profile、materials、floor_pattern、coffer_pattern |
| `vault_compile` | 跟随统一拱形参数场的实体壳体、递进凹格、可选对角肋及底面顶半砖 | size_xz、spring_y、rise、profile、thickness、recess_depth、coffer_counts、coffer_pattern |
| `tracery_compile` | 外拱框、双分栏、中心圆窗、连接杆和可选玻璃；无不透明背板 | size_uv、depth、profile、material、trim、glazing、glass_palette |
| `facade_compile` | 窗间墩、逐层水平层带、窗框、下半砖窗台及后退玻璃，返回各实际开口范围 | bays、storeys、opening、pier_width、sill_height、lintel_height、recess、material、trim、glass |

## 凹窗与层带立面

`facade_compile` 适用于成组矩形窗的立面片段。先按活动区净尺寸决定开间、层高和窗台，再选需要重复的跨数。候选正面朝北（-Z），外侧框位于 Z=0，玻璃沿 +Z 后退 recess 格。opening 指真实窗洞宽高，层间节距由 sill_height、窗高和 lintel_height 相加得到，窗间墩宽控制整体宽度。每个构件宽高最多64格，较长立面可按实际跨间通过对象图组合。

```json
{"bays":3,"storeys":2,"opening":[3,4],"pier_width":2,"sill_height":2,"lintel_height":1,"recess":1,"material":"bricks","trim":"smooth_sandstone","glass":"glass","sill_material":"sandstone_slab[type=bottom]"}
```

glazing=false 保留贯通候选深度的真实窗孔。候选中的空位置在安装时保持宿主原状，已有墙体上的开洞通过完整工作模型的受检修改处理。按 `openings` 回执核对窗的内外侧，查看墙厚、框的投影、窗台连接及室内使用面。尺寸、玻璃退进和材料可按设计更改，平齐玻璃、通高幕墙或无玻璃开口可另用自由几何表达。

构造观察来自公开的索菲亚应用艺术学校蓝图及其立面、室内图。重复开窗、水平层带与局部竖向强调被提炼为可调构造，来源与版本见[上游记录](upstream-sources.json)。屋面曲线使用[参数化屋顶](modelling-tools.md#参数化屋顶)。

## 共享比例与真实接触

独立跨间请求示例：

```json
{
  "name": "苍金四叶纹回廊·单跨",
  "span": 24,
  "depth": 20,
  "pier_width": 5,
  "spring_height": 14,
  "rise": 14,
  "profile": "pointed",
  "coffer_counts": [3, 3],
  "recess_depth": 2,
  "floor_pattern": {"preset": "byzantine-cross-mosaic"},
  "coffer_pattern": {"preset": "roman-coffer"}
}
```

span、depth 是局部控制尺寸；柱宽、留边和地板使最终画布更大，实际净空按输出几何测量。地板顶面在 Y=1，玩家脚位从 Y=2 开始；spring_height 从该脚位起算，独立券顶的 spring_y 则直接使用局部 Y。profile 为 pointed 或 round，同时驱动拱套、券顶和后墙窗框，不能只改拱券后保留旧窗洞。柱础、柱头随起拱高度变化；拱套各层共用曲线和法向，避免每段重新起相位。

`construction_graph.joints` 检查最终方块的实际半格面接触，包含地板到四柱、四柱到顶、四拱到顶和窗到墙；这些不是材料承载或施工安全计算。对象配方中使用 `recipe.tool="bay_compile"` 即可随参数重算；`scene_save/update` 保留图谱版本与保护约束，不接管手工 SNBT。

## 凹格、透空与资产来源

独立券顶的示例参数为 `{"size_xz":[26,22],"spring_y":16,"rise":14,"recess_depth":2,"coffer_counts":[3,3]}`。凹格按曲面上的归一化单元铺排，不把平面板悬在拱腹。recess_depth 改变真实底面高度，thickness 保留连续覆盖层；slab_material 和 recess_slab_material 须为受支持的顶半砖，分别用于主底面和凹格底面。recess_material 控制凹格内层材质，颜色差异不能代替真实凹深。该顶构为交叉券式参数场，不是穹顶放射分格器或任意曲面展开器。

独立窗棂示例为 `{"size_uv":[19,27],"depth":3,"profile":"pointed","glazing":false}`。glazing=false 留真实空气；true 在孔内放一格厚的完整玻璃方块，玻璃配色沿左右分栏和中心圆窗组织。玻璃不等于可穿行；需要门洞应另设计开口。最小窗棂为11×15格，窄小单元仍用微型拟合。此窗型为固定的双分栏与圆窗语汇，不从任意纹样自动提取三维窗棂。

floor_pattern 和 coffer_pattern 支持 preset、pattern_asset，或对象图中的 pattern_ref 命名绑定；不同时填写多种来源。命名绑定通过 graph.patterns 保存实际资产 ID 与 image_sha256，更换后重算相关对象；内置图先用 pattern_assets.copy 保存为工作区资产，再作图谱绑定。候选返回前重新核对实际图像哈希。地砖全块齐平，配色使用明确几何分区；它不是从灰度图恢复原建筑的全部色彩。

## 验证与边界

改变跨宽、进深、起拱高度或拱高后，重新编译并检查柱头、拱脚、窗洞、凹格和墙体的相接。比例过窄导致窗型低于最低尺寸、凹格单元小于4格、未知碰撞材料、越界或超预算会拒绝；不要为通过而偷偷裁切或缩小构件。

实际查看整体、入口玩家视角、保留完整顶构的仰视、窗棂、地砖及拱脚/凹格近景，分别判断比例、连续线脚、凹深、透空和纹样主次。回执中的 design=pending_visual_review 须由看图评审另行记录，工具不会替 Agent 判断审美通过。复杂主纹仍沿用 ornate 评分；这些结构检查不提供新的主观美学总分。

单跨是前侧及两侧开放的独立构件；技术连通与路线通过不代表整栋建筑密闭，也不代表游戏内实测或结构承载认证。组装完整建筑时继续按整体流程验证外壳、门洞、路线与完整主模型，不把这个试件直接登记为已完成建筑。
