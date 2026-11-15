# NBTCreator 0.2.1 验证

新增提示词工作台AI、共用设计变量、紧凑表单，以及顶部“模型编辑 / 提示词方案 / AI助手 / 任务记录”功能页。功能页切换保留当前模型与草稿，不改变磁盘工作区。嵌入提示词页隐藏重复标题，导入/保存/重置合并到单行工具条。

已执行：

- API服务8个测试通过。
- 提示词离线页8项浏览器检查通过：`build/prompt_compact_02/results.json`。
- 控制台/提示词集成10项检查通过：`build/prompt_ai_integration_02/results.json`。
- 7种窗口/缩放、112次标签检查通过：`build/workspace_layout_01/results.json`。
- 开发版API桌面联调17项通过：`build/api-desktop-1793619854845/results.json`。
- 打包版API桌面联调17项通过：`build/api-desktop-1793619926670/results.json`。
- 打包版普通桌面回归9项通过：`build/desktop-1793619932699/results.json`。
- skill本地引用/语法/注册表与冻结资料库哈希检查通过。

联调覆盖共享连接、设计文字和参数发送范围、AI稿采用后本地元数据/阶段/工具计划保持、过期稿拒绝、方案往返、真实Electron文件下载、设计颜色一致、窄屏和功能页切换。

仅使用本机模拟API，没有使用真实DeepSeek Key；未验证真实模型质量。全屏闪退NBTC-001仍仅登记，不包含全屏验收。并发写锁、持久化任务恢复和自主Agent循环仍未实现。
