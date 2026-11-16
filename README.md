# NBTCreator

面向 **Minecraft Java 1.20.1** 的 Windows NBT 建筑创作工作台，支持模型预览、结构编辑、构件与效果复用，以及内置 AI 和外部 Agent 协作。

修改先生成可审阅的候选，保留原稿；制作版与定稿导出分开，正式 NBT 需手动导出。

## 下载与启动

从 [GitHub Releases](https://github.com/Try2findwhoasked/NBTCreator/releases) 下载 Windows x64 版本。

| 包类型 | 使用方式 |
| --- | --- |
| `windows-x64-portable.zip` | 首次使用，完整解压后运行 `NBTCreator.exe` |
| `windows-x64-app-update.zip` | 更新已有应用，需保留兼容运行环境 |
| `windows-x64-runtime.zip` | 与应用更新包解压到同一父目录，合并同名文件夹 |

完整版内置 Python、NumPy、Pillow、SNBT 解析库、Chromium 和 Git，Electron 提供 Node 运行环境。保留完整目录，不要只复制 EXE。更新前关闭应用，保留原创作工作区。

## 开始创作

1. 选择创作项目根目录作为工作区，建筑存放在 `nbt_models/`。
2. 在项目管理中打开建筑；首次创作可在“提示词方案”编写、审阅要求，再确认交接给外部 Agent。
3. 进入模型编辑，用工具或 AI 修改局部，更新候选预览。
4. 检查实际图片或 3D、保护区与适用的通路报告，保存制作版；满意后手动定稿导出 NBT。

创作 Skill 在实际创作项目中生成：`.agents/skills/nbtcreator-workspace/SKILL.md`。软件源码及安装目录不作为默认创作工作区。

## 文档

完整入口见[文档导航](docs/README.md)。

| 需要做什么 | 阅读位置 |
| --- | --- |
| 了解功能、快捷键、数据位置与常见问题 | [使用指南](docs/guides/USER_GUIDE.md) |
| 编写方案、审阅与交接建筑任务 | [建筑师工作流](docs/guides/ARCHITECT_WORKFLOW.md) · [首次创作](docs/guides/PROMPT_CREATION.md) |
| 让应用与 Agent 使用同一项目 | [共享工作区](docs/guides/SHARED_WORKSPACE.md) |
| 使用 AI 选点、截图和构件移动 | [AI 放置](docs/guides/AI_PLACEMENT.md) · [AI 工作流](docs/guides/AI_WORKFLOW.md) |
| 配置开发环境、运行检查或打包 | [开发指南](docs/development/DEVELOPMENT.md) · [构建与发布](docs/development/CI_CD.md) |
| 查询问题或过去的验证结果 | [已知问题](docs/KNOWN_ISSUES.md) · [历史归档](docs/archive/README.md) |

## 从源码运行

在仓库根目录执行。需要 mise、Node.js 24 和 Python；Python 依赖由仓库的 requirements 文件声明。CI 使用 Python 3.14，完整开发和验证说明见[开发指南](docs/development/DEVELOPMENT.md)。

```powershell
mise exec -- npm ci
mise exec -- npm ci --prefix .agents/skills/minecraft-nbt-modeler/assets/viewer
mise exec -- python -m pip install -r .agents/skills/minecraft-nbt-modeler/requirements.txt
mise exec -- npm run build:web
mise exec -- npm start
```

常用检查：

```powershell
mise exec -- npm run doctor
mise exec -- npm run check:tools
mise exec -- npm run test:api
mise exec -- npm run test:desktop
mise run architecture:test
mise run modular:test
```

复杂整栋的 Agent 入口与源绑定审阅流程见[建筑方案闭环](.agents/skills/minecraft-nbt-modeler/references/architecture-workflow.md)；`mise run architecture:preview` 在隔离项目中验证公共 CLI、冻结入口与真实出图。

## 反馈

在 [GitHub Issues](https://github.com/Try2findwhoasked/NBTCreator/issues) 提供应用版本、复现步骤、任务错误和必要截图，提交前移除 API Key 与私人工作区数据。问题状态以[已知问题](docs/KNOWN_ISSUES.md)为准；历史测试结果只证明当时记录的范围。
