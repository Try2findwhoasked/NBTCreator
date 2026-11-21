# API 与 Skill 集成

本文说明当前软件的连接配置和集成边界。旧版 API 联调结果保存在[历史归档](../archive/README.md)；工作流资料和高级返回协议见[内部 AI 与对外 Skill](INTERNAL_AI.md)。

## 配置连接与知识

在“AI 助手”的内部 API 页面配置连接。API 默认关闭，普通浏览、CLI、建模工具、标注和导出均可离线使用。

1. 选择 DeepSeek 预设或兼容 Chat Completions 的服务。
2. 填写 API 根地址、模型 ID 和 Key，启用并保存。使用 HTTPS；本机地址可用 HTTP。程序在根地址后追加 `/models` 或 `/chat/completions`，兼容服务可能需要在根地址包含 `/v1`。
3. 点击“测试连接 / 获取模型”查询实际可用模型，也可手动填写模型 ID。保存配置或打开设置页本身不发送请求。
4. 切换到提示词方案、模型编辑或资产管理执行生成；各入口使用对应工作流。

Electron 主进程通过 safeStorage 异步加密 Key，保存在 Windows 当前用户配置目录的 `api-settings.json` 中。界面保存后清空 Key 输入框，只获取 `hasKey` 状态。服务来源不变时留空保留旧 Key；更换来源且不填新 Key 时清除旧 Key；“删除 Key”可显式删除。配置损坏时恢复为 API 关闭，不影响离线操作。加密不保证同一 Windows 用户下的其他程序绝对无法访问。

可连接无需 Key 的本机服务；应用不会自动寻找环境变量或其他应用中的凭据。API Key 不写入工作区、模型、Skill 或发行包。

对外 Skill 知识组与内部 API 资料独立配置。对外可导入 UTF-8 Markdown/TXT，单份最多 2 MiB、每次最多 32 份、总计最多 100 项，复制到工作区 `.nbtcreator/knowledge/` 并加入生成入口的相对链接。切换工作区时保留目标已有配置。关闭资料不删除原文，也不会自动上传为远程知识库。内部资料的限制和发送方式见[内部 AI](INTERNAL_AI.md)。

## 任务与返回结果

| 入口 / 模式 | 结果与处理 |
| --- | --- |
| 文字编写 `prompt` | 返回可编辑、复制或下载的设计正文，不执行工具 |
| 提示词方案 `workbench / brief` | 编写建筑对象、空间关系和设计约束，返回 `project_patch`；不生成具体工具步骤，不运行 Python 几何预检 |
| 高级控件与初稿 `workbench / controls`、`draft` | 返回合法设计字段、完整工具序列或已有步骤增量；高级初稿保留初始工具步骤要求 |
| 局部编辑 `structure` | 返回受限 `settings_patch`，用户采用后由本地引擎生成候选 |
| 小型结构 `small_structure` | 返回选区相对坐标的构件操作，经过归一化、检查和局部放置 |
| 选区自然语言编辑 `selection_edit` | 读取真实选区方块，生成可逐步审阅的命名操作 |
| 资产管理独立结构 `component` | 不依赖当前建筑，按指定尺寸与哈希绑定的参考资产生成、预览，再显式入库 |

默认提示词流程为“编写设计要求 → 人工审阅 → 确认并交接”。具体工具和脚本由接收任务的 Agent 读取真实模型、标注与接口后编写；高级工具提案仍可单独使用。详见[首次创作](../guides/PROMPT_CREATION.md)。

AI 不得改变源/输出路径、阶段、保护上下文、预算、批准或已有源模型尺寸。不接受任意 Python/shell、未开放的工具和执行字段。建模候选检查格式、工具、坐标、方块状态、保护和预算；需要几何预检时由共享 Python 引擎执行。JSON 模式不能替代完整规则校验。

源、选区或参数改变会使旧候选失效。采用方案、生成预览、保存资产和手动导出 NBT 分阶段执行；实际看图、通路与游戏验收、精修批准仍分别处理。

## 发送范围

请求发送本次要求和对应工作流的上下文。普通局部任务使用尺寸、选区和最多 32 种材质摘要；选区编辑会发送实际选区的材质表与压缩方块数据。独立结构可附带引用资产的精简元数据，由本地引擎解析完整资产。

所选内部规则、按总计 12000 字符和每篇 4000 字符预算选取的默认正文，以及显式开启的视口截图会发送给当前服务。显式选择参考集合时，集合中的获准片段替代默认正文；截图要求模型支持图像。未选资料、对外 Skill 的知识组、本地路径、完整源模型和批准记录不会自动附加。用户手写进输入框的路径或私人文字仍会随请求发送。任务记录保留要求、结果摘要和测量数据，不保存 Key、认证头或截图 base64。

## 并发、超时与重试

连接默认允许 2 个并发生成，可配置为 1～4 个。每个请求有独立编号、超时和取消信号；同一建筑的采用与预览仍依次执行。请求超时默认 90 秒，可配置为 5～300 秒。

资料准备最多并行 2 项。入队时固定工作流、创作偏好与所选文档版本，取得名额后才读取大段文档和检索集合；排队期间资料变化会拒绝旧快照。切换工作区取消旧请求、等待结束并拒绝迟到结果，不将旧候选写入新工作区。

返回内容超限、格式错误或本地校验失败时，会反馈错误请求修正，总共最多 3 次；长度截断最多精简重试 1 次。网络和鉴权错误不触发格式重试，可随时取消。残缺或歧义结果不直接应用；服务报告达到令牌上限时，完整且通过校验的 JSON，或明确闭合的最终文字结果仍可使用。

默认最终结果不设应用字数限制；可配置为 100～60000 个 Unicode 字符，0 表示关闭。文字默认 6144 输出令牌，结构/控件默认 12288，手动请求参数优先。关闭字数限制仍受本地最终结果 12 万 UTF-16 码元及总响应 2 MiB 上限约束。参数和增量返回细节见[内部 AI](INTERNAL_AI.md)。

任务记录分别保留 `capture_ms`、`context_prepare_ms`、`queue_ms`、`validation_ms` 等测量。阶段可能重叠，不能简单相加当作总耗时。共享 Python 进程的取消、空闲退出与切换清理见[建模会话](../../.agents/skills/minecraft-nbt-modeler/references/parametric-components.md#建模会话与结果复用)。

## 外部 Agent 接口

在创作项目根目录使用生成的 Skill，CLI 不要求启动 Electron：

```powershell
mise run nbt -- machine --schema
mise run nbt -- paths
```

`machine --request <JSON>` 提供版本化契约与统一错误封装。用 `prompts.get` 的 `compact` 视图按需读取任务，或用 `task-client` 查看、领取、续租和回传指定任务。任务登记与用户批准保持独立。参见[机器接口](../../.agents/skills/minecraft-nbt-modeler/references/agent-protocol.md)。

建筑对象可通过 `scene_compile / scene_read / scene_update` 编译与修改，再显式 `scene_save` 保存新图谱。图谱绑定父版本、保护、留白、路线和预算，不自动识别手工 SNBT 对象，也不直接修改当前建筑或导出定稿。详见[建筑对象图](../../.agents/skills/minecraft-nbt-modeler/references/object-scenes.md)。

## 验证入口

从软件源码根目录执行：

```powershell
mise run test -- api
mise run build:web
mise run test -- api-desktop
mise run test -- ai-batch
mise run test -- agent-protocol
```

这些入口覆盖默认关闭、加密配置、最小上下文、受限操作、过期候选、取消与有界并发、工作区切换和机器任务回执。桌面检查使用本机模拟 HTTP 接口及真实 Electron/Python 引擎；通过不代表真实供应商兼容性或生成质量已经验收。

实现依据：[API 服务](../../desktop/api-service.cjs)、[请求参数校验](../../desktop/api-options.cjs)、[工作台契约](../../desktop/workbench-contract.cjs)。外部协议参考：[DeepSeek JSON 输出](https://api-docs.deepseek.com/guides/json_mode/)、[模型列表](https://api-docs.deepseek.com/api/list-models/)、[Electron safeStorage](https://www.electronjs.org/docs/latest/api/safe-storage)。

返回[文档导航](../README.md)。
