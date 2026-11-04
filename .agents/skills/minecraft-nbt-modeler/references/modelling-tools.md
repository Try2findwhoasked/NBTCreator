# 通用建模、扩散与破坏工具

`scripts/nbt_tools.py` 提供无副作用的 `modelling_plan(model, operation, protected=()) -> (edits, report)`。新作品design阶段可用 `apply_modelling(model, operation, wall_positions=(), protected=())`，返回更新墙mask与报告。已有作品的落盘修改使用真实看图确认后的 `nbt_refine.py apply`，支持下表全部kind，不能用design API绕过确认。工具制作和合成测试无需资产确认。

与现有工具分工：自由形场/坐标扭曲/平滑融合用nbt_fields；混材用nbt_patterns；可走地面识别与半砖坑用nbt_floors；苔痕裂纹组合用nbt_weathering。新工具补齐通用编辑和效果，不取代建筑设计。

## 共用参数与坐标

- `kind`、`lo`、`hi`必填。lo/hi为全局整数XYZ、包含边界，限定操作域；每次最多规划200万格。复制/变换的lo/hi是源选区，目标另验整体边界。稀疏缺角由精修器再次检查。
- `state`默认stone；`from_states`可选精确合法状态列表（不是仅ID匹配），省略则域内所有位置合格。replace强制声明from_states。
- `seed`为整数；随机值按全局坐标哈希，不按切片重置。`max_writes`默认100000，仅计实际状态变化；精修器的总变化预算另外执行。
- `classification`用body/wall/inherit。复制/旋转不会自动搬迁墙mask；逐次明确选择，混合墙/主体选区先拆分操作。inherit保留目标原有归属，不表示沿用源选区归属。
- 整数体素 `(x,y,z)` 的几何取样点是 `(x+.5,y+.5,z+.5)`。geometry内部连续box用min/max表面坐标，不是包含边界的体素lo/hi。
- 显式选区就是裁剪域，超出选区的几何不会生成；需要完整形状时先为其包围盒留足范围。复制目标越界拒绝，绝不静默截断。

所有操作先完整规划再写，预算/参数/保护失败不部分修改design模型。形状、复制、形态学触及保护位置拒绝；扩散将保护位置当障碍，爆炸与散落跳过保护位置并留下统计。跳过可留下不自然的孤岛，必须看图并重验。所有工具都不自动识别承重结构，请显式保护壳、支撑、端口、通路和重要主题节点。

## 可执行操作

| kind | 参数 | 语义 |
| --- | --- | --- |
| geometry | geometry对象、mode=set/add/subtract/intersect | set写选中形状；add仅填空气；subtract挖空气；intersect删除域内形状之外的合格体素，不影响域外 |
| replace | from_states、state | 域内精确状态替换 |
| copy_region | offset整数XYZ、include_air=false、overwrite=false | 从原快照平移复制；目标被不同实体占用时默认拒绝，不递归复制刚生成内容 |
| repeat_region | 同copy、count=1（1..128） | 将源快照复制到offset的1..count倍处；副本状态冲突拒绝；环形阵列可逐次transform |
| transform_region | destination、quarter_turns=0、mirror=null/x/z、move=false、include_air=false、overwrite=false | 先镜像再绕Y旋转90度整数倍；destination是变换后包围盒最小体素；奇数转交换XZ长度；move清除源选区，不能同时筛选源状态 |
| morphology | mode=dilate/erode/shell/opening/closing、iterations=1（0..128） | 六邻接膨胀/侵蚀；shell保留厚iterations的内表皮；opening先蚀后胀，closing先胀后蚀。选区外视为空，边缘可能被侵蚀；膨胀填空气，不覆盖未选中的其他实体。新格使用state |
| diffusion | seeds整数XYZ数组、steps=8（0..128）、decay=0..1、surface_only=false | 六邻接广度增长；steps是最远图距离，decay使远处分支更难生长；所有seed须在合格且未保护的位置；surface_only仅沿邻空气表面传播，不能跨不相连墙面 |
| explosion | centre连续XYZ、radius、roughness=.15（0..1不含1）、rays=0（0..128）、ray_length=1.5×radius、ray_width=.55 | 挖球形缺口+连续起伏边缘+可选放射管状裂缝；球包围须在域内，射线到域边界截断；仅修改已有实体，保护位置跳过；报告明确physics_simulated=false |
| scatter | fraction=.1、spacing=1（0..128）、supported=true | 按稳定随机顺序挑选位置，间距是欧氏距离；supported仅接受下方非空气且自身为空气的位置。只是粗略支承筛选，不认证半砖、栅栏或重力方块的真实物理 |

transform仅支持无属性方块，及属性集合只包含axis/facing/waterlogged的状态家族；方向和水平轴随变换更新。楼梯转角、门铰链、轨道、连接墙、带rotation的方块等未覆盖家族明确拒绝（即使原文件省略属性也读取注册表默认值），不要为凑通过删掉状态。平移copy不改变方向，可原样复制楼梯。完整模型仍需邻接与实际碰撞检查。

爆炸、扩散、散落可以组合：先限定可破坏材料与壳厚，做静态缺口，再从破口边缘在合格表面扩散裂纹或焦痕，最后在有底部支承的局部区域散落碎石。坠落方向、遮挡、冲击能量、抛物线、真实TNT、实体、液体与方块更新均未模拟。风化优先走已有连片风化工具；不要把爆炸随机应用到所有旧墙。

按目标选择效果而非无差别叠加：

- 地面弹坑：球心靠近地面，范围包括上方空气，限定可破坏地面材料；保护坑底和必经路，检查不穿透下层房间。坑缘与碎石另做，爆炸工具不会自动生成安全坑底。
- 墙面爆破/放射裂缝：小radius加适量rays，墙后密闭壳和过梁列入保护；需要真实外部破口时返回整体开口设计流程，不能把新的漏口当作普通精修接受。
- 渗水/霉斑/烧灼扩散：用多个有来源的seeds、surface_only和from_states，decay控制支脉；先做小范围只读计划，再选材质。不使用扩散改变岩壳厚度来模拟颜色。
- 根系/矿脉体积生长：限定材料域后做多源体积diffusion；polyline/bezier控制主轴，扩散作为次级分支。纯增长不证明所生成细枝有物理支承。
- 局部剥落、边缘圆钝与孔洞整理：用erode/opening/closing的少量迭代；先限定目标构件，薄梁、门套和接缝显式保护，避免把全模型侵蚀一遍。

## geometry对象

| shape | 参数 |
| --- | --- |
| box | min/max连续表面XYZ（min<max） |
| sphere / ellipsoid | centre、radius / radii；ellipsoid可传正交3×3 rotation |
| cylinder / cone | centre、radius（底半径）、height、axis=x/y/z（默认y）；cone可选top_radius=0 |
| torus | centre、major_radius、minor_radius；环面在XZ平面 |
| polyline / bezier | points连续XYZ列表（至少2点）、radius（正数或每采样点半径）；bezier可选samples=64（2..1024） |
| extrude | 简单非自交XZ多边形vertices、bottom、top；不自动修复自交多边形 |
| union / intersection / difference | children数组，difference恰好两项；嵌套不超过16层 |

cone的底沿axis负方向、顶沿正方向。浮点曲线是体素近似，细杆/斜线不保证六邻接连通；平滑融合、任意方向扫掠和有机扭曲可直接使用nbt_fields API。不存在“一个命令自动完善建筑”的保证。

## 使用示例与只读CLI

初稿生成器或合成fixture中：

```python
from nbt_tools import apply_modelling
walls, report = apply_modelling(master, {
    'kind': 'geometry', 'lo': [4, 4, 4], 'hi': [19, 15, 19],
    'geometry': {'shape': 'cylinder', 'centre': [12, 10, 12],
                 'radius': 4, 'height': 10},
    'state': 'stone_bricks', 'classification': 'body'
}, wall_positions=walls, protected=protected)
```

已有模型只读预检（operation.json就是单项operation；保护体素可从任务配置生成）：

```powershell
python .agents/skills/minecraft-nbt-modeler/scripts/nbt_tools.py --source <完整主稿> --operation <单项操作JSON> --protected <保护XYZ数组JSON> --output <全新计划JSON>
python .agents/skills/minecraft-nbt-modeler/scripts/check_modelling_fixtures.py --output <全新合成回归目录>
```

CLI只输出源指纹、候选变化与统计，不落盘NBT、不批准精修，也不证明密闭、路径、游戏加载或美术合格。精修plan在operations中放相同操作并加label/classification，按原流程approve/apply；实际模型输出仍由精修器统一验证、差异记录、出图和机械切片。


## 可复用构件

`paste_component` 使用已验证的 palette 与相对 lo 的 voxels，一项操作可表示复杂构件；分类由 classification 决定，混合主体/墙 mask 的资产拆分为两项。默认拒绝占用冲突，overwrite 只允许覆盖普通目标，不能改变保护约束。保存、导入及放置命令见 [构件资产](component-assets.md)。

## 自动道路铺设

`auto_road` 用 `start/end` 整数 XYZ 指定同一高度的路面方块中心。`route` 为 `straight`（连续阶梯状斜线）、`x_first` 或 `z_first`（直角折线）；`width` 1～16、`depth` 1～8。偶数宽度向正轴多延伸一格；厚度向下延伸。`lo/hi` 必须容纳完整路面，不裁剪。`state` 须为实体方块，默认不覆盖已有不同材质；`overwrite=true` 才允许替换。保护、单步 `max_writes` 与总预算继续生效。首版为平面铺设，不自动避障、清空头顶或适应地形；使用后实际预览和检查通行，再显式导出新版本。UI入口在建筑模型下方的“自动道路”分类，CLI使用共用 `tools` 映射的单项操作 JSON。

## 连通与表面选区

`selection_replace` 的 `selection=connected/surface/connected_surface`、`seed_position`、`match=state/solid` 控制六邻接选区。surface 无需种子；其他模式从种子开始，默认精确同状态。`from_states` 进一步过滤，`faces` 指定暴露于真实空气或模型外部的方向（选区边缘不视为空气）。`thickness=1..16` 在表面模式向合格实体内部扩展，不跨空气。使用 `state=air` 可挖除。`nbt_selection.select_voxels` 是只读坐标查询 API，编辑仍通过共用预览与显式导出流程。

## 对齐与吸附

`align_region` 使用源 `lo/hi` 的快照平移，不旋转状态。`mode=align` 的 `target_lo/target_hi` 和三个 `axes=min/center/max/keep` 定义各轴对齐；半格中心偏移明确拒绝。`mode=anchor` 使用全局 `source_anchor/target_anchor`。`mode=ground` 以 `destination` 的 XZ 为目标包围盒最小位置，Y 为向下搜索起点；只接受已知完整方块支承，逐源实体列的最低格需要一致的落地偏移，不自动挖地或悬空。move/include_air/overwrite 均为显式布尔。墙和主体请分开操作并明确 classification，inherit 仍表示保留目标原归属。

## 环形与沿路径阵列

`array_region` 从原快照复制，`source_anchor` 为源内的全局锚点，默认 lo。`mode=path` 的 points 是连续全局 XYZ 折线，spacing 为弧长间距，end_margins 为起止留白；最多 128 次放置。`mode=radial` 使用 centre/radius/count，start_angle=0 指向北，正角顺时针，sweep_angle 默认360度，完整圆不重复末端。位置四舍五入到整数网格，重复锚点及不同状态冲突拒绝。orientation=fixed 保持源朝向；cardinal 按路径切线或径向朝外取最近90度，仍使用现有保守状态变换，不提供任意角旋转。报告包含每个实际锚点及 quarter_turns，须看图检查体素近似。

## 半格楼梯、坡道与平台

`auto_stairs` 用整数 start/end（XZ 为行走格，Y 为玩家脚位高度）生成完整块与底半砖交替的半格台阶坡道。width=1..7；straight 要求同轴。switchback 用 flight_length，回程 end XZ 必须为 (start.x,start.z+width+2)。spiral 是方形环绕阶梯，centre/radius/turns 定义路径；起终点 XZ 为中心西北 radius 处。转角和两端保留平平台，空间不足明确拒绝。state 必须已知完整碰撞块，slab_state 必须底半砖。不会自动挖空头顶、添加栏杆或底部柱撑；逐对相邻脚位用实际碰撞检查，防止绕路误认证。结果是待看图候选，不代表游戏动态验证。

## 地形道路与避障

`terrain_road` 保留旧 auto_road 的平面语义。start/end 的 Y 必须匹配真实最高地表格。terrain_states 为允许替换/挖除的精确状态，只接受已知完整块；非地形最高实体视为障碍。A* 在 lo/hi 内按最高地表搜索，逐列检查完整宽度、两格头顶净空及保护区；最多10万搜索节点。相邻地表高度差最多1，较高行自动铺朝上的底楼梯，最终逐段验证真实通行。max_cut/max_fill=0..16 限定横断面整平，不提供任意地形开山路线；默认均0。max_bridge_span 默认0，显式1..16时允许以起点高度跨越空列，报告 bridge_cells；没有桥墩或结构承重认证。复杂尖峰、转角或宽路冲突可拒绝，需先整地或分段设计，不会静默生成不可走道路。

## 截面成形

geometry 新增三个 shape，仍经过相同布尔、裁剪、保护和预算路径。`section_sweep` 用 vertices（局部UV简单多边形）、points（全局XYZ折线）及 up（默认Y）生成各段定截面棱柱的并集。U=normalize(up×tangent)，V=tangent×U；平行 up 的路径段拒绝。转角使用平帽棱柱并集，不自动斜接，急弯可能缺角，须看图检查。`loft` 用严格递增 y 的 sections，每项 vertices 为全局XZ简单多边形；各截面顶点数和顺序对应，逐体素高度线性插值，拒绝采样到的自交截面。`revolve` 将 profile 的半径/相对高度多边形绕 centre 的Y轴旋转，可用 start_angle/sweep_angle 做部分圆周；半径不得负。三者只生成体素几何，不自动安排楼梯、壳厚或承重。
