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
| auto_road | 自动道路铺设 | 起终点Y为路面高度且须相同；straight / x_first / z_first自动生成连续道路，宽1～16、厚1～8，完整路面须在选区内；覆盖已有路面须显式开启，不自动避障。 |
| selection_replace | 连通 / 表面选区换材 | 从seed_position六邻接选取同状态或实体；surface按暴露朝向选面，thickness仅向实体内扩展。保护及预算继续生效。 |
| align_region | 对齐 / 锚点 / 落地吸附 | lo/hi是源包围盒；align按轴min/center/max/keep对齐；anchor指定源和目标全局锚点；ground按destination的XZ和最高搜索Y落地，拒绝不平整或未知支承。归属请显式设置。 |
| array_region | 环形 / 沿路径阵列 | lo/hi为源；source_anchor默认lo。path按折线弧长布置；radial用centre/radius/count/start_angle/sweep_angle。cardinal朝向取最近90°，不支持任意角度状态旋转；位置量化碰撞和预算均预检。 |
| auto_stairs | 半格楼梯 / 坡道 / 平台 | start/end是玩家脚位，end.y必须高于start.y。straight须沿X或Z轴，水平路程L至少2*(end.y-start.y)+2*width+1，给两端平平台留白；放不下时改为明确box阶梯或另设计折返。不能自动清头顶或补支撑；须实际预览通行。 |
| terrain_road | 地形道路 / 避障 / 有限填挖 | A*按真实地表绕开非地形障碍；端点Y为真实地表格。高度差最多1，自动楼梯并逐段通行检查；仅允许列出的地形材质填挖。桥段需显式max_bridge_span，不认证承重。 |
| auto_roof | 屋顶 / 屋脊 / 屋檐 | roof=gable/hip/gambrel/dome/curved_hip。curved_hip 使用 curve_power、eave_lift、corner_lift 调整曲面、起翘与翼角，并连接相邻顶皮。footprint 为XZ角点，eaves 不得超选区。finish=blocks/slabs/stairs。屋面与宿主的梁柱支承、密闭和游戏表现另验。 |

GUI的“建模工具”支持同样的有序operations。每步 enabled 为可选布尔开关，省略等于 true；false 保留在设置/计划中，但编译与执行跳过，不写任何方块。名称由 label 保存，数组顺序决定执行顺序。Agent使用control plan/preview或原refine流程调用，旧的专用API保持兼容。计划、预览、应用、导出和精修确认是不同阶段；能力清单不授予任何批准。

统一入口：`node scripts/cli.mjs capabilities`；独立复制skill后使用 `python <skill>/scripts/nbt_capabilities.py`。各命令参数请用 --help 查询。overwrite/write_group是可选操作元数据，见tool-catalog.json的optional_operation_fields；未提供时保留原工具行为。AI与构件放置的显式覆盖开关不能越过保护和预算。

## 无界面命令

- inspect → scripts/nbt_task.py
- snapshot → scripts/nbt_task.py
- render → scripts/nbt_task.py
- regress → scripts/nbt_task.py
- control → scripts/nbt_detail_control.py
- refine → scripts/nbt_refine.py
- model → scripts/nbt_working_model.py
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
- architect → scripts/nbt_architect.py
- session → scripts/nbt_engine_session.py

工作区入口为 `python .agents/skills/nbtcreator-workspace/nbt.py <命令>`。`feedback scan` 扫描结构版本的评论索引，`feedback collect/archive` 校验或归档意见证据，详见 [Agent读取意见](agent-feedback.md)。

外部Agent改模后的版本登记和评论核对见 [任务回传](agent-task-return.md)，agent-tasks get/record 与应用共用源哈希；确定性检查的通俗解释与定位见 [检查结果解释](diagnostic-guidance.md)，diagnostics 只解释已保存报告，不重新验证或自动修复；按任务挑选资料片段和复用资产见 [本地参考检索](reference-retrieval.md)，retrieve search/bundle/read 共用来源哈希；选区自然语言工具步骤见 [选区编辑](selection-edit.md)，selection-edit context/compile 共用真实方块摘要、坐标平移与写入范围约束；构件的保存、整理、导入及候选放置见 [构件资产](component-assets.md)；参数化工具序列、材质主题和XYZ网格阵列见 [配方与主题](reusable-recipes.md)，recipes compile与components batch仅返回候选步骤；批量创作的过程目录、模型关联与交付图册见 [制作批次](batch-workspaces.md)，batches create/record/list/get/locate 在应用外也可使用；项目多选、只读批量预览与检查、进度及重试见 [项目批量任务](project-batch.md)；内部 API 与外部 Agent 共用的各区域创作参数见 [AI创作偏好](ai-creative-preferences.md)。

## 容易混淆的入口

命令均通过创作工作区入口 `nbt.py` 调用。运行 `nbt.py capabilities --routes` 可单独查询这张表。

### 检查

| 任务 | 调用或字段 | 输入 | 结果 |
| --- | --- | --- | --- |
| 校验候选快照 | `validate --request <请求JSON> --snapshot <候选快照> --output <新检查目录>` | 同一次 control preview 的原始编辑请求与回执的 result.snapshot（after.json）。 | 写 validation.json，检查源绑定、实际改动、保护和几何。以 result.passed 判定是否通过。 |
| 复验已保存的制作源 | `model --request <请求JSON>` | JSON 填 source、source_sha256 和 validate:true。路径与哈希从保存回执 result.saved 取。 | 返回 result.validation。只检查时省略 actions 和 save_draft。 |
| 复验建筑及绑定方案 | `architect plan-check --request <请求JSON>` | JSON 填绑定过建筑方案的 source 和 source_sha256。 | 返回 validation、绑定方案和 plan_sha256。 |
| 查询制作源是否可编辑 | `control inspect --source <制作源>` | 现有制作源路径。 | result.editing_ready 表示是否具备编辑条件，context_readiness 给出上下文缺失或失配的原因。 |

### 构件

| 任务 | 调用或字段 | 输入 | 结果 |
| --- | --- | --- | --- |
| 预检方案中的单个构件 | `architect part-preflight --request <请求JSON>` | JSON 填 plan 或 plan_id，以及要检查的 part。用 capabilities --architect-action part-preflight 查参数。 | 编译指定构件，返回方块状态支持和接口问题。整栋装配与宿主验证由 plan-build 执行。 |
| 填写结构配方 | `recipe.tool = "structure"` | 填写建筑方案的 parts[].recipe 或主模型 install 的 recipe。capabilities --recipe structure 返回配方示例。 | 配方由调用方编译为构件体素，用于组装。 |
| 生成独立构件候选预览 | `components agent --tool structure_preview --request <请求JSON>` | JSON 的 spec 填构件规格。capabilities --agent-tool structure_preview 返回可运行的请求示例。 | 写临时候选快照与缩略图。安装和入库各有独立入口。 |
| 创建纹样并取得拟合输入 | `components agent --tool pattern_create --request <请求JSON>` | 用 capabilities --agent-tool pattern_create 查小位图或图层配方参数。 | 保存纹样资产，result.fitting_input 可直接合入 pattern_microfit 请求。用 pattern_assets 的 action:get 和 result.id 回查。 |

### 看图与交付

| 任务 | 调用或字段 | 输入 | 结果 |
| --- | --- | --- | --- |
| 准备建筑审阅 | `architect review-prepare --request <请求JSON>` | JSON 填 source、source_sha256 和新的 output 目录。补拍可用 view_overrides 按原 ID 替换失败机位。 | 复验保存源并写审阅包及相机。运行回执的 render_command 出图。 |
| 渲染实际图片 | `render --source <制作源> --cameras <相机JSON> --output <新目录>` | 提供制作源与相机。渲染候选时使用 --snapshot 与相机。 | 写 PNG 和 render_manifest.json。先打开实际图像，建筑审阅再登记观察。 |
| 登记建筑看图观察 | `architect review-record --request <请求JSON>` | 审阅包路径及哈希、父修订、渲染清单、实际看图所得 observations 和 issues（无问题填 []）。参数用 capabilities --architect-action review-record 查询。 | 写观察记录，返回覆盖与交付摘要。精修另须用户看过对应图像并明确同意。 |
| 保存可编辑 SNBT | `model --request <请求JSON>` | 在 model 或 architect plan-build 的 JSON 请求中填写 save_draft。 | 保存新 SNBT 制作版，返回 saved.source 与 saved.source_sha256，供复验和出图。 |
| 导出定稿 NBT | `finalize --source <已保存制作源> --source-sha256 <审阅源哈希> --inputs-sha256 <审阅输入哈希>` | 审阅时用 --inspect-inputs 记录源和输入哈希；仅在用户明确要求定稿时导出。无墙的独立建筑须在保存时声明 allow_empty_wall_mask:true。 | 验证并在 nbt_models/_exports/ 写 NBT 完整主模型、分片与交付回执。 |

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
| parametric_list | 查询16类模块、可直接编译的对象配方库、柱式与扶手样式、参数及安装边界；只读。 |
| parametric_compile | 编译参数化模块候选：柱式、外置楼梯扶手、独立栏杆、梁、托架、拱框、门窗框、基座及家具。配方见parametric_list.object_library；不改当前建筑。 |
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
| scene_compile | 按稳定对象ID、尺寸引用和贴附关系编译建筑对象图；检查依赖、实际接触、重叠、保留空间与声明通路，只返回候选。 |
| scene_save | 显式保存对象图和编译快照的新版本；校验候选内容与父版本，保留旧版，不写建筑或定稿NBT。 |
| scene_read | 读取建筑对象图及不可变版本快照，校验文件哈希；不推定已审阅或已批准。 |
| scene_update | 修改已有对象并按依赖联动重算，复验整图，检查原保护区与修改预算；返回候选，须另用scene_save保存新版本。 |
| mount_batch | 从一次绑定的完整源顺序规划最多64次安装，不反复落盘；整体复核覆盖、总预算、最终背衬、净空和路线后原子返回候选，不写入或批准。 |
| surface_decorate | 保留宿主配方与批量饰面参数，在内存中重新编译嵌纹构件；支持工作区纹样资产绑定，可作为对象图配方，不烘焙掉纹样来源。 |
| pattern_filter | 读取带图像SHA的纹样资产，用实数FFT或空间滤波生成新的灰度资产；支持低通、高通和双尺度带通。auto对小核/高斯采用空间或可分离算法，对较大非分离圆盘核估算FFT；不加速体素匹配或通路搜索，不自动应用到建筑。 |
| tracery_compile | 生成真实透空拱窗、成对分栏拱、圆窗与可选分区玻璃；不生成不透明背板。 |
| vault_compile | 按共享拱曲面生成半格券顶、真实递进凹格及相连对角肋架；参数与源图绑定保留。 |
| bay_compile | 由统一跨宽、跨深、起拱和拱高联动柱、连续拱套、墙窗、曲面凹格与多色齐平地砖。 |
| compute_info | 检查CPU/CuPy CUDA后端，执行真实设备探测；不安装依赖、不修改模型。 |
| field_compile | 在显式画布采样有界体场图；支持CSG、超椭球、gyroid及组合扭转/弯曲/渐缩/剪切/波浪/仿射，CPU/GPU返回纯候选。 |
| pattern_warp | 对绑定纹样进行逆采样透视/旋涡/波浪/放射重复，保留RGBA配色、创建独立资产；不修改原图，变换后须重新拟合和检查拓扑。 |
| facade_compile | 生成真实凹窗、窗台与层带的参数化立面候选，返回开口坐标，支持对象图和完整工作模型。 |


## 外部 Agent 机器接口

`machine --schema` 返回 tool-catalog.json 的 machine_protocol 契约；`machine --request <JSON>` 使用统一请求与错误封装。任务领取、超时重领、幂等重试和批注独立接口见 [机器接口说明](agent-protocol.md)。
