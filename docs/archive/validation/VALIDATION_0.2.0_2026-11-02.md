# NBTCreator 0.2.0 · 可选API与界面验证

日期：2026-11-02（Asia/Shanghai）。本次仅修改NBTCreator活动源码，原SAODG和references冻结资料库保持不变。

## 变更

- 新增Electron主进程可选Chat Completions接入，DeepSeek预设、自定义根地址/模型、模型列表测试、JSON模式、取消与超时。
- Key使用Electron 45异步safeStorage API加密；关闭默认不联网，更换API来源不继承旧Key，配置损坏回到离线模式。
- 两类生成：提示词正文、选区内受限结构/换块参数。结构建议在本地编译检查后载入预览，保留显式导出和原源文件。
- 现代浅色主题、顶部品牌/API入口、统一卡片/控件/选中样式，保留原布局和标注流程；修复长工作区路径导致的侧栏横向溢出。
- 兼容效果预览返回的旧数组形式cuts：首次从效果预览启动3D时统一转换为viewer需要的对象格式。

## 已执行检查

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| API服务测试 | 8个通过 | npm run test:api |
| 开发版API桌面联调 | 8项通过 | build/api-desktop-1793618794269/results.json |
| 打包版API桌面联调 | 8项通过 | build/api-desktop-1793618925030/results.json |
| 新UI下普通桌面回归 | 9项通过 | build/desktop-1793618807418/results.json |
| 0.2.0打包版普通桌面回归 | 9项通过 | build/desktop-1793618929775/results.json |
| 窗口/缩放布局 | 7种组合、112次标签检查通过 | build/modern_layout_01/results.json |
| skill检查、资料库哈希 | 通过 | node scripts/cli.mjs check; npm run verify:archive |

API联调使用本机模拟HTTP服务，验证实际Electron加密/解密、请求Authorization、配置持久化、提示词结果、局部结构建议、过期参数拒绝、Python本地预览及原稿保持。没有使用真实DeepSeek Key，也没有对真实模型质量、服务配额、外网代理或所有兼容服务做验收。

开发截图：`build/api-desktop-1793618794269/modern.png`、`assistant.png`。Windows解压目录包：`dist/NBTCreator-win32-x64/NBTCreator.exe`，版本0.2.0；Python与依赖仍需外部环境。

NBTC-001全屏闪退继续仅登记，未触发全屏测试或宣称修复。多人、游戏导入、完整自主Agent循环与跨进程写锁不在本次验证范围。
