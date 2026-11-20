# 完整主模型的统一组合入口

新建建筑、编辑已有制作源及独立构件使用共享 `nbt_working_model.WorkingModel`。它管理当前完整候选、实例安装基线和制作版；`ModellingSession` 继续只负责缓存。原有几何与参数化工具可继续使用，无需把整栋建筑强制改成对象图。

新增构件编译器或工作模型操作时，使用[处理器与配方注册器](extensions.md)。工作模型与对象图通过同一编译注册器接入，公共参数仍以工具目录为准。

在创作项目根目录运行 `mise run nbt -- capabilities --model` 查询请求契约；执行 `mise run nbt -- model --request request.json`。软件源码维护时使用 `mise exec -- node scripts/cli.mjs --workspace <隔离工作区> model --request <JSON>`。引擎位置仍由工作区 `paths` 返回，不写死安装路径，不在软件源码生成创作入口。

复杂建筑可由[可执行建筑方案](architecture-workflow.md)编排同一个工作模型。方案绑定随制作版保存，普通 `validate` 也复检实际空间、梯段、承托和风格规则；不改变用户看图与定稿边界。

## Python 制作脚本

```python
from nbt_working_model import WorkingModel

model = WorkingModel(workspace, [96, 24, 48], context={
    "mode": "standalone", "openings": [],
    "max_changed_blocks": 120000,
}, limits={"max_changed_positions": 120000})
model.install("west_pillar", {
    "tool": "parametric_compile",
    "arguments": {"kind": "pillar", "size": [3, 7, 3]},
}, position=[47, 1, 12])
print(model.inspect("west_pillar"))
# 继续构造本次设计的地面、围护、顶构和路线，再按实际阶段检查。
receipt = model.save_draft(name_zh="本次建筑", shape="standalone")
```

`install`、`update`、`remove`、`detach`、`patch` 和 `apply_operations` 先在副本上检查，成功后才替换内存候选；不自动保存或定稿。`install` 接受纯编译配方与世界锚点，内部完成 build、状态变换和放置。构件每轴与方块上限保持原接口约束；完整主模型允许跨48格存储边界。实例 ID 在该建筑中稳定且唯一。

`inspect` 返回实例配方、安装参数、占用数，以及对象图子对象的宿主世界坐标和真实接触接口；`inspect(positions=[[x,y,z]])` 或CLI顶层 `positions` 可查询实际方块、墙层和实例归属，用于构造带旧值的宿主补丁。`update` 返回实际差异和受影响子对象。宿主切削后重新核对实际接口与声明连接，失效接口不会复用旧的通过回执。`preview(output, cameras)` 在全新目录写候选SNBT、审阅快照和机位；用既有 `render --source <候选SNBT>` 生成纹理图并实际查看。快照和图片不代表技术检查或用户批准。

## 宿主修改与预算

新增几何与宿主增删改保持不同含义。构件未写的位置保持原状；显式空气才表示删除。`patch` 的每项是 `{"pos":[x,y,z],"before":["minecraft:stone",true],"after":["minecraft:air",false]}`，绑定预期旧状态及墙层，任何不一致都拒绝整批操作。`apply_operations` 调用现有工具序列，通过同一完整宿主检查，不使用逐分片编辑。

`limits` 分别限制 `max_component_blocks`、`max_written_positions` 和 `max_changed_positions`。最后一项按本次工作副本初始主模型到最终候选的方块状态/墙层变化坐标并集计算，不能把多个各自未超预算的组合拼成超预算结果。保存制作版后，以新保存版本作为下一次编辑基线。上下文 `max_changed_blocks` 与工作模型上限取较小值。

保护按完整模型执行；`reserved_boxes` 拒绝新增占用，`require_routes:true` 使用 start、targets 及 route_legs 在完整候选上复查。未配置路线时不宣称已验通路。源文件、二进制源的墙层附属文件、外部上下文或已发布制作版的核心资料变化，会使工作副本失效。续版绑定规范化后的有效约束与保存预算，替换上下文或修改内存上下文均不能放宽保护、留白和路线；机位可另行调整。自由体素脚本在保存时也复核保留空间与 require_routes。对象图的保护、留白、路线和预算在受管安装后继续执行。

## 实例更新与手工编辑

安装记录配方、局部到全局变换、实际安装结果和被替换的原方块/墙层。与宿主完全同值的重复写入不会取得已有方块的所有权。不同受管实例不能争用同一归属；同格镶嵌须作为宿主配方的一部分或一次显式替换。

`update(id, recipe=..., transform=...)` 对照上次安装结果、当前宿主和拟生成结果。当前等于基线时可更新；当前已等于新结果时可合并。其余受管位置的分歧返回 `INSTANCE_EDIT_CONFLICT`，包含实例、世界坐标、基线、当前和拟生成值。墙层单独变化、手工挖空及新位置占用均参与比较。第一版对这些分歧整体拒绝，使用 `detach(id)` 可显式保留当前方块并解除管理，之后按自由几何编辑；不把局部手改伪装成可随对象移动的参数化覆盖层。

缩小、移动或 `remove` 时，只有该实例实际取得归属且未被冲突修改的位置才恢复原底材。底材逐格记录，不能统一补成某种石材。无安装记录的旧作品以自由体素打开，不猜测归属和历史底材。

## 检查、保存与恢复

建筑按实际阶段检查。`design` 可以保存进行中的制作稿，报告明确整体验证尚未执行；`seal()` 在真实未开洞模型上检查全部 interior_probes，并保留开洞前主模型；`open_declared()` 按上下文策略处理独立 `openings`。要求密闭时必须先取得有效封闭记录；未要求密闭时可直接按声明开洞。无声明洞口时不写几何，进入沿用名称的 `opened` 验证阶段。`opened` 保存前执行完整建筑验证。独立 `component` 不强制通过整栋建筑的密闭/开门流程，每轴≤64，按实际尺寸、状态及方块预算检查。设计阶段、静态通过、看图完成和用户批准分别记录。

`save_draft` 只发布 SNBT 制作版。先在工作区 `.nbtcreator/model-staging/` 写齐并回读，再在建筑锁内核对父版本并发布完整目录：

- `master/model.snbt`：实际方块与显式墙层；有真实开洞前证据时另存 `master/preopening.snbt`。
- `model-instances.json`：配方、实例安装基线与底材，以及可选建筑方案绑定。
- `coordinates.json`：有效上下文。
- `validation/working-model.json`：本次实际检查及未验范围。
- `changes.json`：相对父制作版的方块状态与墙层实际变化。
- `model-version.json`：绑定上述核心文件、引擎和父版本的不可变清单。
- `room_description.json`：建筑库登记信息，预览与定稿输出继续是派生资料。

版本放在原建筑的新 `v_model_<清单摘要>/` 目录。配方不同但方块相同也形成不同版本。保存不移动、覆盖原稿，不生成 NBT、批准或游戏部署。当前工作版在 `.nbtcreator/model-heads/` 以相对路径绑定；桌面/CLI从同一父版保存时，只允许仍基于当前父版的一方推进。

同一候选重复保存核对并复用已有成果；发布后历史登记失败返回 `history_pending:true`，重试同一保存可幂等补录。版本已完整发布、但更新工作版指针中断时，只在父版仍未改变的条件下修复，不倒退较新的工作版。旧历史格式继续兼容。历史切换、派生、桌面转换和 CLI 共用建筑锁与工作版指针；旧请求重放只复用已发布结果。补录按已验证清单先登记祖先再登记子版，历史索引中由旧故障留下的空父关系可据清单补全，并通过新的历史提交记录。

CLI已有源请求须给 `source_sha256`，相对路径以创作项目为基准。请求中的 `save_draft:{}` 表示显式保存已有建筑下一制作版；新建时提供 `save_draft:{"name_zh":"中文名","shape":"standalone"}`。定稿继续使用单独的 `finalize`，精修继续遵守对应图像后的真实用户确认。

验证：在软件项目根目录运行 `mise run model:test`；测试使用独立临时创作工作区，包含真实 CLI、冻结Skill入口、跨48安装、底材恢复、手改冲突、整模预算及版本恢复。`mise exec -- npm run test:model-preview` 先构建前端，再对合成柱梁顶组合生成同机位前后纹理图，输出在 build/model-render-*，不会发布用户资产或定稿NBT。
