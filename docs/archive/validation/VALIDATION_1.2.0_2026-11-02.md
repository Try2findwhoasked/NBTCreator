# 1.2.0 · 工作区交互与AI配置表单

## 行为

- 模型页左栏缩小，上方工作区/搜索/高级控件默认折叠；提示词入口统一由顶部功能页提供。选择建筑即载入图片，没有图片时自动打开只读3D；独立NBT仍按原限制查看。
- 3D隐藏缩略图，保留图片选择和标注操作；评论输入/意见列表分栏，支持搜索、状态过滤、坐标定位、字数反馈与Ctrl+Enter保存。方案/运行详情位于评论下方，结果与技术数据区分显示。
- 任务记录显示当前会话的类型、状态、时间/耗时、变化量和产物链接，支持筛选与搜索，JSON默认折叠。这不是重启恢复或持久化任务队列。
- 提示词方案左侧加宽，底部读取/保存固定可见。AI可提议更新设计控件和工具序列；回填前校验，已有源、阶段、预算、保护和批准字段保持。
- 自定义Markdown/TXT知识复制到当前工作区，可选择暴露并随工作区迁移。说明明确面向Codex/兼容文件式Skill的Agent，不自动发送到API。
- 紧凑侧栏的方块选择器使用preventScroll聚焦，避免展开后又被焦点滚动事件关闭。

## 本机验证

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 完整控制台浏览器回归 | 40项通过 | build/ui_control_regression_12c/results.json |
| 多窗口/缩放布局 | 7种组合、140次标签检查通过 | build/ui_layout_12_final/results.json |
| 离线提示词工作台 | 8项通过 | build/prompt_ui_12/results.json |
| API/控件回填契约 | 10个测试通过 | npm run test:api |
| 工作区、skill与自定义知识 | 8个测试通过 | tests/workspace-contracts.py |
| 最终1.2打包版主流程/评论/任务页 | 15项通过 | build/desktop-1793625910061/results.json |
| 最终1.2打包版API/AI控件/知识导入 | 22项通过 | build/api-desktop-1793625921036/results.json |
| 最终1.2打包版NBT与工作区知识携带 | 4项通过 | build/catalog-desktop-1793625931167/results.json |
| skill、18类工具清单与409文件资料库哈希 | 通过 | cli check、check:tools、verify:archive |

交互截图在对应任务目录，已实际查看模型评论区、提示词方案和知识配置布局。输出为 `dist/1.2.0/NBTCreator-win32-x64/NBTCreator.exe`。

API联调使用本机模拟服务，不能证明真实DeepSeek模型的配置质量。没有触发全屏，NBTC-001仍待排查。Python仍外部依赖；同项目并发写入锁和重启任务恢复不属于本轮实现。
