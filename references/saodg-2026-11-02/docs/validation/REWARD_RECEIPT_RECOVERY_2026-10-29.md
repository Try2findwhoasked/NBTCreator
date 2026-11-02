# 奖励玩家文件已确认、世界确认前的进程中断

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

对应验收矩阵 T07 的独立零费用原生奖励边界。源提交 `7a868e96c387`，源码仍为 0.41.15，协议 20。只增加显式测试和 runner，不改生产领奖代码、配置或模组包。

## 真实故障点

专用 `reward_receipt` checkpoint 复用生产大厅、实际地图生成/战斗/封印大厅转场/首领通关。到达 SETTLING 且奖励箱存在后，选择该局实际个人 CHEST 方案的固定选项，通过生产 `RewardService.claim` 领取。

夹具仅在测试源集中用反射装饰实例的 `RewardService.Barrier`。第一次 INTENT 保存完整委托原生产检查点；第二次已通过原生端口 `saveAndConfirm`，即将写世界 CONFIRMED 时截断，不调用第二次世界保存。不改 phase、不构造成功战绩，也不手改玩家文件。

硬退出前实际回读断言：

- 权威世界日志仍为该 operation 的 INTENT，原选择与整个固定选项集合保持；该操作的 committed fact 还没落盘。
- 玩家文件已经有相同 operation/run/payload hash/choice 的实际回执，库存与内存相同；原生端口识别 MATCH。
- 实际已发 1 个本次固定 trial_token，攻略经验增加恰好是该 payload 的数值；原三颗钻石和测试钱包字段仍保留。
- 该人物的资产锁仍归同一个操作所有。
- 将检查结果、原区域清单、成功战绩、完整玩家库存/成长/回执和原 operation 保存为夹具，然后 `Runtime.halt(73)`，不执行正常停服或回程。

## 实际运行

从上述提交创建独立 Git 导出 `.gradle/reward-receipt-7a868e96c387`，复用根 Gradle 缓存，执行：

```powershell
python tools/verify_process_recovery.py --java-home D:/Java/jdk-17 --checkpoint reward_receipt
```

每轮使用新建专用世界，本次目录为导出下 `run/gameTestServer-recovery-20261029-024208-e6660b9f`。

| 身份 | 值 |
| --- | --- |
| run | `7fe0405b-086f-4538-b17b-b3dfe2a1dad8` |
| player | `7c9e570e-e12a-4e6a-a95a-00a80184d027` |
| operation | `8a0d298c-1518-4dde-8024-b79dc49d08fd` |

首进程 Gradle 用时 1 分钟，标记 `world=INTENT player=MATCH tokens=1` 后 JVM 按预期退出 73。runner 同时核对原 fixture 存在、特定标记和退出码，再启动第二进程。

第二进程 1 项 required GameTest 通过，正常退出 0，Gradle 用时 37 秒；runner 整体退出 0，核对前后 run/player/operation 身份完全相同。

恢复实际断言：

1. 人物上线前，启动恢复保留同一选项、同一修订的 INTENT，原玩家文件已应用的资产和回执不变。
2. 同 UUID 实际 PlayerList/EmbeddedChannel 人物登录，生产 reconcile 根据原玩家回执修复世界为 CONFIRMED，释放资产锁。完整库存、成长和回执（包括原 commit UUID）与中断前完全一致。
3. 旧领取请求重放 10 次全部返回 ALREADY_APPLIED，每次检查资产与回执相同；另一份个人 BASE 方案保持 OFFERED 原样。
4. 重复登录并保存后，世界磁盘确认 CONFIRMED 与恰好一个 committed fact；同一局仍只有原 COMPLETED 成功战绩。
5. 实际回程恢复原位置/模式；全部持久房间、49 格连接及首领奖励箱区域逐块为空。实际 cleanup 作业票据为零、原槽位 FREE，回程标记清除。

## 保留证据

根 `logs/` 保留：

- `reward-receipt-recovery-04115-20261029.log`：外层 runner。
- `process-recovery-20261029-024208-e6660b9f-crash.log`：SHA256 `e7eab3c9eb4aa5a566eb18f8c29a2ca80623713492be9f21a51fb84121e99497`。
- `process-recovery-20261029-024208-e6660b9f-recover.log`：SHA256 `245a2b8ae011129089c4945c19a67f208584d4954caeb267d420ec237ff212d1`。
- `process-recovery-20261029-024208-e6660b9f-result.json`：SHA256 `fdbe0bf462025cf16f1b014990eb3066b76b6e8f4e815859294f1c0a56272bbd`。

这只证明本次已确认玩家文件之后的 JVM 硬退出窗口。未覆盖文件写到一半、系统断电、T05/T06 其他进程窗口、付费宝箱、实际 SAO 钱包或真实远程客户端。测试钱包只是保留字段，不冒充原生钱包事务。没有重复全量 JUnit/GameTest，也未启动或改动用户客户端、原服与私有整合包；完整奖励故障矩阵和正式入场仍未完成。
