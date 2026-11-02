# 取消额外玩家倍率并保留怪物原生数值

> 后续状态：2026-11-01 按新需求增加 JSON 分档怪物属性、密度与怪物池，当前规则见 [DIFFICULTY_JSON.md](../DIFFICULTY_JSON.md)。本文保留为此前恢复原生属性的历史验证；玩家额外战斗倍率仍保持取消。

2026-10-31。落实用户后续决定：取消副本额外玩家数值倍率；保留新增怪物、分区分散生成和高点远程；怪物先保留原生数值；经验与奖励逻辑不动。

## 当前行为

- 删除 `DungeonCombatScaling`、`DungeonCombatCurve` 和伤害事件订阅，不再按副本等级乘输出或除承伤；不保留默认开启的实验开关。
- 删除普通波 32–40 基础 HP、4–5 基础攻击的夹限，移除角色/队伍 HP 和攻击倍率、统一护甲/韧性及怪物单次攻击上限。
- SAO、Cataclysm、原版实体与新增弓手/巨兽的原生战斗属性不被 SAODG 覆盖，不清空已有属性修饰。新弓手继承 Skeleton，巨兽继承 Ravager；弓手保留原有高点偏好、远程距离和目标跟踪改善。
- 只有 `DungeonEnemy` 这一 SAODG 自有构装体类使用既有自有遭遇/首领参数，且不再加人数或角色倍率。独立模式自有首领仍采用定义的 320 HP；自有阶段守卫使用原定义，原版僵尸守卫保留僵尸数值。
- 保留整条路线的数量预算、分散布点、整身碰撞检查、窄空间替代、怪物类型登记、星标/小首领身份、原生投射物租约、建筑防破坏和出生装备资产保护。
- 不改玩家原生 SAO 属性、人物等级曲线、独立副本经验/等级、通关经验、奖励资格、经验预算预留、物品/宝箱/钱包事务。只影响此代码更新后新生成实体的初始化；不会扫描并重写已存活实体的旧属性或玩家存档。

## 修改文件

- `src/main/java/cn/saodg/application/EncounterService.java`：波次、原生首领和守卫不再统一覆盖战斗属性；调用仅配置自有构装体的初始化方法。
- `src/main/java/cn/saodg/platform/forge/RoomEnemyTypes.java`：新增 `prepareCombatStats`，保留原生属性和修饰，仅自有构装体应用原遭遇数值。
- `src/main/java/cn/saodg/platform/forge/InstanceEvents.java`：移除新增伤害倍率订阅，其他实例/安全事件保留。
- `src/main/java/cn/saodg/platform/forge/SaodgRegistries.java`：弓手不再把基础攻击设为 4，使用原版 Skeleton 属性。
- `src/main/java/cn/saodg/domain/encounter/EncounterBalance.java`：仅保留数量预算。
- 删除 `src/main/java/cn/saodg/platform/forge/DungeonCombatScaling.java`、`src/main/java/cn/saodg/domain/progression/DungeonCombatCurve.java` 和旧 `DungeonCombatCurveTest`。
- 将旧 `DungeonCombatScalingGameTest` 替换为 `src/gameTest/java/cn/saodg/NativeCombatStatsGameTest.java`：验证原生属性/修饰、支援怪基础数值、满级与低级的玩家/箭矢事件伤害不变、无新增伤害上限、人物属性和持久数据不被改写。
- `src/gameTest/java/cn/saodg/MinibossSpawnGameTest.java`：真实波次保留原生属性，小首领星标不附加数值倍率，自有首领不加队伍 HP 倍率；装备保护与日志往返断言保留。
- `src/test/java/cn/saodg/domain/encounter/EncounterBalanceTest.java`：保留数量/长路线预算断言，移除已撤销的统一数值断言。
- 更新 `docs/ENCOUNTER_BALANCE.md`，并在旧实现/评估记录顶部标明后续决策，不把历史倍率测试称为当前行为。

## 验证

使用独立输出，避免与其他任务的共享 `build/resources` 改写冲突；没有运行整体 `clean`。临时 init 脚本 `build/encounter-isolated.init.gradle` 内容：

```groovy
allprojects { layout.buildDirectory.set(file('build/encounter_validation')) }
```

针对性 JUnit：

```powershell
.\gradlew.bat -I build/encounter-isolated.init.gradle --project-cache-dir .gradle/encounter-validation test --tests '*EncounterBalanceTest' --tests '*RoomEnemyRosterTest' --tests '*EncounterTest' --tests '*NativeEquipmentIdentityTest' --tests '*RewardTest' --tests '*CompletionExperienceTest' --console=plain
```

结果：**18 tests，0 failures，0 errors，0 skipped；BUILD SUCCESSFUL**。日志 `logs/native-combat-stats-junit.log`。包括既有奖励与通关经验的定向测试。

运行测试命令：

```powershell
.\gradlew.bat -I build/encounter-isolated.init.gradle --project-cache-dir .gradle/encounter-validation runGameTestServer '-PgameTestNamespaces=saodg_population,saodg_miniboss,saodg_room_rewards,saodg_completion_rewards' -PgameTestRunDirectory=run/gameTestNativeCombatStats20261031 --console=plain
```

首轮结果：8 项中 7 项通过，覆盖原生属性/修饰、满级/低级玩家与箭矢伤害、全部 **68 个生产战斗房间**的完整占地覆盖与高点偏好，以及原有奖励/通关经验恢复。小首领夹具用 `AttributeMap.save()` 与新建实体比较时，因已初始化的属性槽位不同产生序列化差异而失败；该方法不是默认属性的规范化快照。修正为比较生命、攻击、护甲、韧性、移速、追踪距离和抗击退的实际数值，保留原生修饰专门测试与装备指纹断言，没有改动生产数值或放宽原生身份检查。

随后只复跑受影响的小首领夹具：

```powershell
.\gradlew.bat -I build/encounter-isolated.init.gradle --project-cache-dir .gradle/encounter-validation runGameTestServer '-PgameTestNamespaces=saodg_miniboss' -PgameTestRunDirectory=run/gameTestNativeCombatStatsMiniboss20261031 --console=plain
```

结果：**1/1 required test passed，BUILD SUCCESSFUL**。最终去重为 **8 项运行场景均通过**，并非声称首轮 8/8 全绿。日志分别为 `logs/native-combat-stats-gametest.log` 和 `logs/native-combat-stats-miniboss.log`。

打包验证：

```powershell
.\gradlew.bat -I build/encounter-isolated.init.gradle --project-cache-dir .gradle/encounter-validation '-Dnet.minecraftforge.gradle.check.certs=false' build -x test --offline --console=plain
```

结果：**BUILD SUCCESSFUL**，编译 main / GameTest / packTest 并完成 reobf 打包；显式跳过默认完整 JUnit，不能称完整测试集全绿。前两次构建在 ForgeGradle 的在线证书预检阶段失败（在线及 `--offline` 均触发预检），记录在 `logs/native-combat-stats-build.log` / `logs/native-combat-stats-build-offline.log`。最终仅在此次离线缓存构建命令关闭该插件预检，没有修改系统证书、项目配置或整合包；成功日志为 `logs/native-combat-stats-build-cached.log`。

主包为 `build/encounter_validation/libs/saodg-0.41.65-dev.jar`，不是同目录的 `pack-acceptance` 测试附件。实际打开主 JAR 检查：两个倍率类已删除，新增弓手/巨兽仍在，运行夹具未入主包。散列与检查结果记录于 `build/native-stats-package-verification.json`。

另已确认独立编译输出不再含两个倍率类。对修改前保存的 15 个经验/奖励/进度相关实现及配置逐字节 SHA-256 比对，均未变化，清单在忽略目录 `build/native-stats-preserved-files-before.json`。`InstanceService` 也未改动，因此经验容量预留逻辑保持。此次未修改任何遭遇/首领/奖励 JSON。

## 边界

- 定向开发环境验证不等于 SAO/Cataclysm 实际整合包的多人、重连、持久属性、平衡或性能验收。
- 保留原生数值意味着原生不同等级怪物仍有差异，不声明当前随机池已经完成统一平衡。
- 未部署到实际客户端或服务端，未修改实际存档，未执行整体 `clean`，未提交/推送/发布。
