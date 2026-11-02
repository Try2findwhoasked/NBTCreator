# 两人入场半途中断与恢复（2026-10-29）

测试提交 `505b6000908d`。生产逻辑保持 0.41.14.1 / 协议 19 / writer schema 3；仅新增显式 `--checkpoint transfer` 故障夹具和运行器支持。独立导出 `.gradle/transfer-recovery-505b6000908d` 中执行 `python tools/verify_process_recovery.py --java-home D:/Java/jdk-17 --checkpoint transfer`，未编译、替换或重启正在试玩的根开发客户端。

专用世界 `run/gameTestServer-recovery-20261029-014334-47bd5fdd`，run `52eb16d7-e3db-4436-b766-c0690c521342`。两名实际 PlayerList 登录的 ServerPlayer 分别为 `f2186add-fc3a-4415-ab6d-13d33df7354a` 和 `3c287294-9be6-4cff-9f8d-26f5b548de49`，使用不同原位置/朝向、创造/生存模式、3/5 颗带各自 UUID 标签的钻石及不同测试钱包字段。经生产大厅邀请、各自准备和地图放置进入入场流程。

第一人的实际 Forge `PlayerChangedDimensionEvent` 回调内中断：此人已在副本/冒险模式，另一人仍在原世界/生存模式。服务状态仍为 READY，槽位 RESERVED，2 份回程标记保留。保存世界及两份实际人物文件，回读确认不同维度/模式、完整物品 NBT，以及主日志的完整 READY 记录和 2 份回程后，才保存独立夹具并 `Runtime.halt(73)`。不是改写 phase 或手工移动两人来模拟这一窗口。首进程 55 秒、JVM 明确退出 73；Gradle 失败为预期注入。

第二进程启动明确从 READY 恢复，仍有 2 份回程。重新登录两个原 UUID，1 项 required GameTest 通过，正常全维度保存，39 秒退出 0，外层退出 0。两人的位置、朝向、原模式、完整库存 NBT 和各自测试钱包字段分别保留；人物文件维度/模式/库存回读一致，active_run 清除。各自只有一份重启中止复盘，无评分/通关凭证/奖励/成功事实，重复登录/检查点不改写复盘。持久清单内所有 49 格房间、连接、独立首领区逐块为空；实际观察的清理作业票据归零，槽位 FREE、待回程为 0、实例索引移除。运行器还匹配准备/恢复回执中的完整两人 UUID 列表。

保留根日志：`logs/transfer-recovery-041141-20261029.log` 与 `logs/process-recovery-20261029-014334-47bd5fdd-{crash.log,recover.log,result.json}`。

覆盖 L01 的实际入场循环部分传送窗口。登录使用 EmbeddedChannel，并非两个真实远程客户端；测试钱包字段不是 SAO 钱包原生事务验收。中断发生在已保存边界，不代表随机文件损坏、操作系统掉电、真实双队/整合包或完整故障矩阵通过。无需重新打包，不解除正式入场限制。
