# 参数化构件与配方

通过 `capabilities.agent_tools` 查询严格参数 Schema，使用 `components agent` 调用同一 Python 引擎；不依赖 Electron、GUI、浏览器端脚本或 API 服务商。工具定义以 `tool-catalog.json` 为准。

柱、拱、窗墙、顶构与地砖需要共同调整时，见[联动跨间](architectural-bays.md)。bay_compile、vault_compile、tracery_compile 生成有体积和真实接触的构造候选；二维纹样拟合继续用于局部装饰。

## 按职责进入

本篇负责构件类型、参数、硬约束、组合与局部重生成；只读当前需要的完整章节。

| 要完成的事 | 对应资料 |
| --- | --- |
| 组织完整主模型与实例归属 | [统一工作模型](working-model.md) |
| 柱梁、窗、顶构随参数联动 | [对象图](object-scenes.md)；[建筑跨间](architectural-bays.md) |
| 制作、导入或裁取纹样图源 | [纹样来源与制作](pattern-authoring.md) |
| 拟合小主纹、重复铺排与质量验收 | [纹样拟合](pattern-fitting.md) |
| 安装到已有建筑、齐平或浅槽嵌入 | [贴面安装](surface-mounting.md) |
| 复用纯候选调用 | [建模会话](modeling-sessions.md) |

## 纹样优先从微型单元开始

见 [纹样优先从微型单元开始](pattern-fitting.md).

## 拉伸、嵌入与量化视觉质量

见 [拉伸、嵌入与量化视觉质量](pattern-fitting.md).

### 显式拉伸

见 [显式拉伸](pattern-fitting.md).

### 齐平与浅槽嵌入

见 [齐平与浅槽嵌入](pattern-fitting.md).

### 拟合后质量与复杂度

见 [拟合后质量与复杂度](pattern-fitting.md).

## 建模会话与结果复用

见[建模会话与缓存边界](modeling-sessions.md)；拟合细节补搜见[纹样拟合](pattern-fitting.md#复杂微型纹样的细节补搜)。


## 对象与参数

| kind | 对象 | 安装约定 |
| --- | --- | --- |
| pillar | 带基座、柱身和柱帽的装饰柱 | 底面支撑 |
| stairs | 沿 +Z 上升的原版楼梯 | 底面、上下平台需核对 |
| table | 桌面、桌腿与裙边 | 底面支撑 |
| wall | 分格、收边与凸起线脚 | 背面 Z=0 贴实墙，凸出 +Z |
| ceiling | 格栅、交叉梁与层叠边框 | 顶面贴承托，向下悬挂 |
| plant | 单株盆栽 | 底面支撑 |
| planter | 按间距种植的长花槽 | 底面支撑 |
| shelf | 立柱、层板和可选背板 | 底面支撑 |
| bench | 凳面、支腿和可选靠背 | 底面支撑 |
| lantern | 基座、灯杆与灯头 | 底面支撑 |
| railing | 立柱、实心、格构或横档栏杆；可设坡升 | 沿 +X 展开；能精确表示时提供 start/end，薄件不认证半格接口 |
| beam | 实心矩形梁、格构梁、加腋梁 | 沿 +X 跨接；须绑定真实承托 |
| bracket | 叠涩、弧形或斜撑托架 | 背面 Z=0，顶面承托，突出 +Z |
| arch | 圆拱、尖拱、平拱的有厚度拱框 | 框内留空；不挖已有墙，不放入通路冒充可通行 |
| frame | 素面、十字或竖梃门窗框 | 局部 XY 洞口，深度沿 Z；不生成玻璃或门扇 |
| pedestal | 方形、层叠或圆形基座 | 底面支撑 |

必需参数 `kind`、`size:[X,Y,Z]`，通常每轴3～32；矩形梁截面支持1格，柱高最多64。默认 `style=classic`（框架收边）；`stepped` 增加层叠、加厚或侧边；`open` 减少围合、背板或填充。样式按对象解释，新固定截面按下节约束执行；不能将它们视作统一风格的完成建筑模板。

`material` 控制主体，`accent` 控制收边；必须是 Java 1.20.1 合法状态且非空气。`spacing=3`（2～8）控制墙饰分格、吊顶梁格、架层与植物阵列；`thickness=1`（1～3，须小于 X/Z 的一半）控制框边、柱体留边和家具支腿；不影响不使用这些构造的对象。`foliage` 控制盆栽/花槽叶片，默认持久橡树叶。`stair_material` 单独控制阶面，必须为朝 south、bottom、straight、waterlogged=false 的原版楼梯，默认石砖楼梯；material 不替换阶面。name 可选，max_changed_blocks 默认65536，可降低预算。

size 是整体设计包围空间，部分对象为薄浮雕或悬挂构造，不填满整个体积；不自动拉伸到墙面。墙饰仅添加，不挖墙、不猜开口、不破坏外壳。吊顶不凭预览证明连接或承重。楼梯的底部直阶提供半格碰撞形状，仍需放置后核对连续支撑、净空与真实玩家路线，不能仅凭几何认证通行。

## 模块对象库与楼梯扶手

`parametric_list` 的 `object_library` 返回具名配方，每项包含稳定 `id`、中文 `name`、分类 `category` 及可直接传给 `parametric_compile` 的完整 `arguments`。传 `kind` 可筛选；返回值复制后可改尺寸、材质及 form，不会创建资产或批准。应用的“资产管理 → 让 Agent 生成资产 → 参数化模块库”读取同一份库；选择配方会填入建议尺寸，预览后再保存新资产。不同配方有独立尺寸需求，缩小到无法表达时明确拒绝。

库覆盖14种柱配方、12种楼梯扶手组合（其中4种横索式为推荐，另外8种为试作）、5种独立栏杆，以及梁、托架、拱框、门窗框、基座、家具、植物、墙裙和吊顶。五种古典柱式沿用已有实现，新增 `form.section=octagonal/bundled`（八角、束柱）；`band_spacing=2..16` 在柱身按间距换成 accent，保持原截面占用。柱础、柱身、柱头仍保留各自部件边界及原有局部重生成。古典造型是方块适配，不是历史复原。

新的楼梯 `form.handrail` 与旧布尔 `form.rail` 分开；旧调用保留原几何。横索式扶手示例：

```json
{
  "kind":"stairs", "size":[18,12,15],
  "material":"stone_bricks", "accent":"polished_andesite",
  "form":{
    "profile":"spiral", "run_width":3, "rise":8, "landing":3,
    "handrail":{
      "side":"both", "style":"horizontal", "height":2, "post_spacing":3
    }
  }
}
```

- `profile` 继续支持 straight、quarter_turn、switchback、spiral；新方形旋梯至少4级，包含分隔上下入口的延长平台。
- `run_width` 是踏步净宽。扶手在踏步外侧，画布需额外容纳一格边距、转角平台和扶手高度；不会从踏步宽度中扣除栏杆。`rise` 为阶数，每级一格高；不是整段画布高度。
- `side` 为 left/right/both（默认 both），左右以从下向上行进为准；平台衔接同侧上下端点，双侧不会合并。`style` 为 baluster/panel/lattice/horizontal（默认 baluster）。
- `height` 为踏步上方的设计格数2～5（默认2），`post_spacing` 为沿栏杆网格相邻列的节奏1～8（默认3）。立柱向踏步侧下探一层，邻级栅栏在同一高度以横臂连接；半砖用于平台和节奏柱的柱头。默认横索式平台护栏可见高度约1.2格（使用半砖扶手面时约1.5格），台阶内的格点和半格碰撞高度仍须用实际模型核对。
- 默认推荐横索式：深色立柱配不发光的细链索，平台使用薄金属扶手面；坡段在原版方块网格中用同高度横臂衔接。木质竖杆和细金属格构暂标为试作，界面不显示在默认列表；旧封闭 `panel` 仍可显式请求。
- `material` 控制栏体材质，支持完整方块、未含水栅栏、石墙和铁栏杆。`cap_material` 控制平台扶手面，支持完整方块、底部半砖或关闭的底部活板门。留空时按样式选材；坡段不增加独立柱帽。主体 `material/accent` 控制楼梯本体，界面另提供扶手材质字段。连接状态显式保存并随放置旋转，游戏邻接更新仍需另验。
- `tread` 接受裸楼梯 ID 或底部、直形、未含水的状态；跑段决定朝向。显式 facing 只允许 south 作为规范输入，拒绝静默丢弃 top、转角或其他朝向属性。

新楼梯返回 `construction`，包含实际 `walk_columns`、`rail_bases`、`entrance`、`exit`（均为局部 XYZ）、踏步净宽及实际栏杆列数。它是构造回执；`routes/support` 仍为 `not_checked`，安装后用最终模型核对碰撞路线、净空和真实接触。

独立栏杆沿 +X 放在深度中线。`form.profile` 使用同样四种栏体名，`pitch=2..8` 控制立柱或横索款的节奏，原版铁栏杆格构使用固定网格、界面不提供间距调整，`slope=0..24` 为整段坡升；尺寸 Y 至少为 slope+3。`rail_material/post_material` 分别控制扶手面与立柱/格构（默认随样式选材），材质范围同上。界面用专门的扶手材质输入，不再把无效的主体/收边输入用于独立栏杆。`status` 表示配方整理状态：`recommended` 为当前推荐，`stable` 为已有配方，`draft` 为试作。它不代替用户资产的看图批准或游戏验收。默认薄件的接口标为 `fine_rail_faces_not_halfcell_certified`，不声称栅栏/石墙具备半格精确装配面；完整方块和半砖能精确表示时仍提供 `start/end`。对象图可编排薄件，显式精确接触要求遇到未知细碰撞时仍拒绝。其他新模块的 profile 可从 `parametric_list.form_profiles` 查询。

梁提供底部两端的 `support_start/support_end` 接口；托架提供 `back/top`，侧装托架须显式设置 `quarter_turns`。这些接口绑定实际实体，但不自动证明整段梁或上方荷载得到支承。

在软件仓库根目录执行 `mise run modular:test`，验证全库编译、扶手两侧与平台、栏体静态模型盒的接触和空隙比例（铁栏杆、链条使用视觉包络，不认证精确碰撞）、净宽、四向旋转/镜像、SNBT回读、旧调用兼容及公共对象图/CLI。自定义材质组合需要重新检查实际接触；这些测试不构成用户资产的看图批准或游戏验收。

## 梁、托架与门窗洞口模块

以下8条配方已加入 `parametric_list.object_library`，沿用 `parametric_compile/preview`、对象图和工作模型安装流程。它们使用固定截面，界面禁用不适用的结构样式/节奏控件。API 的 `style` 仅接受默认 classic，不接收顶层 spacing/thickness；壁厚和框边厚度使用 `form.border`。旧 solid/coffered/braced、旧托架和旧矩形窗框保持原生成路径。

| 配方 ID | 构造与方向 | form.profile |
| --- | --- | --- |
| beam-timber-rectangular | 沿 +X 的素木梁，裸木材 ID 自动转为沿梁轴木纹 | rectangular |
| beam-concrete-rectangular | 通体矩形混凝土梁 | rectangular |
| beam-steel-i | 上下翼缘与中心腹板，两侧凹槽贯通 | i_section |
| beam-steel-box | 四壁箱形截面，内腔沿 +X 贯通，两端不封堵 | box_section |
| bracket-timber-knee | 背部立杆、顶部横杆、面接触的斜杆，保留三角留空 | knee_brace |
| bracket-steel-angle | 薄 L 形托架，不填满三角区 | angle_bracket |
| frame-timber-doorway | 两侧门梃与顶楣，无底部横槛，默认仅1格厚 | doorway |
| frame-recessed-window | 框、后退玻璃和前挑顶部半砖窗台 | recessed_window |

梁的 size 为沿 X 的长度、截面高 Y、截面宽 Z。矩形梁跨度至少3格，截面可小到1×1格；其他构件每轴仍至少3格。I/箱梁 `border=1..3`，必须满足 `2*border < min(Y,Z)`。矩形梁不使用 border；主体控制中段，accent 控制两端，默认两者同材。I/箱梁主体控制腹板，accent 控制翼缘，默认同色。裸木材 ID 按杆件方向设 axis；显式提供 axis 时保留作者状态。

托架背面为 Z=0，向 +Z 挑出，顶部承接上部构件。`border` 控制杆件厚度，实体位于 X 中线，不用填满画布宽度。背部与顶杆用主体，斜杆用 accent；默认同材。改变整体方向仍通过显式 quarter_turns，接口随放置旋转。

门框 `frame_depth` 默认1，不大于画布深度。净门洞从 Y=0 开始，不自动加门扇；现有墙上的开洞仍经工作模型受检修改完成。窗框正面朝 -Z，框从 Z=1 开始，`recess` 默认2且须位于1到深度-1。`glazing=false` 移除玻璃但保留框体。`glass_material` 只接受完整玻璃方块，`sill_material` 只接受未含水顶部半砖，以便与后方框底形成真实接触。示例：

```json
{"kind":"frame","size":[5,5,3],"material":"white_concrete","accent":"white_concrete","form":{"profile":"recessed_window","recess":2,"glazing":true,"glass_material":"glass","sill_material":"smooth_quartz_slab[type=top]"}}
```

新构件返回 `parts` 与 `construction`。梁提供 support_start/support_end、end_start/end_end、top；托架提供 back/top；门窗提供 left_seat/right_seat/head_top。每个声明区域包含实际实体，装配后仍须核对承托与接触，不把接口当承载能力计算。`construction.apertures` 标注洞口范围、是否有玻璃、是否只是通行候选；玻璃窗不宣称通行。`parametric_regenerate` 支持翼缘、腹板、斜撑、门梃、顶楣、窗台和 glazing 区域；删除玻璃可对同一 glazing 区域重生成。

构造关系参考 [AISC 的空心截面资料](https://www.aisc.org/aisc/solutions-center/hss/)、[工字截面示意](https://www.aisc.org/globalassets/aisc/publications/standards/a370-21w.pdf)、[柱梁与斜撑接头](https://timberframehq.com/post-and-beam-knee-brace-connection/)及 [Andersen 的窗框构件定义](https://www.andersenwindows.com/ideas-and-inspiration/blog/tips/how-to-measure-windows)，于2026-11-17核对；仅提炼形状和构件关系，不复制产品尺寸、设计标准或额定承载值。

在仓库根目录执行 `mise run modular:test`，同时验证对象库和 `tests/engine/structural-members.py`：截面/内腔、木纹、真实门洞路线、玻璃阻挡、局部玻璃移除、柱梁联动、接口、旋转/镜像、SNBT回读和保护。

## 花式窗框与独立资产数据

新配方维护于独立 `NBTCreator-AssetLibrary`，引擎只实现确定性几何；软件内快照和外部库通过 [拓展资产库](asset-libraries.md) 同步。新的推荐数据有上下分格木窗、古典线脚/山花窗、圆拱石窗、玫瑰尖拱彩玻窗，以及编译后的华丽陈设和原创浮雕/镶地。它们不是从远端加载的 Python 插件。

| form.profile | 形体与参数 |
| --- | --- |
| sash_window | 默认 panes=[3,4]，每小格至少2格净尺寸；行数必须为偶数。下扇玻璃在 recess，上扇在 recess+1，须留足深度。只生成静态窗扇，不模拟滑动或配重。 |
| classical_window | 内外两层窗套、前挑窗台、dentils 齿饰及 head=cornice/triangular。cornice_material 仅用于平檐口，须为底部半砖；三角山花使用框材，显式传该字段会拒绝。可用 panes 加分格。 |
| round_arch_window | 圆弧拱框、前方楔石，lights 控制竖向分栏。玻璃服从真实弧形，不用矩形不透明板补背面。 |
| pointed_arch_window | 默认双光尖拱、玫瑰窗和连接杆；复用建筑窗棂生成器。复杂窗棂至少11×15格，固定 border=1、lights=2。tracery=false 可做较简洁分栏尖拱窗。 |

玻璃在 `glass_material` 与 `glass_palette` 中选一种，配色1～8项且必须为原版完整玻璃方块。框和窗棂使用不透明完整方块；`bar_material` 控制分格条/窗棂，裸木材自动设杆向木纹。`sill_material` 须为未含水顶部半砖。`recess` 位于1到深度-1，上下木窗另需多一层玻璃空间。新窗型不叠加通用 ornament，避免把玻璃刷成不透明纹样；装饰由窗型本身的线脚、齿饰和窗棂组织。

```json
{"kind":"frame","size":[13,24,4],"material":"smooth_sandstone","accent":"cut_sandstone","form":{"profile":"classical_window","head":"triangular","dentils":true,"recess":3,"detail_material":"chiseled_sandstone","sill_material":"smooth_sandstone_slab[type=top]"}}
```

`construction.apertures` 返回轮廓、名义洞口 cells_xy 和实际贯通的 clear_cells_xy；有玻璃时不声称通行。三个安装接口只声明真实占用的承托点，不夸大成完整顶面。`glazing=false` 保留窗框及窗棂；可通过同边界 glazing 区域局部重生成。组件保存不自动挖宿主墙，安装仍须按当前主模型的保护、预算、墙 mask 和源哈希处理。

构造识别参考 [Historic England 传统窗资料](https://historicengland.org.uk/images-books/publications/traditional-windows-care-repair-upgrading/heag039-traditional-windows-revfeb17/)和 [V&A 哥特式语汇](https://www.vam.ac.uk/articles/the-gothic-style-an-introduction)，于2026-11-17核对。新资产是方块化设计，不声称复原具体建筑或通过游戏实测。`mise run modular:test` 包含花式窗7项回归；已制作的独立华丽库另用 `python -B tests/engine/ornate-library.py --library <库目录>` 验证旋转、SNBT、类型覆盖和齐平镶地路线。

## 装饰风格与纹样参数

结构 `style` 与 `ornament.profile` 分开：例如通透结构 open 可以叠加古典装饰，stepped 也可以叠加哥特语汇。默认 profile=none 保持旧几何。

| ornament.profile | 可选 motif | 查询资料与适配范围 |
| --- | --- | --- |
| classical | dentil、fluting | [Met 的柱式、分槽与檐带](https://www.metmuseum.org/ko/essays/architecture-in-ancient-greece)；[Met 框饰资料中的齿饰](https://resources.metmuseum.org/resources/metpublications/pdf/Italian_Renaissance_Frames.pdf)；实现为重复小块和竖向分格，不复原完整柱式 |
| gothic | pointed_arch、tracery | [V&A 哥特式介绍](https://www.vam.ac.uk/articles/the-gothic-style-an-introduction)；方块化尖拱轮廓与几何窗饰，不挖真实窗洞 |
| art_deco | chevron、sunburst | [V&A 装饰艺术介绍](https://www.vam.ac.uk/articles/an-introduction-to-art-deco)、[NGV 纹样教学资料](https://www.ngv.vic.gov.au/artdeco/education/resources/Deco_Clues.pdf)；折线和放射节奏 |
| art_nouveau | vine、leaf | [V&A 新艺术介绍](https://www.vam.ac.uk/articles/art-nouveau-an-international-style)；植物曲线与叶饰的体素近似，不宣称精细雕花 |
| geometric | lattice、diamond | 通用格栅、菱形图案，是本工具的几何设计，不标注为特定地域传统工艺 |

资料于2026-11-14查询。上述特征来自资料，具体体素规则为本工具的设计适配；尺寸离散、纹样组合和安装方法不由史料证明。资料只存链接和适配摘要，运行工具不联网。

`ornament` 是可选严格 JSON 对象：

- profile：none/classical/gothic/art_deco/art_nouveau/geometric。
- motif：auto 默认选该风格第一项；显式纹样必须属于该风格。
- density：0～100，默认65，确定性选择内部纹样单元；不控制固定边框。完全无装饰用 profile=none；只取消内部纹样可设 density=0。
- scale：2～8格，默认4，控制纹样周期或放射分段的离散尺度。
- depth：1～3，默认1。墙饰从背面+Z突出，必须小于Z尺寸；吊顶从顶面下一层向下展开，不能超过Y-1。家具仅在已有实体表面着色，楼梯仅在已有踏步下侧面着色，不挖空、不向通路新增方块。
- symmetry：默认true，横向镜像纹样和密度采样；false允许不对称。
- border_layers：0～3，默认1，控制装饰面外围固定边框；装饰面最小宽高须至少为2*border_layers+3，否则明确拒绝。
- material：装饰专用原版方块状态；未提供时沿用用户的accent，否则默认雕纹石砖；不允许空气。
- seed：0～2147483647，默认0，控制密度分布；相同参数确定性复现。

这些参数不会覆盖主材、收边材或结构样式。植物只装饰容器不替换叶冠；桌、架、凳和灯架只处理局部+Z侧已有实体；吊顶处理XZ装饰面。depth对家具代表已有实体内的饰面厚度，不凭空加雕花。局部可用面不足时返回 added_or_recolored_blocks=0，不能称作已产生装饰。所有面仍受原尺寸、保护、占用与总预算约束；改变材质可能改变碰撞，放置后必须重验。

查询全部或筛选风格：

```json
{"kind":"wall","ornament_profile":"gothic"}
```

把上面 JSON 传给 parametric_list，其 ornament_profiles 返回风格特征、可用纹样与来源链接。参数化编译请求例如：

```json
{
  "kind":"wall", "size":[15,13,4], "style":"open",
  "material":"stone_bricks", "accent":"polished_andesite",
  "ornament":{
    "profile":"gothic", "motif":"pointed_arch",
    "density":100, "scale":4, "depth":2,
    "border_layers":1, "symmetry":true,
    "material":"chiseled_stone_bricks", "seed":42
  }
}
```

将此请求交给 parametric_compile 或 parametric_preview。结果 ornament 返回解析后的参数、来源、实际新增/换材方块数与限制，参数和配方哈希随预览绑定并在入库后保留。小尺寸下纹样会近似，始终需看实际图。

## 模型返回的硬约束验收

外部调用方先保存用户的硬约束，调用 `parametric_contract` 取得 `response_schema` 和 `constraints_sha256`，将 Schema 提供给模型；若服务支持结构化输出，可按其支持的 Schema 子集设置响应格式。本工具不替调用方配置远程服务的解码器，也不保证任何兼容 API 都支持完整 JSON Schema。

请求示例（contract.json）：

```json
{"constraints":{"kind":"wall","size":[15,13,4],"profiles":["gothic"],"motifs":["pointed_arch"],"min_density":80,"max_density":100,"max_depth":2,"max_blocks":2048,"max_operations":30,"require_decoration":true}}
```

```powershell
mise run nbt -- components agent --tool parametric_contract --request contract.json
```

模型只能返回 proposal 方案，不能附带或修改 constraints。调用方用自己保存的原始 constraints 组装验收请求：

```json
{
  "proposal":{"kind":"wall","size":[15,13,4],"ornament":{"profile":"gothic","density":100,"depth":2}},
  "constraints":{"kind":"wall","size":[15,13,4],"profiles":["gothic"],"motifs":["pointed_arch"],"min_density":80,"max_density":100,"max_depth":2,"max_blocks":2048,"max_operations":30,"require_decoration":true}
}
```

```powershell
mise run nbt -- components agent --tool parametric_validate --request validation.json
```

Schema限制字段、枚举、明确数值与固定尺寸；本地验收另外检查解析后的默认参数、风格与纹样组合、实际材质白名单、方块数和操作数，并运行共享几何编译。缺省参数不能绕过上限。materials可指定合法状态白名单（使用规范化minecraft命名），会检查最终实际调色板，包括叶片、土壤、阶面等自动生成材质。require_decoration=true还要求实际产生装饰，不能用零变化糊弄通过。

不合格返回错误且不写文件，不裁切、不偷偷换风格或放宽预算。合格返回 accepted=true、确定的spec、constraints_sha256与几何证据；它不表示用户批准或游戏验收。调用方只将返回的spec传给structure_preview，再走既有入库/放置/导出。

这是验收门禁，不能保证模型从不生成违规文字。外部编排必须始终调用parametric_validate，且约束来自可信调用方；不能让模型同时填写自己的硬约束，也不能验收后重新从模型回答取另一份spec。原parametric_compile仍是通用编译接口，不携带会话级用户硬约束。调用方可按错误要求模型修正，但没有自动扩大权限的重试。契约哈希用于比对同一份约束，不是用户授权签名。

## CLI 示例

从创作项目根目录运行；这里的软件源码目录不生成工作区 facade。无 facade 的维护调用使用 `python .agents/skills/minecraft-nbt-modeler/scripts/nbt_components.py --workspace <创作项目> agent ...`。

准备 `params.json`：

```json
{"kind":"wall","name":"石构墙面分格","size":[15,9,3],"style":"stepped","material":"stone_bricks","accent":"chiseled_stone_bricks","spacing":4,"thickness":1,"max_changed_blocks":2048}
```

```powershell
# empty.json 内容为 {}
mise run nbt -- components agent --tool parametric_list --request empty.json
mise run nbt -- components agent --tool parametric_compile --request params.json
mise run nbt -- components agent --tool parametric_preview --request params.json
```

三个调用均返回 `{ok,result}`。compile 只在内存中生成并校验 spec，返回确定性配方 SHA256、内容 SHA256、方块数、安装约定和未验收状态；不创建文件。preview 另生成绑定预览、主模型草稿、快照、真实简化缩略图和相机，不保存资产、不修改建筑、不创建批准。

根据 preview 的实际路径看图；需要纹理审阅时用 `render` 对返回的 source 和 cameras_file 出图。简化缩略图不代表纹理、碰撞、支承或游戏验收完成。

参数化预览的原始参数、生成器 revision、配方哈希和安装约定写入哈希绑定的 draft.json；structure_write/structure_save 入库后保存在 `.nbtcreator/components/recipes/<资产ID>.json` 的 parametric_recipe 字段。调整时取回 parameters 重新编译，另存新资产，不修改旧资产。

下一步调用 `structure_write`，请求为 preview 返回的 `preview_id` 与 `preview_sha256`。返回新的资产 ID 和内容 SHA256。再调用 `structure_place`：

```json
{"id":"真实返回的资产ID","content_sha256":"真实返回的内容SHA256","position":[20,2,20],"size":[48,24,48],"quarter_turns":1,"overwrite":false}
```

position 为局部锚点在目标建筑中的位置：普通构件底部中心、墙饰背面底部中心、吊顶顶面中心。quarter_turns 绕 Y 轴旋转，mirror 可选 x/z，按既有保守状态转换，不支持的状态拒绝，不猜方向。返回 operations 仍只是候选；用真实建筑源和上下文走现有 control preview/validate，保护、冲突、边界与总预算都必须通过。overwrite 不取消保护。保存下一制作版与定稿 NBT 保持显式授权和原有确认流程。

Agent 也可将 compile 返回的 spec.operations 合入整体主模型生成器；其坐标仍是对象局部坐标，必须自行正确变换并使用共享引擎验证。不能直接把未平移的操作套在全局建筑上。重用同一参数会得到相同几何；配方哈希绑定生成器 revision、输入参数和展开 spec，不是用户批准。

本阶段是体素参数化对象库，不支持任意曲线扶手、真实家具交互、自动贴合任意曲面或墙面开口识别；不增加新的底层 operation kind，编译结果复用现有工具。


## 安装在已有建筑上

见 [安装在已有建筑上](surface-mounting.md).

## 批量安装与保留宿主配方

见 [批量安装与保留宿主配方](surface-mounting.md).

## 专用构造、组合与局部重生成

`parametric_list` 返回主题和各类构件适用的 form 字段。form 用于指定下表的专用构造，省略时沿用原有结构样式。ornament 可以继续叠加装饰。对于不适用的 form 字段，工具会拒绝请求。

| 构件 | form 参数 |
| --- | --- |
| 墙饰 | base_height、dado_height、cornice_height、panel_pitch、relief_depth 控制踢脚、墙裙、檐口、分格和凸出深度 |
| 柱子 | base_height、capital_height、base_material、capital_material 控制柱础与柱头。section 选 square、cross 或 round；form.order 可选古典柱式。taper、inset、flutes 控制收分和槽纹 |
| 吊顶 | profile 选 grid 或 parallel。drop、pitch、border、light_strip 控制下吊、节奏、边框和灯带 |
| 楼梯 | profile 选 straight、quarter_turn、switchback 或 spiral。run_width、rise、rail、tread 控制跑宽、高差、挡边与踏步材质。landing 适用于转角和折返，方形螺旋的平台宽度随跑宽 |
| 植物 | profile 选 upright、trailing 或 climbing。pot_height、crown_height、radius、density、seed 控制盆器与叶冠的体素形态。climbing 生成贴平面的叶冠，实际贴墙位置由调用方确定 |

吊顶安装可设 min_clearance 检查新增构件正下方连续净空。安装和布局可设 require_routes=true，按坐标资料中的起点和目标检查放置后模型。楼梯含原版踏步与转向平台，rail 生成实块挡边。旋转支持直形楼梯方块并变换朝向，有左右手性的转角楼梯状态维持拒绝。螺旋为方形多跑组合。

装饰布局使用 ornament.layout 选择 continuous、centerpiece 或 corners。ornament.center_clear 给中心纹样留空，边框另由 border_layers 控制。已有主体方块保留。主题 theme 选 stone_hall、timber_room 或 deepslate_workshop，提供主体材质、收边材质和间距默认值，每个对象可显式覆盖。

微型拟合候选与质量评分使用同一精确位图连通统计：主纹按8邻接、孔洞按4邻接，仅统计不触边的背景区域。位运算加速不缩小图片、不减少候选、不改变楼梯/半砖选择或质量阈值；真实安装仍检查接触、保护、占用和预算。

### 柱础、柱头和独立嵌纹

需要罗马柱时先用 form.order 的五种[古典柱式](classical-columns.md)，圆柱身、凹槽、涡卷、莨苕叶和颈饰由脚本生成。柱子高度可到64格，宽深仍最多32格。以下通用柱端造型与平面嵌纹可用于自定义方案。

柱子的 form 可分别指定 `base_profile` / `capital_profile`：plain（原有整块端部）、stepped（层叠）、beveled（收坡）、torus（圆鼓线脚）、bell（钟形）、bezier（自定义曲线）。它们使用原 base_height / capital_height / base_material / capital_material，始终留在 size 中，不悄悄增大占地。非plain至少3格高，柱础与柱头总高须小于柱高。省略新参数时保持原有几何。

bezier 须分别给 `base_curve` / `capital_curve`：4个0.2～1的半径比例控制值，按部件底部到顶部排列，例如 `[0.55,0.9,0.4,1]`。它控制中间线脚的三次曲线，最底/顶承台及连续中心仍保留；体素分层不会等同于光滑曲面。默认柱头轮廓相对柱础翻转，显式curve不自动翻转。

上下端还可分别给 `base_pattern` / `capital_pattern`，其中 pattern 提供 preset 或 pattern_asset / pattern_ref、size_uv、材质、形状和微型质量参数；faces 可选 north/east/south/west，默认四面。工具自动居中、定向并齐平镶嵌，保留一格背衬；不手填每面坐标。纹样上下及四角各至少留1格，超出部件拒绝，不截断或降低质量门槛。脚本在装饰所在高度自动保留完整实面饰带，因此纹样较高时会减少可见的收分层数；需要更明显线脚时增加该端高度或使用更矮单元。

```json
{
  "kind":"pillar", "size":[9,32,9], "material":"quartz_block", "accent":"light_gray_terracotta",
  "form":{
    "base_height":6,"capital_height":8,"base_profile":"torus","capital_profile":"bell","flutes":true,
    "base_pattern":{"pattern":{"preset":"micro-scroll","size_uv":[4,2],"material":"quartz_block","quality_profile":"border","min_quality_score":85}},
    "capital_pattern":{"pattern":{"preset":"micro-palmette","size_uv":[4,4],"material":"quartz_block","quality_profile":"border","min_quality_score":85}}
  }
}
```

end_decorations 分别返回上下端每面的真实拟合、朝向和局部放置回执，坐标仍为原柱子画布。完整柱子保持body归属，新增柱端不会被误记为建筑墙层。生成期间在内部留空气边界检查外侧格；已声明实面饰带按逐格支承检查，不把设计收分当作外墙未知门洞。写回建筑时仍须检查建筑自己的支承、保护、开口和通路。

对象图的 pattern_ref 可放进这两个参数，更新绑定后重新生成柱端；parametric_regenerate 仍支持 base / capital 局部重生成并拒绝改变部件外的柱身。shape、材料、收分与纹样属于同一柱子配方，不需把上下端烘焙成失去来源的独立方块。

### 家具与构件组合

将以下请求交给 `parametric_compose`。按各对象的局部锚点放置，支持 quarter_turns。可组合桌、凳、架、植物以及其他参数化对象。

```json
{
  "name": "木构用餐区",
  "size": [18, 8, 18],
  "objects": [
    {"id": "table", "position": [6, 0, 6], "object": {"kind": "table", "size": [5, 3, 5], "theme": "timber_room"}},
    {"id": "bench", "position": [6, 0, 11], "object": {"kind": "bench", "size": [5, 3, 3], "theme": "timber_room"}}
  ],
  "reserved_boxes": [{"lo": [9, 0, 3], "hi": [10, 2, 13]}]
}
```

reserved_boxes 可声明椅后通道、使用侧或柜门开启空间。工具检查边界、保留空间、碰撞重叠和方块预算，返回对象编号、各自配方哈希、包围盒及可交给 structure_preview 的 spec。

### 仅修改一个部件

`parametric_regenerate` 接收 object_id、original、original_recipe_sha256、replacement 和 part，可选 max_changed_blocks。original 与 replacement 都使用参数化请求格式。part 支持柱础 base、柱身 shaft、柱头 capital、吊顶边框 trim、盆器 container、叶冠 crown、墙裙 wainscot 和檐口 cornice。两份参数必须属于同一类型和尺寸，并保持选定部件边界。如果参数改变部件之外的任何方块，工具会拒绝。

例如，将原柱子配方复制到 replacement，仅改 form.capital_material，再选 part=capital。结果带原对象编号、父配方哈希、修改范围及变化量，输出可预览的新 spec。由调用方保存该结果与版本关系，已有资产继续按现有显式保存接口管理。


### 贴面连接与整栋审阅

见 [贴面连接与整栋审阅](surface-mounting.md).


### 华丽纹样与样本拟合

见 [华丽纹样与样本拟合](pattern-authoring.md).

### 实际建筑纹样与收边

见 [实际建筑纹样与收边](pattern-authoring.md).

### 样本减色与半格轮廓拟合

见 [样本减色与半格轮廓拟合](pattern-authoring.md).


### 纹样库与多面板拟合

见 [纹样库与多面板拟合](pattern-fitting.md).

#### 圆柱环绕

见 [圆柱环绕](pattern-fitting.md).

### 小纹样生成、区域采样与组合资产

见 [小纹样生成、区域采样与组合资产](pattern-authoring.md).

### 当前推荐与现实构造参考

横索扶手按 [Viewrail](https://www.viewrail.com/rod-railing) 的立柱与细杆层次取意；竖杆试作参考 [Keuka Studios](https://www.keuka-studios.com/case-studies/custom-metal-stairs/flat-bar-railing/) 的规则竖杆与统一扶手线，网格试作参考 [Jakob Frames](https://www.jakob.com/pl/en/portfolio/frames) 的框架与细网填充。以上为构造关系的方块化适配，不声称复原产品或满足现实规范。参考于2026-11-17核对。

柱子新增三组基础对象：`pillar-modern-flush` 通体现代方柱、`pillar-timber-post` 石础木柱、`pillar-classical-plain` 素面古典圆柱。前两组用 `form.shaft_inset=0` 让非圆柱身与柱端齐平；默认仍为1，旧请求保持几何。圆柱使用原有 `inset/shaft_ratio`。古典柱继续保留柱础、柱身、柱头与分部再生，构件角色可参照 [Met 的实物柱身与柱础](https://www.metmuseum.org/art/collection/search/471346)。尺寸是可调整的建模包围空间，放入具体建筑时须按玩家尺度选择。
