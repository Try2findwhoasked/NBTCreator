# 实例进程中断与真实重登恢复

2026-10-28，0.35.0-dev / Forge 47.4.10 / Java 17。仅新增隔离测试与运行工具，未改生产恢复策略。

执行 `python tools/verify_process_recovery.py --java-home D:/Java/jdk-17`，外层返回 0，完整两阶段通过。
独立世界：`run/gameTestServer-recovery-20261028-035410-18f78781/world`；所有文件保留，未复用/删除既有开发或正式世界。
来源环境仅 Minecraft、Forge、SAODG，没有 SAO/KubeJS/FTB/TACZ。

## 第一进程

专用 `saodg_recovery` 命名空间只注册一个夹具，普通 37 项不在此进程运行。
真实 PlayerList 成员从明确安全的原位置/创造模式进入实例，携带 3 颗钻石及测试钱包字段。
主日志实际检查点与世界保存完成后，读取真实玩家文件，确认仍在 `saodg:dungeon`、冒险模式。
夹具将 run/player/slot/原位置写入独立 AtomicNbtStore，之后调用 `Runtime.halt(73)`，跳过正常停服、中止、回程和清理回调。
运行器必须同时确认非零进程结果、准备标记、持久夹具以及 Gradle 报告的 JVM 退出码 73，才能进入第二阶段；不能把任意异常退出当成已测试崩溃。

实际 run `01a65857-bb06-4baa-8acc-50622fc1a6f2`，测试成员 `de8f5394-5c68-4eb1-8b96-975c50b88531`。
日志 `logs/process-recovery-20261028-035410-18f78781-crash.log`，阶段 53 秒，预期 Gradle 失败，73 是故意的 JVM 退出结果。

## 第二进程

同一目录重启，生产启动流程读取 EXPLORING 记录，中止未完成实例；缺少运行布局快照时保留未知统计。
夹具验证恰一条持久化 ABORTED/重启原因复盘，无分数/通关凭证、奖励 offer 或成功事实。
同 UUID 真实玩家重新登录，从磁盘载入人物，经生产登录/回程流程恢复原维度、位置与游戏模式。
内存及重新回读的人物文件均保留恰好 3 颗钻石；背包其他槽、盔甲和副手为空，测试钱包字段保持。
待生产清理结束后验证预约槽 FREE、运行记录移除、回程标记清空、活动票据归零；重复 loggedIn/checkpoint 后复盘内容不变且没有第二条。
返回人物文件的维度/模式/物品数量再确认后，写入通过标记；运行器核对其 run/player 与第一进程完全一致。

日志 `logs/process-recovery-20261028-035410-18f78781-recover.log`：唯一 required test 通过，退出 0，39 秒。
机器可读报告 `logs/process-recovery-20261028-035410-18f78781-result.json`，关联两进程的同一局和成员。

## 隔离与回归

普通任务仍默认 `saodg` 命名空间；新参数 `gameTestNamespaces` 可显式选择测试集，`recoveryStage` 仅接受 crash/recover。
中断夹具另要求工作目录名为 `gameTestServer-recovery-*`，普通世界/客户端任务不能意外执行 halt。
运行器始终新建带时间和随机后缀的专用目录，拒绝覆盖，失败保留全部文件；不附加/终止用户客户端或其他 Java 进程。
夹具只在 gameTest 源集，资源使用本工程已有空模板的相同副本，不进入发布 JAR。
编译阶段曾误用不存在的票据统计方法、遗漏网络初始化异常声明，均修正后执行上述实际试验；早期失败日志保留在 `logs/recovery-fixture-compile*.log`。
随后不带新参数运行默认 GameTest，同一原测试目录的 37 项再次全部通过：`logs/gametest-default-after-recovery-2026-10-28.log`，退出 0，1 分 20 秒。

本次只证明入口 EXPLORING、无活动战斗实体、已完成保存边界后的 JVM 硬退出及一次恢复，不等同于操作系统断电、任意写入中断、两队同时恢复、战斗中召唤物/弹体、奖励/经验/钱包事务的完整故障矩阵。
钱包字段只是独立环境中的保全探针，没有验证真实 SAO 钱包所有者。正式门禁保持。
