# 资产与效果完整流程核验

本轮针对原生工具效果接入后的实际使用断点，检查 Agent 生成、界面应用、失败恢复、候选校验、手动导出和重新读取。测试使用隔离合成工作区，不修改用户建筑，也不产生用户看图批准。

## 修复

- 界面会把 `andesite` 规范化成 `minecraft:andesite`。候选提交现在以控件恢复后的规范参数比较，避免把有效配置误判为用户修改；失败时可以恢复原参数与原画面。
- Agent 可以只保存面板的部分字段。样例补齐默认值，实际载入保留目标未提供的字段；选区、预算和已有步骤仍保留。
- 切换效果、预览失败、导入失败和回收操作会清理旧画面；重新打开窗口恢复所选效果。延迟到达的关闭事件不会取消新一轮预览。
- 没有选择、没有目标建筑、样例未就绪或效果已回收时，对应按钮禁用。切换回收站不保留另一列表的隐含选择。

## 结果

| 检查 | 实际证据 |
| --- | --- |
| Agent 保存构件，经 UI 放置、效果处理、失败回退、检查、主动导出、NBT／主模型回读、项目发现和 Agent 读取，9 项 | `build/authoring-journey-1793814469902/results.json` |
| 原生道路配置、真实前后样例、失败清图、重开、候选应用、导入拒绝、回收状态及 Skill 入库，11 项 | `build/tool-effects-1793814459728/results.json` |
| AI 构件放置、整体移动和恢复，17 项 | `build/ai-placement-1793814229594/results.json` |
| 桌面主流程，30 项 | `build/desktop-1793814229879/results.json` |
| 实际 Electron 桥接下的 AI 配置、候选、采用、草稿和 Skill 共用协议，42 项；仅本地模拟 API | `build/api-desktop-1793814320507/results.json` |
| 1600／1360／1100／960 宽度、75%／100%／125%／150% 缩放及管理交互，7 项 | `build/library-layout-1793814340901/results.json` |
| 效果引擎回归，8 项 | `python tests/effect-assets.py` |
| 环境、工具清单、Skill、迁移参考完整性 | `npm run doctor`、`npm run check:tools`、`python .agents/skills/minecraft-nbt-modeler/scripts/check_skill.py`、`npm run verify:archive` 均通过 |

`npm run test:authoring-journey` 可重新运行完整链路。它从外部 Skill 保存真实资产，通过界面明确触发导出，再比较显示候选、导出主模型和结构 NBT 的几何哈希，并核对原文件未改写。测试按钮操作不构成实际用户批准。

## 工作区资料

当前创作工作区的整理索引登记 54 个构件、40 个原生工具效果和 46 个原配方／材质主题。数字目录显示来自旧序号标签；已清理当前库并在浏览旧工作区时隐藏此类标签。原配方的可调参数、资产 ID、几何和整理前备份保留，预览草稿不自动入库。此统计来自工作区资料，不把用户资产随应用分发。

统一索引位于 `nbt_models/asset_library/catalog.json`；原生效果位于 `nbt_models/asset_library/tool_effects/`，批次清单位于 `nbt_models/asset_batches/`，独立效果样例位于 `nbt_models/_workspaces/effect_previews/`。索引是整理时的快照，各资产入口读取实际库。

## 验证边界

这里证明软件链路与参数／几何一致性，不代表任意建筑的审美、游戏内表现或所有外部 API 供应商兼容性已经验收。模型仍需实际看图和适用的游戏检查。正式版本发布的签名、自动更新、系统安装器，以及桌面和 Agent 对同一建筑的全局并发写锁，不在本次资产修复范围内。
