# 历史归档

这里保留迁移、发布、验证及分支交接的原始记录。文中的版本、命令、路径、通过数量和未完成项描述当时状态；证据可能只保存在原机器的 `build/` 或 `dist/` 中，不随源码提供，也不能作为当前版本已通过验收的证明。

当前操作说明见[文档导航](../README.md)，当前问题状态见[已知问题](../KNOWN_ISSUES.md)。归档按原始版本或日期命名，整理目录不改写历史测试结论。

## 发布记录

| 版本 | 记录 |
| --- | --- |
| 5.0.1 | [梁架局部匹配、重复纹样与檐底移植](releases/RELEASE_5.0.1.md) |
| 4.3.0 | [外部 Agent 知识检索与 AI 提示词编辑](releases/RELEASE_4.3.0.md) |
| 4.2.0 | [知识检索、建模与 Agent 版本校验](releases/RELEASE_4.2.0.md) |
| 4.1.0 | [编辑会话与发布冲突恢复](releases/RELEASE_4.1.0.md) |
| 4.0.0 | [项目约束、建模工作台与外部 Agent](releases/RELEASE_4.0.0.md) |
| 3.3.0 | [统一素材库与模块化构件](releases/RELEASE_3.3.0.md) |
| 3.2.0 | [活动路线、参考图构造与审阅位置](releases/RELEASE_3.2.0.md) |
| 3.1.0 | [可执行建筑方案、提示词改写与 AI 输出](releases/RELEASE_3.1.0.md) |
| 2.0.0 | [建筑师工作区、SNBT 制作版与版本历史](releases/RELEASE_2.0.md) |
| 1.11.0 | [共用建模、标注、候选检查与交付](releases/RELEASE_1.11.0.md) |
| 1.0.0 | [初次版本快照（2026-11-02）](releases/RELEASE_1.0.0_2026-11-02.md) |

本目录只收录仓库已有的发布说明，不代表完整版本列表或最新发行版。当前源码版本以 [package.json](../../package.json) 为准。

## 验证记录

| 版本 / 范围 | 日期 | 记录 |
| --- | --- | --- |
| 1.20 资产流程 | 2026-11-05 | [资产与效果完整流程](validation/VALIDATION_1.20_ASSET_FLOW_2026-11-05.md) |
| 1.20 共用配置 | 2026-11-05 | [共用配方与操作状态](validation/VALIDATION_1.20_SHARED_CONFIGURATION_2026-11-05.md) |
| 1.10.0 | 2026-11-03 | [工作区配置、版本内方案与完整设置](validation/VALIDATION_1.10.0_2026-11-03.md) |
| 1.9.0 | 2026-11-03 | [设置与更新入口](validation/VALIDATION_1.9.0_2026-11-03.md) |
| 1.8.0 | 2026-11-03 | [AI 构建工作流与交互](validation/VALIDATION_1.8.0_2026-11-03.md) |
| 1.7.1 | 2026-11-02 | [部件容错与 3D 旋转](validation/VALIDATION_1.7.1_2026-11-02.md) |
| 1.7.0 | 2026-11-02 | [知识库、局部坐标与分离发行包](validation/VALIDATION_1.7.0_2026-11-02.md) |
| 1.6.0 | 2026-11-02 | [内部 AI 与对外 Skill 分离](validation/VALIDATION_1.6.0_2026-11-02.md) |
| 1.5.0 | 2026-11-02 | [Portable 与 3D AI 放置](validation/VALIDATION_1.5.0_2026-11-02.md) |
| 1.4.0 | 2026-11-02 | [首次创建方案与 AI 小型结构](validation/VALIDATION_1.4.0_2026-11-02.md) |
| 1.3.0 | 2026-11-02 | [单栏导航与 Agent 交接](validation/VALIDATION_1.3.0_2026-11-02.md) |
| 1.2.2 | 2026-11-02 | [通俗帮助与 Agent 精修文案](validation/VALIDATION_1.2.2_2026-11-02.md) |
| 1.2.1 | 2026-11-02 | [评论与提示词布局](validation/VALIDATION_1.2.1_2026-11-02.md) |
| 1.2.0 | 2026-11-02 | [工作区交互与 AI 配置表单](validation/VALIDATION_1.2.0_2026-11-02.md) |
| 1.1.0 | 2026-11-02 | [生产前端迁移](validation/VALIDATION_1.1.0_2026-11-02.md) |
| 0.3.0 | 2026-11-02 | [共用接口与工作区配置](validation/VALIDATION_0.3.0_2026-11-02.md) |
| 0.2.1 | 2026-11-02 | [提示词联调](validation/VALIDATION_0.2.1_2026-11-02.md) |
| 0.2.0 | 2026-11-02 | [可选 API 与界面](validation/VALIDATION_0.2.0_2026-11-02.md) |
| 0.1.0 | 2026-11-02 | [初始迁移](validation/VALIDATION_2026-11-02.md) |

## 审计与交接

| 记录 | 范围 |
| --- | --- |
| [分支合并核对（2026-11-04）](reviews/BRANCH_AUDIT_2026-11-04.md) | 分支提交、主线整合与后续处理 |
| [结构 Agent 分支交接（2026-11-04）](reviews/STRUCTURE_AGENT_REVIEW.md) | 实现行为、专项验证与界面整合 |
| [外部 Skill 与 Agent 验收（2026-11-03）](reviews/AGENT_SKILL_ACCEPTANCE_2026-11-03.md) | 真实建筑复验、独立前向测试与评论交接 |

## 迁移记录

[初始迁移记录（2026-11-02）](MIGRATION.md)说明从 SAODG 快照到独立 Electron 项目的初期边界及后续方向。冻结原始资料仍位于仓库 `references/`，与这里的历史说明分开管理。
