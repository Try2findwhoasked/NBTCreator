# NBTCreator 1.0.0 · 初次版本快照

这是首个提交与v1.0.0标签对应的功能快照，不表示所有已知问题或生产验收已完成。

## 功能范围

- Electron窗口、统一界面、模型编辑/提示词方案/AI设置/任务记录功能页。
- 应用、CLI、skill共用18类工具和同一Python引擎。
- 默认Agent项目根目录，优先相对路径，保留旧绝对引用兼容。
- 工作区知识组配置、可调用skill入口与完整本地运行时同步；切换保留原工作区和已存在的目标配置。
- 目录选择能从nbt_models、缓存或房间目录识别项目根；列表支持主模型及引擎支持的完整NBT。
- 没有作者坐标配置的完整NBT可只读查看3D，未据此认证路线或允许直接导出。
- 原有预览、图片/3D标注、显式新版本导出、原稿保留和分层交付。
- 默认关闭的API接入；真实Key不存入仓库。提示词和受限结构建议仍需本地检查和用户操作。

## 本机验证

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 工作区迁移/相对路径/skill搬迁 | 7项通过 | tests/workspace-contracts.py |
| NBT目录与读取 | 3项通过 | tests/catalog-nbt.py |
| 默认工作区与子目录归一 | 4项通过 | tests/workspace-resolution.cjs |
| API服务 | 8项通过 | tests/api-service.test.cjs |
| 原细节控制后端 | 24项通过 | build/v1_control_validation/results.json |
| 原网页新版本转换 | 10项通过 | build/v1_revision_validation/results.json |
| 1.0打包版NBT/工作区切换 | 4项通过 | build/catalog-desktop-1793622433325/results.json |
| 1.0打包版API/知识配置 | 19项通过 | build/api-desktop-1793622438305/results.json |
| 1.0打包版桌面主流程 | 11项通过 | build/desktop-1793622446470/results.json |
| 工具接口生成、skill与冻结资料哈希 | 通过 | check:tools、cli check、verify:archive |

用户截图对应SAODG目录只读诊断：归一到项目根目录后扫描1393个文件，识别395个建筑版本，无读取错误。诊断缓存写入NBTCreator本地build，不修改原建筑。

## 使用与限制

本机目录包：`dist/1.0.0/NBTCreator-win32-x64/NBTCreator.exe`。重新生成可用 `npm run package -- --out dist/1.0.0`（输出目录须尚不存在）。源码仓库不提交dist、node_modules、个人配置、工作区资产或同步的运行时副本；首次运行应用或 `node scripts/cli.mjs exposure apply` 会生成工作区skill。

Python、NumPy/Pillow仍需外部环境；可移植skill未内置可选Node渲染依赖。支持的NBT遵循当前引擎1.20.1版本/完整体积/尺寸与实体限制，不宣称任意NBT都可载入。没有统一并发写锁、自动合并或自主Agent循环。

NBTC-001全屏闪退继续仅按用户反馈记录，未进入全屏复现或宣称修复。未执行真实DeepSeek质量验收、游戏导入或多人验收。
