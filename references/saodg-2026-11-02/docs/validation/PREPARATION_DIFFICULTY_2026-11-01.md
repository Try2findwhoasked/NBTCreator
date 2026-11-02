# 队伍准备与四档难度验证

日期：2026-11-01。基线：Minecraft 1.20.1、NeoForge 47.1.106、Java 17、Gradle 8.8。此记录仅描述本次本地验证，不代表整合包或生产验收。

## 最终检查

- `gradlew.bat build -x test --console=plain`：通过，包含 Java / GameTest 夹具编译、资源处理与打包。产物为 `build/libs/saodg-0.5.3-neoforge-dev.jar`。
- 定向 JUnit：8 项通过，0 失败/跳过。`DungeonMenuContextTest` 5 项，`EncounterTuningTest` 1 项，`RewardTuningTest` 2 项。验证菜单跟随与同局结果定位、星标与存活预算边界、极难经验及旧参数兼容。
- 定向 GameTest：`saodg_config,saodg_lobby,saodg_start`，10 项全部通过。新增了逐成员风险确认、队伍修订失效、缺少 FTB 时禁止默认解锁、难度与奖励配置序列化、旧日志默认行为验证。专用世界为 `run/menu-difficulty-tests`。
- `python tools/verification/content_audit.py --check`：通过，80 个活动房间、5 个受保护非活动定义、340 个生产模板；无审计错误。
- `git diff --check`：通过。
- `gradlew.bat runClient -PadminConfigPreview`：通过，检查了风险提示/确认窗口、合并后探索页与战报、难度配置及小尺寸配置页面截图。截图位于 `build/previews/admin-config/`。这是无服务器的投影预览，不是联机验收。

定向 JUnit 命令：

```powershell
.\gradlew.bat test --tests cn.saodg.domain.encounter.EncounterTuningTest --tests cn.saodg.domain.reward.RewardTuningTest --tests cn.saodg.client.DungeonMenuContextTest -I build/menu-difficulty-test.init.gradle --console=plain
```

临时 init 脚本仅把报告输出到 `build/test-results/menu-difficulty` 和 `build/reports/tests/menu-difficulty`，隔离与长时全量扫描的结果文件；未改变测试代码或过滤器。

GameTest 实际通过命令：

```powershell
$env:JAVA_HOME = 'D:\Java\jdk-17'
$env:JAVA_TOOL_OPTIONS = '-XX:TieredStopAtLevel=1'
.\gradlew.bat runGameTestServer '-PgameTestNamespaces=saodg_config,saodg_lobby,saodg_start' -PgameTestRunDirectory=run/menu-difficulty-tests --console=plain
```

第一次运行暴露两处旧夹具预期（管理项仍写死 36 个、精英仍期望旧通关前置）及预览滚动定位失效，已更新并重新验证。一次普通 JVM 重跑在启动加载阶段出现 C2 编译后的 `CompoundTag.getList` 原生访问冲突（`EXCEPTION_ACCESS_VIOLATION`，`run/menu-difficulty-tests/hs_err_pid2256.log`）；此后使用上述仅当前进程环境参数关闭 C2，最终测试通过。没有修改系统 Java 设置；不能将该结果描述为默认 JVM 参数下全量通过。

## 未完整完成的检查

最初启动过未过滤 `build`。其中 `ArenaLayoutTest.everyDifficultyKeepsFixedRoomsReservedPortalAndFourCellBossIsolation` 已通过，覆盖包含极难的四档、每档 512 个种子；简单和标准各 10000 个实际内容布局种子也已完成。完整扫描耗时较长，在高难 10000 种子扫描期间主动停止，Gradle 最终报告失败退出；该次运行不作为全量构建成功证据。最终产物使用明确的 `build -x test` 打包，并单列上面的定向结果。

尚未运行完整默认 GameTest，也未执行 SAO/FTB 整合包的真实双客户端、通关/重置、跨队伍、重启和 NPC 游戏内验收。没有部署至服务器。

## SAO 项目配合结果

已按用户授权在 SAO 项目建立 NPC 对接会话。对方已实现地牢引导员聊天入口，并报告 NPC/UI/任务历史/任务线等静态验证通过；交接文件为该项目 `docs/SAODG_NPC_HANDOFF.md`。SAODG 另外对实际 `ftb-quests-forge-2001.4.22.jar` 执行 `javap`，核实 `TeamData.get(Player)`、`isCompleted(QuestObject)`、`BaseQuestFile.getID(Object)`、`getQuest(long)` 和 `ServerQuestFile.INSTANCE`，未将静态 API 核对称为真实联机通过。

行为与存档/配置说明见 [DIFFICULTY_AND_PREPARATION.md](../DIFFICULTY_AND_PREPARATION.md)。网络协议为 27，客户端和服务端需要同步更新。
