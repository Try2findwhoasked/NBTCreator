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
| scene_update | 绑定 id / revision / version，修改已有对象、联动重算并返回候选；须另用 scene_save 保存 |

其中三个纯查询/候选动作 `scene_compile`、`scene_read`、`scene_update` 也可通过 `session` 连续调用；`scene_save` 使用单次命令，保留明确的保存边界。会话与参数化工具入口见 [参数化建模](parametric-components.md#建模会话与结果复用)。

## 对象与依赖

graph 包含 schema_version=1、name、size 和 objects。每个对象有 id、recipe，并在 lo 与 attach 中二选一。lo 是**旋转后局部包围盒的最小角**，不同于 structure_place 的锚点坐标。

recipe.tool 可选 `parametric_compile`、`pattern_compile`、`pattern_microfit` 或 `structure`；arguments 分别使用对应工具参数，structure 则接受已有结构 spec。原参数 Schema、合法方块及工具限制继续生效。对象不支持用显式空气覆盖其他对象。

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

侧面墙饰按 face 自动绕 Y 定向，楼梯和半砖状态随之变换，此时不叠加 quarter_turns。其他对象可用 quarter_turns=0～3 整体旋转。contacts 可额外声明必须实际面接触的对象，例如一根梁同时连接左右两根柱子；这些对象也计入依赖。没有声明关系的根对象不会自动获得支承或工程承载认证。

对象数组无需人工排序。脚本依据尺寸引用、attach 和 contacts 建立依赖；缺失引用、重复 ID、循环依赖直接拒绝。无法联动的布局应明确修改关系，而非悄悄固定旧坐标。

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

scene_update 使用保存回执的 id / revision / version，并给 changes。每项以 id 定位，提供要替换的 recipe、lo、attach、quarter_turns 或 contacts；recipe 和 arguments 整体替换，不隐式深度合并旧参数。指定 lo 会移除旧 attach，反之亦然。此版 update 修改已有对象；增删对象可重新编译完整图，再绑定父版本保存。

```json
{"id":"<场景ID>","revision":1,"version":"<版本哈希>","changes":[{"id":"pillar","recipe":{"tool":"parametric_compile","arguments":{"kind":"pillar","size":[3,8,3]}}}]}
```

柱子增高后，顶帽按依赖重新定位。结果中的 affected_objects 是引用关系传播范围，recompiled_objects 是实际重算范围；当前会重算并检查整图，不宣称只重算受影响节点。没有发生预期依赖变化时先检查对象关系，不能把手动改坐标称作自动联动。

接受候选后，将返回的 graph、graph_sha256、content_sha256 和 parent 交给 scene_save。保存检查父版本并原子更新 head；并发者若已提交则拒绝旧父版本，不覆盖、不自动合并。旧版本继续可读。该接口不提供机器任务提交接口的幂等回执；响应不确定时先读当前版本，不盲目重复保存。

## 约束和建筑接入

graph 可给 reserved_boxes、protected_boxes、routes 和 max_changed_blocks。保留空间禁止任何对象占用；保护区允许保存现有几何，但联动更新不得改变其中的方块状态或墙层。routes 为 start 和非空 targets 数组，采用原半格玩家碰撞引擎；检查失败则不返回通过候选。续版必须保留原总尺寸、保留/保护区域、路线及预算约束。

对象的实际方块不得重叠，即使材质相同。新增连接、位移导致的旧块移除与新块增加都计入修改；还会复核未受影响对象，拒绝意外几何变化。scene_update 失败不会保存头记录，旧快照不变。

spec 可交给 structure_preview 生成真实预览，之后使用已有资产保存和放置接口。scene_save 只保存对象图，不能让当前建筑跟着自动变化。写回建筑仍需绑定它的真实源、安装环境、保护与通路，另存新版本；完整建筑的密闭、开口、看图确认和定稿流程保持不变。实际看图和游戏验收不能由图谱的 verification 字段替代。
