# 本地 MCP 与桌面进程

同一个安装中的桌面和 MCP 调用活动 Python 引擎。stdio 进程启动时固定工作区。MCP 请求和桌面 IPC 均使用固定工具名和结构化参数。

| 现有入口 | 本次迁移 |
| --- | --- |
| `scripts/cli.mjs machine` → `nbt_machine.py` | MCP 通过同一个 Python 入口发现和调用任务、注释和制作工具。请求编号、回执、租约及权限由 Python 管理。 |
| `/__detail__/retrieve/*` → `nbt_knowledge.retrieval` | MCP 调用现有检索 CLI。桌面内部 AI 回读集合走可信主进程客户端。前端检索 HTTP 路由保留到调用方迁移。 |
| `desktop/ai-candidate-validator.cjs` → Python 建模会话 | 桌面通过 MCP 预检，继续使用现有 Python 校验与响应。组件交互依赖的 viewer 会话仍由 viewer 服务持有。 |
| `render` → `nbt_task.py` → `render-batch.mjs` | 共享实纹理出图。从源与机位哈希生成审阅产物，使用带哈希的 URI 读取。 |
| `/__detail__/jobs`、`snapshot`、`asset`、项目登记 | viewer 继续拥有交互编辑任务及快照。前端迁移前需统一源、任务、候选和图像绑定。 |
| 版本历史、编辑工作副本和显式 NBT 导出 | 制作工作包通过现有 machine 临界区写入。桌面现有显式导出流程继续使用原入口。 |
| `desktop/worker.mjs`、静态服务器 | 保持生产资源 HTTP 和来源验证。桌面另外启动工作区绑定的 stdio 服务。 |

## 独立 Agent

解压 Windows x64 Agent ZIP。使用 Node.js 20.19 或更新版和已有的 Python。已验证 Node.js 24、Python 3.14。在解压目录安装 Python 依赖。

```powershell
python -m pip install -r .agents/skills/minecraft-nbt-modeler/requirements.txt
```

需要记录 Git 版本历史的制作操作使用宿主 Git，可用 `NBTCREATOR_GIT` 指定。MCP 与桌面使用安装中的活动引擎。已有工作区 facade 和 `.nbtcreator/runtimes` 冻结入口由原流程维护。若工作包对照的引擎指纹不同，按引擎回执检查工作包是在何处签发的。

在客户端 MCP 配置中指定可执行文件、服务脚本和创作工作区。脚本与工作区均使用绝对路径。可以在服务进程环境中用 `NBTCREATOR_PYTHON` 指定解释器。

```json
{
  "command": "node",
  "args": [
    "D:/Tools/NBTCreator Agent/scripts/mcp/server.mjs",
    "--workspace",
    "D:/Projects/建筑 工作区"
  ]
}
```

Windows 终端可用 `NBTCreator-MCP.cmd --workspace "D:\Projects\建筑 工作区"` 启动同一 stdio 入口。安装内包含预构建前端、默认纹理、Playwright 和锁定 Chromium。运行服务时无需 Electron、Vite 或 npm。

服务通过 `initialize` 协商 MCP 版本，然后接收 `notifications/initialized`。工具以 `tools/list` 所列为准。默认允许查询和生成审阅辅助产物。`--allow-write` 开放 machine 写入，必须提供稳定的 `request_id`。`--package-session` 从宿主指定的 JSON 读取工作包邀请或租约。此时工具列表和每次操作按引擎的工作包权限检查，并仅提供该工作包可用的制作动作。认领后的租约应由宿主写回同一会话文件，凭据通过服务启动配置和机器接口管理。

对于建筑修改任务，调用 `tasks.claim` 后，将任务的 `id`、回执中的 `lease_token` 和 `lease.fence` 一并放入 `model.commit` 的 `task_lease`。提交后用该租约、最新任务修订号以及新制作源和 SHA256 调用 `tasks.record`。已有本地任务会话也可继续传 `task_session`，一次提交只提供其中一种。

超时、取消和进程异常后，写入结果可能需要回读。按 machine 契约查询当前状态，或用相同 `request_id` 和相同参数查询或恢复原来的操作。桌面会在随后收到请求时重启服务，已经发出的请求由调用方处理回执。

## 桌面 renderer

仅当前工作区窗口的可信主 frame 可以调用 `window.nbtDesktop.mcp`。工作区切换关闭旧连接、取消旧调用并启动新连接。

| 接口 | 返回值 |
| --- | --- |
| `status()` | `{ state, generation, protocolVersion?, serviceVersion?, error? }`。状态为 `idle`、`starting`、`ready` 或 `unavailable`。 |
| `onStatus(callback)` | 返回取消订阅函数。启动时同步读取一次 `status()` 可补上窗口导航前的事件。 |
| `listTools()` | 在 `data` 返回当前可用工具的 schema。 |
| `callTool({ requestId, name, arguments })` | 在 `data` 返回结构化结果。`requestId` 用于取消，可使用 UUID。machine 写入另需在 `arguments.request_id` 提供稳定业务编号。 |
| `cancel(requestId)` | 返回本连接是否有该前端请求。 |
| `readArtifact(uri)` | 在 `data` 返回 `{ uri, mimeType, blob? , text? }`。图片是 base64，JSON 是 UTF-8 文本。 |

工具列表、调用和资源接口统一返回 `{ ok, data, error }`。错误字段为 `{ code, message, retryable, details }`。machine 成功回执还带 `protocol_version` 和 `request_id`。启动失败会出现在状态及调用回执中。桌面允许普通模型候选和明确提交制作版的工具，工具是否可用取决于随安装提供的 machine 目录。

`render.model` 接收 `source`、`source_sha256`、`cameras`、`cameras_sha256`，以及可选的 `width`、`height`、`quality`。路径位于工作区 `nbt_models` 中。交付审阅时，将引擎候选物化回执中的源、机位路径和哈希原样传入。成功返回源、几何和机位哈希及 `artifacts[]`。每项含 `uri`、`path`、`name`、`mimeType` 和 `sha256`。`path` 为工作区相对路径，可连同哈希传给已有审阅记录入口。应用通过 `readArtifact(uri)` 读取，独立客户端通过 `resources/read` 读取。图片、元数据和清单可在同一工作区服务重启后按原 URI 回读。制作版、实图观察及最终 NBT 导出继续遵循各自工作流。

当工具列表包含 `model.preview` 时，`render.candidate` 合并物化与出图。调用方先从 `model.candidate({ model })` 得到 `candidate_sha256`，再向 `render.candidate` 传入同一个 `model`、候选指纹、`cameras` 数组、稳定的 `request_id` 和可选的出图设置。结果中的 `preview` 保留候选指纹、模型哈希、源和机位哈希以及 `visual_review: "pending"`。它不创建制作版。调用方可在看图后经已有入口记录观察，明确发起制作版提交。此工具面向桌面及启用 `--allow-write` 的独立 Agent。

## 开发与验证

从仓库根目录运行下列命令。

```powershell
mise run test -- mcp
mise run test -- mcp-desktop
mise run package:agent -- --out dist/agent
mise run ci:package -- dist/portable-local
```

便携包验收在真实 Electron 窗口测试 IPC。Agent 包验收在含空格和中文的安装路径解包，验证 ZIP 和内容哈希，从 Windows 启动器完成握手，并用内置 Chromium 生成、读取和校验实纹理 PNG。[MCP stdio 传输](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
