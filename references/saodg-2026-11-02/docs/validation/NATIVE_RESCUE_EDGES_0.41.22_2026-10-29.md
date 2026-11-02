# 原生救援边界：0.41.22

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

运行时代码 `6fb9508ec225ec5c1ca2d5b05ec82ac3ae2f82a6`，最终夹具 `4281584`。0.41.22 包含 0.41.21 的房间门高配置和默认开放开发生成/启动规则；协议仍为 20，世界 writer schema 4，不新增存档格式变化。

静态原生字节码显示，救援完成后原局部倒计时仍可能为零，随后执行最终死亡；另一个边界是原生超时使用 GENERIC_KILL，原迷宫区死亡确认会将其与管理员清理一并忽略。本版仅为受管实例的成功救援保留同 tick 保护，并在原生超时实际 hurt 的同步作用域记录精确人物、伤害来源和实例。次 tick 仍须确认实际死亡且未取消；普通管理员 GENERIC_KILL 不计入。Mixin 继续受既有 SocialSystem 二进制散列门禁约束，没有开放任意版本绑定。

独立 Git 导出 `.gradle/source-release-6fb9508ec225-20261029-053154-cc365f31` 编译、重混淆及包内检查通过；41 个已提交结构、482 个中文键，未打入 beta。仅运行 1 项 `saodg_combat` GameTest，84 秒、正常退出 0，覆盖通关、首领、死亡取消/确认、重生回程和清理。日志 `logs/rescue-boundaries-04122-20261029.log`，SHA256 `711570482a672ccf09db90398d250674578908d12cb52998f367a3b59757ba18`。未运行 JUnit 或全套测试。

开发包 `build/verified/0.41.22-dev-6fb9508ec225-20261029-053154-cc365f31/saodg-0.41.22-dev.jar`，SHA256 `5aa06cecf7fcbbdc456e9aa19eea633f585f1e69b859f99bc000af95774a11ec`。未替换或启动用户客户端、原服。

## 授权私有整合包结果

仅在 `run/pack-acceptance-20261028-081137-fd148a65` 使用 `-Dsaodg.packNativeRescueEdgesAcceptance=true`，四个实际 PlayerList 临时人物属于同一原生社交队和一个预置 EXPLORING 实例。EmbeddedChannel 每个真实服务器 tick 按需驱动正常网络游戏处理器并断言一次 PlayerTick.END，共 2232 次连接更新；没有把救援进度加速写满。此夹具没有生成完整副本或走正式入口。

结果 `native-rescue-probe-7ceb7c79-34ec-4873-a8c7-2051c78584cb.json`，passed=true：

- 等待原生出生保护结束后，实际致死伤害消耗一枚原生复活结晶；存活、未倒地，恢复 10 点生命。
- 原生 200 tick 倒计时的最后一 tick 完成连续 60 tick 救援，保持存活；诊断值为 `SUCCESS_BRANCH_OBSERVED_UNVERIFIED`。该值没有单独证明最后 tick 保护分支已被观察，不据此提升整个适配器验收状态。
- 第一人救援 20 tick 后更换救援者，进度重置为 1；替代者完成自己的 60 tick。中断者没有额外奖励，两次成功分别由原生系统发放一枚币。
- 无人救援时实际经过 200 tick，执行原生最终死亡，钩子报告 `FINAL_DEATH_OBSERVED_UNVERIFIED`；下一 tick 迷宫区只确认一次死亡并淘汰。另一成员的普通 GENERIC_KILL 负对照不增加迷宫区死亡数。
- 实际 PlayerList 重生并接回现有连接，回到 overworld；实例归属为空、淘汰和只读复盘投影正确。回城后正常行动属于预期，不能用全局 canAct=false 判断已离开实例。
- 保持测试前库存、原生 XP 与钱包基线，仅扣除夹具加入的结晶、增加两笔原生成功救援币。测试期间显式使用 keepInventory=true 并于结束恢复，因此不代表所有死亡掉落配置已验收。
- 生产回程/中止/清理完成；最终在线人数 0，runs/lobbies/pendingReturns/tickets 均为 0，四槽 FREE。正常停服退出 0，端口 25579 已关闭。

测试前备份 `validation-history/native-rescue-edges-4281584-0be472ed`。841 个受保护文件中 839 字节相同，包括全部 169 个既有人物相关文件；其余两个仅 Java properties 时间注释变化，unexpected=[]。最终夹具 SHA256 `591ec5a3bf20606c3bf68c2d3c82c04c5a7de9e21668d4d38f71951059490154`，已从 mods 移至备份目录。

私有服已备份升级为 0.41.22，显式保持 `unrestrictedDevelopmentEntry=false`、原开发入口及奖励关闭；其余脚本/有效配置保持。该测试副本使用 schema 4，降级必须恢复升级前完整世界备份，不能只替换旧 JAR。

结果 SHA256 `26fbad94320b01efb82bb5b2a8710f30e891c2043b7c9d9b5eb50b34c8b1c151`；控制台 `logs/pack-native-rescue-edges-4281584-20261029.log` SHA256 `d5d490074fe51537764b5da0eb2d3f698d7c16eea71d095d526650abae24a2ae`。原始结果已复制到 logs，保全记录 `logs/native-rescue-edges-4281584-preservation-20261029.json`。

首次尝试 `6fb9508` 未等出生保护结束，实际结晶伤害被拒；第二次夹具 `282b3f0` 完成上述原生边界后，错误地要求回城人物不能行动。两次均记录 passed=false、正常清理停服和保全，不计入通过。最终只修夹具，运行时代码未再改变。

C06 增加以上有限证据，仍缺真实远程输入、所有取消/掉落配置、倒地时断线重连及完整多队原生通关矩阵；不据此勾选整个 C06 或发布验收。
