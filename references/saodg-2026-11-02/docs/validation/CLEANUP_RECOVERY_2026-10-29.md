# 清理半途中断与恢复（2026-10-29）

测试提交 `3b55564bd99f`，生产代码仍为 0.41.14.1 / 协议 19 / writer schema 3。命令 `python tools/verify_process_recovery.py --java-home D:/Java/jdk-17 --checkpoint cleanup` 在独立 Git 导出 `.gradle/cleanup-recovery-3b55564bd99f` 运行，仅复用根 Gradle 缓存，未编译正在试玩的客户端目录。

独立世界 `run/gameTestServer-recovery-20261029-013824-1281b21f`，run `7d4fab25-f5e0-484a-b67c-3ed37519bed9`，人物 `b3195d9d-4bcf-4cc7-a75b-32404819c32e`。真实大厅开局和全部结构放置后，生产 abort/回程/清理路径依次执行；原有 142307 个非空气方块清到剩余 69283 个，中间区域地板已消失、末尾首领区仍存在，人物已回原世界/创造模式，待回程为 0，槽位仍为 CLEANING，实际清理作业仍持有票据。保存世界、人物和部分清理区块，回读主日志确认 CLEANING 与完整清单，再保存独立夹具并 `Runtime.halt(73)`；首进程 Gradle 失败为预期故障注入。

第二进程启动日志明确从 CLEANING 恢复且回程为 0。1 项 required GameTest 通过，正常全维度保存，40 秒退出 0，外层工具退出 0。恢复后逐块检查完整持久清单的 49×49×height 区域全部为空，包含一格连接和独立首领区；实际观察到的恢复清理作业票据归零、槽位 FREE、运行索引移除。人物原位置/模式、三颗钻石及测试钱包字段保留，人物文件回读一致；已归档中止复盘逐字相同，重复登录/检查点不新增或改写复盘，没有成功奖励/事实。

根日志保留：`logs/cleanup-recovery-041141-20261029.log`，以及 `logs/process-recovery-20261029-013824-1281b21f-{crash.log,recover.log,result.json}`。同一 run/player 在准备和恢复回执中匹配。

本项覆盖 L01 的清理阶段中断，使用已保存边界后的 JVM 硬退出；不代表随机磁盘写入损坏、真实网络多人、目标整合包或完整故障矩阵通过。未发现生产代码问题，未重新打包、重启客户端或解除正式入场限制。
