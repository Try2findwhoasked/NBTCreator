# 玩家保存静默失败后的奖励恢复

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

对应奖励故障矩阵 T06 的一次独立原生零费用场景。源提交 `f70cc1e0234c`，仍为 0.41.15 / protocol 20，仅扩展测试及显式运行器，生产领奖代码、配置和模组产物不变。

## 故障与预期

真实创建大厅、生成地图、清房、封印大厅转场和首领通关后，通过生产 `RewardService.claim` 领取该局个人 CHEST 固定方案。测试只替换原生端口的 `PlayerSaveBarrier.save`：模拟公共保存调用未抛出异常、底层没有写入；`read` 仍读取真实玩家文件。没有伪造磁盘回执或手写生产操作状态。

实际物品、攻略经验和回执已应用到内存，但磁盘仍是原库存/成长且无回执。首次领取及十次重试均返回 UNCONFIRMED，共 11 次保存尝试，内存资产与回执完全不变，资产锁保持。普通库存 PICKUP 在故障前能够执行并恢复原库存，故障后实际容器入口被锁拦截；实际丢弃入口也未转出物品，但该局本身另有禁止丢弃规则，不单靠后者证明资产锁。

只保存世界 APPLIED_UNCONFIRMED、原选择和固定 payload，核对无 committed fact；随后保存实验夹具并 `Runtime.halt(73)`。独立预期库存为原三颗钻石加固定 token 数量，成长由原经验加固定 payload 计算。

## 执行与结果

独立 Git 导出 `.gradle/reward-unsaved-f70cc1e0234c`：

```powershell
python tools/verify_process_recovery.py --java-home D:/Java/jdk-17 --checkpoint reward_unsaved
```

首次实验 `gameTestServer-recovery-20261029-025342-7dd7c930` 在服务启动阶段结束，尚未到故障边界，没有恢复夹具；保留原日志/目录，不记作通过。确认原进程与会话均已结束后，在新目录 `gameTestServer-recovery-20261029-030338-3ebcd27b` 重跑。

| 身份 | 值 |
| --- | --- |
| run | `991ed4d9-a70f-4b62-b40f-cc73d0680a92` |
| player | `517b12a3-70ff-4d3f-9285-7607151fc82d` |
| operation | `e199e1d2-df7d-4cec-b2db-a0b9c1f93392` |

首进程标记 `world=APPLIED_UNCONFIRMED diskReceipt=NONE swallowedSaves=11`，预期退出 73，Gradle 53 秒。第二进程 1 项 required GameTest 通过、正常退出 0，Gradle 38 秒；运行器报告 passed=true，两个进程的 run/player/operation 相同。

恢复检查：

- 人物上线前原 APPLIED_UNCONFIRMED、原玩家文件和已恢复资产锁保持。
- 同 UUID 的真实 PlayerList/EmbeddedChannel 人物登录，生产 reconcile 检查真实磁盘基线后只补发一次；新的持久回执 commit UUID 与重启丢失的内存回执不同。
- 完整库存、攻略经验/等级及回执匹配独立预期；另一个 BASE 待领和原成功战绩不变。
- 十次旧请求均 ALREADY_APPLIED，库存、成长和持久回执不变；磁盘世界 CONFIRMED、唯一 committed fact，锁释放。
- 原位置/模式恢复；全部持久区域（含 49 格连接、独立首领区和奖励箱）逐块清空，实际清理票据为零、槽位 FREE、回程清除。

## 证据与限制

外层日志 `logs/reward-unsaved-recovery-retry-04115-20261029.log`；两进程日志及身份报告已按原字节复制至根 `logs/process-recovery-20261029-030338-3ebcd27b-{crash.log,recover.log,result.json}`。原实验与导出均保留。

SHA256：crash `ea1c76a9a778c409e17ba515f604a36eb2dc389b921fff071021f3296386d153`；recover `59b2a0adc6c7b5259f8279463176144fda58825bb1095e19f18bf31d913ea8cf`；result `e06161d4cab6d141efce516e05bab0d501b3816aad7725f987cde3314147eda7`。

这证明一次静默缺失写入及重启后的原生免费奖励恢复，不覆盖部分文件写入、系统断电、SAO 钱包、付费箱、真实远程客户端或完整故障矩阵。未重跑 T05/T07、全量 JUnit 或默认 GameTest；不需更新当前开发包，正式开本保持关闭。
