# NBTCreator 桌面与外部 Agent

应用、CLI 和工作区 Skill 共用 tool-catalog.json 及 Python 引擎。外部 Agent 读取当前项目 `.agents/skills/nbtcreator-workspace/SKILL.md`，按用户在 AI 助手中选择的知识路由工作。默认工作区是调用者项目根目录，资产位于 nbt_models，无需启动 Electron。普通文件式 Agent 不一定自动发现 Skill，提示词应明确写出入口。

## 从提示词开始

首次创建时，给 Agent 建筑用途、风格、形状或活动空间要求；提示词工作台可以补齐设计草稿。Agent 按 Skill 的适用阅读路由设计完整主模型，使用 Python API/工具落盘并出整体、入口和节点图，完成技术与视觉初稿检查。初稿生成不需要 refine approve；用户看图之后的进一步精修另走 refinement 流程。

已有模型先用 control inspect 检查完整源、坐标配置和当前版本；已有标注使用 [评论扫描/收集](agent-feedback.md)，校验源和证据，解释实际要改的构件范围。

```powershell
mise run nbt -- capabilities
mise run nbt -- paths
mise run nbt -- feedback scan --workspace .
mise run nbt -- feedback collect --version nbt_models/形状/中文名/版本 --output nbt_models/_tasks/意见核查_新编号
mise run nbt -- model --help
mise run nbt -- render --help
```

需要写任务生成器时，用 paths 查询当前 scripts 模块路径和工具版本，无需读包装器或猜旧目录；首次创建的非标准独立门洞由 nbt_openings.open_declared_openings 处理，见 toolkit。不修改冻结引擎或历史示例来批量换皮。NBTCreator 开发项目也可通过 node scripts/cli.mjs 调用同一实现。

control plan/preview 输出候选计划/展示快照；refine prepare 创建审阅资料；真实确认之后才 approve/apply。用户明确导出已看过的网页效果另走 convert，两者不混用。

`mise run nbt -- validate --request <参数JSON> --snapshot <preview/after.json> --output <新目录>` 与应用的“检查当前效果”使用同一候选校验。它按实际制作阶段复算并检查快照、保护、预算和几何，另存报告。

完整建筑的通路检查需要实际 `start` 和非空 `targets`。要求密闭时还需 `interior_probes`，且独立模式必须声明 `openings`，无洞口时用 `[]`。无需密闭且项目允许无声明洞口时，可省略 `openings`。策略为 `required` 时至少声明一个实际洞口。SAODG 接入使用 `ports`。详见[分项验收](validation-workflow.md#独立建筑的显式上下文)。

## 文件与共用交接

应用生成的计划与审阅目录在当前结构版本的 `Agent交接/plan-*`、`Agent交接/review-*`。交给 Agent 的 Markdown 包含源哈希、参数、计划、配置和意见位置；旧建筑根的审阅目录仍可发现，但内容必须匹配源/配置/确认哈希。

下一版建筑保存在同一建筑下的新版本目录。新标注 JSON、旁边的 `.evidence.json` 和 `评论索引.json` 都写入被标注版本的 `修改意见/`，归档证据位于其 `证据/` 子目录。建筑根目录用于兼容读取旧标注。首次修改旧标注时，更新后的记录及证据索引写入对应版本，旧文件原样保留。详见[标注归档](agent-feedback.md#归档与迁移)。

工作区 `.nbtcreator` 包含 skill-exposure、internal-ai、preferences、runtimes 及渲染环境绑定，不能当旧缓存整删。相对实现、知识文件和资产可随工作区移动；共享渲染环境可能位于应用/便携包中，移机后按 rendering.md 检查或重新同步。

## 运行环境和边界

源码开发需要 Python、NumPy、Pillow 和相应 Node/浏览器环境。完整 portable ZIP 带运行时；小型 app-update ZIP 依赖匹配的运行时，单独一个 EXE 不等于完整 portable 包。工作区 facade 使用运行它的 Python。批量渲染使用共享依赖绑定或独立 skill 锁定安装，详见 [渲染](rendering.md)。

内部 AI 的 API、workflow/rules/资料库独立于对外 Skill 配置。API 可辅助完整设计草稿或返回相对坐标的小型部件，由本地脚本验证/插入/预览；它不获得任意代码执行能力，也不取代 Agent 完整初稿和精修验收。截图是否发送按相应工作流显式配置，密钥不随工作区或发布包分发。

任务服务与 CLI 尚无统一跨进程写锁及持久化任务队列，不同时写出同一建筑。技术、设计、游戏运行、49布局和多人验收分别报告，工具通过不代替真实看图或游戏验证。

## 内部 AI 请求提速与严格输出

连接配置、工作流配置及创作偏好独立读取时并行处理；参考文档每批最多4个并行读取。长资料按本次要求在本地选取片段，单篇最多4000字、正文总预算12000字，保留开头与相关段落并标记省略和原始行号；正文仅在装入该次文档份额时保持完整，工作流规则和补充要求独立于正文预算。显式检索集合继续按原哈希验证并发送用户选定片段，不再二次裁剪。这不改变外部 Agent 的完整阅读要求。

“详细请求配置与 JSON”中可启用严格结构化输出（strictSchema）；需要兼容接口和模型支持 response_format.json_schema。当前 DeepSeek Chat Completions 只支持普通 JSON 模式，选择 DeepSeek 时不能启用严格 Schema。旧配置默认关闭；不支持 Schema 的接口会明确报错，不自动降级重试。文字编写仍输出正文。

严格模式由同一份 Schema约束服务端生成与本地接收：summary最多160字，小构件最多48步、截断精简重试最多24步，独立构件最多48步，选区编辑最多32步，完整方案最多64步，控件增量最多16项。可选字段以null表示不修改，本地移除后交给原校验；换材映射在线路中用key/value列表表达，本地恢复为映射。几何和工具 Schema从共用目录模板生成；模板未涵盖的高级参数可使用普通JSON模式。Schema仍不能取代合法状态、源哈希、保护、预算、实际预览或显式导出。

严格输出有额外Schema输入成本，减少格式失败和冗长输出不等于保证整体生成更快；应结合请求字节数、令牌数、重试与总耗时比较。未进行真实供应商调用时，不据此宣称提速比例。
