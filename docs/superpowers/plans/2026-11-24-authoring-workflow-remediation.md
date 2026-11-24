# NBTCreator 参考图与分区建模架构整改方案

> **实施交接**　按下文清单逐项执行和复验。可使用已配置的 subagent-driven-development 或 executing-plans 工作方式。每项交付都可独立审查。

**目标**　把试作中用手工脚本完成的参考图交接、分区委派、局部方块修改和整栋验收，接到 NBTCreator 的共享创作流程里。

**架构**　制作版 SNBT 和现有发布锁继续负责几何与版本。制作运行将实际参考图、空间承诺、受限工作包和审阅证据串起来。子代理回传带旧值的候选，主代理在整栋中合并和复验，再发布一个子版本。

**技术栈**　Python 建模引擎、JSON 工具目录和本地机器协议、Node 托管的 loopback 服务、Electron 工作台及现有 Playwright 实景渲染。

**设计依据**　本文第 1–5 节和三轮试作取证。项目结构、发行门槛和质量度量沿用原有约定。 [现有架构](../../development/ARCHITECTURE.md) · [建筑质量与反馈](../../development/BUILDING_QUALITY_FEEDBACK.md)

## 1. 整改范围

| 试作证据 | 架构缺口 |
| --- | --- |
| 白宫用生成图定房间风格，但需要校正生成图中的图书室位置。桌花看起来悬浮，逐格回读才确认相邻状态之间有半格空隙。 | 参考信息需要标明观察、推定和校正。构件代理需要真实方块摘要和支承邻域。 |
| 栖湾核电厂分成冷却区、发电区，发电区再委派桥吊。整厂净改 312 格，18 个声明静态路线目标通过。分工、接口和合模靠人工约定及专用脚本。 | 统一记录谁能写哪些坐标、谁负责交接，以及哪份候选可以进入同一版。 |
| 栎脊旅店的首稿外部精细、内部偏空。第二轮补两批家具后，实际合模图还看出楼上整格地毯在楼下顶面露色，以及局部柜门浮离箱身。最终净改 203 格，19 条静态路线通过。 | 每个重点房间要有明确内容和机位。验收要覆盖同一楼板的上下两面、相邻支点和原有路线。 |

旅店补做同时增加了近景图和三级家具分工，现有结果能说明组合流程的效果。单独增加图片或单独增加委派各有多少收益，需要受控对照。产品先把房间用途和构件承诺变成可核对的工作项，再由参考图传递结构及外观意图。

试作回执位于创作归档下，可用 `white-house-build/reviewed-readback.json`、`nuclear-plant-trial/work/trial-verification.json` 和 `medieval-inn-trial/work/interior-detail/verified-comparison.json` 核对。正式回归使用独立合成夹具，不依赖用户图片、私人路径、网络或手工启动绘图服务。

首个可交付流程从已有普通 SNBT 分派两个多构件批次，产出同一建筑的一份可编辑子版本。随后接入图像引导的新建整栋流程。纯文字、单件建模、既有建筑方案、自由脚本和大型组装仍可从当前入口执行。

## 2. 可复用能力与协作边界

| 已有实现 | 缺口及接法 |
| --- | --- |
| `nbt_building/plan.py`、`workflow.py` 管理方案和构件。当前源工作区还有增量编译、粗布局搜索等在途改动。 | 工作流仅绑定布局或方案回执。已有布局求解继续负责楼梯、邻接和用途。 |
| `nbt_review/reference_views.py` 登记同尺度的正、侧、俯三视图。桌面 `reference-sources.mjs` 记录素材、书库和网页出处。 | 增加普通照片、生成概念图和图版内参照位置。仅在实际有标定证据时进入精确比例拟合。 |
| `nbt_project/batches.py` 记录本地制作批次、独立尝试和关联产物。`nbt_agent/protocol.py`、`tasks.py`、`task_client.py` 提供租约、修订、fence、幂等回执与恢复。 | 制作批次可挂载区域与构件工作包。共用现有租约和回执语义，增加父子关系及层级权限。 |
| `nbt_selection_edit.py` 能读取真实局部方块和墙层。`WorkingModel.patch` 核验旧方块状态及墙层，`assembly_handoff.py` 在大型组装源上已有读区、写区、保护和整批回装。 | 把现有能力串到普通 SNBT。只提取两类源真正共用的边界和冲突规则，保留各自文件格式及发布入口。 |
| `nbt_building/review.py` 有三尺度审阅、观察和比较，当前加载器需要建筑方案绑定。`render-batch.mjs` 已生成实际图像和清单。 | 自由脚本和普通 SNBT 也应能按空间盒、机位和构件坐标取得作用域明确的同机位证据。共用渲染、报告及比较。 |

现有独立工作树中有整栋规划、空间图布局、双轨 AI 和审阅机位推荐等任务。它们分别影响布局、入口和机位建议。实际实施前先确认哪些已合入，按合并后的契约适配。11 月 23 日的《整栋建筑生成流程实施计划》已经覆盖请求级引擎指纹、粗布局搜索、局部重建和大型组装发片，作为本方案的邻接工作。下文新增名称均是提案。

## 3. 目标流程

~~~mermaid
flowchart LR
    A["用途、尺寸与保护约束"] --> B["冻结参考图与房间简报"]
    B --> C["选粗布局或打开已有制作版"]
    C --> D["一级冻结坐标和接口"]
    D --> E["二级划分区域和活动"]
    E --> F["三级领一批相关构件"]
    F --> G["读局部方块并回传旧值补丁"]
    G --> H["整批预检与整栋候选"]
    H --> I["真实渲染、路线与相邻面复验"]
    I -->|"提取具体问题"| E
    I --> J["发布可审阅 SNBT"]
    J --> K["用户看图后明确授权精修"]
    K --> L["显式定稿导出"]
~~~

### 3.1 参考图和房间内容

- 图像引导任务先冻住参考图、已知尺度和方向。首期接受用户导入图或宿主交付的 PNG/JPEG。生成器型号、提示词和出处按实际可得性记录。纯文字和已有制作版的编辑可选图像附件。
- 将每条参考信息绑到用途和部位。图像可承担外轮廓、房间布置、材质、细部装配或局部截面。把照片可见事实、概念提议、补全假设和依据尺寸或资料的校正分开写。存在标定的正交图继续走既有三视图入口。
- 房间简报用实际使用行为定义完成度。例如炉厅有落座、备餐、取柴及回到主通道的站位。客房要能从门口走到床边和取物侧。阁楼包含读写区与坡下收纳。每个承诺登记用途、主构件、配套及代表视角，并标明必做或允许延期。留白按用途判定。

### 3.2 三级工作包

- 一级负责全局坐标、共同结构、跨区域通路和整栋发布。二级对一个区域交付负责，可发出多个构件包。三级可一次完成多件相关构件，例如一组长桌、长凳、桌巾和桌上小件。三级工作包完成后停止递归。并发使用宿主可用的槽位，同一套包可按顺序领取。
- 工作包有全局写区、只读邻域、明确保护、预期站位和接口。兄弟写区若交叠，签发前划分清楚，或把接点交给上级独立处理。只读邻域可以交叠。楼板、梯洞、围护和两区之间的支点默认有明确上级归属，下级权限只能收窄。
- 分派多个构件时，每件仍有稳定 ID、位置、用途、支承或接口和观察方法。父级核对缺项、路径和适用的证据后接收工作成果。一级控制主模型发布，候选工作包或审阅记录不授予正式精修批准。

### 3.3 读局部、写候选、合整栋

1. 从冻结的制作版或已绑定候选读取写区与支承邻域，默认外扩一格，跨楼板时显式读取上下两面。沿用压缩方块状态和墙层。摘要超限返回缩区建议，有多个读页时保持同一读取指纹。尺寸、坐标与真实站位都来自当前模型。
2. 三级把当前状态、目标轮廓、承托和使用侧写清，再按一组相关变化生成补丁。既有工具步骤或配方可在同一快照物化为精确差异。预期旧值包括方块状态与墙层。世界坐标从局部到全局转换一次。
3. 主代理先按批核对来源、写区、读区、旧值、墙层及保护。预算按本次整合的去重位置并集计算，同时沿用既有写入量限制。写区相离但读取的支点被改动时，标为受影响候选，重新读取接点并复验。第一期通过显式重签处理父版本变化。
4. 在整栋候选上检查合法状态、包围、门洞、必要路线、活动操作侧与实际相机脚位。把楼板上下、门厚、梯顶和共享荷载点映射到受影响区域。渲染成功、静态可走、实看设计、实际游戏行为各自保留准确结论。未知碰撞和搜索达到上限均显示待核查原因。
5. 对照固定眼位、目标、FOV、剖切、光照和纹理配置，绑定前后真实图片和各自源指纹。已有机位被挡或无法落脚时登记原因，转入其他机位补证。近景说明实际看到的部件及接缝，整栋图说明空间关系。涉及共同楼板的改动同时查看两层。
6. 满足必做条件后由一级使用现有发布入口生成一个 SNBT 子版本，并回读核对。从该落盘源生成或重新绑定最终展示用的图像证据，候选阶段的观察不直接冒充正式版本的出图。失败保留当前 head、原候选与问题证据。正式精修仍要求用户看过对应缩略图并明确授权。正式 NBT 仍从独立入口显式导出。

## 4. 数据、接口与兼容性

### 4.1 持久化数据

| 对象 | 首期字段与语义 |
| --- | --- |
| `AuthoringRun` v1 | ID、模式（`image_guided`、`existing_draft`、`text_only`）、修订、阶段、选中的需求/布局及参考清单、模型基线、工作包根和审阅回执。放在现有制作批次的独立 run 内，路径相对创作工作区。 |
| `ReferencePack` v1 | 每张图的 ID、路径、SHA-256、像素宽高、类型（`photo`、`concept`、`part_detail`、`orthographic`）、角色和来源。图版裁片用原像素半开坐标。世界锚点仅用于已有标定。 |
| `SourceBinding` | `source`、`source_sha256`、含墙层的 `model_sha256`、`context_sha256` 和请求级引擎指纹。图像证据复用既有 `geometry_sha256` 与自身图片哈希。 |
| `WorkPackage` | ID、`parent_id`、层级、角色、修订、源绑定、`write_boxes`、`read_boxes`、`protected_boxes`、安装接口、构件列表及预期视角。写区采用全局整数 XYZ，端点包含。 |
| `PatchCandidate` | 包及修订、读区指纹、补丁 `{pos,before:[state,wall],after:[state,wall]}`、构件完成情况及证据。空气统一使用 `minecraft:air` 和 `false`。每个坐标的状态和墙层作为一个原子值。 |
| `ReviewReceipt` | 候选批次及哈希、前后源、受影响区域和站位、实际路线、同机位图片和观察。用稳定问题 ID 跟踪新增、持续、已复验解决和缺证据。 |

制作运行状态依次为 `planned → references_bound → baseline_bound → review_ready → draft_saved`。纯文字模式记录参考不适用后继续。工作包使用 `pending → claimed → submitted → checked → adopted`，问题项回到待修改，取消和过期复用任务租约语义。深度从 1 开始，三级叶子禁止继续签发。人工审批和正式导出沿用各自状态来源。

### 4.2 拟议逻辑方法

这些是供工程实现的逻辑名字。先通过机器接口和 JSON 目录定契约，CLI 与桌面消费同一个后端。已有正式方法保留兼容。

| 方法 | 输入与产物 |
| --- | --- |
| `authoring.create` / `authoring.inspect` | 工作区、模式、任务、来源绑定。读操作返回当前修订、冻结证据状态和下一步，可请求紧凑或完整视图。 |
| `authoring.bind_reference` / `authoring.bind_baseline` | 当前运行修订、参考包或实际源哈希，并附采用的布局、空间简报和已知约束。服务确认上下文后前进一个阶段，缺资料时返回具体缺项。 |
| `authoring.issue` / `authoring.claim` | 父包 ID、修订、授权区、工作内容。签发受限范围，领取沿用租约和 fence，保留原请求 ID 回放。 |
| `authoring.context` / `authoring.submit` | 包及修订、源绑定、读取指纹和候选。输出只读方块摘要，或待复验候选回执。 |
| `authoring.plan_merge` | 选定候选及哈希、预期父源。返回实际冲突坐标、候选差异、跨区检查和可出图的候选引用。 |
| `authoring.save_draft` | 预检回执、同一候选集合及当前运行修订。锁内复核当前 head、源绑定和引擎，发布一次并可重放原成功回执。 |

父版本变化统一沿用 `STALE_PARENT`，支持读取最新版本及重新签发。旧值不合、越界、保护冲突、读区变化和证据过期分别返回可处理的稳定错误。发片、回装和链接历史各保持原子边界。中断后原回执按原请求编号和原参数重放，历史补登复用现有恢复入口。一级以外的发布请求必须拒绝。

### 4.3 工程约束

- Minecraft Java 1.20.1，DataVersion 3465。保留显式墙层、SNBT 版本链和发布锁。大型组装路径及 SAODG 的分片、运行缝、方块更新和旋转继续按项目约束。
- 公共命令在 skill 的顶层 `scripts/`，内部按现有职责挂到子包。`tool-catalog.json` 为工具定义事实源。桌面共用 Python 规则，保持 loopback 的 Host/Origin 和工作区校验。
- 工作区路径、图像尺寸与字节上限由服务校验。写范围和预算由工作包签发。宿主的调度能力只消费数据协议，桌面 IPC 继续保持受限。参考图以已获授权的本地文件交换，启用外部图生由宿主与用户选择。
- 旧版制作源和冻结 Skill 保持原有入口。新运行清单采用加法接入，无需批量迁移旧资料。以独立模式先验通，配置选择性启用，现有格式和依赖沿用。

### 4.4 单个工作包示例

下面的坐标属于合成夹具。实际工作包必须从当前落盘源取得范围和旧值。默认只读外扩一格可由支承或跨楼层接口扩大，授权写区保持原样。

~~~json
{
  "id": "attic_furniture",
  "parent_id": "upper_level",
  "depth": 3,
  "write_boxes": [{"lo": [14, 15, 18], "hi": [23, 17, 25]}],
  "read_boxes": [{"lo": [13, 14, 17], "hi": [24, 18, 26]}],
  "components": [
    {"id": "under_eave_chest", "intent": "坡下可辨的低储物箱"},
    {"id": "reading_desk", "intent": "有桌脚、桌沿和可达使用侧的书案"}
  ],
  "interfaces": ["attic_floor", "stair_landing_clearance"],
  "expected_views": ["attic_furnishings", "attic_stair_arrival"]
}
~~~

签发后，如果近景发现柜面悬空，下一候选只发送柜面及支点相关的实际差异。重复旧包的写入会在相应修订被关闭后拒绝。若改动落在楼板或承托登记的坐标上，预检生成相邻侧复验项。两个批次共享已冻结的全局原点，局部坐标与贴面操作各自复用现有转换。

## 5. 验收与质量试验

| 审查重点 | 可验证结果 |
| --- | --- |
| 单张透视参考图、图版内裁片、参考图片被替换 | 非标定图可登记及定位。已有三视图能力继续要求有效标定。更换字节后旧绑定失效。 |
| 多构件批次、越界、四级派发、墙层冲突 | 多件同一批可接收。并行读区允许共享，非法写权和第四层拒绝并定位。整批失败时 head 保留。 |
| 两批不写同一坐标，却共用受改支点 | 依据读区和安装接口范围提示失效候选，要求重签并重新检查。 |
| 二楼地毯导致一楼天花板露色，修改后门口和任务路线仍可走 | 合模反馈明确给出楼板的两侧空间与机位。前后实际图片、站位、修改来源和修复回读可以逐项对上。 |
| 进程重启、最后一次响应丢失、旧租约迟到、用户已另存 | 可恢复在途任务和候选，重放同一请求不重复发布，旧租约和过期父版本不推进 head。 |
| 有 PNG 但没看图，或留有未知碰撞 | 审阅条目与通路条目各自标明缺证据。产物存在、修改格数和渲染成功不能替代实看或实际游戏记录。 |

三项合成回归贯穿实施。旅店夹具覆盖普通 SNBT、两批家具、共享楼板和修饰支点。工业夹具覆盖两区、跨区挂接、越界和断路。参考冲突夹具覆盖单张透视、正交标定、已知尺寸和明确校正来源。对创作质量保留现有评分的分项，同时记录必做项覆盖率、失败定位耗时、手写粘合脚本数、人工实看耗时和路线回归。图生等待与引擎时间分开记录。

对内饰效果做一次两因素四组试验。因素一是原内饰图或加构件近景，因素二是房间单任务或按活动分批。固定起始模型、引擎、时长与修改预算。用相同渲染条件匿名评审部件可辨性、支承、用途和房间覆盖，允许平局。先收集逐例证据，之后再确定是否默认启用或推荐补图。路线回归和硬约束失败独立记录。

## 6. 实施计划

以下路径以 `.agents/skills/minecraft-nbt-modeler/` 为 skill 根。测试从仓库根用 mise 执行。拟新增 suite 在 `tests/suites.mjs` 登记，加入影响到的现有 CI 门槛。每阶段先做回归，再用实际命令验证。P2 可先在测试或显式试用模式保存技术已验证的制作版，状态标注待视觉审阅。P3 接通实际证据后开放面向用户的审阅就绪状态。

### P0 制作运行和参考包

**文件**　新增 `scripts/nbt_project/authoring_runs.py`、`scripts/nbt_review/reference_pack.py`、`tests/engine/authoring-run.py`。修改 `tool-catalog.json`、`scripts/nbt_agent/machine.py`、`tests/suites.mjs`。

**产出**　`create_run(workspace, request) -> RunReceipt`，`register_pack(workspace, request) -> ReferencePackReceipt`，`inspect_run(workspace, request) -> RunView`。为已有布局和空间简报保留明确的绑定字段。

- [ ] 添加回归 `test_concept_photo_and_stale_reference`。覆盖单张透视、分图角色、错哈希、超像素范围、旧三视图和纯文字。
- [ ] 用 `mise run test -- authoring-run` 确认新反例后，实现登记、独立修订与紧凑读取，产出可读的来源校验结果。
- [ ] 执行 `mise run test -- authoring-run` 和 `mise run test -- reference-views`。确认纯文字和已有三视图结果可复现。

### P1 受限工作包与局部读取

**文件**　新增 `scripts/nbt_agent/authoring_tasks.py`、`tests/engine/authoring-delegation.py`。修改 `scripts/nbt_agent/machine.py`、`task_client.py`、工具目录和 suite。租约共用原协议与存储。

**产出**　`issue_package(workspace, request) -> PackageReceipt`，`package_context(workspace, request) -> LocalContext`，`submit_patch(workspace, request) -> CandidateReceipt`。

- [ ] 加 `test_three_levels_multi_component_with_fences`。覆盖第三级单包四件、第四层、第三级越权发布、跨区写、读区重叠、写区冲突、领取超时和旧 fence。
- [ ] 实现工作包的派发、读区/写区和候选登记。`selection-edit` 能提供编码组件，包上下文另附只读邻域与绑定。没有子代理的宿主走同一契约的顺序流程。
- [ ] 运行 `mise run test -- authoring-delegation`、`mise run test -- agent-protocol` 和 `mise run test -- selection-edit`。核对旧客户端领取和重放通过。

### P2 普通制作源原子合模

**文件**　新增 `scripts/nbt_composition/authoring_merge.py`、`tests/engine/authoring-merge.py`。保留原 `working_model.py` 和大型 `assembly_handoff.py` 的输入输出兼容。复用现有补丁、版本锁和发布历史。

**产出**　`plan_merge(workspace, request) -> MergeReceipt`，`save_merged_draft(workspace, request) -> DraftReceipt`。预检和落盘双方核对同一份选中补丁清单。

- [ ] 加 `test_atomic_merge_roundtrip_and_parent_race`。两组合法补丁产生一个子版。混入错误墙层、重叠、过预算、受保护坐标、变化读区或陈旧父版本时，一个子版本也不发布。重试返回同一版。
- [ ] 落地一次读取、整批预检、一次候选补丁和一次锁内保存。用现有错误类型保留具体坐标与候选来源，正确复核发布间隙的来源和引擎变化。
- [ ] 运行 `mise run test -- authoring-merge` 和 `mise run test -- model-workflow`。核对单源与大型组装回读、显式墙层和桌面并发另存的保护。

### P3 跨区域真实审阅和复验

**文件**　新增 `scripts/nbt_review/authoring_review.py`、`tests/engine/authoring-review.py`。复用 `scripts/nbt_building/intent.py`、`review.py`、`scripts/nbt_review/compare.py` 与 `assets/viewer/render-batch.mjs`。

**产出**　`prepare_review(workspace, request) -> ReviewPack`，`record_observation(workspace, request) -> ReviewRevision`。普通 SNBT 支持区域盒和局部坐标，已有建筑方案继续支持 part 和 interface。

- [ ] 加 `test_shared_floor_dual_side_review` 和 `test_same_camera_evidence_binding`。检查地毯与天花板两个影响面、实际玩家机位、漏图和错渲染配置。增加一个能走到却站错柜台操作侧的反例。
- [ ] 实现补丁影响到区域、路线和机位的关联。确认真实源和图片绑定，观察记录含位置与内容。新增、持续问题与已复验解决分开显示。
- [ ] 运行 `mise run test -- authoring-review`、`mise run test -- architecture-preview` 和 `mise run test -- building-quality`。从旅店和工业夹具的正式落盘候选出实际图，实看入口、接点和家具使用侧。

### P4 工作台接入与发布

**文件**　新增 `assets/viewer/src/projects/authoring-workflow.js`、`tests/desktop/authoring-workflow.mjs`。从现有项目批次界面接入。更新 `docs/development/ARCHITECTURE.md`、`docs/guides/SHARED_WORKSPACE.md` 和工具目录生成物。

**产出**　工作台可看到图像、范围、在途工作包及验收证据。读写走同一个本地后端。前端先展示只读候选与冲突，再按工作包权限及用户动作执行采纳或保存。

- [ ] 加桌面用例，覆盖恢复在途状态、三层任务树、图片失效、空间边界显示、候选保存和现有精修/导出入口。
- [ ] 接入和同步 `mise run tools:sync`。核对新工程能够发现命令，旧冻结工作区的既有入口可用。
- [ ] 执行 `mise run doctor`、`mise run check`、`mise run ci:build`、`mise run test -- authoring-workflow` 和 `mise run test -- desktop`。发行继续走现有 Windows 打包和 CI 审查。

## 7. 交付顺序与取舍

最先交付 P0–P2，可在 CLI 中复现普通 SNBT 的两批家具合模，过程状态可恢复。P3 通过真实预览和相邻面复验后，再在桌面开放这条工作流。试作用户可先按旧入口使用，并从制作批次读取新的候选和证据。

第一期暂缓应用主动启动外部代理、从单图自动还原完整建筑、自动跨版本改基和新的游戏碰撞仿真。完工指标依赖可读的家具、可达站位和实际渲染。颜色、折线与半格造型继续使用现有 Minecraft 方块表达，游戏内行为另由真实游戏记录验证。

**本版方案状态**　已对照当前源码、在途工作树和三轮创作回执。上面的新方法、回归套件与工作台能力是待实施提案。
