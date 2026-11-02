# 原生双队与既有隔离现场：0.41.34

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

生产包仍为 `9e3ddc4e9793` 的 0.41.34，SHA256 `7f2fda3eace26417750cd0d62d9ef52f3d51690ea5a896cf6ed4269231727286`。仅使用已授权私有目录 `run/pack-acceptance-20261028-081137-fd148a65`、127.0.0.1:25579，四个磁盘入口/奖励开关保持 false；用户客户端和原服未改。

## 已完成的旧队恢复与中断记录

夹具提交 `0dd2874be429` 增加明确匹配当前现场的恢复场景：仅登录已知四个测试人物，处理第二队 `ba19b52d-c38c-44bd-a024-51fcddee274d` 的两个回程，保留槽位 0 / `f99ebe03-0e35-4e73-822a-063b6b01c318` 的保护隔离。它逐项比较隔离局持久记录与租约，不重试清理、不释放隔离槽位，不处置未知结晶。

独立导出 `.gradle/native-dual-fixture-0dd2874be429-031fcb4c` 的 `packTestJar --offline --console=plain -x downloadMCMeta` 成功，15 秒。运行前完整备份 `validation-history/native-dual-retained-0dd2874-6c1865bf`，附加包 SHA256 `26f81b30b726f9033866e8bcc1ffd596df932e1dcacc2916cff0f406552604c9`。PID 17976 的实际四人物登录、回程、库存/末影箱/钱包/迷宫区成长及保存读回通过；原生 XP 分别 0、440、0、40，均保持，待处理经验为零。原第二队生产清理释放槽位后，仅剩原隔离局，回程和票据为零。

报告 `logs/native-dual-recovery-probe-127e2d86-b032-47e8-bcde-9ec2e50adf18.json`，`passed=true`，SHA256 `794fccf08c3fcef550f5f8f6c3f330e37d266f210eba0c1813032c8b620d976d`。这是已知场景恢复通过，不是全故障矩阵通过。

随后同进程的新两队分别生成到槽位 1、2，各 832012 次写入、215 生成 tick、176 张票据。第一队 `144b4347-3595-4a4a-a5f4-f50ea4380b2e` 在 17:58:03 清理释放；第二队 `8046219f-5eda-451f-9f58-9e3a6b28828d` 在 17:58:22 击败首领。之后观察到进程不存在、会话 76316 不存在、端口关闭，控制台没有正常 stop、没有最终双队报告，JFR 为零字节，未见新增 hs_err。中断原因未知，不推断为代码崩溃、正常退出或完整双队通过。

- 控制台 `logs/pack-native-dual-retained-0dd2874-20261029.log`，SHA256 `ec416ca2670ea7af1a5bd171d654da06a7ffb2a5f7e8aa835e66dc40e4be4b74`。
- 保全 `logs/native-dual-retained-0dd2874-interruption-20261029.json`：957 份受保护文件中 939 份字节保持，2 份 properties 仅注释变化，16 份预先允许的旧测试人物文件因恢复保存更新；269 份其他人物文件保持，无意外变更。
- 附加包已归档为该备份目录的 `fixture-retained-interrupted.jar`，未清除世界恢复日志或回滚人物文件。

该次新人物：`dg_dual_a0` / `00ea8004-d175-41db-a041-25ca7da3224c`、`dg_dual_a1` / `309deb7f-4362-437d-b38c-0519cdb3899b`、`dg_dual_b0` / `cfef9688-f86d-4189-b982-c6a03b8bffa2`、`dg_dual_b1` / `7a109c2a-9218-4a34-94f0-f0b8d76fd816`。

## 独立运行器重跑

夹具提交 `c807142dfd7f` 只增加上述固定人物/局的恢复场景，生产代码不变；独立导出 `.gradle/native-dual-fixture-c807142dfd7f-3560fe2d` 的 `packTestJar` 编译/重混淆成功，16 秒，未跑 JUnit 或完整 GameTest。日志 `logs/native-dual-detached-fixture-20261029.log`，SHA256 `177c56395e1525c91bb449d08c202aff61c878e1df2fd8b941c8fc7af493f0cb`，附加包 SHA256 `09915e16ce9fcbebcbcb3982afa47aa4132c55d17236bbc85ce479a577e229d5`。

运行前完整备份 `validation-history/native-dual-detached-c807142-3dc419c8`，973 份保护文件。隐藏独立 Python 运行器 PID 21284 启动 Java PID 13772。恢复夹具因固定要求两个回程标记而失败，未启动新队；实际服务器显示回程为零、原第二队在 CLEANING。停服后只读解析四个人物文件，均已位于主世界且无 active_run/return_location，说明上轮已保存回程。此为夹具预期过窄，保留失败记录，不把中断反推成完整通过。

运行器已发送正常 stop，Java 退出 0，JFR 10670715 字节；报告 `logs/native-dual-recovery-probe-786b3e0d-93e2-4937-a02d-f278e9e442b6.json` 为 false，SHA256 `8f3eda0dc40703196c2b2b2c08ddd5a205e0c23f420472cf5b54ebfb8ece69b7`。保全 `logs/native-dual-detached-c807142-preservation-20261029.json`：973 份受保护文件中 955 份字节保持，2 份仅 properties 注释变化，16 份为预先允许的测试人物文件；285 份其他人物文件保持，无意外变化，附加包已归档 `fixture-recovery-precondition.jar`。没有最终双队报告。

后续提交 `8d2be20ec127` 对这一明确场景先读取四个人物的真实存档，要求回程所有权属于指定中断局，按零或两个实际待回程人物与世界标记核对；其他原场景仍要求两个标记。独立导出 `.gradle/native-dual-fixture-8d2be20ec127-882d37d9` 的 `packTestJar` 成功，15 秒。只改夹具，不改变生产回程或隔离规则。日志 `logs/native-dual-disk-return-fixture-20261029.log`，SHA256 `69dcbd082b34aca6b77372d927d0dc765523f37d481cdb69f5374352692d9722`。再次完整备份 `validation-history/native-dual-detached-8d2be20-99af4262` 后启动独立运行器，附加包 SHA256 `56eda36838918656c9be551096eca5866bcffcb0fac7a9bd53f43efcf049b46f`。

## 双队完整主线回归通过

独立运行器 PID 17392、Java PID 12260。首先实际登录上一轮固定四人物，确认零待回程与人物文件一致，库存/末影箱/钱包/迷宫区成长及 XP 保持，等待原第二队生产清理释放。恢复报告 `logs/native-dual-recovery-probe-97cff072-2e38-45eb-b79e-c1bc04562ea5.json` 为 true，SHA256 `ddfae53962ed92b1a710b618265ab7f6ea17683d79db845f159b476a525f02e1`。

之后四个新人物通过实际原生邀请建立两支队伍，生产大厅准备/开始，分别使用槽位 1、2；各 832012 次生成写入、215 个生成 tick、176 张票据。双向同位置实际跨队伤害被拒绝，第二队挣得主线钥匙后另一队不能消耗它或开门；第一队封印大厅传送不移动第二队。第二队停留主线第一间战斗房，第一队完成首领并离开、生产清理后，第二队人物/进度/钥匙/煤炭门/票据/返回标记保持，随后第二队继续完整主线。两队成功记录互不串入。

| 项目 | 第一队 | 第二队 |
| --- | --- | --- |
| 实例 | `96d9f976-5810-4ff5-9be9-474006403a5f` | `b3a8e43e-00c1-4a05-93f9-9d2ce75877a3` |
| 成员 | `28183b80-e005-4e75-83f5-15df577251a6`、`250bc918-a5d7-44a5-9869-310653e14fba` | `5ba730fe-deae-4a20-9f51-951fe8bdb10a`、`bcc7947d-6d3c-4086-9119-29f760d83adc` |
| 主线门 / 确认死亡 / 原生 XP 链接 | 4 / 17 / 17 | 4 / 17 / 17 |
| 两人物本局原生 XP 增量 | 0、440 | 0、440 |
| Embedded 连接驱动 / 保活回复 | 3312 / 10 | 2882 / 10 |
| 全队封印大厅转场、首领、独立战绩、正常回程、清理 | 通过 | 通过 |

最终双队报告 `logs/native-dual-trial-probe-361eda5b-fd79-4837-b024-cfedfd414c02.json` 为 true，SHA256 `14dfd1540440e6b2b27c857924bce7eecd4fbdc845f519fa74cccc52454509d7`。原隔离局持久记录和租约保持；最终 `runs=1, lobbies=0, pendingReturns=0, tickets=0`，槽位 0 仍为原 QUARANTINED，槽位 1/2/3 FREE。不能把这个结果写成所有槽位均已清空。

正常 `stop` 后 Java 退出 0、端口关闭、所有维度保存完成，运行器终态收据 `.gradle/native-dual-disk-return-process.json` 与报告一致。测试附加包已归档 `validation-history/native-dual-detached-8d2be20-99af4262/fixture-dual-passed.jar`。保全 `logs/native-dual-disk-return-8d2be20-preservation-20261029.json`：973 份受保护文件中 955 份字节保持、2 份 properties 仅时间注释变化，16 份为预先允许的旧四人物保存文件；285 份其他人物文件保持，无意外变更，配置语义保持。

停服后只读解析实体区块，与本轮运行前完整备份逐项比较原未知物品 `5807e079-af9f-4057-92de-000f4bfec4c6` 的完整实体 NBT，完全相等，仍为一枚原生月光结晶。证据 `logs/native-dual-retained-asset-8d2be20-20261029.json`；实体规范 JSON SHA256 `3c3c62efcb48086542bd06025c5d34fdcbe94439ed987af28271829e0f332088`。未删除、领取、猜测归属或绕过隔离清理。

- 控制台 `logs/pack-native-dual-detached-8d2be20-20261029.log`，SHA256 `07f2ba9e0b1278811fc31300b6fd85f427960921431868063b6d24bd34d2e770`。
- JFR `logs/native-dual-detached-8d2be20-20261029.jfr`，23465661 字节，SHA256 `5176869f7fb18241685f65e538d557524d95de561eade17422e22f95d5e07ca1`，本轮未分析，不作性能出口通过证据。

这是第一次取得本夹具完整双队主线终局通过的报告，前述中断与夹具失败仍保留。没有重跑其他全套检查，未发布奖励、未更新用户客户端或原服。

夹具使用实际原生队伍、服务端人物、生产生成/战斗/经验/回程接口，但以高伤害、无敌和逐房传送驱动，并用 EmbeddedChannel 回复保活；不替代真人远程输入、技能/宠物全兼容、平衡、奖励经济或长期性能验收。
