# 0.41.65-dev：职业弓免箭拉弓入口

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

## 原因与范围

用户报告选择弓手职业后，迷宫区内右键不能拉弓，背包没有箭；该职业在迷宫区外支持免箭。首次仅检查旧 `SAO-server-0.7` 的 r234 原生弓，误判为缺少弹药。继续只读检查发现当前 `D:/Minecraft/.minecraft/versions/SAO-0.8/mods` 另有 `sao_archer-0.6.0.jar`，旧服务端目录没有这个组件。

当前组件的 `local.sao.archer.ArcherEvents.nock` 在职业、等级和楼层条件满足时，直接为 `ArcherBow` 调用 `startUsingItem`，不要求库存箭。`loose` 取消原版发射并调用 `Archer.normalShot`；最终生成原版箭实体，预先设置 `Pickup.DISALLOWED`，消耗弓耐久而不消耗库存箭。自动射击另由 `AutoBow` 和虚拟弹药 Mixin 负责。

SAODG 的 `InstanceEvents.interactItem` 在上述 `nock` 之前调用 `RangedUsePolicy.ranged`；后者只接受原版弓/弩/三叉戟、已核对的 r234 两种弓以及 TACZ。新组件所有职业弓共用的 `local.sao.archer.ArcherBow` 没有登记，因此右键在职业免箭逻辑执行前就被取消。`ProjectileDebits.before` 在释放阶段重复使用同一白名单，也需要修正。

这不是 `RangedUsePolicy.ammunition` 强制要求实体箭：该方法原本已允许空弹药，留给武器和职业判断能否发射。方块右键取消也不能单独作为本次根因：Forge 47.4.10 的默认取消结果为 `PASS`，仍可进入物品使用回退。

## 修改

`SaoRangedItems` 新增 `ArcherBow` 的精确类名、直接继承 `BowItem` 和原始类资源 SHA256 检查：

`1d737debcff9d6b94b4c7ca32c7e4c7e36557a0d15c2ec9eb02cb18fb2a27476`

继续由原职业组件决定职业、等级、楼层、免箭、射速和武器损耗，不创建库存箭，不扩大到任意第三方弓。原有 `mayFire`、实体所有者观察、登记、实例路径和拾取边界保持。没有复制该专有组件的源码或资产，也没有将其 JAR 加入仓库或构建依赖。

版本变为 `0.41.65-dev`，存档格式及网络协议没有因本次修改变化。整合包仍需自行包含职业组件；这个修复包不会给缺少组件的旧服务端增加弓手职业。

## 验证

使用 JDK17、Forge47.4.10 和实际安装的职业组件，执行：

```powershell
$env:JAVA_HOME = 'D:\Java\jdk-17'
$env:SAODG_ARCHER_REFERENCE_JAR = 'D:\Minecraft\.minecraft\versions\SAO-0.8\mods\sao_archer-0.6.0.jar'
.\gradlew.bat --offline test --tests cn.saodg.integration.sao.SaoRangedItemsTest --console=plain
```

3项定向JUnit通过：实际职业弓类可识别；相同类名但原始字节不匹配时拒绝；未知弓子类及普通物品拒绝。测试只加载类和读取资源，没有初始化职业模组或执行其拉弓逻辑。外部参考JAR未配置时，两个二进制测试会跳过，不能把跳过报告作原生兼容通过。日志 `logs/archer-bow-0.41.65-focused-tests.log`。

工作区另有并行谜题、内容和UI修改。修复包使用基准提交 `c243c96b2a9b8465b154d387e84b9e25a443c878` 的独立Git导出，仅覆盖版本、`SaoRangedItems` 和本次测试文件；来源清单为 `logs/archer-bow-0.41.65-source.json`。

独立导出完成 `build -x test`，包含主代码、GameTest/packTest编译和重混淆打包；随后单独执行上述定向JUnit，3项通过、0跳过。打包命令实际同时显式列出了 `test` 和 `-x test`，因此构建阶段没有执行测试，测试结果仅来自后续独立调用。日志分别为 `logs/archer-bow-0.41.65-isolated-build.log` 和 `logs/archer-bow-0.41.65-isolated-tests.log`。

修复包：`build/verified/archer-bow-0.41.65-dev/saodg-0.41.65-dev.jar`，3,613,717字节，SHA256：`232150ec6ddfdd310e9cf14d05ac6a5e187eb7bdc2ee41fa1233b6c0a2b26e9a`。已直接检查JAR包含新识别类名和散列、版本及refmap正确，不含packTest、职业组件类或本地beta模板。产物清单为 `logs/archer-bow-0.41.65-artifact.json`。

本轮未进行整合包客户端实测、双人/跨实例运行、自动射击、重启恢复或部署；不能据此宣称全部弓和全部职业技能完成兼容。没有运行默认完整JUnit套件。
