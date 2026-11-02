# 领奖意图已保存、发放前的进程中断

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

对应奖励故障矩阵 T05 的一次独立原生零费用场景。源提交 `5f63735ad7e8`，仍为 0.41.15 / protocol 20，仅扩展测试与显式 runner，生产领奖代码和默认配置未变。

## 故障边界

复用真实大厅、地图生成、星标清房、封印大厅转场与首领通关，确认 SETTLING 和实际奖励箱后，通过 `RewardService.claim` 选择该局个人 CHEST 奖励。

测试源集装饰 `RewardService.Barrier`，完整委托第一次世界保存。在原生资产 plan.apply 之前回读权威日志，确认原 operation 已为 INTENT、选择及全部固定 payload 已保存；同时核对玩家文件与内存均是原库存/成长，目标操作回执不存在、奖励数量为零、该操作仍持有资产锁。保存隔离夹具后 `Runtime.halt(73)`。

预期奖励库存单独按原钻石堆及固定 token 数量构造，攻略经验/等级由原进度加固定 payload 推导；没有拿恢复结果反填预期资产。重启后第一个回执必须匹配原 operation/run/player/choice/hash，并用原生端口验证 MATCH，随后保留其 commit UUID 检查重复请求。

## 实际执行

独立 Git 导出 `.gradle/reward-intent-5f63735ad7e8`，复用根 Gradle 缓存执行：

```powershell
python tools/verify_process_recovery.py --java-home D:/Java/jdk-17 --checkpoint reward_intent
```

新建世界：导出下 `run/gameTestServer-recovery-20261029-024730-597202b6`。未使用用户测试世界或私有整合服。

| 身份 | 值 |
| --- | --- |
| run | `967ec2e4-a4de-4d66-a417-77c4c19f0739` |
| player | `92f84550-5dcb-4c7f-b14b-1115f47a2526` |
| operation | `225ba9b3-2374-4c06-95a6-0cfe3f69118f` |

首进程标记 `world=INTENT player=NONE tokens=0`，按预期退出 73，Gradle 用时 1 分 2 秒。runner 核对 durable marker/夹具及退出码后启动第二进程。第二进程 1 项 required GameTest 通过，正常退出 0，Gradle 用时 37 秒，runner 整体退出 0，前后 run/player/operation 身份相同。

恢复实际检查：

- 人物上线前，原 INTENT 和未发放的玩家文件保持。
- 同 UUID 的真实 PlayerList/EmbeddedChannel 人物登录，由生产 reconcile 按原固定选择发放一次并持久确认；完整库存、迷宫区成长和回执匹配预期，测试钱包字段保持。
- 旧领取请求重复 10 次均 ALREADY_APPLIED，不再增加物品或经验，回执/commit UUID 不变；另一份 BASE 方案完全不变。
- 世界磁盘为 CONFIRMED，内存和磁盘各只有一个该操作的 committed fact；原成功战绩唯一且不变，资产锁释放。
- 原位置/模式恢复；全部持久区域（含 49 格连接与奖励箱）逐块为空，实际 cleanup 作业票据为零、原槽位 FREE、回程清除。

## 证据与范围

根 `logs/reward-intent-recovery-04115-20261029.log` 保留外层结果，`logs/process-recovery-20261029-024730-597202b6-{crash.log,recover.log,result.json}` 保留两进程日志和身份报告；原导出与世界不删除。

只运行这一项，没有重跑 T07、全量 JUnit 或默认 GameTest。T07 的既有证据仍对应其当时提交，见[玩家回执窗口](REWARD_RECEIPT_RECOVERY_2026-10-29.md)。本次不是文件写到一半或系统断电，不覆盖 T06 未确认保存、真实 SAO 钱包/付费箱、远程网络或完整故障矩阵；正式开本保持关闭。不需替换现有 0.41.15 模组。
