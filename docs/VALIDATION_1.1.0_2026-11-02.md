# 1.1.0 · 生产前端迁移验证

本轮将桌面生产包从Vite开发服务切换为预构建页面与本机静态HTTP宿主。主模型、墙mask、操作参数、标注、验证和导出格式未变。

## 实现

- `npm run build:web`构建控制台/3D两个入口，打包依赖JS/CSS并复制锁定的Lodestone资源包，生成逐文件SHA256清单。
- 构建输出为引擎skill的assets/viewer/web-dist，不入Git；打包自动重建，工作区skill同步携带这些资源。
- 正式桌面包严格使用production模式；缺少构建文件时拒绝启动，不偷偷启动开发服务。
- Node静态宿主只暴露构建资源及已登记的模型/本机API；保留Host/Origin校验，源文件、node_modules、Vite客户端地址不作为静态页面暴露。
- 生产运行路径无需import Vite；包内已排除Vite模块。开发调试显式用start:dev，无构建的独立源码仍兼容开发回退。
- 静态宿主同样用于批量纹理渲染，不要求Agent点击桌面界面。

## 本机实际结果

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 静态宿主、路径限制、Host/Origin、快照、资源包、无node_modules运行及开发回退 | 10项通过 | build/production-server-1793623251667/results.json |
| 批量纹理渲染 | 19项通过 | build/static_render_validation_01/results.json |
| 工作区/skill搬迁 | 7项通过 | tests/workspace-contracts.py |
| 打包版桌面、静态页面与无Vite客户端 | 12项通过 | build/desktop-1793623125367/results.json |
| 打包版API、知识选择与工作区 | 19项通过 | build/api-desktop-1793623135559/results.json |
| 打包版NBT与切换工作区skill同步 | 4项通过 | build/catalog-desktop-1793623143011/results.json |
| 工具目录一致性、skill本地检查、原409文件归档哈希 | 通过 | check:tools、cli check、verify:archive |

前端构建生成14个文件，共3,931,778字节；构建器提示3D相关chunk超过500kB，未据此宣称载入性能已达标。打包后确认Vite模块目录不存在，frontend-manifest.json存在；实际Electron仍能运行3D、参数预览、标注和新版本导出。

本机验证包：`dist/1.1.0/NBTCreator-win32-x64/NBTCreator.exe`。Node/Playwright/浏览器仍用于批量出图，Python/NumPy/Pillow仍未内置。未引入跨进程写锁、持久化任务恢复或自主Agent循环。

全屏闪退NBTC-001继续仅记录，没有触发全屏或宣称修复。API使用本机模拟服务，未使用真实DeepSeek凭据，未做模型质量、游戏或多人验收。
