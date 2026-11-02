# 0.5.4 开发修改完整回归

2026-11-02，Minecraft 1.20.1 / NeoForge 47.1.106 / Java 17。此记录覆盖当前未提交工作区；不是发布或正式整合包验收。

本记录对应配置同步修复前的源码快照。后续已复现并处理配置重载竞态，新快照验证见[配置重载同步](CONFIG_RELOAD_SYNCHRONIZATION_2026-11-02.md)；不要把这里的通过数量和产物散列套用到后续修改。

## 已取得的证据

- Python共享工具测试35项全部通过，日志 `logs/full-regression-tools-20261102.log`。
- 独立客户端使用 `runClient -PadminConfigPreview` 完成自动截图并正常退出，日志 `logs/full-regression-ui-20261102.log`。已实际检查 `build/previews/admin-config/admin-config-difficulty.png` 与 `admin-config-small.png`：新增三项刷怪设置的中文标签、默认值、控件和新开局生效提示可见，640×480预览中的校验错误及操作区可见。这是默认值视觉夹具，不是客户端连接服务器后保存设置的端到端验收。
- 未过滤 `build` 成功，耗时17分19秒；JUnit 191项，189通过、2项可选原生二进制用例跳过，失败/错误为0。日志 `logs/full-regression-build-20261102.log`，完整XML及统计保存在 `logs/full-regression-unit-verified-20261102/`。两项跳过来自未提供参考JAR的 `SaoRangedItemsTest`，不代表已核验该可选原生弓二进制。

## 默认运行套件首轮与修正

首轮独立世界 `run/full-regression-core-20261102` 完成85项，6项失败，日志 `logs/full-regression-core-20261102.log`。

1. 数学房通路夹具将门洞内侧一格作为可站立目标，但该孤立房间没有图连接，新墙体封堵正确填满了其厚墙范围。调整通路夹具的孤立模板放置，省略图端口封堵，仍保留原本全部端口、刷怪点、机关的行走/可见性断言。未连接门洞的封实性继续由独立 `DoorwayWallFillGameTest` 检查。
2. 战斗夹具的血房第二轮仍用历史 `EncounterBalance.population` 计算预期人数，未考虑本局持久化的密度/指定数量策略。改为使用本局遭遇策略的分配结果；波次间等待、不提前发首领钥匙、两轮总人口等原断言保持。
3. 首轮上述失败遗留的实例/slot32模板导致后续重连、外来资产隔离、全部模板遍历及消息生命周期用例失败。没有因此删除外来内容拒绝、回收、钥匙或重连断言，也没有修改生产生成/结算代码。

上述两处修正均仅在 `src/gameTest`。全量JUnit运行期间未改生产源码；启动时974份源码/资源哈希记录为 `logs/full-regression-source-before.json`。

## 完成的运行验证

- 新世界默认套件：`run/full-regression-core-fixed-20261102`，85项全部通过，日志 `logs/full-regression-core-fixed-20261102.log`，耗时10分59秒。包含修正后的数学房及全部模板通路、完整战斗、重连、双实例、外来资产隔离、门洞封堵、管理员配置和奖励测试。
- 功能套件首轮：17项中16项通过，失败项为 `NativeCombatStatsGameTest` 的支援怪攻击默认值断言，日志 `logs/full-regression-features-20261102.log`。独立SAODG弓手当前明确注册基础攻击3，旧夹具却要求它与原版骷髅攻击完全相同；改为检查弓手明确的基础攻击3，仍保留原生生命/护甲、重装兵攻击及外部修饰器不被覆盖的断言，没有改生产属性。
- 功能套件复测：`run/full-regression-features-fixed-20261102`，17项全部通过，日志 `logs/full-regression-features-fixed-20261102.log`，耗时3分40秒。命名空间与CI功能组一致，覆盖电路、符文、音效、结算奖励、退出、房间奖励、人口及实际小首领生成。
- JAR完整性和内容校验通过：340份生产NBT集合及每个文件字节均与源码一致，中文与默认语言文件相同，包含新增策略和门洞填充类、不含GameTest类。记录 `logs/full-regression-artifact-20261102.json`。

三处回归修正都只涉及GameTest。全量构建启动后的生产源码/资源保持不变；不把旧的过滤测试结果冒充本轮未过滤构建结果。

两轮默认运行中，NightConfig自动重载线程均记录过一次 `Table with path [difficulty] has been declared twice`。读取第二轮当前服务器TOML时可正常解析，未发现持久重复表；这不足以证明没有重载竞态，暂保留为待调查日志项。不能用绿色的其他范围测试隐去这条信息。

## 复现命令

以下命令不清理制作资产，不指向用户客户端或生产服务器。`tools/ci/runtime.init.gradle`只约束运行JVM为2G、两个处理器，不筛选默认套件，不改变生产规则。

```powershell
$env:JAVA_HOME = 'D:\Java\jdk-17'
.\gradlew.bat build --offline --console=plain --max-workers=1 '-Dorg.gradle.jvmargs=-Xmx1536m -Dfile.encoding=UTF-8'
.\gradlew.bat -I tools/ci/runtime.init.gradle runGameTestServer -x downloadAssets --offline --console=plain --max-workers=1 '-Dorg.gradle.jvmargs=-Xmx1024m -Dfile.encoding=UTF-8' '-PgameTestRunDirectory=run/full-regression-core-fixed-20261102'
.\gradlew.bat -I tools/ci/runtime.init.gradle runGameTestServer -x downloadAssets --offline --console=plain --max-workers=1 '-Dorg.gradle.jvmargs=-Xmx1024m -Dfile.encoding=UTF-8' '-PgameTestNamespaces=saodg_circuit,saodg_rune_portal,saodg_sound,saodg_completion_rewards,saodg_exit,saodg_room_rewards,saodg_population,saodg_miniboss' '-PgameTestRunDirectory=run/full-regression-features-fixed-20261102'
```

真人多人、SAO/Cataclysm整合包原生技能、实际联机断线与进程重启、生产经济和完整界面端到端交互尚未由本记录证明。未部署、推送或发布。

本记录验证产物已归档至 `logs/full-regression-verified-20261102/saodg-0.5.4-neoforge-dev.jar`，4,109,603字节，SHA-256 `1d9b14110c86d43f687dfeb5f04e26715ddd7449e2c21d211dee0f122af2a6af`。`build/libs`可能指向更新的开发包。这些历史通过结果不能消除上述配置重载待调查项。
