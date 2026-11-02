# 领奖回应丢失、立即断线后的恢复

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

对应奖励故障矩阵 T08 的一次独立原生零费用场景。测试源提交 `db448cac1ace`（初版 `6e23b16c5ce4`），仍为 0.41.15 / protocol 20；没有改生产代码、配置或产物。

## 实际请求与故障

使用生产大厅、生成、星标清房、封印大厅传送与首领流程通关。由真实 PlayerList 中的非 OP 人物通过 Brigadier 执行 `/saodg claim <operation> <choice> <revision>`，领取本局固定 CHEST 方案。

在该人物的 EmbeddedChannel 加入测试出站处理器，仅截获并丢弃实际 `ClientboundSystemChatPacket` 中键为 `saodg.reward.applied` 的成功消息。断言命令正常完成、恰好丢弃一条成功消息，世界 CONFIRMED、玩家回执 MATCH、完整库存/成长为独立预期、资产锁已释放。不是只忽略 Java 返回值或手工标记“已领取”。

随后实际从 PlayerList 移除原人物并关闭传输通道；确认 UUID 已离线，原人物对象重放被拒绝。玩家文件和世界确认保持后保存实验夹具并 `Runtime.halt(73)`。第二进程重登同一 UUID，检查原回执 commit UUID、库存与成长不变。

## 执行结果

独立 Git 导出 `.gradle/reward-response-db448cac1ace`：

```powershell
python tools/verify_process_recovery.py --java-home D:/Java/jdk-17 --checkpoint reward_response
```

新建世界：导出下 `run/gameTestServer-recovery-20261029-031233-bbb4a499`。

| 身份 | 值 |
| --- | --- |
| run | `2e42c3bc-676f-470a-ac98-630931e47173` |
| player | `ee541aac-4904-4bc6-aad2-959464d774f5` |
| operation | `42a1479c-fdf0-4ec7-a9e4-767dd3114e99` |

首进程标记 `world=CONFIRMED player=MATCH dropped=1 disconnected=true`，预期退出 73，Gradle 59 秒。恢复进程 1 项 required GameTest 通过、退出 0，Gradle 39 秒；运行器退出 0，报告两个进程的 run/player/operation 相同。

实际恢复断言：

- 上线前的操作保持原 CONFIRMED、原选择和全部固定方案，真实人物文件与原已领取资产一致。
- 同 UUID 的新人物登录，完整库存、经验/等级及原 receipt/commit UUID 不变；测试钱包字段未改变。
- 新个人奖励页的生产 snapshot 不再提供该项领取，同时保留另一项原 BASE 待领。这里只检查实际服务端投影，没有宣称客户端视觉通过。
- 十次旧领取请求均 ALREADY_APPLIED，资产和回执不变；内存及磁盘各只有一个 committed fact，成功战绩保持唯一，锁释放。
- 恢复原位置/模式，全部持久区域（包括 49 格连接、独立首领区和奖励箱）逐块清空，实际作业票据零、槽位 FREE、回程清除。

## 留存证据与限制

根外层日志 `logs/reward-response-recovery-retry-04115-20261029.log`，根 `logs/process-recovery-20261029-031233-bbb4a499-{crash.log,recover.log,result.json}` 为原字节副本；导出与世界保留。

SHA256：crash `1021ff3e0b0b454f576477b2ccc0ce76915969e286447e184c7b29df84035597`；recover `827091fe96fc8dfeb3f900487a5d5d6aadf9712ae228390db63e65eab2846dbd`；result `581710e9f21189b5b9dd09bf63483374b1e62d20574ecade75b65d5238368350`。

首次导出 `.gradle/reward-response-6e23b16c5ce4` 的 `20261029-031118-6f339a45` 实验在编译测试时发现 Connection.channel 为私有字段，未启动服务或到达故障边界；改为测试内只读反射获取原隔离传输，保留原失败日志，在新目录重跑通过。

该测试覆盖真实命令/出站成功包、服务端人物注销与跨进程重新登录；传输为 EmbeddedChannel，不是远程 TCP、多客户端网络丢包或客户端按钮渲染。仅验证原生免费 token/迷宫区 XP，不覆盖 SAO 钱包、付费箱或全部故障矩阵。未重跑其他 checkpoint、全量 JUnit 或默认套件；正式开本保持关闭。
