# NBTCreator 0.3.0 · 共用接口与工作区配置

## 已完成

- 工具定义以实现skill内的tool-catalog.json为单一源；CLI读取命令映射，Python检查18个kind与实际refine支持集合一致，应用建模工具页与提示词页使用生成的同目录清单。打包前强制check:tools。
- 模型编辑新增“建模工具”页，可将共享operations序列交给原计划、预览和新版本转换管道；不是只展示名称。
- AI助手仅保留API/AI相关配置，右侧为Skill暴露配置。提示词生成在提示词方案，结构生成在模型编辑的AI建模页。
- 每工作区 `.nbtcreator/skill-exposure.json` 选择知识组，生成 `.agents/skills/nbtcreator-workspace/SKILL.md` 和nbt.py无界面入口；核心约束保留。选择是Agent知识路由，不删除资料库、不构成文件访问控制，也不自动向API上传文档。
- Agent调用项目根目录为默认工作区；新请求/参数使用工作区相对路径，建筑描述的master使用描述文件相对路径。旧绝对引用仍可读，跨盘或外部文件保留绝对定位。

## 本机迁移

用户确认当前项目根目录为工作区，已将此前开发版workspace和文档目录默认输出盘点并迁入根目录的nbt_models。

两处旧目录合计只有3个索引缓存文件，没有建筑NBT。文件按哈希复制到 `_migration/legacy_*/preserved-runtime`，旧文件原字节保持，并写入跳转记录。报告位于：

- `nbt_models/_migration/legacy_5f039856cd/migration.json`
- `nbt_models/_migration/legacy_2fe6bc3aed/migration.json`

本机旧工作区设置曾指向嵌套_workspaces，已改为用户确认的项目根目录；原偏好文件另存备份。没有搬动原SAODG建筑库、冻结资料库、活动世界或任何模组资源。

## 检查结果

- 工作区/迁移/相对引用/知识选择合成测试：6个通过。
- 默认根目录选择测试：3个通过。
- API服务测试：8个通过。
- 原细节控制后端：24项通过，`build/shared_control_01/results.json`。
- 原新版本转换：10项通过，`build/relative_revision_01/results.json`。
- 离线提示词页面：8项通过，`build/catalog_ui_01/results.json`。
- 布局：7种组合、140次标签检查通过，`build/shared_layout_02/results.json`。
- 打包版API/知识暴露/工作区联调：19项通过，`build/api-desktop-1793621375259/results.json`。
- 打包版桌面/共享工具实际执行/相对任务文件：11项通过，`build/desktop-1793621382883/results.json`。
- skill本地检查、单源生成一致性及原409文件资料库哈希检查通过。
- 打包内容确认不含根nbt_models、.nbtcreator配置或用户生成的skill入口；这些在各工作区创建，不随应用分发。

模拟API测试没有使用真实DeepSeek凭据。Python仍是外部运行环境；未实现GUI/Agent跨进程写锁、自动合并或自主Agent循环。NBTC-001全屏问题继续仅记录，不宣称已修复。
