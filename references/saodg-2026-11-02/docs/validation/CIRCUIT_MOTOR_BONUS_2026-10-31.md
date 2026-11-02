# 继电机房 Y 清房与电动机 Δ 追加挑战

日期：2026-10-31。工作区版号保持 `0.41.65-dev`，未提交、未部署、未推送、未打标签。当前记录只证明下述独立源码快照的定向验证；仓库统一集成与 Git 操作交由维护聊天收尾。

## 最终行为

- 初始 Δ 不给追加奖励。U2、V2、W2 汇接 STAR、三个首端隔离后，立即按 Y 形成功清房并记录原解谜参与者。可以直接离开。
- Y 完成后，右键原复位台可选启动电动机；不需要潜行。面板在可触及控制台时提供“启动电动机（可选）”，服务端仍检查真实在线对象、成员行动资格、近距视线、实例阶段和谜题修订号。
- 启动后，控制器按“星点 → 断开 → Δ → 自身绕组首端（短路）”切换。目标 Δ 为 U2–V1、V2–W1、W2–U1。清房状态在改线过程中保持完成；指示点和连线颜色反映追加目标。
- Δ 成功后每房仅记一次 `circuit_bonuses`，有效追加参与另记独立证明。通关且奖励启用时，每名符合既有出勤/行动资格的成员在基础个人奖励中增加 **60 副本经验/房**。不增加货币或原生 SAO 经验，不绕过既有奖励所有者、准入或事务。
- Y 之前短路仍判本房失败；Y 之后短路只永久终止追加挑战，保留 Y 清房、评分和原参与证明。两种短路都保留爆炸伤害与延迟雷击，普通复位不恢复追加挑战。
- Δ 成功后接线锁定，启动、接线和领取请求重放均不重复发奖。

## 改动文件

领域：`domain/puzzle/PuzzleProgress.java`、`DeltaStarWiring.java`、`domain/reward/RewardProfile.java`。

应用与保存：`application/EncounterService.java`、`RoomInteractionService.java`、`InstanceService.java`、`RewardService.java`，以及 `infrastructure/persistence/RunRecord.java`。

客户端与文案：`client/DungeonScreen.java`、`assets/saodg/lang/zh_cn.json`。以上 Java 路径均相对 `src/main/java/cn/saodg/`，语言文件相对 `src/main/resources/`。

测试：扩展 `DeltaStarWiringTest`、`RewardTest`；新增 `src/gameTest/java/cn/saodg/CircuitMotorGameTest.java`。当前内容清单、房间制作指南和特殊房替换计划同步更新。

## 实际验证

使用 `D:/Java/jdk-17`、离线 Gradle 8.8、Forge 47.4.10。在 `.gradle/circuit-motor-validation-20261031/` 复制工作区源码并单独编译，保留 `source-sha256.json`；没有执行根目录 `clean`，没有复制或修改作者资产、世界、参考仓库。

首次执行：

```powershell
.\gradlew.bat --offline test --tests cn.saodg.domain.puzzle.* --tests cn.saodg.domain.reward.RewardTest build runGameTestServer -PgameTestNamespaces=saodg_circuit -PgameTestRunDirectory=run/gameTestServer
```

其中定向 JUnit **22/22 通过**：DeltaStarWiringTest 8、PuzzleTest 5、StatePuzzleTest 3、RewardTest 6；`build` 的编译、重混淆打包、全部 GameTest/packTest 夹具编译完成。测试带过滤器，**不代表默认完整 JUnit 套件通过**。同一命令随后运行的 GameTest 首次为 3/5，两个新房间夹具在准入时因未启用测试所需的 `keepInventory` 被拒绝，尚未进入玩法断言；补齐夹具配置并恢复规则后重新执行：

```powershell
.\gradlew.bat --offline runGameTestServer -PgameTestNamespaces=saodg_circuit -PgameTestRunDirectory=run/gameTestServer-2
```

最终 **5/5 Forge GameTest 通过**，`BUILD SUCCESSFUL`，包含：

1. 非法场景元数据在激活前拒绝。
2. 原短路爆炸/延迟雷击、跨房保护、方块保护、永久失败、不得分与重复操作保护。
3. 追加奖励的真实个人存盘事务、资格排除、奖励日志重载与十次领取去重；试炼实际为 120 基础 +60 追加 =180 副本经验。修改冻结奖励数量被拒绝。
4. 实际生成房间内 Y 先清房、远程启动拒绝、物理控制台启动、旧修订号拒绝、Δ 一次性成功、奖励标识 NBT 往返与重复保存项拒绝。
5. 实际生成房间内追加短路后保留 Y 评分/参与/清房，不能复位或重复取得追加奖励，最后完整清理实例。

日志：`logs/circuit-motor-isolated-initial-20261031.log`（首轮定向单测、构建与准入夹具失败）、`logs/circuit-motor-isolated-20261031.log`（最终 5/5）。更早直接在共享根目录的测试遇到并发重编译，导致运行中 `RoomInteractionService$Member` 缺失，记录于 `logs/circuit-motor-runtime-20261031.log`；该失败没有当作玩法验收，后续改用独立快照。新增奖励夹具最初一次缺少 `PlayerSaveBarrier` 构造参数，已在运行前修正。

候选开发包：`build/verified/circuit-motor-20261031-b847ac93/saodg-0.41.65-dev.jar`，同目录包含 `verification.json`、`SHA256SUMS.txt` 与独立源码文件散列清单。原构建留在 `.gradle/circuit-motor-validation-20261031/build/libs/`。

SHA-256：`b847ac930e069403c5b4ecadec61db5bb3e8276978e2e080167f6adb7b3043a7`。

包内 `zh_cn` 与生成的 `en_us` 相同，追加文案齐全，包含 refmap，不包含 GameTest 夹具。修复后的变化仅为测试配置，不改变此运行时 JAR。

## 保存与范围限制

新增可选 `circuit_bonuses` 整数集合；缺失时按空集合读取，拒绝重复、非完成或已失败房间。追加数量进入冻结奖励指纹；没有追加奖励的旧指纹保持不变，不追补旧局。继续沿用现有活动局重启处理策略，没有新增活动谜题跨进程续玩能力。

本次未运行默认完整单测、真实双客户端、完整整合包/SAO/KubeJS 所有者实机支付、客户端视觉或性能验收。测试玩家为真实服务端对象配合 EmbeddedChannel；这不等同真人网络联机。独立快照建立后其他聊天仍修改了共享根目录的声音、实体和事件代码，最终统一源码仍需由维护聊天回归，本记录不覆盖那些后续改动。
