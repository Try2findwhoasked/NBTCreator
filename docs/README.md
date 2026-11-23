# 文档导航

NBTCreator 的文档按使用指南、开发维护和历史记录归类。首次使用从[仓库首页](../README.md)开始；查找过去某一版的测试结果时进入[历史归档](archive/README.md)。

## 使用指南

| 文档 | 内容 |
| --- | --- |
| [使用指南](guides/USER_GUIDE.md) | 下载、主要功能、快捷键、数据保存位置、命令行与常见问题 |
| [建筑师工作流](guides/ARCHITECT_WORKFLOW.md) | 方案编写、人工审查、任务交接、标注和版本管理 |
| [三视图与贝塞尔建模](guides/ORTHOGRAPHIC_BEZIER_MODELLING.md) | 参考图配准、分段拟合、建模及回投影检查 |
| [首次创建模型与 AI 方案](guides/PROMPT_CREATION.md) | 新建建筑要求、保存位置与外部 Agent 制作流程 |
| [3D 选点与 AI 放置](guides/AI_PLACEMENT.md) | 局部范围、选点放置、候选预览与导出 |
| [AI 工作流](guides/AI_WORKFLOW.md) | 构件参考、视口截图、任务记录与整体移动 |
| [共享工作区](guides/SHARED_WORKSPACE.md) | 目录、知识路由、运行时同步、协作与评论校验 |
| [设置与更新](guides/SETTINGS_AND_UPDATES.md) | 偏好保存、Skill 入口、下载校验与手动更新 |
| [房间质量辅助模型](guides/ROOM_QUALITY.md) | 评分公式、资料完整性、使用入口和局限 |
| [整栋建筑质量评分](../.agents/skills/minecraft-nbt-modeler/references/building-quality.md) | 五维试用评分、真实图像证据、阻塞定位和续版复验 |
| [已知问题](KNOWN_ISSUES.md) | 问题状态、现有证据与尚未验证的范围 |

## 开发维护

| 文档 | 内容 |
| --- | --- |
| [开发指南](development/DEVELOPMENT.md) | mise 环境、依赖安装、启动、检查、打包及主要目录 |
| [架构与文件结构](development/ARCHITECTURE.md) | 运行边界、任务生命周期、源码与创作目录、发布门禁 |
| [构建与发布](development/CI_CD.md) | CI 门禁、完整包与分离包、版本标签和发布边界 |
| [API 与 Skill 集成](development/API_INTEGRATION.md) | 连接配置、任务类型、发送范围、取消重试和机器接口 |
| [内部 AI 与对外 Skill](development/INTERNAL_AI.md) | 工作流资料、创作偏好、请求参数、增量返回和诊断 |
| [外置知识库与网络搜索设计](superpowers/specs/2026-11-20-knowledge-retrieval-design.md) | 离线书库接入、共同引用与联网阶段设计 |
| [产品验收](development/PRODUCT_ACCEPTANCE.md) | 验收要求、源哈希、证据收据与判定边界 |
| [产品完善清单](development/PRODUCT_IMPROVEMENTS.md) | 持续工作范围、完成项和原始进展记录 |
| [大型建筑建模复盘与下一步开发](development/LARGE_MODEL_ROADMAP.md) | 艾恩葛朗特案例、现场问题、P0–P2 开发顺序与验收条件 |

## 引擎与创作 Skill

软件维护使用 [minecraft-nbt-modeler 实现目录](../.agents/skills/minecraft-nbt-modeler/)中的活动引擎；工具定义以 [tool-catalog.json](../.agents/skills/minecraft-nbt-modeler/tool-catalog.json) 为准。参数化建模、工作模型、对象图等细节继续保留在引擎的 `references/` 内，不在本目录复制一份。

实际创作时，Agent 应读取创作项目生成的 `.agents/skills/nbtcreator-workspace/SKILL.md`，按已选知识路由工作。软件源码根目录不生成这个创作入口。

拓展配方与构件的数据协议、远端清单、缓存、回退和 CLI 入口见[拓展资产库](../.agents/skills/minecraft-nbt-modeler/references/asset-libraries.md)；官方新资产维护在独立 NBTCreator-AssetLibrary 仓库，软件只保存发行快照。

## 文档维护约定

- 仓库 `README.md` 保留最短上手路径；操作细节放 `guides/`，环境、接口与验收约定放 `development/`。
- 当前指南采用稳定主题文件名，沿用现有 `UPPER_SNAKE_CASE.md`；历史版本、日期及原始文件名保留在 `archive/`。
- 新增或移动文档时更新本导航、引用方和相对链接。每篇使用一个一级标题，命令写明执行目录与前置条件。
- 软件开发命令从源码根目录执行，优先 `mise run <task>`，没有任务时用 `mise exec -- <command>`。创作项目的 Skill 命令在该创作根目录执行，不混用两个工作区。
- 当前操作说明随实现更新；历史记录保留当时的结果、失败与未验证范围，不把旧结果改写成当前版本的验收结论。
- API Key、私人路径、用户资产与临时日志不作为示例资料提交；测试与构建证据保存在项目约定的 `build/`、`dist/` 中。

历史资料按[发布记录](archive/README.md#发布记录)、[验证记录](archive/README.md#验证记录)、[审计与交接](archive/README.md#审计与交接)及[迁移记录](archive/MIGRATION.md)查询。
