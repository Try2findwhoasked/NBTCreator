# 应用与skill共用工具接口

本文件由tool-catalog.json生成，不手改工具清单。应用工具选择器、提示词工作台和Python/CLI读取同一份源；Electron无需启动即可调用。

默认工作区为Agent调用时的项目目录，资产位于 `nbt_models/`。使用相对路径，或显式指定 --workspace。

| kind | 名称 | 起始参数与限制 |
| --- | --- | --- |
| geometry | 几何 / 布尔 / 拉伸 | 形体取样在方块中心；内部box的min/max是连续表面。几何超出lo/hi会被裁剪。 |
| box | 体素填充 / 挖空 | lo/hi含边界。挖空时将state改为air。 |
| hollow_box | 空心外壳 | 内部会挖空气；保留密闭外层与支承。 |
| frame | 平面边框 | 选区必须恰有一个轴的lo=hi。 |
| beam | 直线 / 斜梁 | width仅1、3、5；自行检查端点支承与六邻接。 |
| replace | 精确状态替换 | 精确状态匹配；填写完整原状态，朝向不会自动迁移。 |
| move_region | 平移构件 | 保留源状态与墙mask；目标冲突和保护区修改拒绝。 |
| copy_region | 快照复制 | 复制不旋转朝向；主体与墙体请拆分操作。 |
| repeat_region | 线性阵列 | 源快照复制到偏移的1..count倍处，目标需有足够空间。 |
| transform_region | 旋转 / 镜像 | 先镜像再绕Y转90°整数倍；不支持的状态家族拒绝，楼梯/门/轨道不能任意旋转。 |
| morphology | 膨胀 / 侵蚀 / 表皮 | 六邻接；域外视为空。薄梁与外壳要保护，新格用state。 |
| diffusion | 多源 / 表面扩散 | 种子必须在合格未保护位置，steps为图距离；不会跨越断开的表面。 |
| explosion | 静态爆炸 / 放射裂缝 | 静态挖除，不是TNT物理；球包围必须在选区内，保护位置跳过，保留坑底与外壳。 |
| scatter | 带间距散落 | supported只做下方非空气筛选，不认证真实碰撞或重力。 |
| pattern | 带权混材 / 连片噪声 | palette是相对权重，fraction是覆盖率。源状态/形状策略另验。 |
| surface_palette | 低密度表面换材 | 不挖空气；带权需求请用pattern。 |
| weathering | 连片风化 / 苔痕 / 裂纹 | 完整块材质为主；地面自动识别优先auto_floor。 |
| auto_floor | 多层地面识别 / 半砖坑 | 需要真实start/targets/ports/interior_probes；依赖实际模型，网页不能估算通过。 |
| paste_component | 构件资产粘贴 | palette为完整状态数组；voxels为相对lo的[x,y,z,材质编号]，最多65536格。默认拒绝冲突；墙层与主体拆为不同操作。 |
| auto_road | 自动道路铺设 | 起终点Y为同一高度的路面。宽度在路径两侧和起终点前后扩张，完整占用须在选区内。ROAD_BOUNDS 给出占用范围与越界方向。覆盖已有路面须显式开启。 |
| selection_replace | 连通 / 表面选区换材 | 从seed_position六邻接选取同状态或实体；surface按暴露朝向选面，thickness仅向实体内扩展。保护及预算继续生效。 |
| align_region | 对齐 / 锚点 / 落地吸附 | lo/hi是源包围盒；align按轴min/center/max/keep对齐；anchor指定源和目标全局锚点；ground按destination的XZ和最高搜索Y落地，拒绝不平整或未知支承。归属请显式设置。 |
| array_region | 环形 / 沿路径阵列 | lo/hi为源；source_anchor默认lo。path按折线弧长布置；radial用centre/radius/count/start_angle/sweep_angle。cardinal朝向取最近90°，不支持任意角度状态旋转；位置量化碰撞和预算均预检。 |
| auto_stairs | 半格楼梯 / 坡道 / 平台 | start/end是玩家脚位，end.y必须高于start.y。straight须沿X或Z轴，水平路程L至少2*(end.y-start.y)+2*width+1，给两端平平台留白；放不下时改为明确box阶梯或另设计折返。不能自动清头顶或补支撑；须实际预览通行。 |
| terrain_road | 地形道路 / 避障 / 有限填挖 | A*按真实地表绕开非地形障碍；端点Y为真实地表格。高度差最多1，自动楼梯并逐段通行检查；仅允许列出的地形材质填挖。桥段需显式max_bridge_span，不认证承重。 |
| auto_roof | 屋顶 / 屋脊 / 屋檐 | ridge_axis 仅控制 gable 和 gambrel 的屋脊。hip、dome、curved_hip 按足迹生成。curved_hip 使用 curve_power、eave_lift、corner_lift 调整曲面、起翘与翼角。用 architect part-preflight 的 underside_xz 按世界坐标查屋底，梁柱支承和密闭另验。 |

GUI的“建模工具”支持同样的有序operations。每步 enabled 为可选布尔开关，省略等于 true；false 保留在设置/计划中，但编译与执行跳过，不写任何方块。名称由 label 保存，数组顺序决定执行顺序。Agent使用control plan/preview或原refine流程调用，旧的专用API保持兼容。计划、预览、应用、导出和精修确认是不同阶段；能力清单不授予任何批准。

统一入口：`mise run nbt -- capabilities`；独立复制skill后使用 `python <skill>/scripts/nbt_capabilities.py`。各命令参数请用 --help 查询。overwrite/write_group是可选操作元数据，见tool-catalog.json的optional_operation_fields；未提供时保留原工具行为。AI与构件放置的显式覆盖开关不能越过保护和预算。

## 无界面命令

- inspect → scripts/nbt_task.py
- snapshot → scripts/nbt_task.py
- render → scripts/nbt_task.py
- regress → scripts/nbt_task.py
- control → scripts/nbt_detail_control.py
- refine → scripts/nbt_refine.py
- model → scripts/nbt_working_model.py
- assembly → scripts/nbt_large_assembly.py
- reference → scripts/nbt_reference_views.py
- curve → scripts/nbt_curved_surface.py
- convert → scripts/nbt_web_revision.py
- registry → scripts/nbt_registry.py
- library → scripts/nbt_library.py
- check → scripts/check_skill.py
- capabilities → scripts/nbt_capabilities.py
- migrate-workspace → scripts/nbt_workspace.py
- exposure → scripts/nbt_exposure.py
- feedback → scripts/nbt_feedback.py
- paths → scripts/nbt_paths.py
- validate → scripts/nbt_candidate.py
- components → scripts/nbt_components.py
- ai-style → scripts/nbt_ai_style.py
- recipes → scripts/nbt_recipes.py
- project-batch → scripts/nbt_project_batch.py
- prompts → scripts/nbt_prompts.py
- feedback-tasks → scripts/nbt_feedback_tasks.py
- batches → scripts/nbt_batches.py
- selection-edit → scripts/nbt_selection_edit.py
- retrieve → scripts/nbt_retrieval.py
- diagnostics → scripts/nbt_diagnostics.py
- agent-tasks → scripts/nbt_agent_tasks.py
- project-repair → scripts/nbt_project_repair.py
- asset-batches → scripts/nbt_asset_batches.py
- asset-libraries → scripts/nbt_asset_libraries.py
- room-score → scripts/nbt_room_score.py
- effect-assets → scripts/nbt_effect_assets.py
- history → scripts/nbt_history.py
- snbt → scripts/nbt_snbt.py
- finalize → scripts/nbt_finalize.py
- machine → scripts/nbt_machine.py
- task-client → scripts/nbt_task_client.py
- creation → scripts/nbt_creation.py
- architect → scripts/nbt_architect.py
- session → scripts/nbt_engine_session.py

工作区入口为 `mise run nbt -- <命令>`。`feedback scan` 扫描结构版本的评论索引，`feedback collect/archive` 校验或归档意见证据，详见 [Agent读取意见](agent-feedback.md)。

外部Agent改模后的版本登记和评论核对见 [任务回传](agent-task-return.md)，agent-tasks get/record 与应用共用源哈希；确定性检查的通俗解释与定位见 [检查结果解释](diagnostic-guidance.md)，diagnostics 只解释已保存报告，不重新验证或自动修复；按任务挑选资料片段和复用资产见 [本地参考检索](reference-retrieval.md)，retrieve search/bundle/read 共用来源哈希；选区自然语言工具步骤见 [选区编辑](selection-edit.md)，selection-edit context/compile 共用真实方块摘要、坐标平移与写入范围约束；构件的保存、整理、导入及候选放置见 [构件资产](component-assets.md)；参数化工具序列、材质主题和XYZ网格阵列见 [配方与主题](reusable-recipes.md)，recipes compile与components batch仅返回候选步骤；批量创作的过程目录、模型关联与交付图册见 [制作批次](batch-workspaces.md)，batches create/record/list/get/locate 在应用外也可使用；项目多选、只读批量预览与检查、进度及重试见 [项目批量任务](project-batch.md)；内部 API 与外部 Agent 共用的各区域创作参数见 [AI创作偏好](ai-creative-preferences.md)。

兼容入口

- `task` → `prompts task`

## 创作速查

从创作项目根目录用生成 Skill 所示前缀执行 `capabilities --routes` 单独查询这张表。已知命令可查 `<命令> --help`。工作区有同名任务时，前缀会指向文件任务。专题从已启用的知识中选读。

### 创作起步

| 任务 | 起点 | 契约或示例 | 输入 | 产物与接续 |
| --- | --- | --- | --- | --- |
| 从零起整栋初稿（亭子、入口、空间和构件） | 命令 `architect plan-build --request <请求JSON>` | `capabilities --architect-action plan-build`<br>[请求与用例](simple-building.md) | 按用途选尺寸、空间、材质、开口和机位。入口亭示例内含 save_draft，会发布制作版；只编译和检查时省略。 | 返回建筑编译与检查；保存时另有 saved、next.request 和 revision_request。<br>保存后把 next.request 原样交给 architect review-prepare；续版用 revision_request。 |
| 先看整栋外观与重点房间，再按选定参考搭建 | 命令 `creation --session <会话名> start --request <请求JSON>` | `creation --help`<br>[请求与用例](creation-workflows.md) | 领取初稿任务，声明 reference_roles。宿主展示外观及重点房间，再登记用户选择和工作区参考文件。 | 简报返回图集、选择和导入阶段，可跨会话接续。<br>依次 reference-show、reference-choose、reference-import。制作版保存后实际查看并展示从落盘 SNBT 渲染的室内图。 |
| 比较整栋空间与通路布局 | 命令 `architect layout-search --request <请求JSON>` | `capabilities --architect-action layout-search`<br>[请求与用例](architecture-workflow.md) | 基于同一粗模方案，用 variables 枚举 XZ 位移，或用 graph 声明空间关系与摆位候选。 | 给出通过实际通路和使用面检查的候选，以及各次尝试的失败证据。<br>选定候选后将其 plan 交给 architect plan-build，在构造和装饰深化后保存制作版。 |
| 复杂整栋的分层、面积与必经连接 | 命令 `architect layout-check --request <请求JSON>` | `capabilities --architect-action layout-check`<br>[请求与用例](whole-building-planning.md) | 用 program 与 layout 预检布局；用 source 和 source_sha256 回读成品。 | 返回目标、实测值、通过状态及楼层和问题坐标。<br>用 program-layout-search 生成候选，用 layout-prepare 把选择绑定到建筑方案。 |
| 按明确几何装配，或打开制作源续版 | 命令 `model --request <请求JSON>` | `capabilities --model`<br>[请求与用例](simple-building.md) | 新建填 size（XYZ 格数），已有制作版从原保存回执取 source 和 source_sha256；按需要填 actions。 | 返回模型摘要及操作结果；validate:true 复验，save_draft 另存 SNBT。<br>核对 result.validation（启用时）及 result.saved（保存时）；制作源用 render --source 出图。 |

### 局部修改

| 任务 | 起点 | 契约或示例 | 输入 | 产物与接续 |
| --- | --- | --- | --- | --- |
| 给已有建筑局部换材（保留边缘或立柱） | 命令 `selection-edit context --request <请求JSON> [--snapshot <同源after.json>]` | [请求与用例](selection-edit.md) | 从当前版本回执取 source 和 source_sha256，按实际全模型坐标选整数 lo、hi；快照沿用同一次候选回执。 | 读取真实选区，返回以 lo 为原点的 palette、runs、size 和 geometry_sha256。<br>保持源、边界和快照，传回 geometry_sha256；编写局部 operations 后调用 selection-edit compile。 |
| 编译局部步骤并接回原编辑计划 | 命令 `selection-edit compile --request <请求JSON> [--snapshot <同源after.json>]` | `capabilities --operation <kind>`<br>[请求与用例](selection-edit.md) | 沿用 context 的输入与几何哈希，operations 从局部 [0,0,0] 起算。按本次修改权限填写 allow_overwrite。 | 返回已平移一次且带 write_bounds 的全局 operations。<br>原样追加到同一源的 settings.operations；用 control plan、control preview 和 validate 检查候选。 |

### 找素材与复用

| 任务 | 起点 | 契约或示例 | 输入 | 产物与接续 |
| --- | --- | --- | --- | --- |
| 查找已有尖拱等资产 | 命令 `asset-libraries browse --request <请求JSON>` | `asset-libraries --help`<br>[请求与用例](asset-libraries.md) | JSON 填名称或标签 query 和数量 limit，例如 {"query":"尖拱","limit":4}。离线查现有来源。 | result.items 含候选及来源、版本、清单和资产哈希，result.errors 列来源异常。<br>同一命中的 id、sha256、source_id、version、manifest_sha256 原样交给 asset-libraries preview；复制或放置还需预览的 content_sha256。 |
| 重新编译已存配方 | 命令 `recipes compile --id <配方ID> --position <x,y,z> --size <sx,sy,sz>` | `recipes compile --help`<br>[请求与用例](reusable-recipes.md) | 从 recipes get 取配方及 revision_sha256；按目标模型选择画布、位置、主题和覆盖参数。 | 返回编译后的可复用候选操作。<br>追加到原编辑计划，再走预览和验证。 |
| 从参数生成构件 | 命令 `components agent --tool parametric_compile --request <请求JSON>` | `capabilities --agent-tool parametric_compile`<br>[请求与用例](parametric-components.md) | 按构件形态选 kind、尺寸和材料；具体参数见单项契约。 | 返回编译构件候选及几何信息。<br>用 parametric_preview 获取可查看的候选，再选择安装或显式保存资产。 |
| 查询屋顶等建模操作 | 命令 `capabilities --operations` | `capabilities --operation auto_roof` | 从操作清单选 kind，屋顶取 auto_roof；结构配方另查 capabilities --recipe structure。 | 操作清单返回名称和提示，单项查询返回参数。<br>把 auto_roof 填入 operations[].kind，形态和尺寸按单项契约填写。 |

### 自由曲面

| 任务 | 起点 | 契约或示例 | 输入 | 产物与接续 |
| --- | --- | --- | --- | --- |
| 拟合自由曲面 | 命令 `components agent --tool surface_fit --request <JSON>` | `capabilities --agent-tool surface_fit`<br>[请求与用例](freeform-surfaces.md) | 给出带 UV 的三维样点、四条 Bézier 边界，或同时提供两者。 | 返回控制网格、样点误差和边界锁定状态。<br>把返回的 patch 交给 surface_compile。 |
| 将自由曲面编译为方块壳体 | 命令 `components agent --tool surface_compile --request <JSON>` | `capabilities --agent-tool surface_compile`<br>[请求与用例](freeform-surfaces.md) | 提供控制网格、本地画布、材质和可选厚度。 | 返回结构 spec、可复用配方、细分误差上界和方块连通数据。<br>用 structure_preview 查看，或将 recipe 放入完整工作模型。 |

### 曲面纹样

| 任务 | 起点 | 契约或示例 | 输入 | 产物与接续 |
| --- | --- | --- | --- | --- |
| 规划和核对曲面样段 | 多步流程 `curve compose --request <JSON> / curve verify-mask --mask <JSON> --sha256 <哈希> / curve plan --request <JSON> [--compact] / curve verify --plan <JSON> --sha256 <哈希> / curve review-record --request <JSON> / curve review-verify --record <JSON> --sha256 <哈希>` |  | 可从来源与内容哈希绑定的构件切片显式映射动作，再绑定宿主、已验证截面、掩模、UV 映射及真实审阅机位。 | 输出可重算的分层掩模与凸饰、切槽、嵌纹候选，报告实际面、背衬和连续性；不保存制作版或批准。 |

### 三视参考

| 任务 | 起点 | 契约或示例 | 输入 | 产物与接续 |
| --- | --- | --- | --- | --- |
| 登记、拟合与回投影 | 多步流程 `reference register\|fit\|verify-fit\|cameras\|verify-cameras\|compare\|verify\|review-prepare\|review-record\|review-verify` |  | 提供同尺度三视图、像素原点、轴方向、带依据的锚点及显式轮廓掩模。 | 输出绑定哈希的 loft 截面、轮廓指标和叠图；不替代看图、真实确认或游戏验证。 |

### 大型组装

| 任务 | 起点 | 契约或示例 | 输入 | 产物与接续 |
| --- | --- | --- | --- | --- |
| 导入并核验大型组装制作源 | 命令 `assembly import --request <JSON>` |  | 指定画布、工作区内 SNBT 分区、各自 SHA256 与全局偏移；输出为新建筑版本的 master 目录。 | 逐份回读并登记历史；可用 assembly inspect、model 和 render 操作，定稿导出仍须独立支持。 |
| 签发和回装协作切片 | 多步流程 `assembly slice --request <JSON> / assembly merge --request <JSON>` | [请求与用例](large-assembly.md) | 签发时绑定主稿、范围和必要路线；回装时提供原签发清单哈希及各候选哈希。 | 复核可写域、重叠、保护和全局路线后保存一个新制作版；不批准或导出。 |

### 任务与交接

| 任务 | 起点 | 契约或示例 | 输入 | 产物与接续 |
| --- | --- | --- | --- | --- |
| 按编号读取已交接的任务 | 命令 `task --id <任务编号>` |  | 从创作项目根目录运行。支持提示词和建筑修改编号。用 --view compact 查看下一步。 | 回读已校验的内容和失效附件提示。读取任务与领取、建模、精修批准分开。 |
| 查找两类交接任务 | 命令 `task-client list --pending` |  | 省略 --pending 可看其他任务；--kind 可限定 prompts 或 tasks。 | 提供各任务的查看命令，建筑任务来源失效时返回诊断。 |
| 查看任务记录和绑定证据 | 命令 `task-client inspect <prompts 或 tasks> <任务编号>` |  | 提示词任务用 prompts，已有建筑修改任务用 tasks。 | 默认返回任务阶段、来源核对与下一步；按 expand 视图展开，再用 task-client start 明确领取。 |
| 多区建模或明确要求分工 | 多步流程 `batches create / batches run / machine --request <JSON>` | `machine --schema`<br>[请求与用例](authoring-workflow.md) | 在制作批次建立 authoring 尝试，冻结完整普通 SNBT、空间与共享接口，并按需要登记参考图。 | 工作包按授权读局部页和裁片，回传含旧方块及墙层的补丁，协调方预检、审阅并保存统一制作版。<br>从落盘制作版重新核验室内实图。需要独立局部 SNBT 文件交接时使用大型分片路线。 |
| 执行已领取的建筑初稿 | 命令 `creation --session <会话名> start` |  | 从已领取的提示词读取冻结模式。极限效果用 --request 显式登记要探索的设计轴。 | 本地编译或接收 WorkingModel，回读、检查、出图并保存证据。按模式处理单候选或匿名 A/B 审阅；选用后另存制作版。 |

### 工作区与运行时

| 任务 | 起点 | 契约或示例 | 输入 | 产物与接续 |
| --- | --- | --- | --- | --- |
| 核对同步版本和渲染依赖 | 命令 `paths --runtime` |  | 从已同步的实际创作工作区运行，适用于迁移或批量出图前。 | 报告当前 Python、同步时的运行时、Playwright 和 Chromium 路径。实际图片用 render 验证。 |
| 检查或修复外部 Agent 资料 | 命令 `exposure show` |  | 看 custom_issues；恢复原文件、exposure import 或 exposure edit --id <编号> --setting remove。 | 修复登记与重新同步工作区入口，仅改变外部 Agent 阅读范围。 |

### 知识库

| 任务 | 起点 | 契约或示例 | 输入 | 产物与接续 |
| --- | --- | --- | --- | --- |
| 离线检索参考 | 命令 `retrieve search --request <JSON文件>` |  | 填 workflow 和 query；可用 keywords 给短检索词，include_extension_assets 同时查外部 Agent 的离线资产候选。 | 返回已启用文档、书库与收藏的简短命中。用 receipt 和 ref 查看局部出处，或以 selected 保存引用集合。 |
| 联网补查公开原页 | 命令 `retrieve research --request <JSON文件>` |  | 任务明确要求联网时填 workflow，提供公开 query 或已知 HTTPS urls。 | 返回原文证据、来源和未完成项。默认取得一条即返回。 |
| 管理网页证据收藏 | 命令 `retrieve saved-web --request <JSON文件>` |  | 填 workflow。action 为 list、add 或 remove，保存或移除时填已有的 web: 证据 id。 | 保存的证据进入本工作流离线搜索，既有引用集合仍绑定原快照。 |

### 构件节奏

| 任务 | 起点 | 契约或示例 | 输入 | 产物与接续 |
| --- | --- | --- | --- | --- |
| 按间距与材质目标生成梁架候选 | 命令 `model --request <请求JSON>` |  | 在 actions 中使用 beam_rhythm，填写梁架目标、世界修改区域和允许起点。用 capabilities --model 查字段。 | 返回通过宿主约束的排序、实测差异和拒绝坐标。可写候选预览，由 adopt_beam_rhythm 明确选择。 |
| 移植单个开间的檐底细节 | 命令 `model --request <请求JSON>` |  | 在 actions 使用 wavelet_eave。填写实际目标与参考檐边、方向、屋脊和细节尺度。用 capabilities --model 查字段。 | 返回目标与实测半格曲线、实际改动、轮廓和接缝复验。看真实预览后可用 adopt_wavelet_eave 选择。 |

### 检查

| 任务 | 起点 | 契约或示例 | 输入 | 产物与接续 |
| --- | --- | --- | --- | --- |
| 校验候选快照 | 命令 `validate --request <请求JSON> --snapshot <候选快照> --output <新检查目录>` | `validate --help`<br>[请求与用例](diagnostic-guidance.md) | 同一次 control preview 的原始编辑请求与回执的 result.snapshot（after.json）。 | 写 validation.json。ok:true 表示生成报告；result.passed 决定是否通过，失败退出 1。<br>失败时把 result.validation 所指报告交给 diagnostics --kind candidate；通过后检查绑定并实际看图。 |
| 复验已保存的制作源 | 命令 `model --request <请求JSON>` | `capabilities --model` | JSON 填 source、source_sha256 和 validate:true。路径与哈希从 model 的 result.saved 或 architect 的 saved 取。 | 返回 result.validation；验证抛出冲突时，退出 1 并带错误及冲突。只检查时省略 actions 和 save_draft。 |
| 复验建筑及绑定方案 | 命令 `architect plan-check --request <请求JSON>` | `capabilities --architect-action plan-check` | JSON 填绑定过建筑方案的 source 和 source_sha256。 | 成功退出 0，返回 validation、绑定方案和 plan_sha256；失败退出 1。<br>需要看图时把 next.request 交给 review-prepare。 |
| 回放并缩减建筑活动失败 | 命令 `architect failure-replay --request <请求JSON>` | `capabilities --architect-action failure-replay`<br>[请求与用例](architecture-workflow.md) | 通过版 source、源与方案哈希、失败方案或差分组、活动失败判据及检查预算。 | 返回原始与缩减失败、候选检查和极小性覆盖。指定 output 可保存可复跑回放包。 |
| 评估整栋建筑或复核续版质量 | 命令 `architect quality-check / quality-compare --request <请求JSON>` |  | 制作源和哈希，可选 review-record 的审阅绑定。对照时提供上一版或失败回执绑定。 | 返回五维评分、证据覆盖、优先问题和同条件分差。可用 --compact-report 保留完整回执。 |
| 查询制作源是否可编辑 | 命令 `control inspect --source <制作源>` |  | 现有制作源路径。 | result.editing_ready 表示是否具备编辑条件，context_readiness 给出上下文缺失或失配的原因。 |
| 解释检查失败并定位证据 | 命令 `diagnostics --kind <model、review 或 candidate> --report <完整回执>` | `diagnostics --help`<br>[请求与用例](diagnostic-guidance.md) | 建筑执行失败用 model 和 report.path；审阅覆盖或观察用 review；候选检查用 candidate 和 result.validation。 | 返回问题、位置、证据及下一项核对；退出 0 表示解释成功。<br>按证据核对原请求或绑定。需要修改时重新编译及复验。 |

### 构件

| 任务 | 起点 | 契约或示例 | 输入 | 产物与接续 |
| --- | --- | --- | --- | --- |
| 预检方案中的单个构件 | 命令 `architect part-preflight --request <请求JSON>` |  | JSON 填 plan 或 plan_id，以及要检查的 part。用 capabilities --architect-action part-preflight 查参数。 | 编译指定构件，返回方块状态支持和接口问题。整栋装配与宿主验证由 plan-build 执行。 |
| 填写结构配方 | JSON 字段 `recipe.tool = "structure"` |  | 填写建筑方案的 parts[].recipe 或主模型 install 的 recipe。capabilities --recipe structure 返回配方示例。 | 配方由调用方编译为构件体素，用于组装。 |
| 生成独立构件候选预览 | 命令 `components agent --tool structure_preview --request <请求JSON>` |  | JSON 的 spec 填构件规格。capabilities --agent-tool structure_preview 返回可运行的请求示例。 | 写临时候选快照与缩略图。安装和入库各有独立入口。 |
| 创建纹样并取得拟合输入 | 命令 `components agent --tool pattern_create --request <请求JSON>` |  | 用 capabilities --agent-tool pattern_create 查小位图或图层配方参数。 | 保存纹样资产，result.fitting_input 可直接合入 pattern_microfit 请求。用 pattern_assets 的 action:get 和 result.id 回查。 |

### 看图与交付

| 任务 | 起点 | 契约或示例 | 输入 | 产物与接续 |
| --- | --- | --- | --- | --- |
| 准备建筑审阅 | 命令 `architect review-prepare --request <请求JSON>` | `capabilities --architect-action review-prepare` | JSON 填 source、source_sha256 和新的 output 目录。补拍可用 view_overrides 按原 ID 替换机位，单独出图时用 view_ids 选择机位。 | 复验保存源并写审阅包及相机；coverage_passed 是机位覆盖检查，visual_status 表示仍待看图（完整回执在 coverage 下）。<br>运行回执的 render_command 出图，保留同份回执的 review_record_bindings。 |
| 推荐建筑审阅补拍机位 | 命令 `architect review-recommend --request <请求JSON>` | `capabilities --architect-action review-recommend` | 填原审阅 pack、pack_sha256 和新 output。可填已登记的 notes_sha256、待补位置及搜索预算。 | 按半格脚位和实际模型估计取景，返回推荐机位、预计覆盖与待补原因。<br>有推荐时将 next.request 交给 review-prepare，再出图并实际查看。 |
| 从制作源渲染实际图片 | 命令 `render --source <制作源> --cameras <相机JSON> --output <新目录>` | `render --help` | 使用保存回执的制作源；建筑审阅沿用 review-prepare 生成的相机。 | 写 PNG 和 render_manifest.json；检查 status:complete 及源、相机、图像哈希。<br>打开实际图像，建筑审阅用 review-record 登记观察。 |
| 从候选快照渲染实际图片 | 命令 `render --snapshot <候选after.json> --cameras <相机JSON> --output <新目录>` | `render --help` | 快照来自 control preview 的 result.snapshot；对比前后时沿用相机，给两次出图各选新目录。 | 生成绑定候选快照的 PNG 与渲染清单。<br>打开图片并核对候选绑定；改动仍需通过候选验证。 |
| 登记建筑看图观察 | 命令 `architect review-record --request <请求JSON>` | `capabilities --architect-action review-record` | 原样取 review-prepare 的 review_record_bindings，再填实际看图得出的 observations 和 issues（无问题填 []）。 | 写观察记录，返回覆盖与交付摘要。精修另须用户看过对应图像并明确同意。 |
| 保存可编辑 SNBT | 命令 `model --request <请求JSON>` |  | 在 model 或 architect plan-build 的 JSON 请求中填写 save_draft。 | 保存新 SNBT 制作版，model 返回 result.saved，architect 返回 saved；源路径及哈希供复验和出图。 |
| 只读记录定稿所需的审阅输入 | 命令 `finalize --source <已保存制作源> --inspect-inputs` | `finalize --help` | 审阅时用本次对应的制作源。 | 返回 source_sha256 和 inputs_sha256，供同一版本显式定稿时传回。<br>把哈希与本次审阅关联；输入变化时重新核对审阅。 |
| 导出定稿 NBT | 命令 `finalize --source <已保存制作源> --source-sha256 <审阅源哈希> --inputs-sha256 <审阅输入哈希>` |  | 审阅时用 --inspect-inputs 记录源和输入哈希；仅在用户明确要求定稿时导出。无墙的独立建筑须在保存时声明 allow_empty_wall_mask:true。 | 验证并在 nbt_models/_exports/ 写 NBT 完整主模型、分片与交付回执。 |

### 路径和状态

源码入口的全局 `--workspace <目录>` 放在子命令之前，启动器在所选创作目录执行。一些 Python 子命令另有自己的 `--workspace`，用子命令帮助核对。相对 `--request` 文件路径从命令工作目录解析；JSON 内的建筑或工作模型资源相对于创作工作区，control 和 selection-edit 的资源相对于命令工作目录。文件内明确以元数据为基准的引用仍从该元数据所在目录解析。完整 capabilities 的 `cli_path_bases` 给出这几个基准。

先看进程退出码，再看该命令的业务状态和源绑定。参数用法错误通常退出 2。建筑或工作模型执行失败退出 1，检查 `error`、`code` 和 `conflicts`；过期绑定还可查看 `recovery`。候选 validate 生成失败报告时仍可返回 `ok:true`，但 `result.passed:false` 且退出 1。紧凑任务回执用 `source_matches`、`next` 和 `expand` 判断可否接续。看图确认及显式定稿需各自的用户授权。

## 共用结构 Agent 工具

`components --workspace <project> agent --tool <name> --request <json>`

内部 API 与外部 CLI 调用同一 Python 实现；参数 Schema 见 capabilities.agent_tools。预览、保存新资产、候选放置和显式 NBT 导出保持独立。

| 工具 | 用途 |
| --- | --- |
| structure_list | 列出当前工作区可复用结构资产；不读取其他工作区。 |
| structure_read | 读取结构体素、材质、墙归属、锚点与内容哈希。 |
| structure_view | 为已有结构创建独立只读3D快照、真实缩略图和一个相机；不写NBT。 |
| structure_preview | 从共用建模工具或已有结构放置参数创建独立候选和预览；不修改建筑、不写入构件库。 |
| structure_write | 显式将绑定预览保存为新的构件资产；不能覆盖已有资产或导出NBT，保存不表示设计批准。 |
| structure_place | 按锚点、旋转、镜像生成放置操作；不实际写建筑，仍须control preview/validate和显式新版本导出。 |
| structure_save | 直接保存模型生成的资产：spec、component或绑定预览三选一；本地校验和真实预览后入库为待审阅资产，生成资产批次清单。保留手动导入，不产生NBT或设计批准。 |
| parametric_list | 查询参数化模块、可直接编译的对象配方库、柱式与扶手样式、参数及安装边界；只读。 |
| parametric_compile | 编译参数化模块候选：可调周期与相位的建筑重复频谱、柱式、外置楼梯扶手、独立栏杆、梁、托架、拱框、门窗框、基座及家具。配方见parametric_list.object_library；不改当前建筑。 |
| parametric_preview | 按参数编译并生成真实独立构件候选与缩略图；不入库、不批准、不写建筑。 |
| parametric_contract | 由可信调用方给定硬约束，返回供模型输出使用的JSON Schema及语义门禁说明；模型回复不能修改该契约。 |
| parametric_validate | 使用调用方保留的硬约束验收模型proposal，再运行共享编译器；超限拒绝，不截断、不降级、不写建筑。 |
| parametric_surface | 查询真实完整方块平面、缺口、遮挡与厚度，汇总几何状态并区分宿主表层、相邻外侧及向内各层保护；先校验实际开洞上下文，绑定源和候选，不推断门窗语义。 |
| parametric_mount | 按平面UV锚点安装参数化对象，硬检查安装面、缺口边距、碰撞、保护和预算；返回只读候选操作。 |
| parametric_layout | 按网格、边框或中心布局安装对象；明确拒绝或跳过缺口/保护冲突并逐项报告；不写建筑。 |
| parametric_compose | 按对象编号、锚点与朝向组合构件，检查重叠和保留空间，返回可预览结构方案。 |
| parametric_regenerate | 核对原配方并仅重生成指定部件，检查其他体素相同，返回含对象编号和父配方哈希的候选。 |
| pattern_list | 查询纹样图、哈希、适用安装面和建议尺寸；microfit.preferred 标记小尺寸专用纹样，recommended_size_uv 按安装面给出已测微型尺寸。 |
| pattern_compile | 将库中或工作区的灰度纹样编译为地板、墙、柱或吊顶面板方案。 支持surface=cylinder的圆柱环绕，楼梯和半砖状态由脚本按局部轮廓和切线自动确定。 |
| pattern_preview | 编译纹样面板并生成引擎候选预览。 支持surface=cylinder的圆柱环绕，楼梯和半砖状态由脚本按局部轮廓和切线自动确定。 |
| pattern_mount | 将图库或样本纹样贴合绑定安装面，地板生成原层镶嵌替换候选，墙柱和吊顶生成外贴候选，硬检查保护、开口、占用、净空和预算。 |
| pattern_cylinder_mount | 对哈希绑定的既有竖直圆柱生成环绕外饰候选，自动确定楼梯与半砖状态，检查完整柱芯、碰撞接触、保护、开口和预算。目标框包含柱芯及一格外饰边。 |
| pattern_create | 用小位图、几何绘图或图层组合创建原生纹样。CLI 回执的 result 直接包含 id、image_sha256 和 fitting_input。把 fitting_input 合入 pattern_microfit 请求，或用 id 和 image_sha256 组装 pattern_asset。 |
| pattern_assets | 用 action:list 查询纹样资产，用 action:get 和 id 读取指定纹样。copy 可从内置图库创建本地副本。修改资产绑定 content_sha256，重用图像绑定 image_sha256。 |
| pattern_microfit | 先拟合可辨纹样单元，再铺排；支持质量门槛与硬拓扑约束，可选活版门、石墙、玻璃板、铁栏杆、栅栏、雪层、地毯、压力板、末地烛、链条等精细形状。 |
| scene_compile | 按稳定对象ID、尺寸引用和贴附关系编译建筑对象图；检查依赖、实际接触、重叠、保留空间、声明通路与关系锁，只返回候选。 |
| scene_save | 显式保存对象图和编译快照的新版本；校验候选、父版本及保留或明确解除的关系锁，保留旧版，不写建筑或定稿NBT。 |
| scene_read | 读取建筑对象图及不可变版本快照，校验文件哈希；不推定已审阅或已批准。 |
| scene_update | 预览已有对象、纹样或关系锁的修改，按依赖联动重算，验证接触与原约束；返回实际方块差分及候选，或可定位的冲突。候选须另用scene_save保存。 |
| mount_batch | 从一次绑定的完整源顺序规划最多64次安装，不反复落盘；整体复核覆盖、总预算、最终背衬、净空和路线后原子返回候选，不写入或批准。 |
| surface_decorate | 保留宿主配方与批量饰面参数，在内存中重新编译嵌纹构件；支持工作区纹样资产绑定，可作为对象图配方，不烘焙掉纹样来源。 |
| pattern_repeat_detect | 在哈希绑定的拉正图中，用线性二维 FFT 和空间域复核找出矩形基本单元。输出周期、有效像素对、单元来源或失败原因。 |
| pattern_filter | 读取带图像SHA的纹样资产，用实数FFT或空间滤波生成新的灰度资产；支持低通、高通和双尺度带通。auto对小核/高斯采用空间或可分离算法，对较大非分离圆盘核估算FFT；不加速体素匹配或通路搜索，不自动应用到建筑。 |
| tracery_compile | 生成真实透空拱窗、成对分栏拱、圆窗与可选分区玻璃；不生成不透明背板。 |
| vault_compile | 按共享拱曲面生成半格券顶、真实递进凹格及相连对角肋架；参数与源图绑定保留。 |
| bay_compile | 由统一跨宽、跨深、起拱和拱高联动柱、连续拱套、墙窗、曲面凹格与多色齐平地砖。 |
| compute_info | 检查CPU/CuPy CUDA后端，执行真实设备探测；不安装依赖、不修改模型。 |
| surface_fit | 从带 UV 的三维样点和/或四条锁定边界拟合张量积 Bézier 曲面，返回控制网格与样点误差。 |
| surface_compile | 将 Bézier 控制网格体素化成可预览和装配的曲面壳体，返回结构 spec、离散误差上界与方块连通数据。 |
| field_compile | 在显式画布采样有界体场图；支持CSG、超椭球、gyroid及组合扭转/弯曲/渐缩/剪切/波浪/仿射，CPU/GPU返回纯候选。 |
| pattern_warp | 对绑定纹样进行逆采样透视/旋涡/波浪/放射重复，保留RGBA配色、创建独立资产；不修改原图，变换后须重新拟合和检查拓扑。 |
| facade_compile | 生成凹窗与层带立面候选。可指定跨数，或按净面宽和固定门洞排窗并保留转角柱。返回局部开口坐标，支持建筑方案、对象图和完整工作模型。 |


## 外部 Agent 机器接口

`machine --schema` 返回 tool-catalog.json 的 machine_protocol 契约；`machine --request <JSON>` 使用统一请求与错误封装。任务领取、超时重领、幂等重试和批注独立接口见 [机器接口说明](agent-protocol.md)。
