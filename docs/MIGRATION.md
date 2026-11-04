# 迁移记录 · 2026-11-02

## 目标与首阶段边界

独立项目目录为 `D:/Documents/Coding/Software/NBTCreator`。来源为SAODG工作区的当前本地文件，不以原Git HEAD代表包含未跟踪skill文件的完整来源；逐文件哈希记录在资料库清单中。原SAODG不做反向同步。

第一阶段使用 **Electron → Node utility process → 原本机detail server → Python**。界面复用原Three.js控制台，skill继续通过Python/CLI直接调用，既有精修批准与手动导出分支不合并。外部Python通过参数数组启动，不执行输入JSON中的代码。

Electron主进程只接管生命周期和原生选择器；preload只暴露info/chooseWorkspace/chooseSource，校验主frame和本机来源，sandbox/contextIsolation开启，nodeIntegration关闭，不允许新窗口或任意导航。Utility process是Node服务宿主，Python仍由受控子进程执行，不把utilityProcess当作Python解释器。

## 已开始迁移

- 冻结原skill、结构工作台和docs资料，建立ZIP与哈希验证入口。
- 新项目活动skill直接复制后独立维护；核心脚本与注册表暂不搬路径。
- CLI统一命令包装与能力发现，Electron不作为运行前提。
- 桌面窗口、原生源文件/工作区选择、工作区记忆、退出时关闭服务及当前任务。
- 复用模型导入、参数预览、图片/3D意见、提示词、验证与新版本导出。
- Windows解压目录应用打包原型；排除资料库、测试输出、工作区和开发依赖。

## 后续迁移

截至1.1开发阶段：第3项的工具目录统一已完成；第4项的生产前端静态构建与批量出图共用宿主已完成本机验证。统一任务协议、跨进程写锁、持久化任务恢复、内置Python和自主Agent循环仍待继续推进。

1. 把服务方法与HTTP传输分离，建立版本化任务请求、进度事件和统一错误结构。
2. 为GUI与CLI增加同项目写入锁、持久化任务索引、失败目录与恢复策略；保留不可变源/新版本输出。
3. 将JS工具表单目录与Python能力定义统一，生成参数schema、帮助与skill工具参考。
4. 用构建后的前端替换生产包中的Vite运行服务；图像批量渲染统一调度。
5. 单独处理Python运行时、依赖和多平台打包，明确其许可证与版本；再考虑签名、安装器、更新。
6. 应用内Agent作为可选适配器，先定义导入/导出任务包，再接模型服务；不把提示词或JSON视为批准。

## 验证记录

用户报告的“全屏时闪退”已作为NBTC-001记录于 `docs/KNOWN_ISSUES.md`。按用户要求先记录，尚未复现或定位，不包含在普通窗口验收结论中。

实际运行结果位于build独立目录，由测试输出记录，不能借用原SAODG的Java、游戏或多人结果。资料库校验与doctor只证明文件完整性和依赖可导入，不证明运行界面、模型或美术完成。

首阶段开发版与打包版均已完成本机普通窗口端到端测试。具体数量、证据路径和未验证范围见 `docs/VALIDATION_2026-11-02.md`。

0.2.0加入默认关闭的可选API助手与现代浅色界面，未引入自主Agent执行循环。服务协议、发送范围与操作边界见 `docs/API_INTEGRATION.md`；实际验证见 `docs/VALIDATION_0.2.0_2026-11-02.md`。
