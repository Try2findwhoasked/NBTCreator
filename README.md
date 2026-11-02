# NBTCreator

Minecraft Java 1.20.1 NBT 建筑创作工作台，集成建筑方案、模型编辑、3D 预览、AI 构件生成与 Agent 协作。

## 主要功能

- **建筑方案**：选择形状填写尺寸、布局、材质与构造要求，AI 可辅助完善完整初稿方案。
- **模型编辑**：打开完整 NBT 或主模型，调整材质、地面和结构，预览后另存下一版。
- **3D 与标注**：旋转、缩放、切层、取材、选点与修改意见。
- **AI 构件**：45 种构件参考，支持相对坐标生成、3D 放置、立即预览和整体 XYZ 偏移。
- **AI 工作流**：分别配置规则、资料库和视口截图；内部 API 与对外 Skill 独立管理。
- **设置与记录**：常规配置、关于、检查更新，以及 AI 请求和本地预览的阶段日志。

## 下载与启动

从 [GitHub Releases](https://github.com/Try2findwhoasked/NBTCreator/releases) 下载 Windows x64 版本。私有仓库需有访问权限。

| 下载包 | 用途 |
| --- | --- |
| windows-x64-portable.zip | 完整便携版，解压后运行 NBTCreator.exe |
| windows-x64-app-update.zip | 已有兼容运行环境时更新应用 |
| windows-x64-runtime.zip | 与应用包解压到同一父目录，合并同名文件夹 |

完整版内置 Python、NumPy、Pillow 和浏览器，无需安装开发环境。启动时会检查运行环境版本是否兼容。

首次选择项目根目录，建筑默认存放于 nbt_models 下，按形状、中文名称和版本归档。

## 使用流程

1. 在“提示词方案”创建要求，保存或复制给 Agent 制作完整初稿。
2. 在“模型编辑”打开模型，调参或让 AI 生成局部构件。
3. 检查图片、3D 和修改意见，满意后“导出建筑下一版”，保留原稿。
4. 在“任务记录”查看状态，在“设置”调整默认预览、缩放、查看版本和下载更新。

AI 是可选功能，在“AI助手”配置 API；视口截图需要视觉模型支持。生成建议和预览不自动覆盖建筑。

应用与 Agent 共用工作区。启动应用后，Agent 可读取工作区的 .agents/skills/nbtcreator-workspace/SKILL.md 调用同一套工具。同一建筑应轮流修改，完成后刷新列表。

## 更新

“设置 → 更新”可检查 GitHub 稳定发行版，一键下载应用包或完整版并验证 SHA256。下载完成后关闭程序再解压更新，不覆盖运行中的应用。

私有仓库可配置独立的 GitHub 只读访问令牌，与 AI API Key 分开加密保存。

## 开发

源码运行需要 Node.js 24、Python 与 NumPy/Pillow：

```powershell
npm ci
npm ci --prefix .agents/skills/minecraft-nbt-modeler/assets/viewer
python -m pip install -r .agents/skills/minecraft-nbt-modeler/requirements.txt
npm run build:web
npm start
```

```powershell
npm run test:desktop
npm run test:api
npm run test:api-desktop
npm run package:portable
```

详细操作见 [AI 工作流](docs/AI_WORKFLOW_1.8.md)、[共享工作区](docs/SHARED_WORKSPACE.md) 和 [构建发布](docs/CI_CD.md)。
