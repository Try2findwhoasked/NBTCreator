# 贴面安装与宿主绑定

用于把已经编译或拟合的构件装到已有建筑、柱芯或候选快照上；先查询真实面及其哈希，再生成候选。独立构件配方见[参数化构件](parametric-components.md)，图源拟合见[纹样拟合](pattern-fitting.md)，整栋持续组合优先用[统一工作模型](working-model.md)。

## 安装在已有建筑上

三个接口均通过 `mise run nbt -- components agent --tool <工具> --request <JSON>` 调用。

1. `parametric_surface` 接收 `{"surface": {...}}`。surface 提供 source、source_sha256、geometry_sha256、context、context_sha256、lo、hi 和 normal。lo/hi 是单格厚度的支承平面，normal 是装饰伸出的方向，可选 north/south/east/west/up/down。可设 min_support（已确认的连续方块厚度，1～8）和 opening_margin（缺口四周保留格数，0～8）。如使用候选，另提供 snapshot 和 snapshot_sha256。
2. 查询返回 surface_sha256、已确认安装格、厚度、遮挡、未知形状及连通空气缺口。每格另有 protected_surface（宿主表层）、protected_outward（相邻外侧）和 protected_depths（向内0～7格的受保护深度），diagnostics 汇总几何状态及保护数量。usable_uv 只表示几何支承与开口边距可用，不代表完整饰件已经通过保护检查：表层受保护可阻止镶嵌，却不一定阻止未接触保护区的外贴。侧墙的 UV 为 X/Y 或 Z/Y，地面与吊顶为 X/Z，从 lo 开始沿世界正轴计数。空气缺口保持未分类，薄形状、未知形状及其边距纳入避让。
3. `parametric_mount` 接收同一 surface、surface_sha256、`object`（原参数化构件请求）和 `anchor_uv:[u,v]`。侧墙用 wall，下挂面用 ceiling，其余构件从地面向上放置。例如在 `lo=[0,2,7]`、normal=south 的墙面上，`anchor_uv:[8,0]` 对应邻接安装格 `[8,2,8]`。侧墙按法向旋转构件。
4. `parametric_layout` 接收同一组字段，使用 pattern 代替 anchor_uv。grid 为居中阵列，border 为阵列外圈，center 为单个居中对象。gap_uv 控制实例间距，edge_margin 控制边缘留量，reserved_boxes 指定额外留白，max_instances 和 max_changed_blocks 限制布局规模。on_conflict 默认 reject，设 skip 时返回每个跳过的锚点和原因，超出总预算仍会失败。

安装规划要求每个写入点的投影都有可用支承，每个方块连通组接触安装面。保护区、留白和实际占用优先。结果包含 operations、源与上下文哈希及候选几何哈希。按同一源、同一上下文及同一预算进入现有 control preview/validate 流程。几何接触、保护和预算由工具验证，玩家路线、实际承重和设计效果仍需单独审阅。首版支持平直轴对齐安装面。

查询阶段即检查保护上下文与实际源是否匹配，再进行构件拟合。开洞前使用独立的闭壳阶段上下文，将计划门洞、邻接喉道、门槛和顶边列入 protected_boxes；实际开洞后使用真实 openings 及原有保护。不能把尚未打开的门声明为已有开口，也不能为了消除错误删掉真实开口或保护。查询通过不等于整栋建筑已经密闭或通路通过。

安装冲突的错误文字保留原因，并附带 JSON 事实：code、position、uv、normal、face_status 和 known_thickness。outward_blocked、opening_margin、protected、reserved、occupied 等代码用于定位失败点；嵌入厚度不足会补充 required_thickness、checked_depth 和 actual_state。吊顶 clearance_obstruction 指出实际挡住净空的方块，给出 ornament_position、requested_clearance、free_blocks 和 actual_state，避免只凭“净空不足”猜测障碍。根据这些证据调整尺寸、选区或安装方式后重新查询；报错不会自动挪动对象、降低门槛或应用候选。


## 批量安装与保留宿主配方

`mount_batch` 接收一个 target（source、source_sha256、geometry_sha256、context、context_sha256，可选成对的 snapshot / snapshot_sha256）和1～64项 installations。每项有唯一 id、tool（parametric_mount 或 pattern_mount）、局部安装面 surface（lo、hi、normal，可选 min_support / opening_margin）、object、anchor_uv，以及该安装方式适用的 embed_depth / min_clearance / surface_fit / reserved_boxes。每项不再传源或 surface_sha256；工具在内存中依序查询当前候选并返回各自回执。

工具只读取一次完整源，按数组顺序处理，不为每项保存中间SNBT；后来项目可使用先前新增的真实支承，但任何两个项目的写入不得重叠。全部成功后复查每项的保留背衬、净空和图像绑定，完整重放操作核对方块及墙 mask，避免后装构件破坏先前背衬或侵入吊顶净空。失败整体拒绝，不返回部分成功的计划，也不修改源或保存资产。

顶层 max_changed_blocks 控制整批唯一写入格数（包括浅槽空气），并取不超过绑定上下文 max_changed_blocks 的值；最多65536格、展开最多128个操作。顶层 reserved_boxes 对所有项目生效，require_routes / compare_routes 在最终组合上统一比较原声明路线。预算、保护、源/候选/上下文SHA与原质量门槛保持执行。它不会自动跳过失败项、降低门槛、挪动对象或批准候选。

`surface_decorate` 使用同样的 installations，但以 host 配方代替文件 target。host.tool 仅为 structure 或 parametric_compile；其 arguments 使用原结构或参数化Schema。局部安装在宿主实际几何上完成，返回包含宿主和饰面的 spec、content_sha256、安装回执及净空约束，不写临时模型。max_changed_blocks 限制饰面变化；宿主和最终构件还受原结构尺寸/方块总量限制。

需要持续联动时，把 surface_decorate 作为对象图 recipe，保留 host 和 installations。纹样对象可使用 graph.patterns 的 pattern_ref；更新绑定后重新拟合并编译整个配方，不把上次输出 spec 当作下次的唯一配方。只有已烘焙的纯结构不能自动恢复原纹样来源。

## 贴面连接与整栋审阅

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

## 齐平与浅槽嵌入

`pattern_mount` 新增 `embed_depth`，只返回经原稿、保护、开口、占用与预算复核的候选：

- `0`：原有外贴行为；微型墙饰复用原背板。
- `1`：替换宿主最外层笔画所在的方块，不再向外凸出。楼梯和半砖仍保留自身局部凹面，不能在同一个方块内混装两种材质的任意半格。
- `2～6`：仅沿笔画投影开出前方浅槽，再嵌入对应深度。槽中的空气也计入预算、保护与墙层检查；未被笔画覆盖的宿主保持原状。

嵌入只用于墙、平面柱饰与吊顶；`embed_depth + surface.min_support` 不超过8格，并逐格确认完整宿主，嵌入后保留 min_support 格完整背衬。薄墙、未知形状、开口、被占用的外侧或受保护的槽体拒绝安装，不靠穿墙让纹样“融合”。地板原本已平齐镶嵌，不使用此参数。圆柱径向嵌入尚未由该参数支持，不能把平面贴附的结果称作圆柱内嵌。

先用 `parametric_surface` 查询真实安装面，再使用返回的 surface_sha256。下面仅展示 `pattern_mount` 的新增字段，surface 仍需完整源和上下文绑定：

```python
# surface_request 为绑定真实源与上下文的完整请求；surface_query 为其真实查询回执。
request = {"surface": surface_request, "surface_sha256": surface_query["surface_sha256"],
           "anchor_uv": [8, 4], "embed_depth": 1,
           "object": {"surface": "wall", "preset": "micro-key", "fit_mode": "micro",
                      "size_uv": [8, 3], "preset_options": {"fit": "stretch"},
                      "material": "waxed_cut_copper", "quality_profile": "border", "min_quality_score": 70}}
```
