# 外部 Agent 参数化建模

通过 `capabilities.agent_tools` 查询严格参数 Schema，使用 `components agent` 调用同一 Python 引擎；不依赖 Electron、GUI、浏览器端脚本或 API 服务商。工具定义以 `tool-catalog.json` 为准。

## 纹样优先从微型单元开始

纹样主流程使用 `pattern_microfit`，先做好2～8格的单个可辨单元，再铺排到墙、柱、地板和吊顶。它接收与 pattern_compile 相同的 preset / sample / preset_options，size_uv 表示**单元**宽高，范围1～12格；单格用于笔画和半砖条带，主纹优先2～8格。无需先画成一张大墙再整体缩小。

```json
{"surface":"wall","size_uv":[4,4],"sample":{"path":"micro-ring.png","sha256":"<原图SHA256>","noise_strength":0},"tile_counts":[4,3],"gap_uv":[1,1],"preview":true}
```

此例先拟合4×4格单元，再复制成4列3行，中间各留1格，最终面板为19×14格。所有单元使用同一组方块与状态，不在铺排时重新缩放采样。原图可以来自 pattern_create 的8～32像素小位图/绘图配方，也可以用 sample.crop 裁出单个叶片、环扣或菱花。pattern_create 默认分辨率已改为16×16，输出的 fitting_input 可直接用于微型拟合。

微型脚本先按源图 threshold 二值化，再计算半格面积覆盖率。它尝试多档覆盖率阈值，锁定主轮廓的四向极值和主孔洞位置，并比较拟合后的连通分量与孔洞。源图的采样轮廓若严格左右/上下对称，会将对应方块联合匹配，避免各格独立选择楼梯/半砖时破坏对称性，preserved_symmetry_axes 记录结果。小于半个采样格面积的孤立细点/孔洞不计入主拓扑，报告会记录数量。source_threshold 与 selected_coverage_threshold 是两个不同阶段的阈值。候选优先保留主拓扑，再比较墨迹交并比 ink_overlap，减少大面积空白对匹配优劣的干扰。raw_coverage_error 是实际投影与源二值掩模的平均面积差异，stylized 表示存在明显的小尺寸简化；这些几何检查仍需结合真实预览评审。

脚本根据 material 自动寻找同材质楼梯和半砖，也可在 shapes 指定材料。朝向与上下状态自动选择。无同材质半砖/楼梯时使用整块，不自动换成别的颜色。full_blocks_only=true 可限制整块。平齐地板只用整块，吊顶只在可用楼梯的下半层细分；无法在给定尺寸保留主纹和孔洞时会拒绝。例如细线环可用四个楼梯拟合成2×2格墙饰，平齐地板的2×2格无法容纳中孔，需用更大的单元。

| 参数 | 用途 |
| --- | --- |
| tile_counts | 每轴1～16份，默认1×1；圆柱未指定时自动计算绕周可容纳的份数 |
| gap_uv | 平面单元间距0～4格，默认1×1；圆柱竖向沿用间距，周向将剩余格数均匀分配 |
| diameter | 仅微型圆柱，柱芯直径4～30，默认13格；size_uv 仍是纹样单元尺寸 |
| micro_max_error | 允许的平均面积差异0～1，默认0.65；主拓扑仍须匹配，不因放宽此值跳过检查 |
| preview | 仅 pattern_microfit，生成真实候选、图片和相机，不保存构件或修改建筑 |

圆柱例：`{"surface":"cylinder","size_uv":[4,4],"diameter":13,"tile_counts":[4,3],...}` 将四份4格宽单元均布在圆周，竖向三排。不会把单元压缩到圆周宽度。总面板尺寸仍受每轴64格、预算和保护约束。

microfit 报告针对单个单元，shape_counts 是全部铺排用量。返回的 mount_object 可直接交给 pattern_mount.object，圆柱则交给 pattern_cylinder_mount.object。微型墙饰和吊顶安装会复用已验证的原墙/顶面，只增加外饰层，不另铺整层背板。两种安装仍绑定原稿、保护和快照哈希。同一模式也可通过 pattern_compile / pattern_preview 的 fit_mode=micro 调用；整图拟合使用标准模式及 repeat。

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

必需参数 `kind`、`size:[X,Y,Z]`，每轴 3～32。默认 `style=classic`（框架收边）；`stepped` 增加层叠、加厚或侧边；`open` 减少围合、背板或填充。样式按对象解释，不能将它们视作统一风格的完成建筑模板。

`material` 控制主体，`accent` 控制收边；必须是 Java 1.20.1 合法状态且非空气。`spacing=3`（2～8）控制墙饰分格、吊顶梁格、架层与植物阵列；`thickness=1`（1～3，须小于 X/Z 的一半）控制框边、柱体留边和家具支腿；不影响不使用这些构造的对象。`foliage` 控制盆栽/花槽叶片，默认持久橡树叶。`stair_material` 单独控制阶面，必须为朝 south、bottom、straight、waterlogged=false 的原版楼梯，默认石砖楼梯；material 不替换阶面。name 可选，max_changed_blocks 默认65536，可降低预算。

size 是整体设计包围空间，部分对象为薄浮雕或悬挂构造，不填满整个体积；不自动拉伸到墙面。墙饰仅添加，不挖墙、不猜开口、不破坏外壳。吊顶不凭预览证明连接或承重。楼梯的底部直阶提供半格碰撞形状，仍需放置后核对连续支撑、净空与真实玩家路线，不能仅凭几何认证通行。

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
python .agents/skills/nbtcreator-workspace/nbt.py components agent --tool parametric_contract --request contract.json
```

模型只能返回 proposal 方案，不能附带或修改 constraints。调用方用自己保存的原始 constraints 组装验收请求：

```json
{
  "proposal":{"kind":"wall","size":[15,13,4],"ornament":{"profile":"gothic","density":100,"depth":2}},
  "constraints":{"kind":"wall","size":[15,13,4],"profiles":["gothic"],"motifs":["pointed_arch"],"min_density":80,"max_density":100,"max_depth":2,"max_blocks":2048,"max_operations":30,"require_decoration":true}
}
```

```powershell
python .agents/skills/nbtcreator-workspace/nbt.py components agent --tool parametric_validate --request validation.json
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
python .agents/skills/nbtcreator-workspace/nbt.py components agent --tool parametric_list --request empty.json
python .agents/skills/nbtcreator-workspace/nbt.py components agent --tool parametric_compile --request params.json
python .agents/skills/nbtcreator-workspace/nbt.py components agent --tool parametric_preview --request params.json
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

三个接口均通过 `nbt.py components agent --tool <工具> --request <JSON>` 调用。

1. `parametric_surface` 接收 `{"surface": {...}}`。surface 提供 source、source_sha256、geometry_sha256、context、context_sha256、lo、hi 和 normal。lo/hi 是单格厚度的支承平面，normal 是装饰伸出的方向，可选 north/south/east/west/up/down。可设 min_support（已确认的连续方块厚度，1～8）和 opening_margin（缺口四周保留格数，0～8）。如使用候选，另提供 snapshot 和 snapshot_sha256。
2. 查询返回 surface_sha256、已确认安装格、厚度、遮挡、未知形状及连通空气缺口。侧墙的 UV 为 X/Y 或 Z/Y，地面与吊顶为 X/Z，从 lo 开始沿世界正轴计数。空气缺口保持未分类，薄形状、未知形状及其边距纳入避让。
3. `parametric_mount` 接收同一 surface、surface_sha256、`object`（原参数化构件请求）和 `anchor_uv:[u,v]`。侧墙用 wall，下挂面用 ceiling，其余构件从地面向上放置。例如在 `lo=[0,2,7]`、normal=south 的墙面上，`anchor_uv:[8,0]` 对应邻接安装格 `[8,2,8]`。侧墙按法向旋转构件。
4. `parametric_layout` 接收同一组字段，使用 pattern 代替 anchor_uv。grid 为居中阵列，border 为阵列外圈，center 为单个居中对象。gap_uv 控制实例间距，edge_margin 控制边缘留量，reserved_boxes 指定额外留白，max_instances 和 max_changed_blocks 限制布局规模。on_conflict 默认 reject，设 skip 时返回每个跳过的锚点和原因，超出总预算仍会失败。

安装规划要求每个写入点的投影都有可用支承，每个方块连通组接触安装面。保护区、留白和实际占用优先。结果包含 operations、源与上下文哈希及候选几何哈希。按同一源、同一上下文及同一预算进入现有 control preview/validate 流程。几何接触、保护和预算由工具验证，玩家路线、实际承重和设计效果仍需单独审阅。首版支持平直轴对齐安装面。


## 专用构造、组合与局部重生成

`parametric_list` 返回主题和各类构件适用的 form 字段。form 用于指定下表的专用构造，省略时沿用原有结构样式。ornament 可以继续叠加装饰。对于不适用的 form 字段，工具会拒绝请求。

| 构件 | form 参数 |
| --- | --- |
| 墙饰 | base_height、dado_height、cornice_height、panel_pitch、relief_depth 控制踢脚、墙裙、檐口、分格和凸出深度 |
| 柱子 | base_height、capital_height、base_material、capital_material 控制柱础与柱头。section 选 square 或 cross。taper、inset、flutes 控制收分和槽纹 |
| 吊顶 | profile 选 grid 或 parallel。drop、pitch、border、light_strip 控制下吊、节奏、边框和灯带 |
| 楼梯 | profile 选 straight、quarter_turn、switchback 或 spiral。run_width、rise、rail、tread 控制跑宽、高差、挡边与踏步材质。landing 适用于转角和折返，方形螺旋的平台宽度随跑宽 |
| 植物 | profile 选 upright、trailing 或 climbing。pot_height、crown_height、radius、density、seed 控制盆器与叶冠的体素形态。climbing 生成贴平面的叶冠，实际贴墙位置由调用方确定 |

吊顶安装可设 min_clearance 检查新增构件正下方连续净空。安装和布局可设 require_routes=true，按坐标资料中的起点和目标检查放置后模型。楼梯含原版踏步与转向平台，rail 生成实块挡边。旋转支持直形楼梯方块并变换朝向，有左右手性的转角楼梯状态维持拒绝。螺旋为方形多跑组合。

装饰布局使用 ornament.layout 选择 continuous、centerpiece 或 corners。ornament.center_clear 给中心纹样留空，边框另由 border_layers 控制。已有主体方块保留。主题 theme 选 stone_hall、timber_room 或 deepslate_workshop，提供主体材质、收边材质和间距默认值，每个对象可显式覆盖。

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

`parametric_mount` 和 `parametric_layout` 支持以下可选字段。它们与原有 surface、surface_sha256、object 等字段并列。

```json
{
  "surface_fit": {"max_gap": 2, "material": "stone_bricks"},
  "compare_routes": true,
  "review": {"cameras": "review-cameras.json", "render": true}
}
```

surface_fit 为悬空方块组寻找沿安装面法向的最短可行连接。max_gap 为允许补齐的最大距离（1～8 格）。material 可指定已知完整方块，缺省沿用饰件材质。脚本保留饰件位置，连接格计入预算并受开口边距、占用、留白和保护检查约束。各实例返回 connector_positions。未启用贴面时，悬空组仍会报错。当前实现适用于轴对齐平面上的短直连接，曲面和绕障连接需要另行建模。

compare_routes 检查安装前后的整体路线与各 route_legs，包括各路径段的验证障碍。报告注明可达变化、搜索上限以及旧路径附近的候选写入。候选路径点数可供比较，净宽需要另行量测。require_routes=true 时任一声明的候选路线失败都会拒绝计划。

review.cameras 指向工作区机位 JSON，支持 1～8 个共同机位。工具生成前后独立 SNBT、快照与 review.json，记录包含本次候选、源与上下文。render=true 另输出同机位纹理图，使用现有浏览器渲染环境。审阅目录位于 nbt_models/_workspaces/mount_review，失败时记录失败状态及出图日志。后续按原流程验收并显式保存建筑版本。


### 华丽纹样与样本拟合

ornament.richness 取 0～3，逐级加入珠饰、斜线花丝和中心环。ornament.highlight 控制这些细节最外层的材质，默认沿用装饰材质。此叠加仍遵守布局范围、中心留白和构件保护规则。

```json
{
  "kind": "wall",
  "size": [27, 25, 4],
  "style": "classic",
  "ornament": {
    "profile": "geometric",
    "material": "chiseled_stone_bricks",
    "highlight": "gold_block",
    "richness": 3,
    "depth": 2,
    "density": 100,
    "seed": 42,
    "sample": {
      "path": "references/rosette.png",
      "sha256": "<从本地图片计算的SHA256>",
      "channel": "luminance",
      "fit": "contain",
      "threshold": 50,
      "noise_strength": 20,
      "noise_scale": 4,
      "mirror": false
    }
  }
}
```

亮度模式默认亮处生成装饰，alpha 模式用透明度生成装饰。invert 可反转阈值输入，完全透明区域仍排除。contain 保持比例并留边，cover 等比裁切以填满装饰面。noise_strength 为 0～100，0 保留纯样本阈值。noise_scale 为 1～16 格，数值越大，变化越连片。同一图片哈希、种子和参数可复现几何。sample.mirror 可沿样本左半边镜像，与结构纹样的 symmetry 分开。density 可继续稀疏采样结果。样本替代内部基础纹样，边框、布局、留白和华丽度叠加仍生效。

工具接收工作区内的单帧 PNG、JPEG 或 WebP，最多 8 MiB、4194304 像素。它将图案按装饰面的格数重采样，再用固定种子的二维值噪声扰动阈值。这是一种二维掩模到方块纹样的转换，颜色材质由 material 和 highlight 指定。建议使用高对比正视线稿、浮雕掩模或透明剪影。倾斜照片与复杂背景需要先裁切或校正。后续可用 parametric_preview 查看结果，再按安装面运行贴面、预算和路线检查。


### 实际建筑纹样与收边

`parametric_list` 的 `architectural_samples` 提供馆藏下载页、公开使用标记、建筑用途及裁切建议。卡尚星十字砖适合制作墙面重复单元，布尔萨卷草用于门口边带，卡尚角砖用于角饰。它们是实际建筑使用的实例。模型流程采用建模师常用的做法，将纹样裁成重复单元，先排布整体，再加收边和浮雕。馆藏照片仍需按用途裁切，尤其不能把单块十字砖等同于可无缝覆盖的星十字组合。

```json
{
  "sample_repeat": [3, 1],
  "edge_trim": {
    "slab": "stone_brick_slab",
    "stairs": "stone_brick_stairs"
  }
}
```

以上字段位于 ornament 内，sample_repeat 分别控制横纵重复次数。它按重复单元重新拟合样本，支持1～8次。指定 sample.reference_id 可携带馆藏来源，图片的实际内容仍由本地 path 和 sha256 校验。可使用目录项的 suggested_layout 和 suggested_repeat 作为起点。

edge_trim 仅用于墙饰和吊顶的新增外层边缘，不替换现有基底格。半砖用于薄收边，直形楼梯用于有方向的转折。depth=2 或3可保留内层厚度。安装后仍按现有贴面与路线流程核验。半砖和直形楼梯状态支持现有旋转、镜像。


### 样本减色与半格轮廓拟合

`ornament.sample.colors` 可声明 1～8 对 RGB 色值与方块材质。例如 `[{"rgb":"#204784","material":"blue_concrete"},{"rgb":"#E6DFCD","material":"quartz_block"}]`。样本 RGB 按最近颜色映射到指定材质。透明度或亮度阈值仍独立决定轮廓，边框保留 material，华丽细节保留 highlight。建议先裁出单个周期、去背景，再保留 2～4 个主色，避免把釉面反光和拍摄阴影当成新颜色。

`ornament.sample_shape_fit` 可指定 `{"slab":"quartz_slab","stairs":"quartz_stairs"}`。墙饰在 depth=1 时按每格四个半格选择空格、整块、上/下半砖或东西向直形楼梯。整块按配色表选材，半砖和楼梯使用各自指定的材质。此模式与 edge_trim 互斥。报告分别给出各类方块用量和拟合轮廓中遗漏、多出的半格。图片投影仍需要正视裁切，密集细纹可以先勾出主轮廓。


### 纹样库与多面板拟合

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

#### 圆柱环绕

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

### 小纹样生成、区域采样与组合资产

外部 Agent 可先设计一个小型二维纹样，再交给共用拟合器。`pattern_create` 接收小位图或受限绘图配方，生成实际 PNG、缩略图和配方，并保存为原生纹样资产。它不执行代码，也不写建筑。外部 Agent 已有生图能力时，也可把生成图片保存到创作工作区，再用 `pattern_assets` 导入。

小位图示例：

```json
{"name":"菱花徽记","resolution":[64,64],"layers":[{"kind":"bitmap","rows":["...##...","..####..",".##..##.","##....##","##....##",".##..##.","..####..","...##..."]}]}
```

bitmap 的行数、每行宽度均为1～128，所有行等宽。`#` 或 `f` 为白色，`.` 或 `0` 为黑色，十六进制1～e为灰度。resolution 为最终图片尺寸，每轴8～256，默认16×16。小位图按最近邻放大，绘图与组合则使用四倍采样后归一化。

组合示例：

```json
{
  "name":"八瓣花与菱形格栅",
  "resolution":[128,128],
  "tags":["墙饰","吊顶","组合"],
  "layers":[
    {"kind":"preset","preset":"diamond-lattice","repeat":[2,2],"opacity":0.5},
    {"kind":"ellipse","bounds":[0.4,0.08,0.6,0.5],"radial_count":8},
    {"kind":"ellipse","bounds":[0.44,0.44,0.56,0.56],"blend":"subtract"},
    {"kind":"ellipse","bounds":[0.04,0.04,0.96,0.96],"fill":false,"stroke":0.025}
  ]
}
```

图层从前向后依次计算。支持以下来源：

| kind | 参数与用途 |
| --- | --- |
| bitmap | rows，小位图草图 |
| rect / ellipse | bounds、value、fill、stroke，矩形/椭圆及边框 |
| polygon | points 至少3点，填充或描边 |
| polyline | points 至少2点，连续线条 |
| bezier | points 恰好4个控制点，三次贝塞尔曲线 |
| preset | preset 图库 ID，可选 crop、channel |
| asset | id 与 image_sha256，复用已保存图像，可选 crop、channel |
| sample | sample 中的 path、sha256、crop、channel，使用工作区图片 |

图层通用参数包括 box（在画布中的归一化目标框）、rotation（逆时针角度，旋转在图层内裁切）、flip_x / flip_y、repeat（每轴1～8）、radial_count（1～16份绕图层中心旋转叠加）、opacity（0～1）。几何 points、bounds、box 都以左上角为原点，坐标范围0～1；stroke 是相对图层短边的笔画宽度，value 是0～255灰度。blend 支持 union（取亮）、subtract（镂空）、intersect（取暗）、xor（绝对差）和 add（饱和相加）。最多32层，配方最多512KiB；空白结果拒绝保存。输出的 analysis 记录前景占比和左右/上下边缘差异，边缘差异不为0时不能宣称无缝平铺。

所有拟合接口的 sample 现在支持 `crop:[x0,y0,x1,y1]`，对原图先裁取，再缩放、重复、减色和半格拟合。坐标同样从左上角起算，范围0～1，原图 SHA256 仍绑定整张原图。图库用 preset_options.crop。组合图层也能各自裁取不同区域后拼合。

```json
{"surface":"wall","size_uv":[32,24],"sample":{"path":"references/ornament.png","sha256":"<原图SHA256>","crop":[0.25,0.1,0.6,0.7],"noise_strength":0},"shapes":{"stairs":"quartz_stairs","slab":"quartz_slab"}}
```

`pattern_create` 返回 fitting_input（sample 路径和图像哈希），可直接合并到 pattern_compile / pattern_preview 请求中。楼梯和半砖的匹配、接触、旋转仍由脚本负责。优先以8～32像素绘制单个主纹，用 pattern_microfit 在2～8格验证后再重复铺排；过细时裁取更简单的区域或加粗主纹。

原生纹样库保存于 `nbt_models/asset_library/patterns/<id>/`。pattern.json 保存名称、标签、来源和组合配方；pattern.png 是拟合图片，thumbnail.png 是缩略图；导入或裁取副本另保留 original.image 原始字节。图像、缩略图、原图和元数据都绑定哈希。创建新纹样使用新ID，重命名和回收只修改元数据，图像内容保持可复用。

通过 `pattern_assets` 管理：

| action | 请求 |
| --- | --- |
| list | 仅 action，查询内置与工作区纹样，内置图库不复制进用户目录 |
| get | id，读取配方、图片、尺寸和 fitting_input |
| import | name、sample，或 name、image_base64；可选 tags |
| copy | id、image_sha256；可选 name、tags、crop，生成独立副本 |
| update | id、content_sha256；可选 name、tags、archived，拒绝过期元数据 |

内置 ID 为 `builtin:<图库ID>`，只读，可 copy 创建工作区副本。asset 图层使用 image_sha256 绑定像素，因此仅重命名不会破坏复用。界面在素材库的“纹样”分类中展示同一批资产，支持导入、裁取、组合、改名、回收、拟合预览和保存为建筑构件。纹样资产与拟合后的构件分别保存；不自动定稿 NBT。

基础几何预设包括棋盘格 `checkerboard`、横条 `horizontal-stripes`、竖条 `vertical-stripes`、错缝砖 `running-bond`、编织格 `basket-weave`、人字折纹 `herringbone`、菱形格 `diamond-lattice`、回折纹 `greek-key`、之字带 `zigzag-band`、十字 `cross-tile`、阶梯菱形 `stepped-diamond` 和四瓣花 `four-petal`。建议从 16×16 格开始；不同预设支持的安装面以 `pattern_list` 为准。`repeat` 按面板宽高重复完整图样，建议在较大面板上使用，尺寸太小时细节可能合并。
