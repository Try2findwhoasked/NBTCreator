# 符文房开门、刷怪边界与战后出口

2026-11-02，Minecraft 1.20.1 / NeoForge 47.1.106 / Java 17，沿用 `0.5.4-neoforge-dev`。在已有未提交工作区上修改，保留其他功能改动。

## 行为

- Boss 战后出口以场地中央奖励区域为基准，优先放在入场方向的对面，候选距离依次为 12、16、20、10 格。候选受阻时检查其他方向；仍完整预检门体、地面、通路、实体和房间归属，不挖除原建筑或外来方块。
- 符文房最后一波的最后一个星标目标经服务端死亡确认后，立即进入 `BOSS_READY` 并激活整个符文门，不再生成或等待拾取该房间的实体钥匙。第一波结束仍须等待下一波；取消死亡、普通怪死亡不算通关。
- 保留持久化的一次首领入场授权（内部 `keys` 字段），进入实体门时仍只消耗一次并转移全队。重复完成不重复授权。普通主路通行钥匙继续使用原拾取规则，历史待拾取日志的处理逻辑保留。
- 符文房刷怪调查排除传送门平面及整个后方区域，包括门框两侧。最终选点再次约束实体脚部碰撞箱四角；大型怪的小型后备同样受限。平面和朝向都随房间旋转，不依赖固定世界 Z 坐标。

本次传送门修改没有改生产模板、网络协议或存档 schema。新开局采用新选点；现存实体的位置不会因这次改动被主动重排。本记录的独立开发验证不等同真人多人或生产整合包验收。

## 验证范围

- `RunePortalGameTest`：四种房间旋转下的门前/门面/门后判定、刷怪调查、立即开门、无实体钥匙、重复完成、持久字段回读、完整门洞和清理。
- `ExitPortalGameTest`：三种生产 Boss 场地各四种旋转，中央区域附近的门位、入场方向对面的优先级、受阻换向/全部受阻拒绝、真实玩家碰撞箱通路、逐个成员返回、外人/伪造门拒绝与清理。适配并行更新的多宝箱奖励区，使用实际开发材料奖励配置和全通关分数生成五箱，检查整排居中和全部回收。
- `CombatGameTest`：实际战斗服务中的两波符文怪位置、第一波保持关门、最后星标完成后开门、物理进门转场和重复入场拒绝。

## 实际结果

- 定向 JUnit 9 项全部通过，无失败、错误或跳过：`RoomEnemyRosterTest` 2 项、`SpawnPlacementPolicyTest` 2 项、`BloodRouteTest` 3 项、`PortalAlignmentTest` 2 项。日志 `logs/rune-boss-portals-unit-20261102.log`，逐类统计 `logs/rune-boss-portals-unit-summary-20261102.json`。命令中另一个 `*EncounterProgressTest` 通配符没有匹配到测试，不计入通过项。
- 独立世界 `run/rune-boss-portals-20261102` 的 4 项 GameTest 全部通过：符文门几何、开门特效、战后出口和完整战斗服务。战斗夹具实际完成 7 次正常攻略和 2 次故障周期，结束时实例及待返回记录均为 0。日志 `logs/rune-boss-portals-runtime-20261102.log`，任务耗时 4 分 55 秒。测试服务器已正常退出。
- 内容审计通过：80 个活动房间、5 个受保护非活动定义、340 个引用生产模板，无错误。日志 `logs/rune-boss-portals-content-20261102.log`。
- 改动 Java 文件的 `git diff --check` 通过。
- `build -x test` 编译、重混淆及打包成功，耗时 20 秒；该命令排除了 JUnit，不能计为完整未过滤构建通过。日志 `logs/rune-boss-portals-package-20261102.log`。

打包期间另一路奖励宝箱更新进入工作区，随后在 `run/rune-boss-portals-final-20261102` 复测。开门特效及完整战斗服务通过（再次完成 7 次正常攻略和 2 次故障周期）；五箱出口夹具漏填 `rewardProfile`，实际按缺省规则只生成一个箱子，因而五箱断言失败，遗留 slot 3 几何使随后符文门夹具被外来内容预检拒绝。日志 `logs/rune-boss-portals-runtime-final-20261102.log` 保留此次 2/4 通过结果。补齐夹具冻结的开发奖励配置，没有放宽五箱、空间或外来资产断言，使用新世界复测出口、符文几何及特效。

修正后，新世界 `run/rune-boss-portals-fixed-20261102` 的 3 项 GameTest 全部通过，耗时 2 分 23 秒，服务器正常退出。日志 `logs/rune-boss-portals-runtime-fixed-20261102.log`。结合上一轮通过的当前代码完整战斗服务，最终涉及的 4 项独立运行测试均有通过证据；三种 Boss 场地的 12 个旋转组合均与五箱奖励区同时通过。源码快照为 `logs/rune-boss-portals-fixed-source-20261102.json`。

最后比对快照时，另一路再次更新了 `DungeonRewardChest.java` 和 `RewardChestEntityGameTest.java`；本次三个传送门生产类及相关夹具未漂移。最终复测的主类编译为 `UP-TO-DATE`，使用的是归档包对应的已编译实现。这里交付固定哈希归档，不把随后新增的宝箱源码改动当成本轮已经重新编译或验证的内容。

最初尝试未过滤 `build`，随后在与本改动无关的每难度一万种布局种子遍历期间主动停止测试工作进程，改用上述定向范围；由此产生的连接中断和 `test FAILED` 保留在 `logs/rune-boss-portals-build-20261102.log`，不是一次已完成的全套验证。不能据此报告默认完整构建/测试全绿。

## 复现命令

```powershell
$env:JAVA_HOME = 'D:\Java\jdk-17'
.\gradlew.bat test --tests '*EncounterProgressTest' --tests '*PortalAlignmentTest' --tests '*BloodRouteTest' --tests '*SpawnPlacementPolicyTest' --tests '*RoomEnemyRosterTest' --offline --console=plain --max-workers=1 '-Dorg.gradle.jvmargs=-Xmx1536m -Dfile.encoding=UTF-8'
.\gradlew.bat -I tools/ci/runtime.init.gradle runGameTestServer -x downloadAssets --offline --console=plain --max-workers=1 '-Dorg.gradle.jvmargs=-Xmx1024m -Dfile.encoding=UTF-8' '-PgameTestNamespaces=saodg_rune_portal,saodg_exit,saodg_combat' '-PgameTestRunDirectory=run/rune-boss-portals-20261102'
.\gradlew.bat -I tools/ci/runtime.init.gradle runGameTestServer -x downloadAssets --offline --console=plain --max-workers=1 '-Dorg.gradle.jvmargs=-Xmx1024m -Dfile.encoding=UTF-8' '-PgameTestNamespaces=saodg_rune_portal,saodg_exit' '-PgameTestRunDirectory=run/rune-boss-portals-fixed-20261102'
.\gradlew.bat build -x test --offline --console=plain --max-workers=1 '-Dorg.gradle.jvmargs=-Xmx1536m -Dfile.encoding=UTF-8'
python tools/verification/content_audit.py --check
```

未部署到客户端或服务器；真人多客户端、实际断线/进程重启和整合包原生战斗未由本轮定向验证证明。

## 产物

已核对 JAR ZIP 完整性、三处新逻辑的类/字节码标识、不包含 GameTest 类，以及全部 340 个生产 NBT 与源码逐字节一致；忽略的 `structures/beta` 制作素材按现有构建规则排除。记录 `logs/rune-boss-portals-artifact-20261102.json`。

归档包：`build/verified/rune-boss-portals-20261102/saodg-0.5.4-neoforge-dev.jar`，4,124,133 字节，SHA-256 `40319aad91ed0f541ecbb7284db41612a0be5791c53ab1edd550e6394c4b8d75`。归档与本轮 `build/libs` 产物哈希一致；后者可能被其他工作更新。该包同时包含打包时工作区的既有改动及并行奖励宝箱更新。
