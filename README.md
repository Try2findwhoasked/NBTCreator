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

便携包内置 mise 和 Chromium，Electron 提供 Node。使用环境中已有的 Python 和 Git，已验证 Python 3.14。在解压后的包目录执行以下命令，再启动应用：

```powershell
python -m pip install -r resources/app/.agents/skills/minecraft-nbt-modeler/requirements.txt
.\NBT工具.cmd doctor
```

可用 `NBTCREATOR_PYTHON` 和 `NBTCREATOR_GIT` 指向特定可执行文件。更新时关闭应用并保留原创作工作区。由旧版迁移时，可把新完整包解压到新目录，使用原有创作工作区。

便携包目录下可运行 `mise.cmd --version`。从实际创作项目根目录调用包内的 `NBT工具.cmd task --id <任务编号> --view compact`，可读取提示词或建筑修改任务。不知道编号时用 `NBT工具.cmd task-client list --pending`。该入口经内置 mise 启动共享 CLI，读取任务使用当前工作目录。

## 持续集成与测试包

Windows Portable 按 PR 改动选择验证范围。纯文档改动只运行范围判断和汇总检查。前端源码和引擎 Python 脚本改动运行源码契约与冒烟测试。其余改动、主分支推送、手动运行和版本 tag 执行完整验证及打包。

在 GitHub 的 **Actions → Windows Portable → Run workflow** 选择分支。运行成功后，从 Artifacts 下载带提交 SHA 的 `windows-x64-portable-<SHA>` 测试包。测试包使用与正式版相同的外部 Python 和 Git。正式版由独立的 Windows Release 工作流在版本 tag 推送后构建和发布。

在仓库根目录安装依赖后，可先运行 `mise run ci:build` 和 `mise run ci:quick` 做源码冒烟。发布前运行 `mise run ci:verify` 和 `mise run ci:package -- dist/portable-local` 完成源码与便携包验收。

## 开始创作

1. 选择创作项目根目录作为工作区，建筑存放在 `nbt_models/`。
2. 在建筑库中打开建筑；首次创作可在“创作方案”编写、审阅要求，再确认交接给外部 Agent。
3. 进入模型编辑，用工具或 AI 修改局部，更新候选预览。
4. 切换到同一建筑的“检查与交付”，核对实际图片或 3D、保护区、适用的通路报告与保存位置，保存 SNBT 制作版；满意后手动定稿导出 NBT。

创作 Skill 在实际创作项目中生成：`.agents/skills/nbtcreator-workspace/SKILL.md`。软件源码及安装目录不作为默认创作工作区。

同步后，从创作项目根目录运行 `mise run nbt -- capabilities --routes` 查找命令。项目有同名任务时按生成的入口说明运行。[共用工作区](docs/guides/SHARED_WORKSPACE.md#对齐目录和工具版本)

## 文档

完整入口见[文档导航](docs/README.md)。

| 需要做什么 | 阅读位置 |
| --- | --- |
| 了解功能、快捷键、数据位置与常见问题 | [使用指南](docs/guides/USER_GUIDE.md) |
| 编写方案、审阅与交接建筑任务 | [建筑师工作流](docs/guides/ARCHITECT_WORKFLOW.md) · [首次创作](docs/guides/PROMPT_CREATION.md) |
| 让应用与 Agent 使用同一项目 | [共享工作区](docs/guides/SHARED_WORKSPACE.md) |
| 导入和渲染大型 SNBT 分区 | [大型组装制作源](.agents/skills/minecraft-nbt-modeler/references/large-assembly.md) |
| 按间距与材质目标生成梁架候选 | [梁架节奏原型](.agents/skills/minecraft-nbt-modeler/references/working-model.md#梁架节奏候选) |
| 配准三视图、生成正交相机与匿名对照 | [三视参考与回投影](.agents/skills/minecraft-nbt-modeler/references/orthographic-reference.md) |
| 在偏心曲面规划纹样并检查背衬 | [曲面纹样与背衬](.agents/skills/minecraft-nbt-modeler/references/curved-surface.md) |
| 使用 AI 选点、截图和构件移动 | [AI 放置](docs/guides/AI_PLACEMENT.md) · [AI 工作流](docs/guides/AI_WORKFLOW.md) |
| 连接或维护本地、远端拓展资产库 | [拓展资产库协议](.agents/skills/minecraft-nbt-modeler/references/asset-libraries.md) |
| 配置开发环境、运行检查或打包 | [开发指南](docs/development/DEVELOPMENT.md) · [构建与发布](docs/development/CI_CD.md) |
| 查询问题或过去的验证结果 | [已知问题](docs/KNOWN_ISSUES.md) · [历史归档](docs/archive/README.md) |

## 从源码运行

在仓库根目录执行。需要 mise、Node.js 24 和 Python；Python 依赖由仓库的 requirements 文件声明。CI 使用 Python 3.14，完整开发和验证说明见[开发指南](docs/development/DEVELOPMENT.md)。

源码开发时，可用 `mise run nbt -- --workspace <创作项目目录> task --id <任务编号>` 调用同一个任务读取入口。

```powershell
mise exec -- npm ci
mise exec -- node node_modules/electron/install.js
mise exec -- npm ci --prefix .agents/skills/minecraft-nbt-modeler/assets/viewer
mise exec -- python -m pip install -r .agents/skills/minecraft-nbt-modeler/requirements.txt
mise run dev
```

常用检查：

```powershell
mise run doctor
mise run check
mise run test -- --list
mise run test -- api
mise run build:web
mise run test -- desktop
mise run test -- architecture-workflow
mise run test -- modular
```

复杂整栋的 Agent 入口与源绑定审阅流程见[建筑方案闭环](.agents/skills/minecraft-nbt-modeler/references/architecture-workflow.md)。`mise run test -- architecture-preview` 在隔离项目中验证公共 CLI、冻结入口与真实出图。

## 开源许可证

NBTCreator 主项目采用 [GNU Affero General Public License v3.0（仅第 3 版）](LICENSE)。第三方组件和素材按各自的授权条款分发。Viewer 复用及修改记录见 [上游来源](.agents/skills/minecraft-nbt-modeler/references/upstream-sources.json)，上游许可证见 [LICENSE.upstream](.agents/skills/minecraft-nbt-modeler/assets/viewer/LICENSE.upstream)。

发布 Windows 二进制包时，在同一个 Release 提供该版本的对应源代码。正式发布的源码可从该 Release 的 **Source code** 下载项获取。

## 反馈

在 [GitHub Issues](https://github.com/Try2findwhoasked/NBTCreator/issues) 提供应用版本、复现步骤、任务错误和必要截图，提交前移除 API Key 与私人工作区数据。问题状态以[已知问题](docs/KNOWN_ISSUES.md)为准；历史测试结果只证明当时记录的范围。
