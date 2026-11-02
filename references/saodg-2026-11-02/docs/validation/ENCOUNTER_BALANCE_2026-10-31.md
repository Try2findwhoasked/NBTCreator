# 怪物分布与副本战斗乘数验证（2026-10-31）

> 后续状态：用户已决定取消额外玩家战斗倍率、恢复怪物原生数值，保留新增怪物和分布。本文为变更前历史证据；当前实现与验证见 [NATIVE_COMBAT_STATS_2026-10-31.md](NATIVE_COMBAT_STATS_2026-10-31.md)。

## 范围

Forge 1.20.1 / 47.4.10，Java 17，当前共享工作区开发代码；不表示整个脏工作区已通过发布验收。经验获取、升级经验阈值和通关经验属于其他任务，本任务仅读取副本等级。行为与公式见 [ENCOUNTER_BALANCE.md](../ENCOUNTER_BALANCE.md)。

## 本任务修改文件

以下仅列本任务触及的路径，不把同一文件中其他任务的改动归入本任务：

- `src/main/java/cn/saodg/application/EncounterService.java`：刷怪目标、分区分散放置、弓手/巨兽槽位、窄空间替代、共享属性预算、出生装备指纹、首领/守卫队伍倍率。
- `src/main/java/cn/saodg/application/InstanceService.java`：两种新增实体的身份校验、生成数量的经验容量预留、出生装备一致时允许清理。
- `src/main/java/cn/saodg/domain/encounter/EncounterBalance.java`：数量、存活预算及怪物数值规则。
- `src/main/java/cn/saodg/domain/encounter/RoomEnemyRoster.java`：新增独立支援实体 ID 列表。
- `src/main/java/cn/saodg/domain/progression/DungeonCombatCurve.java`：1.00–1.50 的有界指数战斗乘数。
- `src/main/java/cn/saodg/infrastructure/persistence/RunRecord.java`：仅允许新增明确实体 ID 保存装备指纹，保持旧无指纹日志可读。
- `src/main/java/cn/saodg/platform/forge/DungeonCombatScaling.java`：伤害事件中的攻击和有效生命倍率、怪物攻击尖峰上限。
- `src/main/java/cn/saodg/platform/forge/InstanceEvents.java`：接入伤害倍率；禁止副本生物破坏方块及巨兽伤害非玩家。
- `src/main/java/cn/saodg/platform/forge/RoomEnemyTypes.java`：精确实体类校验及装备清理规则。
- `src/main/java/cn/saodg/platform/forge/RoomSpawnPlacement.java`：安全地面扫描、分区分散放置、高点偏好及整身碰撞检查；保留旧单点选择 API 的谓词语义。
- `src/main/java/cn/saodg/platform/forge/SaodgRegistries.java`：新增实体及属性注册。
- `src/main/java/cn/saodg/platform/forge/entity/DungeonArcher.java`、`DungeonBrute.java`：原版弓手/劫掠兽 AI 的副本身份实体。
- `src/main/java/cn/saodg/client/ClientRegistration.java`：两种实体的原版渲染器。
- `src/main/resources/assets/saodg/lang/zh_cn.json`：两种实体的中文名称。
- `src/test/java/cn/saodg/domain/encounter/EncounterBalanceTest.java`、`src/test/java/cn/saodg/domain/progression/DungeonCombatCurveTest.java`：数量/存活容量/数值差距/指数曲线边界。
- `src/gameTest/java/cn/saodg/RoomPopulationGameTest.java`：逐个生产战斗房间放置并验证覆盖，缺失内容目录必须失败。
- `src/gameTest/java/cn/saodg/DungeonCombatScalingGameTest.java`：真实服务登记、在线测试玩家、事件总线和已登记箭矢伤害；校验取消事件、阶段结束及玩家属性/持久数据不被修改。
- `src/gameTest/java/cn/saodg/MinibossSpawnGameTest.java`：调整新 HP 断言，增加弓手指纹往返和外部改动保护断言。
- `src/gameTest/java/cn/saodg/CombatGameTest.java`：血房第二波的数量断言按新路线预算计算。
- `src/gameTest/resources/data/saodg_population/structures/empty.nbt`：复用现有空白测试模板。
- 本说明与 `docs/ENCOUNTER_BALANCE.md`。

## 实际验证

最终使用独立输出目录，避免并发任务改写运行中的 class/resource 输出。临时初始化脚本位于忽略的 `build/encounter-isolated.init.gradle`：

```groovy
allprojects { layout.buildDirectory.set(file('build/encounter_validation')) }
```

1. 运行级验证：

```powershell
.\gradlew.bat -I build/encounter-isolated.init.gradle --project-cache-dir .gradle/encounter-validation runGameTestServer '-PgameTestNamespaces=saodg_population,saodg_miniboss,saodg_room_rewards' -PgameTestRunDirectory=run/gameTestEncounterBalance20261031d --console=plain
```

结果：**4/4 required tests passed，BUILD SUCCESSFUL（2m 58s）**。日志 `logs/encounter-balance-gametest-d.log`；成功加载 79 个房间，并逐个放置验证其中全部 **68 个生产战斗房间**。每个房间按更高的 8–16 身体压力数量检查完整单元覆盖及高点弓手偏好。其余三个运行夹具检查真实小首领/首领生成与装备指纹、玩家/箭矢倍率，以及旧奖励/安全点逻辑。默认编译了全部现有 GameTest 夹具；血房数量断言已更新，但本轮未执行完整 `CombatGameTest` 流程。

2. 针对性 JUnit：

```powershell
.\gradlew.bat -I build/encounter-isolated.init.gradle --project-cache-dir .gradle/encounter-validation test --tests '*EncounterBalanceTest' --tests '*DungeonCombatCurveTest' --tests '*RoomEnemyRosterTest' --tests '*EncounterTest' --tests '*NativeEquipmentIdentityTest' --console=plain
```

结果：**13 tests，0 failures，0 errors，0 skipped；BUILD SUCCESSFUL（16s）**。日志 `logs/encounter-balance-junit-final.log`，XML 位于 `build/encounter_validation/test-results/test/`。覆盖指数曲线在不同等级上限下的范围/单调性、当前长路线只杀星标时的存活预算、怪物差距、已有波次/死亡推进和装备资产边界。

3. `git diff --check -- <本任务触及的已跟踪代码路径>`：通过；仅存在已有换行规范提示。没有执行整个项目 `clean` 或默认完整 `build`，未生成供游戏安装的已验收发布包。

### 前期失败和修复

- 初次房间扫描已逐个覆盖 68 个生产战斗房间；旧小首领夹具只搭建每个锚点附近 3×3 地板，暴露逐两格采样不足及蜘蛛/大型身体被先前槽位挤占的问题。改为逐格候选，并对大型身体采用受管小型近战替代。
- `build/completion-rewards-gametest-a.log` 中 `keysGlowRandomPlacementAndChestUseRealWorldState` 的安全点失败已复现：新整身检查将旧接口的 `narrow::equals` 点谓词错误应用到了头部高度，导致原有有效单点被拒绝。将头部范围检查限定到新的分布放置接口，旧奖励夹具纳入复测。
- 新倍率夹具最初直接跨维度传送，被现有实例隔离拦截；改用服务已有的受控传送入口，没有放宽生产隔离检查。
- `logs/encounter-balance-gametest-c.log` 的三个 `definition=null` 是资源加载失败的级联结果：运行时找不到 `01_triumph_stairs/p02_body.nbt`，但源码与随后检查的输出文件都存在。共享 `build/resources` 并发改写期间本轮不能作为玩法通过证据。后续使用独立输出 `build/encounter_validation`、独立项目缓存及独立世界复测，没有放宽内容检查。

## 未验证范围

- 未运行默认完整 JUnit 或完整 GameTest 集；不声称历史钱包隔离失败已解决。最终全工作区回归由监督任务统一执行。
- 未运行带 SAO/Cataclysm 实际整合包的多人、重连/重启、持久装备变化及长时间负载验收；当前运行验证使用隔离 Forge 服务端。
- 测试验证出生覆盖及高点偏好；原生 AI 后续追踪、走位和实际射击手感仍需客户端实测。原生装备/抗性仍可能影响实际承伤。
- 不执行整体 `clean`，不覆盖作者放在 `build/` 下的资产，不安装到实际游戏目录，不推送或打发布标签。
