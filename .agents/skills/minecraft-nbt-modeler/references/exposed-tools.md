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

GUI的“建模工具”支持同样的有序operations。Agent使用control plan/preview或原refine流程调用，旧的专用API保持兼容。计划、预览、应用、导出和精修确认是不同阶段；能力清单不授予任何批准。

统一入口：`node scripts/cli.mjs capabilities`；独立复制skill后使用 `python <skill>/scripts/nbt_capabilities.py`。各命令参数请用 --help 查询。

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

工作区入口为 `python .agents/skills/nbtcreator-workspace/nbt.py <命令>`。`feedback scan` 扫描结构版本的评论索引，`feedback collect/archive` 校验或归档意见证据，详见 [Agent读取意见](agent-feedback.md)。
