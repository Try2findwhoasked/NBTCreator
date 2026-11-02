# 0.5beta 仓库维护与发布验证

日期：2026-10-31。版本 `0.5beta`，注解标签 `v0.5beta`。基线为 Minecraft 1.20.1、Forge 47.4.10、ForgeGradle 6.0.54、Gradle 8.8、JDK 17；网络协议仍为24。

## 发布内容与Git维护

从主线 `b9dd8c6` 整理现有工作区，按用途分别提交：

- `0a6efc5`：建筑展示世界的新维度增量包、按维度回导及工具测试/文档。
- `2525415`：数学挑战房、神比NPC、服务器答题状态及个人奖励防重，连同两层生产NBT和原任务验证记录。
- `f60d646`：更新旧GameTest夹具，实体奖励箱检查和交互使用实际实体，虚拟传送入口不再套用实体门洞材料断言。
- 发布提交：统一版号、CHANGELOG和当前文档；发布工具支持紧凑版号 `0.5beta`，仍校验标签、版本和提交一致，并将其标记为预发布。

执行Git commit-graph/loose-objects维护，仅移除已有打包副本的重复松散对象；`git fsck --no-dangling --connectivity-only` 通过。未删除分支、改写已发布提交或旧标签，未清空build、制作模型、存档或参考仓库。JAR、运行世界、原始日志和生成输出继续留在忽略目录。

## 本次验证

| 检查 | 结果与范围 |
| --- | --- |
| 未过滤 `gradlew build` | 通过，耗时33分21秒；JUnit 176项，174通过、2项可选参考二进制测试跳过，失败/错误均为0 |
| 布局矩阵 | trial/standard/elite各10,000个种子全部通过，另有各难度512个独立场地隔离检查通过 |
| Python统一工具测试 | 34项全部通过 |
| 生产内容审计 | 80间活动房，五个原有非活动功能定义保留；340/340份生产模板有引用，无错误 |
| 工作流静态检查 | 固定版本actionlint v1.7.12通过，CI/CD门禁未放宽 |
| 最终默认core GameTest | 72项必需测试全部通过，包含数学挑战与实际建筑遍历 |
| 附加features GameTest | 18项必需测试全部通过，覆盖继电机、符文门、音效、通关奖励/实体箱、归途门、房间奖励、刷怪和小首领 |
| 通关/故障回归 | 最终core内实际完成7次成功循环、2次故障循环，结束时runs=0、pendingReturns=0；重连测试通过 |
| 主JAR内容 | 340份生产NBT逐字节等于源码，数学运行类齐全、包内版号正确、中文/默认语言一致 |

两组运行测试使用独立新世界和 `tools/ci/runtime.init.gradle`，只限制运行JVM为2G/2个处理器并跳过客户端下载任务 `downloadAssets`；各组命名空间与现有CI一致，未增加测试排除，不改变正式准入或奖励门禁。

两项跳过均来自 `SaoRangedItemsTest`，依赖未提供的 `SAODG_ARCHER_REFERENCE_JAR`：`installedArcherBowIsRecognizedWithoutInitializingTheOptionalMod` 和 `changedNativeBinaryCannotReuseTheArcherClassName`。这不代表本版已重新验证可选职业弓的真实二进制兼容。

本次保留失败过程：首轮默认套件72项中3项失败，分别是旧实体门洞断言、旧方块奖励箱断言，以及受前一战斗失败拖延而超时的重连用例。第二轮修正前两处后，又暴露夹具仍调用已停用的方块奖励箱交互重载；完成实体交互修正后，第三轮完整默认套件72项全部通过。没有修改生产结算逻辑来迎合夹具，也没有删除原有成员身份、奖励防重、回收和重连断言。历史主线CI中的守卫技能夹具失败在本轮默认套件中未复现，未据此调整生产行为。

本机原始证据位于 `build/release-0.5beta-build.log`、`build/release-0.5beta-tools.log`、`build/release-0.5beta-core.log`、`build/release-0.5beta-core-final.log`、`build/release-0.5beta-core-verified.log`、`build/release-0.5beta-features.log` 和 `build/release-0.5beta-artifact-check.json`。

打标签前的发布守卫另外发现本机 `build/resources/main` 残留一份源码中已不存在、且不被生产定义引用的 `ruins/entrance_01.nbt`，导致早期JAR多出一份模板。已将该旧输出保留到 `build/releases/0.5beta-evidence/obsolete-entrance_01.nbt`，仅移除这一个构建副本后执行 `gradlew jar` 重新打包；最终模板集合及340份逐字节对照均通过。生产源码和当前模板未改动，未重复运行33分钟矩阵。清理后的一次增量build因classpath变化触发重复单测，已主动停止该重复进程，不把它算作通过；之前完成的176项全量XML已独立保存在 `build/releases/0.5beta-evidence/verified-build/test-results/test`，最终发布检查显式使用这份证据与重新打包的JAR。

## 复现命令

在项目根目录、JDK17下执行；不运行项目级clean：

```powershell
$env:JAVA_HOME = 'D:/Java/jdk-17'
.\gradlew.bat build --console=plain
python -m unittest discover -s tools -t . -p 'test_*.py' -v
python tools/verification/content_audit.py --check
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12 .github/workflows/ci.yml .github/workflows/release.yml
.\gradlew.bat --console=plain -I tools/ci/runtime.init.gradle runGameTestServer -x downloadAssets '-PgameTestRunDirectory=run/release-0_5beta-core-verified'
.\gradlew.bat --console=plain -I tools/ci/runtime.init.gradle runGameTestServer -x downloadAssets '-PgameTestRunDirectory=run/release-0_5beta-features' '-PgameTestNamespaces=saodg_circuit,saodg_rune_portal,saodg_sound,saodg_completion_rewards,saodg_exit,saodg_room_rewards,saodg_population,saodg_miniboss'
```

## 兼容、产物与发布边界

数学挑战增加可选 `math_challenges` 运行记录及非零数学奖励指纹，旧记录按空值/零奖励读取，旧局不追补；种子题库格式版本固定为1。进程重启仍中止未完成副本，未增加继续战斗恢复；不保证旧版降级读写。SAO钱包所有权、原生经验策略与协议24保持，客户端/服务端应同时更新到本版。

本机主产物：`build/libs/saodg-0.5beta.jar`，4,018,012字节，SHA256：

```text
2b624cf9116b38eae827b29fce446343c9b7b5f935b3b400c462fb5a663dafc4
```

本机校验和只标识本机产物；GitHub流水线重新构建的JAR以其附带校验和及来源提交报告为准。新标签触发现有完整CI门禁，全部验证通过后才生成GitHub预发布，不绕过失败检查、不发布到Modrinth/CurseForge。

正式开本仍默认关闭。嵌入式连接和独立Forge运行测试不代表真人双客户端、完整SAO/灾变整合包、实际进程重启/断线重连或生产经济验收通过。本次没有安装到活动存档或部署游戏服务器。
