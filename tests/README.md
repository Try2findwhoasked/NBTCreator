# 测试导航

所有命令从 **NBTCreator 仓库根目录**执行，通过 `mise run <task>` 或 `mise exec -- <command>` 启动。环境安装见[开发指南](../docs/development/DEVELOPMENT.md)。

使用 `mise run test -- --list` 列出套件。例如 `mise run test -- workspace` 运行工作区契约，`mise run test -- retrieval` 运行知识库回归。已有 `model:test`、`ui:test` 等专项任务继续可用。

## 目录职责

| 目录 | 放什么 | 执行方式 |
| --- | --- | --- |
| `engine/` | Python 引擎、工作区契约、建模与资产回归；另含明确命名的基准和审计脚本 | 按功能使用 npm / mise 任务，或直接运行指定 Python 文件 |
| `node/` | Node 逻辑、接口与服务回归 | `*.test.cjs`、`*.test.mjs` 使用 `node --test`；其余脚本按下文说明执行 |
| `desktop/` | Electron 旅程、浏览器渲染、生产前端与便携包集成检查 | 前端相关检查先 `build:web`，再执行指定脚本或组合任务 |
| `support/` | 合成模型生成器、HTTP 模拟服务、最小化截图等共享辅助代码 | 由测试导入或调用，不作为独立测试集合运行 |

按执行环境分层，文件继续按功能命名。例如资产库的 Python 回归在 `engine/asset-libraries.py`，桌面流程在 `desktop/unified-assets-desktop.mjs`。使用 `rg --files tests` 搜索同名功能即可查看相关层。

## 常用入口

以下是按功能选择的检查，**每条命令只覆盖其列出的范围**。完整任务定义见 [package.json](../package.json) 和 [mise.toml](../mise.toml)。

| 要验证的内容 | 命令 |
| --- | --- |
| API、AI 本地协议与引擎会话 | `mise run test -- api` |
| 内部 Agent 起草、润色和提示词交接 | `mise run test -- prompt-archive` |
| 桌面冒烟 | `mise run test -- desktop` |
| 工作区契约与路径选择 | `mise run test -- workspace` |
| 可移植引擎合成回归 | `mise run nbt -- regress --output <新目录>` |
| 建模工具与操作参数 | `mise run test -- modelling` |
| 参数化构件与几何回归 | `mise run test -- parametric` |
| 主模型、对象关系与接口 | `mise run model:test` |
| 梁架节奏、同谱异位、约束与显式采用 | `mise run test -- beam-rhythm` |
| 大型组装、四片楼梯冲突、恢复及同机位渲染 | `mise run test -- large-assembly` |
| 三视配准、回投影与匿名审阅绑定 | `mise run test -- reference-views` |
| 曲面实际宿主、分层叠放、纹样、背衬与候选回放 | `mise run test -- curved-surface` |
| 曲面构件切片、来源绑定与离线回放 | `mise run test -- curve-components` |
| 曲面 UV 模板、端部、方向与配方编译 | `mise run test -- curve-stencils` |
| 偏心曲面代表样段、四个材质机位、保护拒绝及审阅绑定 | `mise exec -- python -B tests/engine/curved-surface-review.py` |
| 建筑方案闭环 | `mise run architecture:test` |
| 模块化对象、结构杆件与窗框 | `mise run modular:test` |
| 外部资产库的离线、完整性与回滚 | `mise run assets:test` |
| 外部资产库桌面流程 | `mise run assets:desktop` |
| 工作台旅程、焦点与窗口布局 | `mise run ui:test` |

单独运行一个检查：

```powershell
mise exec -- node --test tests/node/app-settings.test.cjs
mise exec -- python -B tests/engine/roof-curves.py
mise exec -- python -B .agents/skills/minecraft-nbt-modeler/scripts/fixtures/run.py check_collision_fixtures.py --output build/collision-regression.json
mise run build:web
mise exec -- node tests/desktop/default-preview-desktop.mjs
```

`engine/` 沿用原来的文件名和独立运行方式。多数 Python 文件使用连字符命名，不符合默认 `unittest discover` 的 `test*.py` 模式；不要把默认 discovery 的成功当作引擎回归已执行。`test:modelling` 通过 `engine/modelling-suite.py` 显式枚举 `modelling-*.py`。

`node/` 中 `component-move.mjs`、`prompt-creation.mjs` 和 `workspace-resolution.cjs` 也使用 `node --test`；`feedback-evidence.mjs` 是直接执行的断言脚本。`task-cancel.mjs` 会启动真实 Python 工作，需要显式传入尚不存在的输出目录：

```powershell
mise exec -- node tests/node/task-cancel.mjs --output build/task-cancel-check
```

## 特殊前置条件

- 桌面检查使用隔离的合成工作区，窗口默认最小化。保留现有截图辅助代码，不触发已记录的全屏问题。
- `desktop/production-server.mjs` 等生产前端检查需要先构建网页；`desktop/project-performance.mjs` 还需要其配置的 Playwright 浏览器。按所属任务及脚本要求准备环境。
- `desktop/portable-smoke.mjs` 和产品验收需要已生成的便携包或完整目录，见[构建与发布](../docs/development/CI_CD.md)及[产品验收](../docs/development/PRODUCT_ACCEPTANCE.md)。
- `desktop/ai-live-desktop.mjs` 会调用指定配置的真实 API；普通回归使用本机模拟服务。真实 API 的调用方法见[使用指南](../docs/guides/USER_GUIDE.md#ai-与-agent-协作)。
- `mise run gpu:test` 要求可选 GPU 环境；`mise run ornate:test` 要求相邻的 `NBTCreator-AssetLibrary` 仓库。
- 基准、复杂场景及现有工作区审计需按脚本参数显式运行，例如 `engine/fitting-shapes-benchmark.py`、`engine/fitting-shapes-complex.py`、`engine/workspace-library-audit.py`。
- 大型组装验收生成约 38 万方块并执行真实材质渲染，耗时和内存明显高于普通回归；结果保存在 `build/large-assembly-scale-*`，静态走测和截图不代表游戏内验证。
- 曲面引擎回归覆盖偏心退台宿主、凸饰转角、凹槽背衬、跨层支承及素材绑定。另有可选的代表样段检查，生成约 25 万块宿主，在同一候选中核对斜搭板、双暗窗、切槽和开口卷纹。它使用生产渲染器输出正面、斜面、剖面和远景，运行前需构建前端。结果保存在 `build/curve-review-*`，从 `acceptance.json` 可找到候选、保护拒绝、成对渲染和审阅清单。视觉结论由人工查看这些图像后记录。

## 新增或移动测试

1. 根据执行环境选择目录；可复用的辅助代码放在 `support/`，合成数据和输出写入隔离临时目录或被忽略的 `build/`。
2. 逻辑回归优先沿用 `*.test.cjs` / `*.test.mjs`；Electron 旅程沿用 `*-desktop.mjs`；Python 沿用所在模块的独立脚本方式。
3. 为新增测试接入适用的 npm / mise 任务，按需加入 CI 或产品验收。仅创建文件并不会使现有任务自动运行它。
4. 移动时同步检查相对导入、仓库根目录推导、fixture 调用、脚本内枚举、npm / mise、CI、验收清单和当前文档。

[CI 工作流](../.github/workflows/portable.yml)与[产品验收清单](../config/product-acceptance.json)是不同范围的显式执行清单。`docs/archive/` 保留当时的历史路径和结果，不作为当前命令入口。
