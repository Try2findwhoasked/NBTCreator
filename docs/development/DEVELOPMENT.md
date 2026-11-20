# 开发指南

本文面向 NBTCreator 软件维护。所有命令从仓库根目录执行。制作建筑时应使用独立创作项目，按[共享工作区](../guides/SHARED_WORKSPACE.md)接入，避免在软件目录生成创作 Skill 或正式建筑。

## 环境与依赖

需要 mise、Node.js 24 和 Python。仓库声明的 Node 最低版本见 [package.json](../../package.json)，CI 使用 Node.js 24 / Python 3.14；Python 依赖见 [requirements.txt](../../.agents/skills/minecraft-nbt-modeler/requirements.txt)。便携包内置的 mise 另由 [portable-runtime.json](../../config/portable-runtime.json)锁定。

先查看仓库及父目录的 mise 配置，确认任务、钩子和脚本后执行：

```powershell
mise tasks ls
mise install
mise exec -- node --version
mise exec -- python --version
mise exec -- npm ci
mise exec -- npm ci --prefix .agents/skills/minecraft-nbt-modeler/assets/viewer
mise exec -- python -m pip install -r .agents/skills/minecraft-nbt-modeler/requirements.txt
```

当前 [mise.toml](../../mise.toml)固定 Python 3.14.7，并提供 CPU、GPU、主模型、资产及 UI 测试任务；`mise install` 准备已声明的工具。Node.js 24 仍使用可用环境。`mise exec` 不依赖交互式 shell 的自动激活。

沿用 npm 和两份 package-lock.json，不混用包管理器。个人环境配置写入已被 Git 忽略的 `mise.local.toml`，不要提交密钥。普通离线编辑和自动化测试无需配置外部 AI 服务。

## 启动与命令行

```powershell
mise run dev
```

`mise run dev` 先构建生产前端，再启动桌面。使用 Vite 开发服务时运行 `mise run dev:vite`。只构建前端可运行 `mise run build:web`。开始前端测试前按需要完成构建。修改源码后先关闭测试实例，再重建前端，避免运行中的实例继续请求旧哈希资源。

无界面 CLI 与 UI 使用相同的活动 Python 引擎，可直接查看能力，不需要启动 Electron：

```powershell
mise run nbt -- capabilities --routes
mise run nbt -- --help
```

需要操作创作项目时显式传入 `--workspace`，不要把源码根目录当作资产目录：

```powershell
mise run nbt -- --workspace "D:\MyMinecraftProject" capabilities --routes
```

## 工具入口图

```text
mise run
├─ nbt -- <命令>           创作工具和机器接口，--help 列出全部命令
├─ dev / dev:vite          启动源码桌面
├─ doctor / check          环境检查与静态校验
├─ test -- <套件>          运行现有回归，--list 列出套件名
├─ build:web / package:portable   前端构建和便携打包
├─ tools:sync / patterns:check     更新工具目录、校验图样数据
├─ assets:* / knowledge:* / gpu:*  按职责管理数据或运行基准
└─ migrate:constraints -- <动作>   约束房间迁移的 plan、apply 和 verify
```

从创作项目根目录运行生成入口时，`mise run nbt -- task --id <编号>` 可直接读取已交接的提示词任务。执行其他维护脚本时用 `mise exec -- <解释器> <脚本>` 并明确参数。脚本内部继续复用原有 npm、Node 和 Python 入口。独立的 SAODG 兼容工作台按自己的说明启动。[兼容工作台](../../tools/structures/workbench/README.md)

## 验证入口

按改动范围选择已有检查；只有文档变更时检查链接、命令与差异，无需运行全部桌面回归。测试通过只证明其覆盖的流程，不替代真实看图、用户批准或游戏内验收。

| 范围 | 从源码根目录执行 |
| --- | --- |
| 环境依赖 | `mise run doctor` |
| 工具目录、Skill 自检和冻结迁移资料 | `mise run check` |
| API 与本地协议 | `mise run test -- api` |
| 工作区入口与迁移契约 | `mise run test -- workspace` |
| 书库、收藏和网页引用 | `mise run test -- retrieval` |
| 桌面冒烟 | 先 `mise run build:web`，再 `mise run test -- desktop` |
| 工作台旅程、焦点、真实交付与六页窗口/缩放矩阵 | `mise run ui:test` |
| 更新检查、下载校验与失败重试（本地模拟） | `mise run test -- updates` |
| CPU 批量写入与严格校验 | `mise run cpu:test` |
| 完整主模型、对象关系与接口 | `mise run model:test` |
| 实际主模型预览 | `mise run test -- model-preview` |
| 外部 Agent 机器接口 | `mise run test -- agent-protocol` |
| Agent 离线模拟全流程 | `mise run test -- agent-simulation` |

`mise run test -- --list` 从 [package.json](../../package.json) 的测试脚本读取套件名。专项任务以 [mise.toml](../../mise.toml) 为准。测试分层、单文件运行和前置条件见[测试导航](../../tests/README.md)。修改 `tool-catalog.json` 后先运行 `mise run tools:sync`，再运行 `mise run check`。

桌面自动测试使用隔离的合成工作区，窗口默认最小化，不触发已记录的全屏问题。真实 API 检查会使用指定连接并产生实际请求，入口和边界见[使用指南](../guides/USER_GUIDE.md#ai-与-agent-协作)；常规自动测试使用本机模拟服务。

## 构建与验收

```powershell
mise run package:portable -- --directory-only --out dist/full-folder
mise run test -- portable --directory dist/full-folder
```

`--directory-only` 生成完整免安装目录，不制作 ZIP；省略该参数会生成完整包、应用更新包和运行环境包。完整打包可能下载锁定的运行环境。发布流程见[构建与发布](CI_CD.md)，全流程证据要求见[产品验收](PRODUCT_ACCEPTANCE.md)。可执行文件生成成功不等于运行环境或产品验收通过。

## 可选 GPU

```powershell
mise run gpu:setup
mise run gpu:info
mise run gpu:test
mise run gpu:benchmark
```

GPU 任务将可选 NVIDIA 计算环境安装到 `build/gpu-env`；CPU 路径不要求下载 CUDA 组件。计算后端与变换限制见[计算与变换](../../.agents/skills/minecraft-nbt-modeler/references/compute-transforms.md)，完整主模型接口见[工作模型](../../.agents/skills/minecraft-nbt-modeler/references/working-model.md)。

## 主要目录与边界

| 目录或入口 | 职责 |
| --- | --- |
| `desktop/` | Electron 生命周期、受限 preload 桥与本地 worker；Python/NumPy 不进入主线程或 renderer |
| `.agents/skills/minecraft-nbt-modeler/` | 活动 Python 引擎、前端和可移植 Skill 实现 |
| `scripts/cli.mjs` | 可独立运行的统一 CLI |
| `config/`、`scripts/`、`tests/` | 构建与运行约定、维护入口和回归检查 |
| `docs/` | 使用指南、开发维护文档与历史记录 |
| `references/` | 冻结迁移快照及清单，保持原字节不变 |
| `tools/structures/workbench/` | 导入的 SAODG 兼容组件，模组管理不作为通用功能暴露 |
| `build/`、`dist/` | 测试证据、缓存和构建产物，不提交临时内容 |

维护时保留 Host/Origin 检查、sandbox/contextIsolation、源哈希绑定、真实缩略图确认和独立的手动导出流程。不修改原 SAODG 工作区，不把用户资产、凭据或创作目录打包进应用。

返回[文档导航](../README.md)。
