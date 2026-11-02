# NBTCreator 桌面与无界面调用

0.3.0默认工作区改为Agent当前项目根目录，资产保存到nbt_models。优先使用 `.agents/skills/nbtcreator-workspace/SKILL.md` 的生成入口；AI助手仅作API及知识库暴露配置，提示词生成和结构建议分别在提示词方案/模型编辑。知识配置为 `.nbtcreator/skill-exposure.json`；工具清单统一来自本skill的tool-catalog.json，应用新增“建模工具”页可执行相同operations。

本skill是NBTCreator的活动引擎与可移植指南，复制整个skill目录后仍可使用原Python入口。Electron不是调用前提；不要通过点击桌面界面代替可用的API或CLI。

在NBTCreator项目根目录可使用统一入口：

```powershell
node scripts/cli.mjs doctor
node scripts/cli.mjs capabilities
node scripts/cli.mjs inspect --source <完整主模型路径>
node scripts/cli.mjs control plan --request <请求JSON> --output <新目录>
node scripts/cli.mjs control preview --request <请求JSON> --output <新目录>
node scripts/cli.mjs refine prepare --source <主模型> --config <配置JSON> --review <新审阅目录>
node scripts/cli.mjs convert --input <用户明确指定的参数或效果JSON>
```

各子命令原有参数、确认、保护、源哈希与输出限制保持。通过 `--help` 查实际参数；`control`仅转发nbt_detail_control.py子命令，不能把示例空配置当实际腔体/玩家脚位。`NBTCREATOR_PYTHON`可指定Python完整路径。

桌面原型用Electron托管本机服务和现有控制台，原生按钮可选择工作区或完整源文件；工作区包含nbt_models。手动文件打开并不复制/修改该资产。源目录的坐标配置与图片按原逻辑发现。已有资产写入另走已批准精修或明确手动导出，保存到源建筑的新版本目录，保持原稿。

首阶段仍依赖外部Python、NumPy、Pillow；批量渲染暂时还依赖可用Node与原批量渲染环境。打包桌面exe不意味着这些运行时已内置。任务服务与CLI共享实现，但尚未统一持久化任务队列或跨进程项目写锁；同一源项目不要同时发起桌面与CLI的写出任务。

开发时启动：`npm start`。普通使用者和agent的模型、意见与任务不写入安装目录。参考快照位于项目references，禁止把其视为活动引擎或批准依据。

0.2.0桌面可选API助手支持提示词编写及受限局部结构/换块参数。默认关闭，Key加密保存在用户配置。仅显式生成时发送本次输入和尺寸/选区/部分材质，不发送源路径或完整模型。AI计划必须经过本地校验、预览和用户明确导出；它不取代本skill设计流程或真实精修确认，尚未实现自主Agent循环。原Python/CLI继续离线使用。
