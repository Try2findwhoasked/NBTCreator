# NBTCreator 0.1.0 迁移验证 · 2026-11-02

## 归档与来源

- 资料库409个文件，ZIP为17,167,482字节。
- ZIP SHA256：`687c0626f29b319114e3c5958e55ba7290ffc4e141c7f732ac19acfde68356ea`。
- 展开文件、ZIP内容与原源文件在迁移后逐一核对；409个原文件均未变化。
- 下载的Electron 45.2.1 Windows x64 ZIP核对官方SHASUMS256，SHA256为 `7c342aee45d5b4ccafe5dfe9037028796b082735a576e21e2b4e2d8422ebb727`。

## 本机实际验证

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| doctor | 通过；Node 24.19.0、Python 3.14.7、NumPy 2.4.2、Pillow 12.1.0 | npm run doctor |
| skill引用、语法和注册表 | 通过；34个Markdown，1003个方块 | node scripts/cli.mjs check |
| 通用建模工具 | 9个测试通过 | build/engine_modelling_01/regression.json |
| 参数/快照转新版本 | 10项检查通过 | build/engine_revision_01/results.json |
| 开发版真实Electron端到端 | 9项检查通过 | build/desktop-1793617722116/results.json |
| Windows解压目录包 | 已生成NBTCreator.exe | dist/NBTCreator-win32-x64 |
| 打包版真实Electron端到端 | 9项检查通过 | build/desktop-1793617761706/results.json |

桌面端到端实际覆盖：工作区加载与受限原生桥接、renderer隔离、Python快照、Electron WebGL、3D选点意见保存、参数预览、明确导出下一版NBT、原稿不变、提示词面板与CLI调用。使用独立合成模型，不读取或修改用户建筑；未自动操作系统原生文件选择对话框。

首轮桌面测试使用了以synthetic开头的模型目录，被既有模型索引按合成数据排除规则跳过；改为隔离测试工作区内sample目录后通过。此失败不是全屏问题的复现。

## 未验证与已知限制

- NBTC-001全屏闪退仅按用户反馈登记，没有进入全屏复现，尚未定位。
- 未在另一台机器验证；Python及其依赖未内置，不能宣称免环境安装。
- 未验证所有旧CLI、全部批量纹理渲染/结构工作台功能、游戏导入、SAODG运行或多人。
- 未集成DeepSeek或其他模型服务，没有真实API调用或能力基准结果。
- 尚未实现统一持久化任务恢复、GUI/CLI跨进程写锁、生产前端构建替换、安装器签名或自动更新。
