# 纹样拟合与质量检查

用于把已有预设、图片或命名纹样拟合到实际方块；创建和裁取图源见[纹样来源与制作](pattern-authoring.md)，装到建筑上见[贴面安装](surface-mounting.md)。严格参数以 `capabilities --agent-tool pattern_microfit` 等对应工具为准。

| 本次任务 | 阅读章节 |
| --- | --- |
| 小型主纹与重复铺排 | 纹样优先从微型单元开始；拉伸、嵌入与量化视觉质量 |
| 整图普通面板 | 纹样库与多面板拟合；需要微型模式时回到单元流程 |
| 竖直圆柱 | 圆柱环绕及微型单元的三维转角限制 |
| 引擎维护与效果比较 | 复杂微型纹样的细节补搜；维护验证 |

## 纹样优先从微型单元开始

纹样主流程使用 `pattern_microfit`，先做好2～8格的单个可辨单元，再铺排到墙、柱、地板和吊顶。它接收与 pattern_compile 相同的 preset / sample / pattern_asset 来源，预设用 preset_options，资产用 asset_options；size_uv 表示**单元**宽高，范围1～12格；单格用于笔画和半砖条带，主纹优先2～8格。无需先画成一张大墙再整体缩小。

pattern_asset 为工作区资产的 `{"id":实际ID,"image_sha256":实际图像SHA256}`，可直接由 pattern_assets / pattern_create 回执组装，不必复制图片路径。preset、sample、pattern_asset 必须选择一种；asset_options 与预设采样选项相同，不能替换原图路径或SHA。名称/标签变化不改变图像绑定，PNG被篡改则拒绝，即使编译缓存已经命中。需要多对象共享并一起更新时，用[对象图命名绑定](object-scenes.md#纹样资产与配方联动)。

```json
{"surface":"wall","size_uv":[4,4],"sample":{"path":"micro-ring.png","sha256":"<原图SHA256>","noise_strength":0},"tile_counts":[4,3],"gap_uv":[1,1],"preview":true}
```

此例先拟合4×4格单元，再复制成4列3行，中间各留1格，最终面板为19×14格。所有单元使用同一组方块与状态，不在铺排时重新缩放采样。原图可以来自 pattern_create 的8～32像素小位图/绘图配方，也可以用 sample.crop 裁出单个叶片、环扣或菱花。pattern_create 默认分辨率已改为16×16，输出的 fitting_input 可直接用于微型拟合。

小纹样可先查 `pattern_list` 中 `microfit.preferred=true` 的 12 项专用轮廓：2×2 方环、3×3 十字花、4×4 菱花/菱环/四瓣结/回钩、4×3 折线、4×6 叶片/花蕾和6×6 棕榈叶/卷钩/花章。按 `microfit.recommended_size_uv[surface]` 取已测尺寸，完整清单见[小尺寸图库](../assets/ornament-patterns/README.md#小尺寸专用纹样)。墙上2×2方环用楼梯能保孔，地板和吊顶需3×3；平齐地板仅用整块，部分图形需要更大尺寸。原有 `four-petal` 是大图几何预设，不应默认拿它做2×2微纹样；小四瓣结用 `micro-quatrefoil`。纹样参与主题表达时，检查玩家视角下的轮廓与孔洞，不以工具调用成功或远处不可辨的小点代替视觉验收。

默认 `micro_alignment=auto`，脚本会自动适配图片比例和半格采样相位，不要求先手改图片画布或曲线中心。保留原居中方案，同时探测轻微整体缩放（0.97 / 1 / 1.03）、每轴±四分之一个采样格的偏移；楼梯/半砖采样格为半格，偏移对应±1/8建筑格。未显式填写 sample.fit / preset_options.fit 时，还会在等比留白到铺满指定单元之间尝试比例适配，宽高拉伸比最多2倍。明确指定 contain、cover 或 stretch 时沿用该比例模式，只自动搜索轻微缩放与相位；cover 的裁切及 stretch 的非等比拉伸由调用者明确要求。`micro_alignment=fixed` 关闭自动搜索，但仍执行显式指定的图片比例映射。

自动处理不改原资产、不加粗笔画、不重画纹样、不改变 size_uv 或铺排间距，也不裁掉主纹。源的主要连通分量、孔洞及原有对称轴必须保留。脚本先快速探测，再对最多6个候选执行楼梯/半砖联合搜索，以拟合重合率减去缩放、偏移、拉伸惩罚选形；原方案精确匹配时直接使用。颜色与轮廓应用同一图片映射，避免对齐后配色错位。候选搜索有界，不保证所有小尺寸纹样都能自动恢复。

`microfit.alignment` 记录实际选择的比例模式、缩放、像素/建筑格偏移、缩放后尺寸和粘贴原点、算法版本、原方案是否可用及探测数量。原图SHA256与输入参数仍随配方保存。`ink_overlap`、`raw_coverage_error` 和 `shape_search.baseline_*` 比较**当前映射后的参考图**；`alignment.original_reference_ink_overlap` / `original_reference_contour_error` 则在原居中参考图中评估实际方块。`alignment.baseline_*` 记录未自动适配时的候选及通过情况。改变比例后的高重合率不等于未变形原图的完整还原，可用 fixed 对照真实预览。

微型脚本先按源图 threshold 二值化，再计算半格面积覆盖率。它尝试多档覆盖率阈值，锁定主轮廓的四向极值和主孔洞位置，并比较拟合后的连通分量与孔洞。源图的采样轮廓若严格左右/上下对称，会将对应方块联合匹配，避免各格独立选择楼梯/半砖时破坏对称性，preserved_symmetry_axes 记录结果。小于半个采样格面积的孤立细点/孔洞不计入主拓扑，报告会记录数量。source_threshold 与 selected_coverage_threshold 是两个不同阶段的阈值。候选优先保留主拓扑，再比较墨迹交并比 ink_overlap，减少大面积空白对匹配优劣的干扰。raw_coverage_error 是实际投影与源二值掩模的平均面积差异，stylized 表示存在明显的小尺寸简化；这些几何检查仍需结合真实预览评审。

楼梯与半砖还会按整个单元联合搜索，不只逐格挑选。满足极值、孔洞位置及对称约束的组合不超过4096种时完整枚举；更多组合使用宽度96的有界搜索，并保留原覆盖率阈值方案作为候选。完成的候选先检查主拓扑和 micro_max_error；原方案可用时，候选的墨迹重合率和轮廓误差均不得变差，避免为了多覆盖半格而损伤原有细边。然后比较墨迹重合率；重合率相同时，优先选择内外轮廓误差更小的方案，减少细线加粗和转角多出的半格。不会为追求重合率而把原本满足面积误差预算的单元改为拒绝。大单元的有界搜索不保证全局最优，失败也不代表所有合法组合都不可拟合。

microfit.shape_search 返回搜索方式 method（exhaustive / bounded_beam）、候选数量 candidates_evaluated、原逐格方案的 baseline_ink_overlap / baseline_contour_error / baseline_raw_coverage_error 和 improved；selection_method 表示最终使用 coverage_threshold 或 joint_shapes。contour_error 比较实际半格轮廓与样本覆盖率的相邻边界（包含外框及内部留白），以样本边界总量归一化，越低越好，可大于1，不是百分比。联合搜索方案的 selected_coverage_threshold=0.5 仅用于 requested / missing / extra 的半格统计，实际形状直接比较原覆盖率，不先把各格压成同一阈值掩模。ink_overlap 与 contour_error 均描述几何投影，不代表材质或游戏内光照效果。

脚本根据 material 自动寻找同材质楼梯、半砖和石墙，也可在 shapes 指定材料。朝向与上下状态自动选择。无同材质变体时使用整块，不自动换成别的颜色。full_blocks_only=true 可限制整块。平齐地板只用整块，吊顶只在可用楼梯的下半层细分；无法在给定尺寸保留主纹和孔洞时会拒绝。例如细线环可用四个楼梯拟合成2×2格墙饰，平齐地板的2×2格无法容纳中孔，需用更大的单元。

需要更细的笔画时，在 `pattern_microfit`（或 `fit_mode=micro`）的 `shapes` 显式加入 `trapdoor`、`wall`，可与 slab/stairs 混用。例如：

```json
{"surface":"wall","size_uv":[4,4],"preset":"micro-diamond","shapes":{"slab":"stone_brick_slab","stairs":"stone_brick_stairs","trapdoor":"spruce_trapdoor","wall":"stone_brick_wall"}}
```

精细形状通常采用16×16投影；含半像素边界的链条使用32×32。`microfit.projection_resolution` 返回实际精度，`subcells_per_block` 为256或1024。活版门的开合、朝向与上下状态由拟合器选择；石墙、玻璃板、铁栏杆及栅栏保存显式连接状态，安装旋转和镜像会同步变换方向。全部装饰连通部件须接到背板，雪层、地毯、压力板还须在拟合单元内找到下方完整支撑面，不额外添加源图中没有的承托。

| shapes 字段 | 材质示例 | 适合的静态形状 |
| --- | --- | --- |
| trapdoor | spruce_trapdoor | 3/16格条带、上下薄板 |
| wall | stone_brick_wall | 中央柱、low/tall连接臂 |
| pane | white_stained_glass_pane | 细竖线、板状连接 |
| bars | iron_bars | 镂空栏杆的近似包络 |
| fence | oak_fence | 细立柱、双横杆格栅 |
| snow | snow | layers=1～8的浅层形状 |
| carpet | white_carpet | 1/16格薄层 |
| pressure_plate | stone_pressure_plate | 未触发的1/16格薄板 |
| end_rod | end_rod | 六向细杆及底座 |
| chain | chain | 三轴细线的近似包络 |

每次只选与材质和纹样相关的类别，避免自动混用颜色或不必要地扩大搜索。墙面/柱饰会自动寻找同材质半砖、楼梯和石墙；自动石墙搜索未通过时保留原有半砖/楼梯方案，`auto_wall_search` 记录是否回退及原因。其他精细类别仍显式选择。精细形状用于 wall/column；吊顶可选不要求下方支撑的适用类别，石墙除外。圆柱继续使用原有楼梯/半砖的三维转角检查，平齐地板继续使用整块。

`shape_counts` 记录实际选中的类型；`geometry_constraints_passed` 和 `unsupported_positions` 记录静态连接与支承检查。`geometry_basis=static_shape_envelopes_texture_alpha_excluded` 表示评分不包含纹理透明孔洞；铁栏杆、链条会列入 `approximate_states`。玻璃透明度、游戏邻接重算、红石、碰撞和游戏效果另验，`collision_validated=false` 不得改写成游戏验收通过。

从软件根目录执行 `mise run fit:test` 验证方块、方向、支撑与保存回读。效果对比使用 `mise exec -- python -B tests/engine/fitting-shapes-benchmark.py --output build/<全新目录> --render`，输出同一原图在1/32格基准下的对照分数、耗时、启用材质及真实预览；该脚本只生成合成试件，不定稿或导出NBT。

这项评分比较静态模型盒体投影，不计算活版门纹理中的透明孔，也不模拟红石与游戏邻接更新；石墙侧臂保存的状态需在目标布局中复查。报告用 `geometry_basis`、`state_policy` 和 `collision_validated=false` 明确这个范围。新增候选不扩大玩家通路的精确碰撞支持范围，不能当作游戏内通行或放置稳定性的证明。墙面与柱饰支持两种新形状；吊顶可用活版门，平齐地板和圆柱环绕继续使用原有形状。标准整图拟合不接受这两项，需先拟合微型单元再铺排。

| 参数 | 用途 |
| --- | --- |
| tile_counts | 每轴1～16份，默认1×1；圆柱未指定时自动计算绕周可容纳的份数 |
| gap_uv | 平面单元间距0～4格，默认1×1；圆柱竖向沿用间距，周向将剩余格数均匀分配 |
| diameter | 仅微型圆柱，柱芯直径4～30，默认13格；size_uv 仍是纹样单元尺寸 |
| micro_max_error | 允许的平均面积差异0～1，默认0.65；主拓扑仍须匹配，不因放宽此值跳过检查 |
| micro_alignment | auto（默认）自动适配图片比例和半格采样位置；fixed 保留原比例与居中采样，仅用于微型拟合 |
| preview | 仅 pattern_microfit，生成真实候选、图片和相机，不保存构件或修改建筑 |

圆柱例：`{"surface":"cylinder","size_uv":[4,4],"diameter":13,"tile_counts":[4,3],...}` 将四份4格宽单元均布在圆周，竖向三排。不会把单元压缩到圆周宽度。总面板尺寸仍受每轴64格、预算和保护约束。

microfit 报告针对单个单元，shape_counts 是全部铺排用量。返回的 mount_object 可直接交给 pattern_mount.object，圆柱则交给 pattern_cylinder_mount.object。微型墙饰和吊顶安装会复用已验证的原墙/顶面，只增加外饰层，不另铺整层背板。两种安装仍绑定原稿、保护和快照哈希。同一模式也可通过 pattern_compile / pattern_preview 的 fit_mode=micro 调用；整图拟合使用标准模式及 repeat。

微型圆柱会在实际三维半格几何上检查每列单元的面连通分量、环孔和封闭空腔。绕过方块圆柱的阶梯转角时，只有源单元在该处连续的笔画才补连接：整格高用完整方块，半格高用对应上下半砖。不会通过减少 tile_counts 或放大 diameter 绕过失败；没有合适半砖、发生连接冲突或无法保持拓扑时拒绝。连接块可通过同一纹样的面相连部分接到柱芯，检查覆盖整个真实连通部件，新增连接仍计入占用、保护、留白和预算检查。`microfit.world_geometry` 给出逐列源/结果拓扑、实际实例数、连接块数量和支承检查范围。单元恰好铺满整个圆周时标记 periodic_boundary，允许周期接缝形成额外的环，不把该情形当平面开边界比较。

## 自动找重复单元与整面通铺

对已拉正的参考图或已经展开到局部 U/V 的图像，可先找矩形基本周期。阈值与 `sample.channel` 决定底色和笔画。若提供 `sample.colors`，笔画内用最近色映射到材质，再用材质标签比较重复。透明背景可以是图样的一部分。门窗、反光和其他不可观察区域用同尺寸、带哈希的独立 `valid_mask` 标记，白色有效，黑色或透明无效。图源的 `crop` 同时作用于两张图。

在软件仓库根目录运行，`detect.json` 使用实际创作项目中的文件路径与 SHA256。

```powershell
mise run nbt -- --workspace <创作项目目录> components agent --tool pattern_repeat_detect --request <detect.json>
```

```json
{
  "sample":{"path":"inputs/rectified.png","sha256":"<参考图 SHA256>","threshold":50},
  "detection":{"valid_mask":{"path":"inputs/visible.png","sha256":"<有效掩模 SHA256>"},"max_period_uv":[64,64]}
}
```

回执逐轴列出位移、有效像素对数、对数占可见像素的比例与标签一致率。线性 FFT 先零填充，裁图首尾不算作邻居。搜索上限为各轴 128 像素，并要求每个方向至少有两个周期的长度。候选须达到至少 8 对、20% 有效像素对及 99% 一致率，每种可见标签也须有相同标签像素对。工具在空间域复核最小有效矩形，要求单元每个相位至少两次观测且至少 75% 一致，最多复核 64 种组合。成功时记录复原单元的 RGBA 哈希。证据较弱、只有一个可见标签或出现相位冲突时会给出原因。斜格、透视未拉正和不规则周期需另行准备图源或手工裁取单元。

调用 `pattern_microfit` 时，原样传递 `sample`，把 `detection` 改为 `repeat_detection`（无选项可传 `{}`）。检测周期以**像素**计，`size_uv` 是拟合后单元的**方块**宽高，沿用微型单元每轴 1～12 格。以 `tile_counts:[2,2]`、`gap_uv:[0,0]`、`preview:true` 预览实物单元的连续铺排。手工路径使用已经裁好的 `sample` 并省略 `repeat_detection`。

- **平面**在 `pattern_mount` 设置 `repeat_tiling:true`。先用 `parametric_surface` 绑定宿主，`anchor_uv` 指定单元第一格的坐标。U/V 沿目标框的正世界轴索引，单元朝向沿用安装面的旋转。洞口与边距、受保护写入位和留白只裁去相应格，洞口另一侧保持相位。超出裁切条件的占用或背衬失败仍拒绝候选。
- **圆柱**在 `pattern_cylinder_mount` 设置 `repeat_anchor_uv:[u,v]`。U 是从 `seam_degrees` 起算的柱壳轮廓序号，V 是目标框内自底向上的 Y。目标框仍含一格外饰余量。用 `object.diameter` 指柱芯直径，`object.size_uv` 指单元尺寸。U 周期须整除实际轮廓格数，非整周期报告余格并拒绝闭合。受保护或显式留白范围内的柱芯空气可作为开口裁切。转角沿用楼梯旋转和连接半砖检查，已裁掉的端点不生成连接。
- **开放曲面**可把同一个单元交给 `curve plan` 的版本 3 掩模。截面、图源、实际位置、快照及合成方块由 `curve verify` 重新核对。[开放曲面连续铺排](curved-surface.md#开放曲面连续铺排)

通铺安装的 `object` 只描述单元，省略 `repeat`、`tile_counts` 和 `gap_uv`。默认固定拟合对齐。平面和圆柱候选的 `pattern.repeat_tiling` 记录从目标 UV 到单元格、实际写入坐标、材料状态及静态半格接触。按 `half_cell_joints` 区分预期接触、实测接触和被裁切的接缝。使用同机位审阅候选，按既有流程显式采用。游戏内相邻块更新、视觉效果和承重仍需各自验证。

## 拉伸、嵌入与量化视觉质量

先按建筑构件决定纹样所在的带、框、凹面、柱面与收口。长檐口可采用横向舒展的卷草，窄竖带可伸长叶纹；留白、密度和转折仍需看实际结果。图样拉伸不缩放 Minecraft 方块，不改变原图文件，也不放宽主拓扑与拟合误差限制。

### 显式拉伸

`sample.fit` 和 `preset_options.fit` 支持三种映射：`contain` 等比留白、`cover` 等比裁取、`stretch` 分别按目标宽高拉伸。stretch 不受默认自动适配的2倍比例范围限制，仍受工具尺寸和预算约束。颜色、透明度与轮廓共用同一映射，报告保留实际宽高变形比。不要用原图视觉相似度描述经过主动变形的结果。

```json
{"surface":"wall","preset":"micro-scroll","size_uv":[12,4],"preset_options":{"fit":"stretch"},"quality_profile":"border"}
```

### 齐平与浅槽嵌入

宿主厚度、材料保持、浅槽和实际写入检查见[贴面安装](surface-mounting.md#齐平与浅槽嵌入)。

### 拟合后质量与复杂度

`pattern_microfit`（或 `fit_mode=micro`）返回 `visual_quality`，按实际楼梯/半砖投影与用户指定变形后的参考轮廓比较。`quality_profile` 为 `balanced`、`ornate` 或 `border`；`min_quality_score` 范围0～100，默认0仅报告，指定门槛时未达标直接拒绝候选，不生成成功预览或放宽硬约束。

报告包括：墨迹交并比、带采样容差的轮廓F1、骨架分枝/端点/孔洞与形状复杂度保留、留白密度、相对于源图的对称/重心与行列墨迹节奏保留、额外碎片和面连通分量。骨架会按局部笔画厚度过滤拐角短枝，避免简单厚环仅因栅格放大就增加“装饰分枝”。所有配置都考虑保真、细节、可读性和规则性；border 更重视可读性与墨迹节奏，ornate 另外限制实际结果的细节丰富度，简单圆环即使拟合准确也不能仅凭高IoU获得华丽高分。碎噪点也不会因数量多而提高分数。

这些是版本化的确定性代理指标，不是经人类偏好标定的“美学真值”，也不评价材质、光照、历史风格或整栋建筑的协调性。border 用于条带构图，不要求所有条带必须复杂；balanced 也不强迫简洁构件变华丽。跨尺寸/安装面的分数要结合实际精度解读。保留指标与警告，不能只交一个总分。

复杂样本不达项目目标时，优先增加1～2格、裁取保留主题的局部，或组合基础单元形成更有组织的纹样。确需简化时记录损失；不能用简单徽记替换复杂卷草后声称原目标通过。模型仍须查看最终建筑中的玩家视角，检查是否像后贴的大块招牌、是否遮挡构造或挤占战斗空间。

自动对齐按原有几何排名检查量化质量门槛；首选未达标时继续检查其余已通过拓扑与覆盖误差的有限候选，不改原图、不降低门槛。microfit.quality_selection 记录候选数量、排名、分数与实际选择；所有候选都与同一张原始映射图比较，不能通过改变参考图抬高分数。该评分仍是轮廓代理，不证明建筑风格或主观美感。

### 复杂微型纹样的细节补搜

有限束搜索后，脚本会对仍有误差、且主拓扑可保留的单元重新检查合法楼梯/半砖组合。按原对称轨道调整，最多384次提案；不改原图、主纹极值、孔洞或调用方的覆盖误差预算。候选同时保留原结果的覆盖率与轮廓，再以同一张原始映射图核对量化分数和细节保留率；任一项变差就回退。补搜仍不能表达的复杂源应按真实失败裁取单元或增加尺寸，不放宽门槛。

shape_search.refinement 记录原候选数、提案上限/实数、接受移动数、是否改善，以及 quality_guard 的前后分数、细节保留率和回退结果。初始候选与补搜候选的数目分开理解；完整 candidates_evaluated 包括新评估的投影。投影预打包仅减少重复统计，不减少候选或更换实际半格几何。连续安装仍可使用建模会话复用已拟合单元。

surface=cylinder 且 fit_mode=micro（或直接 pattern_microfit）可复用支持 column 的预设；pattern_list.micro_cylinder_policy 会返回该规则。平面单元随后进入原有真实半格转角、环柄与柱芯接触检查；它不保证任意单元在任意直径都可环绕。普通非micro圆柱模式仍要求预设本身声明cylinder。


## 纹样库与多面板拟合

通过 `components agent --tool pattern_list --request empty.json` 查询纹样图片、SHA256、适用面和推荐尺寸。empty.json 内容为 {}。`pattern_compile` 返回结构 spec，`pattern_preview` 另生成共享引擎候选。两者使用相同请求，例如：

```json
{"surface":"ceiling","preset":"coffer-rosette","size_uv":[64,64],"max_changed_blocks":8192,"shapes":{"stairs":"quartz_stairs"},"preset_options":{"threshold":50,"noise_strength":0}}
```

preset 可以替换为 sample，沿用工作区图片、SHA256、灰度阈值和配色映射。图库参数写入 preset_options，自定义图片参数直接写入 sample，两者互斥。size_uv 每轴 3～64，repeat 为横纵重复数。base 与 material 控制背板和纹样材质。编译默认预算8192格，贴面默认4096格，大面板贴面须显式提供更大预算。四类面板坐标如下：

| surface | 图样平面 | 结构 |
| --- | --- | --- |
| floor | XZ | 单格厚的平齐镶嵌，按图用整块替换面板内的底色 |
| wall | XY | 背板在 Z=0，浮雕在 Z=1，可选半砖与楼梯 |
| column | XY | 平直柱面或壁柱饰板，沿用墙面轮廓拟合 |
| ceiling | XZ | 背板在 Y=1，浮雕在 Y=0，以顶半直楼梯的下半部拟合轮廓 |
| cylinder | 循环周向U × Y | 竖直实心柱芯及一格外饰，size_uv 是柱芯直径和高度 |

图样库保存于 assets/ornament-patterns。预览资产可经 structure_write 或 structure_save 入库，同时保存参数和样本哈希。fitting 返回重采样掩模中 requested、matched、missing、extra 的格数；shapes 开启时每格使用四个半格，吊顶比较下半层的XZ轮廓。此统计不表示与高分辨率原图的视觉相似度。

楼梯方向由拟合脚本自动决定。shapes.stairs 或 ornament.sample_shape_fit.stairs 指定楼梯材质，脚本按实际碰撞轮廓枚举合法朝向和上下半部，先最小化二值轮廓误差，同分时再比较灰度覆盖率。墙饰在局部XY面选择东西向、上半或下半楼梯；吊顶在局部XZ面选择四向顶半楼梯。pattern_mount 随安装面法线旋转这些状态。stair_orientations 返回局部朝向统计，贴面结果的 pattern.world_stair_orientations 返回世界坐标朝向统计，Agent 无需逐块填写方向。

平面安装前以 parametric_surface 查询绑定原稿、保护上下文和安装面的哈希，再调用 pattern_mount。请求与 parametric_mount 相同，但 object 使用上述纹样请求。侧墙四向接受 wall/column，up 接受 floor，down 接受 ceiling。anchor_uv 是构件锚点在查询面上的位置，柱饰锚点在底部中央。地板自动生成覆盖安装面原层的镶嵌候选，墙柱与吊顶贴在外侧，不覆盖已有方块。仍检查开口边距、保护、显式留白、预算，吊顶可提供 min_clearance，通路可提供 require_routes/compare_routes。源文件不会被修改。

### 圆柱环绕

通过同一 pattern_compile / pattern_preview 接口设置 surface=cylinder。size_uv 为柱芯直径与高度，直径4～30格，高度3～64格。外饰在柱芯外占一格，实际结构尺寸为 `[直径+2, 高度, 直径+2]`。柱芯为按圆形截面离散生成的完整方块，圆周纹样坐标由外轮廓自动计算；不需要 Agent 给每段指定朝向。

```json
{"surface":"cylinder","preset":"braided-shaft","size_uv":[13,32],"repeat":[4,1],"shapes":{"stairs":"quartz_stairs","slab":"quartz_slab"}}
```

repeat 的第一项为绕周重复次数，第二项为竖向重复次数。脚本先在周向切线/Y平面匹配半格轮廓，再按局部法线旋转楼梯。半砖自动选择 top/bottom；原版半砖无竖直侧放状态。接缝默认在北侧，seam_degrees 可设为 -180～180 度，0为南侧、90为东侧。纹样坐标在接缝处循环；原图两侧内容不同仍会留下图样接缝。若需连续图案，使用可平铺单元。编译默认预算65536格，包括柱芯；fitting 的误差统计仅计外饰。

已存在的圆柱使用 pattern_cylinder_mount，绑定三维 target 与 object。target 沿用源、几何、保护上下文及可选候选快照的哈希字段，lo/hi 为包含一格外饰余量的三维框，不含 normal 和 surface_sha256。例如13格柱芯、高32格，目标框最小角 `[10,2,10]`，最大角为 `[24,33,24]`。

```json
{
  "target": {
    "source":"nbt_models/example/master.snbt",
    "source_sha256":"<源SHA256>",
    "geometry_sha256":"<几何SHA256>",
    "context":"nbt_models/example/coordinates.json",
    "context_sha256":"<上下文SHA256>",
    "lo":[10,2,10],"hi":[24,33,24]
  },
  "object":{"surface":"cylinder","preset":"braided-shaft","size_uv":[13,32],"repeat":[4,1],"shapes":{"stairs":"quartz_stairs","slab":"quartz_slab"}},
  "max_changed_blocks":4096
}
```

安装脚本核对柱芯形状和完整方块支持，只返回外饰候选，不替换原柱芯。它拒绝外饰占用、保护/声明开口、显式留白、过期哈希和超预算，支持 require_routes、compare_routes 与同机位 review。支持标准的竖直等直径方块圆柱；缺损、变径和倾斜柱须先处理几何。已有半砖或楼梯构成的柱芯无法按完整方块确认支撑时会拒绝安装。

## 维护验证

复杂原图对比可运行 `mise exec -- python -B tests/engine/fitting-shapes-complex.py --output build/<全新目录> --render`。固定原图与尺寸，对比原有、同材质石墙和混材候选，以同一1/32格原图评估 ornate、细节和耗时，并保留失败记录及成功候选的正视/斜视图。新增形状会尝试把仍满足精细约束的原有楼梯/半砖解作为搜索种子；`shape_search.seed_candidates_evaluated` 记录实际接纳数。精细方案的质量评估固定为每格32像素（`quality_sampling_resolution=32`），避免随形状精度重复放大。拓扑、误差和调用方质量门槛继续执行；更大的候选集不保证每种复杂纹样都改善。

## 原图分析与评分的口径

原图的主纹、孔洞、定位点和小特征面积阈值在固定的每格64像素参考上识别；改变楼梯、石墙或链条候选精度不再改变这组目标。`source_sampling_resolution=64` 记录该口径，省略的小特征计数仍保留，不以减少孔洞来冒称成功。

质量协议版本 `quality_protocol_version=3` 将实际几何与原图统一到每格32像素、1/32格边界容差。`visual_quality.evaluation_grid` 和 `quality_sampling_resolution` 记录实际尺度；相同物理几何不因候选类别而获得不同分数。旧协议分数不能直接与新协议比较，调用方要求的门槛不会自动调低。

`shape_search.repair` 记录有界拓扑修复：尝试次数、预算、初始/最终误差与是否找到可行解。`seed_candidates_evaluated` 记录满足当前约束的原解种子。搜索到上限仍失败时保留失败信息，不能据此断言所有尺寸和构造都不可能。
