# 建筑对象图与联动修改

当柱、梁、墙饰、吊顶等构件需要一起调整时，用对象图保留它们的配方、稳定 ID、尺寸引用和接触关系。已有 `parametric_compose` 适合一次性的独立摆放；`parametric_regenerate` 适合同尺寸、同部件边界的局部替换。需要跨对象联动时使用本文接口，不依靠 Agent 手工修改一组逐块坐标。

这是一种受管理的构件组合：每轴1～64格、最多32个对象、最多65536个实际方块。它不扫描已有 SNBT 反推对象，也不自动接管手工修改的建筑。嵌入更大建筑时，仍经已有预览、放置、源哈希、保护及导出流程。

## 四个工具

通过 `components agent --tool <工具> --request <JSON>` 调用，完整参数以 `capabilities.agent_tools` 为准；用 `capabilities --agent-tool scene_compile` 可只读该工具的完整Schema。

| 工具 | 作用与写入范围 |
| --- | --- |
| scene_compile | 编译 graph，返回完整 spec、对象边界、依赖顺序、哈希和检查结果，不写文件 |
| scene_save | 显式保存对象图及编译快照的新版本，不修改建筑，不定稿 NBT |
| scene_read | 读取 id 的当前版本；给 version 可读取历史快照，校验不可变文件哈希 |
| scene_update | 绑定 id / revision / version，预览对象、纹样或关系锁的修改，返回联动候选与方块差分，或可定位的冲突 |

其中三个纯查询/候选动作 `scene_compile`、`scene_read`、`scene_update` 也可通过 `session` 连续调用；`scene_save` 使用单次命令，保留明确的保存边界。会话与参数化工具入口见 [参数化建模](modeling-sessions.md#建模会话与结果复用)。

## 对象与依赖

graph 包含 schema_version=1、name、size 和 objects。每个对象有 id、recipe，并在 lo、attach 与 span 中选择一种定位。lo 是**旋转后局部画布的最小角，即局部零点**，不同于 structure_place 的锚点坐标；构件带留白时，真实占用边界会内缩，以编译结果 bounds 为准。完整模型的安装和安全续版见[统一工作模型](working-model.md)。

recipe.tool 可选 `parametric_compile`、`pattern_compile`、`pattern_microfit`、`surface_decorate`、`tracery_compile`、`vault_compile`、`bay_compile`、`field_compile`、`span_beam` 或 `structure`；arguments 分别使用对应工具参数，structure 则接受已有结构 spec，span_beam 使用下文跨梁参数。surface_decorate 保留宿主配方和饰面安装参数，适合柱芯嵌纹、墙面与吊顶镶嵌，避免将拟合结果烘焙成失去纹样来源的纯结构。[联动跨间](architectural-bays.md)工具可作为单个对象保留内部柱拱墙顶和纹样配方，参数变化时一起重算。原参数 Schema、合法方块及工具限制继续生效。对象不支持用显式空气覆盖其他对象。

## 纹样资产与配方联动

graph 可带最多32项 `patterns`，每项为 `{"id":"scroll","asset":{"id":"工作区资产ID","image_sha256":"实际图像SHA256"}}`。纹样参数中用 `pattern_ref:"scroll"`，并用 asset_options 指定 fit/crop 等采样参数。编译时解析为带哈希的 pattern_asset，仍执行原微型拟合、质量门槛及安装检查；对象回执的 pattern_refs 列出所用绑定，图谱保留原引用。

同一个绑定可供多根柱、墙面、地板和吊顶共用，各处仍有自己的尺寸、材质与拟合参数。`pattern_ref` 仅在对象图中解析；独立调用使用 pattern_asset。工作区纹样图像按不可变ID及SHA引用，修改图案应创建新资产，不能覆盖PNG后继续使用旧哈希，也不自动追随未指定的“最新图”。

scene_update 可给 `pattern_changes:[{"id":"scroll","asset":新资产引用}]`，不必重复提交所有对象配方或逐块坐标；changes 可以省略，也可与对象参数修改一起提交。工具重新拟合所有引用对象，传播到尺寸/接触依赖，返回 changed_patterns、changed_objects、affected_objects 和实际重编译范围。原图范围、保护、留白、路线、总预算及配方内原有质量门槛仍生效。失败不保存头版本；成功仍只是候选，需要显式 scene_save，旧版本继续可读。

surface_decorate 接收 host（structure 或 parametric_compile 配方）和 installations（见[批量安装](surface-mounting.md#批量安装与保留宿主配方)），不递归嵌套任意宿主工具。局部安装面和锚点使用宿主画布坐标；宿主须为外贴预留空间，或明确采用嵌入。对象图编译结束时，会在旋转、平移后的完整占用中再次检查该配方声明的吊顶净空，不能只靠宿主单独通过就忽略其他对象。

它不监控资产文件、不自动保存图谱，也不自动覆盖建筑。更新资产绑定、检查候选、保存图谱和写回建筑是不同动作；仍须真实看图及另存建筑版本。

尺寸或位置中可使用以下受限数据表达式，不接受代码、eval、脚本路径或任意属性访问：

```json
{"object":"pillar","measure":"max_y","offset":1}
```

measure 仅支持实际方块边界的 width / height / depth、min_x / min_y / min_z、max_x / max_y / max_z。可选 multiplier 为-16～16的整数，offset 为-1024～1024的整数。引用的是旋转、贴附后的实际占用范围，不是未解析的输入参数。

```json
{"calc":"subtract","args":[{"object":"right","measure":"max_x"},{"object":"left","measure":"min_x"}],"offset":1}
```

calc 支持 add、subtract、min、max；subtract 恰好两个操作数，其余2～8个，配方参数与表达式总嵌套最多16层。可在配方的尺寸和操作边界中使用同一表达式。脚本解析后仍交给原工具校验，不自动截断越界尺寸。

attach 接受 target、face（up/down/north/south/east/west），可选 offset 和 max_inset。它先对齐目标实际边界与切向中心，再沿法向向内探测真实接触面，默认最多4格，可设0～8格。offset 为切向整数，法向分量必须为0。每个真实半格面连通部件都须接到目标；碰撞、无法接触或未知碰撞形状均拒绝，不补造支撑或删除细节。

侧面墙饰按 face 自动绕 Y 定向，楼梯和半砖状态随之变换，此时不叠加 quarter_turns。其他对象可用 quarter_turns=0～3 整体旋转。contacts 可额外声明必须实际面接触的对象，例如一根梁同时连接左右两根柱子；接触属于位置确定后的验证关系，不形成生成依赖，允许双向声明。没有声明关系的根对象不会自动获得支承或工程承载认证。

对象数组无需人工排序。脚本依据尺寸引用、attach 和 span 建立生成依赖；缺失引用、重复 ID、生成循环直接拒绝。完整几何形成后统一重验 contacts 和具名接口接触。scene_update 分别返回受影响对象与 revalidated_objects；当前仍重编译并检查整图。

## 具名接口与跨梁

柱生成器提供 `base` 与 `capital_top`。其他对象可用 `interfaces:[{"id":"roof_seat","face":"up","lo":[0,0,0],"hi":[12,0,2]}]` 声明原构件局部画布中的接口区域。编译器在实际半格碰撞几何上求真实暴露面，接口随对象旋转变换，并返回法向、半格面、面积与位置。空气区域、被实体遮住的假接口和未知形状拒绝认证。

`attach` 可增加 `interface:"roof_seat"`，face 须与该接口实际方向一致。每个连接部件须沿接口法向接到声明面，不用与目标其他部位的接触冒充指定接口通过。

对象图内部另支持 `recipe:{"tool":"span_beam","arguments":{"width":3,"height":1,"material":"stone_bricks"}}`，配合 `span:{"axis":"x","from":{"object":"left","interface":"capital_top"},"to":{"object":"right","interface":"capital_top"}}`。它按两个朝上承托面生成水平矩形梁，自动计算长度和高度，并重验两端实际接触。两端高度不一、偏离声明轴、截面无法整数居中或需要舍入半格支承时明确拒绝；不自动拉伸任意资产或改变楼梯状态。整体镜像/旋转安装使用工作模型，回执中的子对象和接口同步换算到宿主世界坐标。

## 最小联动例子

以下为两个对象的工具示例，不是建筑布局模板：

```json
{
  "graph": {
    "schema_version": 1,
    "name": "柱与顶帽",
    "size": [12,16,12],
    "objects": [
      {"id":"pillar","recipe":{"tool":"parametric_compile","arguments":{"kind":"pillar","size":[3,6,3]}},"lo":[4,0,4]},
      {"id":"cap","recipe":{"tool":"structure","arguments":{"name":"顶帽","size":[5,1,5],"operations":[{"kind":"box","label":"顶帽","classification":"body","lo":[0,0,0],"hi":[4,0,4],"state":"quartz_block"}]}},"attach":{"target":"pillar","face":"up"}}
    ]
  }
}
```

scene_compile 返回 graph_sha256、content_sha256 和 spec。scene_save 提交该 graph 及这两个哈希，保存位置为 `nbt_models/asset_library/object_scenes/<id>/`。head.json 指向当前版本；versions 中按文件哈希保存不可变配方和真实编译快照。

scene_update 使用保存回执的 id / revision / version，并给 changes。每项以 id 定位，提供要替换的 recipe、lo、attach、span、interfaces、quarter_turns 或 contacts；recipe 和 arguments 整体替换，不隐式深度合并旧参数。指定一种定位会移除其他定位。此版 update 修改已有对象；增删对象可重新编译完整图，再绑定父版本保存。只改配方或关系而未改变方块也可另存语义版本，不伪报方块变化。

```json
{"id":"<场景ID>","revision":1,"version":"<版本哈希>","changes":[{"id":"pillar","recipe":{"tool":"parametric_compile","arguments":{"kind":"pillar","size":[3,8,3]}}}]}
```

柱子增高后，顶帽按依赖重新定位。结果中的 affected_objects 是引用关系传播范围，recompiled_objects 是实际重算范围；当前会重算并检查整图，不宣称只重算受影响节点。没有发生预期依赖变化时先检查对象关系，不能把手动改坐标称作自动联动。

接受候选后，将返回的 graph、graph_sha256、content_sha256 和 parent 交给 scene_save。保存检查父版本并原子更新 head；并发者若已提交则拒绝旧父版本，不覆盖、不自动合并。旧版本继续可读。该接口不提供机器任务提交接口的幂等回执；响应不确定时先读当前版本，不盲目重复保存。

## 关系锁、差分与冲突

版本 1 的图可以声明最多 32 项 `relation_locks`，每项使用唯一 ID。下面的柱脚位于场景坐标 `[2,0,4]`，屋顶接合到梁的 `roof_seat`。

```json
[
  {"id":"left_foot","kind":"fixed_position","object":"left","interface":"base","position_half":[4,0,8]},
  {"id":"roof_join","kind":"interface_contact","object":"roof","target":{"object":"beam","interface":"roof_seat"}}
]
```

- `fixed_position` 比较旋转、定位后场景世界坐标中的一个点。带 `interface` 时取实际暴露接口两个切向轴的最小半格坐标，法向轴取 `plane_half`。省略 `interface` 时使用实际占用边界的最小角，三个坐标均乘 2。半格值 4 表示方块坐标 2。这里的原点是对象图原点。此锁固定所选锚点，仍允许柱顶、截面和非锚点几何改变。
- `interface_contact` 要求子对象的每个实际半格连通块沿接口法向接到指定面。对子对象改用 `lo` 时，此锁仍验证接合。若 `attach` 和 `span` 的原生成关系仍在，它们的坐标推导与接触检查同时生效。接触面积可以变化，回读中的 `contact_face_count` 是相邻的半格面数量。

`scene_update` 用 `add_locks` 添加定义，用 `release_locks` 列出要解除的 ID。只改锁也可保存语义版本。保留的定义沿父版本传递，修改定义时用新 ID 添加并明确解除旧 ID。保存带解除动作的候选时，将回执的 `release_locks` 一同交给 `scene_save`，它会校验实际移除的 ID。直接编译完整图再绑定父版本保存也受相同检查。成功候选和保存回读均可在 `verification.relation_locks` 查看实测值。

成功预览的 `affected_objects` 是依赖传播范围，`geometry_changed_objects` 列出位置、状态或墙层实际改变的对象。`block_diff` 按场景 XYZ 升序给出位置及前后 `[方块状态,墙层归属]`，空位为 `null`。其中 `counts` 统计新增、移除和替换，`sha256` 绑定完整差分，`entries` 默认返回 256 项。按同一父版本和修改携带 `diff_offset:next_offset` 可续读，`diff_limit` 可设 1～2048。小于图谱原预算的本次预算可用 `max_changed_blocks` 预检。决定撤销候选时无需调用其他命令，头版本与宿主都没有写入。

CLI 失败退出 1。关系锁失败用 `code` 与 `conflicts` 返回锁 ID、对象、预期与实测位置或具名接触数据。几何和保护检查已完成时，失败回执仍提供只读 `preview` 差分。只有通过全部必要检查、已知每项锁的结果，并核验冲突子集及移除唯一成员后的可行性时，才返回 `conflict_proof.status:verified_inclusion_minimal`。预览根据给定修改与当前依赖生成一个确定候选，证明限定在这个候选，空子集使用同一几何作为见证。承托、保护、未知碰撞等失败给定位证据。可给 `timeout_ms`（1～120000）在预览阶段边界复核用时，超时回执含阶段与父版本。

设计取自保存既有几何关系的思路，以及用一致性与可行子集核对解释的定义。[Gleicher, Integrating Constraints and Direct Manipulation](https://graphics.cs.wisc.edu/Papers/1992/Gle92/integrat.pdf) · [Junker, QuickXplain](https://cdn.aaai.org/AAAI/2004/AAAI04-027.pdf)

## 约束和建筑接入

graph 可给 reserved_boxes、protected_boxes、routes 和 max_changed_blocks。保留空间禁止任何对象占用；保护区允许保存现有几何，但联动更新不得改变其中的方块状态或墙层。routes 为 start 和非空 targets 数组，采用原半格玩家碰撞引擎；检查失败则不返回通过候选。续版必须保留原总尺寸、保留/保护区域、路线及预算约束。

对象的实际方块不得重叠，即使材质相同。新增连接、位移导致的旧块移除与新块增加都计入修改；还会复核未受影响对象，拒绝意外几何变化。scene_update 失败不会保存头记录，旧快照不变。

spec 可交给 structure_preview 生成真实预览，之后使用已有资产保存和放置接口。scene_save 只保存对象图，不能让当前建筑跟着自动变化。关系锁的续版约束适用于场景保存，宿主按自己的放置变换及保护条件校验。写回建筑仍需绑定它的真实源、安装环境、保护与通路，另存新版本；完整建筑的密闭、开口、看图确认和定稿流程保持不变。实际看图和游戏验收不能由图谱的 verification 字段替代。
