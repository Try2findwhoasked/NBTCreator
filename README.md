# NBTCreator

Minecraft Java 1.20.1 NBT 建模工具的独立 Electron 项目（1.0.0 首次版本快照）。应用、提示词页、Python和skill使用同一份18类工具清单，默认使用Agent当前项目根目录下的nbt_models。原SAODG与冻结资料库不参与修改。已知全屏闪退仍待单独排查，见docs/KNOWN_ISSUES.md；1.0编号不代表这些限制已消除。

顶部 **AI助手** 只用于API和AI相关设置，包括当前工作区的 **Skill暴露配置**：选择建筑风格、自由形、多空间、细微道具等知识组，保存后生成 `.agents/skills/nbtcreator-workspace/SKILL.md`。核心约束保持，原文不删除，工具种类不随知识组减少。提示词生成位于提示词方案；结构建议位于模型编辑的AI建模页。API默认关闭，Key加密保存。详见 `docs/API_INTEGRATION.md`。

顶部提供 **模型编辑 / 提示词方案 / AI助手 / 任务记录** 四个工作区，切换保留当前模型与提示词草稿；“工作区”标签表示应用功能页，与“选择工作区…”中的磁盘项目目录不同。提示词页使用紧凑多列表单和共用API，可生成、编辑、采用AI设计建议；阶段规则、工具计划和验证要求保留本地版本。

输出模型协议保持原skill规范，可与Codex Agent共用磁盘目录；须显式对齐工作区与源路径，目前仍应轮流写出同一建筑。详见 `docs/SHARED_WORKSPACE.md`。

## 启动

本阶段需要 Node ≥20.19、Python，以及 `.agents/skills/minecraft-nbt-modeler/requirements.txt` 中的 NumPy/Pillow。设置 `NBTCREATOR_PYTHON` 可指定 Python 完整路径。

```powershell
npm install
npm ci --prefix .agents/skills/minecraft-nbt-modeler/assets/viewer
node node_modules/electron/install.js # 仅在 Electron 运行时未下载时需要
npm run doctor
npm start
```

也可双击 `启动NBTCreator.cmd`。默认使用调用Agent的项目根目录，不再额外套workspace文件夹；启动器保留调用目录。可用 `--workspace <目录>` 或 `NBTCREATOR_WORKSPACE` 明确指定。手动选择过的工作区可以记住；打包程序从安装/系统目录启动且无法推断Agent目录时，会请用户选择，不向安装目录写资产。

原生按钮“选择工作区…”切换扫描目录，并同步本地skill运行时与知识配置；选到nbt_models或其子目录时自动识别项目根目录。列表支持主模型JSON.GZ与当前引擎支持的完整NBT。“打开 NBT / 主模型…”也可直接选择文件；缺少作者配置的完整NBT可先只读查看3D，修改和导出仍需原配置与验证。沿用撤销侧栏调整之后的旧控制台布局。

## Agent / skill

Agent优先使用工作区生成的 `.agents/skills/nbtcreator-workspace/SKILL.md`；实现位于 `.agents/skills/minecraft-nbt-modeler/`，完整复制实现目录仍可用原Python脚本。生成入口采用相对引擎定位，完整项目搬迁后可继续使用；外部工作区与引擎分开移动后，在应用中重新保存暴露配置即可更新。CLI不需要打开Electron：

首次克隆后先运行应用，或执行 `node scripts/cli.mjs exposure apply` 生成当前工作区的入口及本地运行时。切换到新工作区会同步脚本/数据/知识库，不只生成指向旧安装路径的链接。配置示例在 `config/skill-exposure.example.json`。

```powershell
node scripts/cli.mjs capabilities
node scripts/cli.mjs exposure show
node scripts/cli.mjs exposure apply
node scripts/cli.mjs inspect --source "D:/实际文件/master_geometry.json.gz"
node scripts/cli.mjs control --help
node scripts/cli.mjs refine --help
node scripts/cli.mjs convert --input "D:/实际任务/settings.json"
```

统一CLI目前包装现有脚本协议，尚未重写为持久化任务服务。真实看图精修确认、手动参数效果导出、源哈希、路线保护、新版本输出和切片限制全部保留。

## 资料库与活动源码

- `references/saodg-2026-11-02.zip`：原skill、结构工作台和设计/验收文档源码归档。
- `references/saodg-2026-11-02/manifest.json`：409个原文件的来源、大小、SHA256与原Git HEAD；展开副本用于查阅，不修改。
- `.agents/skills/minecraft-nbt-modeler/`：迁移后活动副本，前端与Python当前仍保留原结构。
- `desktop/`：Electron主进程、有限preload桥接和服务worker。
- `tools/structures/workbench/`：兼容源码；尚未迁为通用桌面结构管理功能。

归档不包括node_modules、Python缓存、活动世界、建筑生成物或日志。现有建筑库并未搬家，需在应用中选择其原工作区。许可证和上游来源声明随skill保留。

## 检查与打包

```powershell
npm run verify:archive
npm run doctor
npm run test:desktop
node scripts/cli.mjs check
npm run package
```

桌面回归只生成合成模型，检查真实Electron窗口、Python调用、WebGL、坐标标注、参数预览、新版本NBT导出和源文件保留。结果与截图位于build中的独立任务目录。

打包输出为 `dist/NBTCreator-win32-x64/NBTCreator.exe`。它是未签名的解压目录原型，不是安装程序；**当前没有内置Python/NumPy/Pillow**，在另一台机器上使用前仍需准备对应环境。批量纹理出图暂时仍走原Node/浏览器工具链。Vite本机服务作为首阶段兼容层保留，后续再迁移为构建产物和更完整的任务协议。

1.0首次版本包另存为 `dist/1.0.0/NBTCreator-win32-x64/NBTCreator.exe`，实际验证与已知限制见 `docs/RELEASE_1.0.0_2026-11-02.md`。

应用与CLI共用引擎，但暂不支持同项目并发写入协调、跨重启任务恢复或自主AI Agent循环。不要同时对同一个源项目发起两路写出。新任务/参数保存为工作区相对引用，外部跨盘文件与历史证据可能保留绝对路径。旧目录迁移用 `node scripts/cli.mjs migrate-workspace --source <旧根目录> --workspace <新根目录>`，校验复制、更新活动描述引用、保留原始证据且不伪造批准。详见 `docs/SHARED_WORKSPACE.md`。
