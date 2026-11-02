# NeoForge 1.20.1 迁移 — 2026-10-31

## 范围

用户确认保留 Minecraft 1.20.1，在 `codex/migrate-neoforge-1.20.1` 分支迁移。基于 Forge `0.5.1beta`，开发版本为 `0.5.2-neoforge-dev`；NeoForge 47.1.106、ForgeGradle 6.0.54、Gradle 8.8、Java 17，官方映射不变。

- 保留 `net.minecraftforge.gradle` 6.0.54，依赖改为 `net.neoforged:forge:1.20.1-47.1.106`，新增 NeoForged Maven 解析 NeoForge 和 FancyModLoader 构件。
- 1.20.1 仍保留 `net.minecraftforge.*`、`META-INF/mods.toml`、`forge` 运行时 mod ID 和 SRG 重混淆。`forge` 依赖下限从 47.4.10 改为实际验证目标47.1.106；这不是对后续 Forge 版本或全部第三方模组兼容的承诺。
- `InventoryAssetTickMixin` 从较新 Forge 的统一 `onInventoryTick` 回调迁移到目标实际存在的 `inventoryTick` 和独立护甲迭代。两者仍进入 `AssetGuard.runAutomatic`，保留资产锁和同步原生写入保护。新增 `InventoryAssetTickGameTest`，实际检查主背包/护甲/副手回调、写入标记、锁定暂停及解锁恢复；测试物品只在GameTest源集中注册，不进入生产JAR。
- CI使用相同完整构建、两组GameTest和工具检查，发布报告字段由 `forge` 改为 `neoforge`。历史发布和标签不变；迁移包不复用旧版文件名。
- 协议25、存档格式、资源ID、80间活动房、五个受保护的非活动定义、340份模板以及 SAO/KubeJS 接口保持不变。未修改参考仓库或现有客户端/服务器安装。
- `tools/compat/prepare_pack_validation.py` 及本机私有整合包启动/部署工具保留历史 Forge 目标校验；它们不是 NeoForge 环境安装器。不要将迁移包部署到原 Forge 整合环境来代替兼容验收。

官方依据：[47.1.106构件目录](https://maven.neoforged.net/releases/net/neoforged/forge/1.20.1-47.1.106/)、[ForgeGradle userdev实现](https://github.com/MinecraftForge/ForgeGradle/blob/FG_6.0/src/userdev/java/net/minecraftforge/gradle/userdev/UserDevPlugin.java)、[1.20.2才引入包名与mod ID变更](https://neoforged.net/news/20.2release/)。本轮还检查了47.1.106的userdev配置和sources构件，确认上述旧API命名。

## 本轮验证

所有Gradle运行均不执行 `clean`，保留作者资产。初次直连解析插件失败；旧 NeoGradle 6.0.21 在 Gradle 8.8 下出现 `Could not find versionParser`，因此保留项目已固定的 ForgeGradle 6.0.54 来读取 NeoForge 1.20.1 userdev；通过本机已有代理为当前命令传入JVM代理参数后重试，不将机器代理配置写入仓库。

- 完整构建：`gradlew.bat --offline --console=plain build` 通过，33分46秒，没有过滤或跳过JUnit。180项用例，178通过、两个可选原生弓二进制用例因缺少参考JAR跳过，失败/错误均为0；包含三档各10,000种子及固定Boss场地布局检查。日志 `logs/neoforge-build-verified-20261031.log`，XML位于 `build/test-results/test/`。
- 最终增量构建再次通过，15秒；编译最终GameTest夹具，JUnit任务为 `UP-TO-DATE`，复用上述完整结果，没有重跑或另计用例。日志 `logs/neoforge-build-final-20261031.log`。
- Python工具：`python -m unittest discover -s tools -t . -p 'test_*.py' -v`，35项通过，日志 `logs/neoforge-python-20261031.log`。
- 发布工具：补充 NeoForge 元数据断言后，`python -m unittest tools.ci.test_release -v`，6项通过，日志 `logs/neoforge-release-tests-20261031.log`。
- 默认核心GameTest：76/76项必需测试通过，正常停服，Gradle成功；包含新增资产tick保护和现有实例隔离、死亡、奖励边界、通路等夹具。日志 `logs/neoforge-gametest-core-20261031.log`。
- 附加功能GameTest：18/18项必需测试通过，正常停服，Gradle成功；命名空间与CI的features作业一致。日志 `logs/neoforge-gametest-features-20261031.log`。
- 任务清单：`tasks --all` 确认 `build`、`test`、`runClient`、`runServer`、`runGameTestServer` 存在；没有启动普通客户端。日志 `logs/neoforge-tasks-verified-20261031.log`。
- 生产内容：`python tools/verification/content_audit.py --check`，80间活动房、五个受保护非活动定义、340份生产/引用模板，零错误。
- 工作流：`go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12 .github/workflows/ci.yml .github/workflows/release.yml`，退出0；首次直连Go代理超时，当前命令使用本机已有HTTP代理后通过。日志 `logs/neoforge-actionlint-proxy-20261031.log`。
- JAR审计：版本和加载器范围正确；340份模板集合及字节与源码一致，中文/默认语言一致，无GameTest、packTest或测试物品。Mixin映射包含 `inventoryTick → m_41666_`、`tick → m_36068_`，重混淆后的shadow字段为 `f_35978_`。报告 `logs/neoforge-artifact-20261031.json`。

运行测试位于独立源码副本 `.gradle/neoforge-runtime-validation-20261031`（核心）和 `.gradle/neoforge-feature-validation-20261031`（附加），由Git归档加当前迁移改动生成，与根工程JUnit使用不同构建输出。对主源码、GameTest、生产资源及三份构建配置共865个文件比较（文本换行归一化、二进制原字节），无差异；作者资产未复制为测试输入。

两组分别在对应副本目录运行下列命令；`--offline` 使用本机已完成联网解析的缓存，`-x downloadAssets` 只跳过无图形服务器不需要的客户端资源下载，资源init仅限制JVM：

```powershell
.\gradlew.bat --offline --console=plain -I tools/ci/runtime.init.gradle runGameTestServer -x downloadAssets -PgameTestRunDirectory=run/neoforge-core
.\gradlew.bat --offline --console=plain -I tools/ci/runtime.init.gradle runGameTestServer -x downloadAssets -PgameTestRunDirectory=run/neoforge-features '-PgameTestNamespaces=saodg_circuit,saodg_rune_portal,saodg_sound,saodg_completion_rewards,saodg_exit,saodg_room_rewards,saodg_population,saodg_miniboss'
```

## 本地产物

`build/libs/saodg-0.5.2-neoforge-dev.jar`，4,060,986字节，开发验证包，未推送或发布。

```text
SHA256 6f3dc66e036e555c37a1413f5d2310955b13d11657ba121bd28b8f5a51e85094
```

## 验收边界

隔离GameTest不代表真人联机或生产验收。NeoForge下的实际双客户端、SAO/灾变/TACZ/FTB/KubeJS完整整合包、原生经济、断线/重启与旧存档迁移仍需另行实测。原环境里声明 Forge 47.2/47.3/47.4 下限或依赖较新 API 的第三方模组可能无法在47.1.106加载，不得批量降低它们的依赖声明绕过检查。

只读兼容元数据预检未完成：会话给出的 `D:\Minecraft\.minecraft\versions\SAO-0.76` 目录在本轮机器上不存在，未扫描任何JAR，不能将零结果理解为整合包兼容。诊断记录 `logs/neoforge-pack-metadata-20261031.json`。
