# 生成半途中断与恢复（2026-10-29）

测试提交 `3d861c6b2f5f`，生产逻辑仍为 0.41.14.1 / 协议 19 / writer schema 3。独立 Git 导出 `.gradle/generation-recovery-3d861c6b2f5f` 中运行 `python tools/verify_process_recovery.py --java-home D:/Java/jdk-17 --checkpoint generation`，显式复用根工程 Gradle 缓存；没有编译开发客户端目录、重新打包或触碰其他世界。

新实验目录 `D:\Documents\Coding\Game\Minecraft\SAODG\.gradle\generation-recovery-3d861c6b2f5f\run\gameTestServer-recovery-20261029-012848-b30f2bc3`，运行 ID `c730d037-c3c0-4587-a4ce-2acc9d9411be`，人物 `13a110ac-c4dc-4879-b779-648598f193dc`。第一进程从真实大厅/准备/开局进入生产生成队列，起始 887432 个写入，剩余 443016 时中断。实际入口地板已放置，但状态仍是 GENERATING、槽位 RESERVED、人物在原世界/创造模式，1 个原回程记录保留。实例清单的所有区域和 49 格 stride 经真实主日志回读确认，人物文件和已写区块完成保存后，保存独立故障夹具再 `Runtime.halt(73)`。运行器要求日志标记、持久夹具和明确 JVM 退出码同时成立，不能把普通失败当成已执行中断。

第二进程实际加载同一世界与人物，启动日志明确从 GENERATING 恢复，未重新生成地图。1 项 required GameTest 通过，正常全维度保存，退出 0；外层工具返回 0。保留原位置/模式、三颗钻石的真实人物文件和测试钱包字段，只有一份重启中止复盘，无成绩/合格通关/成功奖励与事实；清理后逐块检查持久清单内每个 49×49×height 区域全部为空（含未完成房、间隔和独立首领区），槽位 FREE、待回程归零、保留作业票据归零，重复登录/检查点不重复写复盘。

证据已复制到根日志目录：

- `logs/generation-recovery-041141-20261029.log`：外层两阶段与返回结果。
- `logs/process-recovery-20261029-012848-b30f2bc3-crash.log`：首进程明确 73 硬退出；Gradle 非零是预期故障注入结果。
- `logs/process-recovery-20261029-012848-b30f2bc3-recover.log`：恢复断言、清理、通过与正常停机。
- `logs/process-recovery-20261029-012848-b30f2bc3-result.json`：同一原始 run/player 的准备与通过回执。

该场景补充 L01 的生成阶段、以及新 stride 清单的跨进程清理证据。它是已完成保存边界后的 JVM 硬退出，不是随机文件写到一半或操作系统掉电；没有 SAO/KubeJS/真实客户端、双队同时中断、奖励资产事务或其余阶段的完整故障矩阵。没有新增生产功能或发现需修改生产代码的问题，当前开发包不变，不因此开放正式入场。
