# NBTCreator 桌面与外部 Agent

应用、CLI 和工作区 Skill 共用 tool-catalog.json 及 Python 引擎。外部 Agent 读取当前项目 `.agents/skills/nbtcreator-workspace/SKILL.md`，按用户在 AI 助手中选择的知识路由工作。默认工作区是调用者项目根目录，资产位于 nbt_models，无需启动 Electron。普通文件式 Agent 不一定自动发现 Skill，提示词应明确写出入口。

## 从提示词开始

首次创建时，给 Agent 建筑用途、风格、形状或活动空间要求；提示词工作台可以补齐设计草稿。Agent 按 Skill 的适用阅读路由设计完整主模型，使用 Python API/工具落盘并出整体、入口和节点图，完成技术与视觉初稿检查。初稿生成不需要 refine approve；用户看图之后的进一步精修另走 refinement 流程。

已有模型先用 control inspect 检查完整源、坐标配置和当前版本；已有标注使用 [评论扫描/收集](agent-feedback.md)，校验源和证据，解释实际要改的构件范围。

```powershell
python .agents/skills/nbtcreator-workspace/nbt.py capabilities
python .agents/skills/nbtcreator-workspace/nbt.py paths
python .agents/skills/nbtcreator-workspace/nbt.py feedback scan --workspace .
python .agents/skills/nbtcreator-workspace/nbt.py feedback collect --version nbt_models/形状/中文名/版本 --output nbt_models/_tasks/意见核查_新编号
python .agents/skills/nbtcreator-workspace/nbt.py model --help
python .agents/skills/nbtcreator-workspace/nbt.py render --help
```

需要写任务生成器时，用 paths 查询当前 scripts 模块路径和工具版本，无需读包装器或猜旧目录；首次创建的非标准独立门洞由 nbt_openings.open_declared_openings 处理，见 toolkit。不修改冻结引擎或历史示例来批量换皮。NBTCreator 开发项目也可通过 node scripts/cli.mjs 调用同一实现。

control plan/preview 输出候选计划/展示快照；refine prepare 创建审阅资料；真实确认之后才 approve/apply。用户明确导出已看过的网页效果另走 convert，两者不混用。

`nbt.py validate --request <参数JSON> --snapshot <preview/after.json> --output <新目录>` 是与应用“检查当前效果”相同的候选校验；会重新计算参数并绑定实际快照，检查保护、预算和整体几何。通过仍需看图；失败有独立报告，不更改源。缺少start/targets/interior_probes或独立开口声明时先补上下文，不能用空目标获得通过。

## 文件与共用交接

应用生成的计划与审阅目录在当前结构版本的 `Agent交接/plan-*`、`Agent交接/review-*`。交给 Agent 的 Markdown 包含源哈希、参数、计划、配置和意见位置；旧建筑根的审阅目录仍可发现，但内容必须匹配源/配置/确认哈希。

下一版建筑位于同一建筑工作文件夹的新兄弟版本目录，不覆盖旧文件。新评论保存和导出会更新当前版本 `修改意见/评论索引.json`；证据在版本内 `修改意见/证据/`，原意见和可迁移的相对证据索引保留在建筑根修改意见目录。

工作区 `.nbtcreator` 包含 skill-exposure、internal-ai、preferences、runtimes 及渲染环境绑定，不能当旧缓存整删。相对实现、知识文件和资产可随工作区移动；共享渲染环境可能位于应用/便携包中，移机后按 rendering.md 检查或重新同步。

## 运行环境和边界

源码开发需要 Python、NumPy、Pillow 和相应 Node/浏览器环境。完整 portable ZIP 带运行时；小型 app-update ZIP 依赖匹配的运行时，单独一个 EXE 不等于完整 portable 包。工作区 facade 使用运行它的 Python。批量渲染使用共享依赖绑定或独立 skill 锁定安装，详见 [渲染](rendering.md)。

内部 AI 的 API、workflow/rules/资料库独立于对外 Skill 配置。API 可辅助完整设计草稿或返回相对坐标的小型部件，由本地脚本验证/插入/预览；它不获得任意代码执行能力，也不取代 Agent 完整初稿和精修验收。截图是否发送按相应工作流显式配置，密钥不随工作区或发布包分发。

任务服务与 CLI 尚无统一跨进程写锁及持久化任务队列，不同时写出同一建筑。技术、设计、游戏运行、49布局和多人验收分别报告，工具通过不代替真实看图或游戏验证。
