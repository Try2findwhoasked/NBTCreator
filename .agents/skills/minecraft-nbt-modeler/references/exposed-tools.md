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

GUI的“建模工具”支持同样的有序operations。每步 enabled 为可选布尔开关，省略等于 true；false 保留在设置/计划中，但编译与执行跳过，不写任何方块。名称由 label 保存，数组顺序决定执行顺序。Agent使用control plan/preview或原refine流程调用，旧的专用API保持兼容。计划、预览、应用、导出和精修确认是不同阶段；能力清单不授予任何批准。

统一入口：`node scripts/cli.mjs capabilities`；独立复制skill后使用 `python <skill>/scripts/nbt_capabilities.py`。各命令参数请用 --help 查询。overwrite/write_group是可选操作元数据，见tool-catalog.json的optional_operation_fields；未提供时保留原工具行为。AI与构件放置的显式覆盖开关不能越过保护和预算。

## 无界面命令

- inspect → scripts/nbt_task.py
- snapshot → scripts/nbt_task.py
- render → scripts/nbt_task.py
- regress → scripts/nbt_task.py
- control → scripts/nbt_detail_control.py
- refine → scripts/nbt_refine.py
- model → scripts/nbt_tools.py
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

工作区入口为 `python .agents/skills/nbtcreator-workspace/nbt.py <命令>`。`feedback scan` 扫描结构版本的评论索引，`feedback collect/archive` 校验或归档意见证据，详见 [Agent读取意见](agent-feedback.md)。

确定性检查的通俗解释与定位见 [检查结果解释](diagnostic-guidance.md)，diagnostics 只解释已保存报告，不重新验证或自动修复；按任务挑选资料片段和复用资产见 [本地参考检索](reference-retrieval.md)，retrieve search/bundle/read 共用来源哈希；选区自然语言工具步骤见 [选区编辑](selection-edit.md)，selection-edit context/compile 共用真实方块摘要、坐标平移与写入范围约束；构件的保存、整理、导入及候选放置见 [构件资产](component-assets.md)；参数化工具序列、材质主题和XYZ网格阵列见 [配方与主题](reusable-recipes.md)，recipes compile与components batch仅返回候选步骤；批量创作的过程目录、模型关联与交付图册见 [制作批次](batch-workspaces.md)，batches create/record/list/get/locate 在应用外也可使用；项目多选、只读批量预览与检查、进度及重试见 [项目批量任务](project-batch.md)；内部 API 与外部 Agent 共用的各区域创作参数见 [AI创作偏好](ai-creative-preferences.md)。

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
