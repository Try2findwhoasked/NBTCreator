# 曲面纹样与背衬

`curve plan` 使用经 `reference fit` 和 `reference verify-fit` 核对的截面，在既有宿主的局部外露方块面上规划样段。它只生成候选和诊断，不修改原稿、不保存制作版，也不产生用户批准。适合先验一段偏心或退台曲面上的凸沿、暗槽、竖肋、窗列及嵌纹，再决定是否扩展到整栋。

## 准备可复用掩模

掩模是创作工作区内的 JSON 数据，`rows` 从低 Y 到高 Y 排列；每行从起始 U 沿截面顶点顺序前进。`.` 表示不写入，其他符号为单个大写字母或数字。每轴最多 64 个单元，符号表必须恰好覆盖所用符号：

```json
{
  "schema_version": 1,
  "name": "曲面样段",
  "rows": ["R.C..I.."],
  "palette": {
    "R": {"kind":"raise","state":"stone_brick_slab[type=bottom,waterlogged=false]","height":1,"wall":false,"role":"rim"},
    "C": {"kind":"cut","depth":1,"backing":1,"role":"groove"},
    "I": {"kind":"inlay","depth":2,"backing":1,"state":"gold_block","wall":true,"role":"relief"}
  }
}
```

`raise` 从实际宿主面向外放置 1～3 格；`cut` 从外露面向内移除 `depth` 格；`inlay` 在该深度最内格放入指定状态，前面的格为空气。切深为 1～6 格，保留背衬为 1～8 格，二者合计不超过 8 格。材料须为注册表中的已知完整块、半砖或楼梯碰撞形状；`wall` 显式指定墙层，不从材质猜测。`role` 是小写英文、数字、连字符或下划线组成的用途标签。

相邻曲面切口可能占用另一采样原先的背衬。默认仍拒绝此情况；如果设计允许更深的连续修改范围，可对对应 `cut` 或 `inlay` 明确指定 `max_effective_depth`。它必须不小于 `depth`、最多 6 格，并与 `backing` 合计不超过 8 格。工具只沿实际面内向跨过**同一符号已经计划的连续改动**，在允许深度内找到未改动的完整宿主，再逐格核对所需背衬；不同符号、超出上限、空气或缺少完整背衬仍会拒绝。此选项不额外挖块、不放宽保护，也不证明其他方向的壁厚。回执逐个采样面记录 `effective_depth` 和实际保留的 `backing_positions`，汇总中列出最大深度及延深的采样面数量。`effective_depth` 是连续修改所及的深度，包含填入的实体材料，不能当作空腔深度；`air_depth_full_voxels` 单独统计从外露面连续进入的完整空气格，不估算半格空腔，应结合真实写入和剖面图检查。

### 同一 UV 上的分层

需要让凸带跨过暗窗等情况时，可使用版本 2 掩模。各层使用同一截面及同尺寸 UV 网格；重复占用的 UV 必须显式列出允许重叠的层对。以下示例在同一格用黑石替换宿主表层，并在其外放置石砖凸饰：

```json
{
  "schema_version": 2,
  "name": "暗窗上的凸带",
  "layers": [
    {"id":"band", "rows":["R..."],
     "palette":{"R":{"kind":"raise","state":"stone_bricks","height":1,"wall":false,"role":"band"}},
     "support_expectations":{"R":{"state":"blackstone","wall":true}}},
    {"id":"window", "rows":["W..."],
     "palette":{"W":{"kind":"inlay","state":"blackstone","wall":true,"depth":1,"backing":1,"role":"window"}}}
  ],
  "overlaps": [["band","window"]]
}
```

层编号使用小写英文、数字、连字符或下划线，最多 8 层。`support_expectations` 只能针对本层 `raise` 符号，指定允许替换原支承的**完整方块状态和墙层**；原支承保持不变也可通过。实际换材的写入层还必须与凸饰层声明重叠。未声明、最终变成空气／半块或与期望不符时拒绝；凹槽及嵌纹保留背衬始终不得被其他层改动。层顺序不表示覆盖优先级：不同层对同一方块的不同写入一律冲突，完全一致的写入仅在声明重叠后合并。即使不同 UV 因量化落到同一方块，也执行相同的实际重叠与支承检查。

每层的连续性分别报告，`summary.overlapping_uv` 记录声明并实际重叠的 UV 数，`overlap_details` 最多列出 256 个层对与坐标，超出时明确标记截断；`summary.support_replacements` 逐项列出支承换材及写入层。连接和采样预算按整个分层候选累计，保护、路线和原稿检查作用于合并后的候选。版本 1 掩模的格式和行为不变；分层只是显式组合规则，不自动生成窗列、搭接端部或对称构件。

分层中可选 `"connections":{"raised":false,"recess":false}`，分别关闭该层的凸饰或凹槽自动连接；省略时沿用 `mapping` 中已开启的连接策略。设置为 `true` 时必须同时在 `mapping` 中提供对应的全局连接预算，不能借此绕过总预算。被明确跳过的层会列入 `summary.connection_skips`，其原始断笔仍计入该层连续性报告，不会因此变成通过。构件组合请求可在每个来源层中携带相同的 `connections` 字段。

可将用户制作的掩模保存在创作项目，或按项目约定放入独立资产库；不要把用户图源或私有模型打入软件资源。输入使用文件 SHA256，掩模内容变化后需重新规划。

## 从已有构件组合掩模

素材库提供六种可调的**平面 UV 模板**：环段、暗缝、竖肋、窗列、斜搭带和裙边分片。它们使用 `parametric_compile` 的 `kind: "curve_stencil"`，尺寸为 `[U格数,V格数,1]`；模板里的标记方块只描述轮廓，不指定最终是凸饰、切槽还是嵌纹。素材界面可预览模板并复制绑定了参数与内容哈希的曲面素材引用，但不会将平面模板直接当作曲面成品放置。

| `form.profile` | 必需参数 | 范围与含义 |
| --- | --- | --- |
| `curve_ring_segment`、`curve_dark_seam` | `curve_width`、`curve_offset` | 水平带的高度及最低 V；暗缝的最终切割动作仍由映射决定 |
| `curve_rib` | `curve_width`、`curve_offset` | 竖带的宽度及最小 U |
| `curve_window_column` | `curve_width`、`curve_offset`、`curve_window_height`、`curve_gap`、`curve_count`、`curve_start` | 固定窗格的宽度、起点、间距和数量，不自动裁掉末格 |
| `curve_diagonal_band` | `curve_width`、`curve_start`、`curve_rise` | 带的 V 向厚度、起点和有符号升降；负值显式表示反向 |
| `curve_skirt_segment` | `curve_left_bottom`、`curve_right_bottom`、`curve_left_top`、`curve_right_top` | 左右及上下端各自的收分，不自动对称 |

可选 `curve_cap_start`、`curve_cap_end` 分别取 `square`、`low_step` 或 `high_step`，并用 `curve_cap_length` 指定阶梯收头长度；`low`／`high` 指垂直于带方向的低／高坐标侧。两端都为 `square` 时长度为 0；阶梯收头不能超出有效跨度或移除全部内容。沿 U 的搭接与重复由下述 `counts`、`spacing` 明确控制，实际厚度与保留背衬由目标动作指定。改变参数后须重新预览并使用新的编译内容哈希。

`mise run nbt -- curve compose --request <JSON>` 可以将本地构件或已连接资产的明确切片转换成分层掩模。先从素材库读取本地构件的 `id` 和 `content_sha256`；拓展资产则从浏览和预览回执取得 `id`、`sha256`、`source_id`、`version`、`manifest_sha256` 和编译后的 `content_sha256`，可调配方还需带上生成该内容时的 `arguments`。组合和验证只读取本地缓存，不自动联网刷新。

```json
{
  "name": "组合样段",
  "size": [4, 2],
  "layers": [{
    "id": "band",
    "source": {"kind":"local", "id":"<构件id>", "content_sha256":"<内容哈希>"},
    "slice_z": 0,
    "origin": [0, 0],
    "counts": [2, 1],
    "spacing": [2, 1],
    "mapping": [
      {"index":0, "wall":true, "symbol":"R"},
      {"index":1, "wall":false, "symbol":null}
    ],
    "palette": {"R":{"kind":"raise","state":"stone_bricks","height":1,"wall":false,"role":"rim"}}
  }],
  "overlaps": [],
  "output": "nbt_models/_workspaces/curve-masks/sample"
}
```

拓展来源的 `source` 改为 `{"kind":"library","ref":{...}}`，`ref` 包含上述来源字段和可选 `arguments`。构件局部 X 映射为 U，局部 Y 按低到高映射为行；`slice_z` 明确选择一个 Z 层，不投影其他层。`mapping` 必须覆盖所选切片实际出现的每一对材质编号和墙层，`symbol:null` 才表示明确忽略；目标动作和目标墙层由 `palette` 明确指定，不从颜色或源墙层猜测。`origin`、`counts` 和 `spacing` 均为整数 UV 格；重复超出画布或同层不同动作重叠时拒绝，不裁切、不自动镜像。多层组合通过版本 2 的 `overlaps` 和 `support_expectations` 明确声明。

组合结果的 `mask.json` 和 `composition.json` 须保留在同一输出目录。`curve verify-mask --mask <mask.json> --sha256 <掩模哈希>` 重新解析并重算构件切片；`curve plan` 和 `curve verify` 使用该掩模时也会自动执行同样的来源检查。本地构件内容改变、被归档，或者拓展来源被停用、换版、内容或参数不再匹配时，旧掩模与候选失效。把图案另存为无来源绑定的独立掩模不会继承这份来源证明。构件切片复用只是二维动作数据，并不等于已实现可调的曲面环段或端部构造；仍需真实候选出图和审阅。

## 生成与核对候选

在创作工作区运行 `mise run nbt -- curve plan --request <JSON> --compact`。请求需要：

- `source`、`source_sha256`：已有 SNBT、NBT、压缩主稿或组装源及其哈希；可选 `context`。受管制作版须与已绑定保护一致，旧源继续继承其保存的保护。
- `profile`、`profile_sha256`：`reference fit` 生成的拟合 JSON 和回执哈希。工具会重新计算拟合，拒绝变化的锚点或参考图。
- `mask`、`mask_sha256`：掩模文件及哈希。
- `mapping`：`u_start` 为 `[0,1)`，`u_span` 为 `(0,1]`，`y_start` 为最低行的全局整数 Y，`max_distance` 为 0.5～3 格的实际面搜索半径。可选 `u_subsamples` 为每个掩模格沿 U 的采样数，范围 1～8，默认 1；非空格数乘采样数最多 8192，较宽笔画可加密采样，但仍需检查连续性。U 按截面顶点顺序环绕，可跨 1 回到 0；不自动镜像或改变不对称性。
- `cameras`：1～16 个实际审阅机位对象。`output` 须为 `nbt_models/_workspaces/curve-samples/` 下的新目录。
- 可选 `review_feedback`：提供 `binding`、`binding_sha256`、`record`、`record_sha256` 和从 0 开始的 `observation` 序号，关联一次匿名审阅中的具体意见。工具重验审阅包、记录和来源，要求当前宿主就是包中某个渲染的制作源；意见或绑定证据变化后候选核验失效。该关联只说明候选针对了所选意见，不表示问题已经解决或得到批准。

对每个掩模单元，工具在相应高度插值截面，取连续曲线的水平外法向，在附近寻找方向一致、相邻为空气的真实完整方块侧面，再沿该方块面的实际轴向法线检查切深与背衬。水平顶面和底面不在此工具的采样范围内。找不到面、出现等距歧义、支承不足、不兼容的重叠、被保护或超出预算时拒绝整个候选，并保留原稿；不会悄悄挪动笔画。此检查证明的是**局部**外露面，不能证明该空气与建筑外部连通，也不模拟实际承重。

可在 `mapping` 中显式加入 `"connect_raised":{"max_new_blocks":16}`，为断开的单层 `raise` 笔画尝试有界连接；预算可设为 1～64 格，省略时不添加连接。可选 `max_bridge_steps` 为每段 1～3 个中间格，默认 1；只搜索同一掩模笔画相邻采样之间的轴向最短路径，不绕行或扩展到其他笔画。若路径经过同一笔画已采样的方块，优先使用新增方块数最少的路径；仍有多个同样可行的选择时拒绝猜测。工具以原状态和墙层填入中间空位，并验证半格形状逐格接触两端及端点的真实宿主面；多格连接的完整路径与复用方块记录在回执中。连接格可通过已支承的两端接到宿主，不代表每个连接格自身直接贴面。连接不得碰触同符号的另一条来源笔画，也不得覆盖其他写入、保护区或宿主；无法找到唯一路径、连接预算不足、半砖形状不能接触、生成新的孔洞或空腔或拓扑计算超限时，整次规划失败。为避免只凭孔洞数量推断孔洞位置，带孔洞的断笔暂不自动连接；多层凸饰和需要修复的周期接缝也不支持。

凹槽及嵌纹使用独立的显式设置 `"connect_recess":{"max_new_blocks":16}`，预算 1～64 格，按实际切口各层写入数量计数。工具只在相邻采样之间寻找唯一的中间宿主，要求有与两端拟合法向一致的真实外露侧面，且位于搜索距离内；之后逐格检查完整宿主、切深、保留背衬、保护及已有支承。连接格自身仍须在声明切深后保留原始背衬，不自动延长。嵌纹会分别检查切口体积与实际内层材料的半格连通性，不能用空腔相连冒充材料相连。歧义、背衬不足、不同笔画意外相接、带孔洞的断笔或周期接缝均拒绝，不猜测替代路径。普通 `continuity` 报告将空气计作切口体积，它本身不证明嵌纹材料相连；未启用凹槽连接时需要另行检查材料。

凹槽无法连接且没有检测到背衬不足时，`CURVE_RECESS_DISCONNECTED` 会分别报告切口和嵌纹材料的连通分量数，并列出至多 16 对仍断开的相邻采样、实际宿主坐标、法向和坐标距离；分层掩模同时标明出错层。纯切口的材料分量数和连通状态为 `null`；超出数量时标记截断。这些采样对用于定位断笔，不表示中间宿主、切深或背衬已验证，也不会自动选择连接路径。

两类连接的回执均在相应采样的 `connectors` 中逐项记录端点、宿主和真实写入；凹槽还记录外露面法向、深度、背衬和偏差。`summary.connectors_added` 是连接数，`summary.recess_connectors_added` 是其中的凹槽及嵌纹连接数；新增的各层写入计入总体写入统计。验证会重新计算所有连接。连接只生成候选，不代表视觉通过或用户批准。

凸饰连接若出现多个同样可行的最短路径，会返回 `CURVE_CONNECT_AMBIGUOUS`，冲突详情包含端点、UV 和可选的全局方块坐标。检查这些选项后，可在 `connect_raised` 中显式提供 `path_choices`，例如 `[{"endpoints":[[2,2,2],[4,3,2]],"path":[[3,2,2],[4,2,2]]}]`；分层掩模的每项还须提供 `"layer":"band"` 等实际层编号。工具重新检查路径确为当前端点之间的可行最短路径，并继续执行保护、预算、实际接触与拓扑检查。路径不匹配、来源变化或选择没有被使用时会拒绝，回执标记 `selection: "explicit"`；路径选择本身不是看图批准。

回执提供候选源、快照、机位文件、计划文件及各自哈希。计划记录每个 UV 的各采样点、实际宿主坐标、连续法向与方块面法向、偏差、切深、背衬、真实方块变化和墙层。同符号且结果相同的重复方块写入会合并，`merged_writes` 记录次数；`summary.truncated` 记录没有贡献新方块的掩模格，提示采样量化造成的细节丢失，需人工检查。同符号掩模格按八邻接组成笔画，各笔画对应的静态半格形状须通过面邻接形成单一连通分量；切除的空气按切口体积参与该检查。这样上下错开的半砖不会仅因整格相邻就被认为接触。`continuity.passed: false` 表示存在断开的笔画。单格断裂和相邻格未直接接触仍作为局部诊断报告，即使其他格已经将它们连通；距离单位为半格，过大组合的精确距离为 `null`。该检查不代表游戏中的物理或视觉连续性。无法映射的采样会使规划失败并报告位置。

`mise run nbt -- curve verify --plan <curve-plan.json> --sha256 <回执哈希>` 会重新核对原稿、分区、参考图、截面、掩模和保护，重新计算各个 UV 映射并重放方块变化，再验证候选与快照。该验证不替代渲染看图。用回执中的候选源、机位文件通过 `render` 出图，至少看正面、斜面和必要剖面；保留同机位来源及哈希。真实用户看过当前样段并明确确认后，才按已有工作模型/精修流程选择是否保存或铺开；NBT 定稿仍使用独立的显式导出流程。

## 记录候选复核

对已绑定原审阅意见的曲面候选出图，使用[同机位匿名 A/B 审阅](orthographic-reference.md#同机位匿名-ab-审阅)创建新审阅包并记录实际观察；新包至少有一个来源须是该候选，并与原包使用相同的机位、光照、画幅、质量和裁切。需要不同取景时应另建独立审阅。`curve review-record --request <JSON>` 接收 `plan`、`plan_sha256`、新一轮的 `review_feedback`（与上面的绑定格式相同）、`status`、`remaining` 和 `output`。状态为 `improved`、`unresolved` 或 `inconclusive`；后两者须填写未解决项。输出须为 `nbt_models/_workspaces/reference-reviews/` 中的新 JSON 文件。

`curve review-verify --record <JSON> --sha256 <回执哈希>` 重新核查原意见、候选、后续审阅的制作源、相机、图像、参考区域及记录，任一证据变化即失败。状态只是记录者对观察的标注，不证明问题已经解决，也不构成用户批准。
