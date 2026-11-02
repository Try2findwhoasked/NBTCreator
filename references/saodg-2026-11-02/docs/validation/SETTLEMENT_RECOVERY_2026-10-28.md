# 奖励箱结算阶段的硬退出与恢复

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

在 0.41.1 源码上扩展独立两进程工具，增加 `--checkpoint settlement`；省略参数仍运行入口 EXPLORING 验收。Gradle 仅在专用 recoveryStage 下传入白名单 checkpoint，普通客户端和默认 GameTest 不触发硬退出。
结算故障场景复用实际战斗夹具：正式大厅入场，原版星标/普通敌人、主路钥匙与安全房出口、秘密/谜题、封印大厅两轮、两人封印大厅传送以及实际首领阈值/封印/冲锋后完成挑战。只在真实 SETTLING、箱子已生成且两份个人方案已保存后退出，不通过改 phase 伪造成功。

## 实际执行

命令 `python tools/verify_process_recovery.py --java-home D:/Java/jdk-17 --checkpoint settlement`。
私有目录 `run/gameTestServer-recovery-20261028-074200-21513473`，该工具新建且不接受覆盖原存档。
原 run 为 `17782b9c-d319-49de-b099-3cba1677535f`，人物为 `7d75f9cb-3faa-43e7-b932-16ea31f80415`。
首进程保存原世界/人物/实例检查点后以 73 硬退出，刻意不调用正常停服和回程；Gradle 失败是预期现象，runner 同时核对退出码及 durable marker。
第二进程加载同一私有世界和同一人物 UUID，1 项 required GameTest 通过，工具退出 0；报告 `logs/process-recovery-20261028-074200-21513473-result.json`，两份过程日志同此前缀的 crash/recover.log。

实际断言：

- 重启后仍只有一份 COMPLETED 成功战绩和成绩，不补一份中止/失败。
- 原两份个人奖励的 operation UUID、奖励选项、完整载荷、状态与修订号经 RewardCodec 逐项相等，不重掷。
- 人物原三颗钻石、钱包字段、原返回位置和游戏模式均保持；人物文件也确认原物品与返回维度/模式。
- 独立首领场地逐块清空，包含奖励箱；原槽位 FREE，回程标记清除，票据释放，未从旧布局重新生成箱子。
- 清理之后，两份原奖励实际在外面领取，均得到 APPLIED；每份重复请求得到 ALREADY_APPLIED，背包完全不变，原钻石没有被消费。
- 重复登录/检查点不改写或增加原成功复盘。

## 范围

只证明这一次“结算已保存、还未开始领取”的两进程边界，不证明 INTENT/APPLIED_UNCONFIRMED 各阶段硬退出、领取过程中断电、真实 SAO 钱包/经验、离线全队或多客户端故障矩阵。
本轮只修改测试与故障工具，不修改运行玩法、默认配置、协议或用户测试存档；不需要重启正在试玩的客户端。奖励页字体和点击仍由用户检查，不能以恢复测试代替视觉验收。
默认回归执行 `gradlew.bat build runGameTestServer -PgameTestRunDirectory=run/gameTestServer-settlement-recovery-regression-2026-10-28 --offline --console=plain`，`logs/settlement-recovery-regression-2026-10-28.log`：完整构建成功，91 项 JUnit、41 项默认 required GameTest 全部通过，退出 0，1 分 46 秒。结算硬退出测试仍只在专用 namespace/参数下执行，未混入默认套件。
