# 怪物落点优化与位置配置

2026-11-02，Minecraft 1.20.1 / NeoForge 47.1.106 / Java 17，沿用 `0.5.4-neoforge-dev`。保留工作区已有修改和门洞封堵实现。

## 行为

- 新增服务器设置 `spawning.bodySpacing`（默认0.15，0～2）、`spawning.avoidPlayersRadius`（默认4，0～16）、`spawning.rangedHighGround`（默认true）。管理员配置界面难度分类和已有服务端设置命令均可调整，附中文名称与说明。
- 新建副本时，将三项放入不可变遭遇快照；普通波次和大型怪的小型后备选点使用本局规则。最终Boss和阶段援军继续用专用锚点。
- 优先选择本队存活、可行动、非旁观玩家半径外的安全点。全部候选都在半径内时选择离最近队员最远的安全点；0关闭距离偏好。距离是三维距离，不是可行走路径长度。半径外继续按弓手高台偏好、单元占用、怪物间距排序，同分沿用种子抽签。
- 额外间距是同波准备实体碰撞箱膨胀距离，0也不会取消碰撞检查。没有安全位置时仍拒绝生成，不扩大建筑或放宽实例归属检查。
- 每次选点预先统计单元占用数量，代替每个候选重复扫描 `occupied`；距离比较直接读取实体坐标。没有声称具体耗时改善比例，也没有引入跨波次或跨实例缓存。

## 兼容性

`EncounterTuningCodec` 写入版本3，保存位置配置；版本1/2仍可读，使用历史0.15间距、关闭玩家距离偏好、开启高台偏好。版本3缺失字段、类型错误、非法布尔值、非有限值或越界拒绝读取。`withProfile`保留位置配置。完整 `RunRecord.save/load` 回读保留这三项。

旧模组不支持新版遭遇快照，不能把这种迁移称为可直接回退兼容。现有世界日志外层schema、网络协议和生产房间模板未改。配置JSON仍是schema 1，不增加新的JSON字段。

## 实际验证

- `build -x test` 成功，编译主代码、GameTest和packTest并重混淆打包。日志 `logs/spawn-policy-build.log`；其中虽同时指定过test任务，`-x test`使其跳过，不能将该次构建算作JUnit通过。
- 随后单独执行过滤JUnit并运行专用服务器，最终命令：

```powershell
$env:JAVA_HOME = 'D:\Java\jdk-17'
.\gradlew.bat test --tests '*SpawnPlacementPolicyTest' --tests '*EncounterTuningTest' --tests '*EncounterProfileTest' runGameTestServer --offline --console=plain --max-workers=1 '-Dorg.gradle.jvmargs=-Xmx1536m -Dfile.encoding=UTF-8' '-PgameTestNamespaces=saodg_config,saodg_spawn' '-PgameTestRunDirectory=run/spawn-policy-validation-20261102'
```

- JUnit 7项全部通过，无跳过，覆盖避让排序优先级、无玩家及关闭偏好、范围拒绝、替换属性配置时保留位置策略，以及已有数量/权重/配置校验。
- GameTest 9项全部通过。新增夹具实际放置地板/高台并调用生产选点器，检查玩家附近避让、所有点在半径内时仍选最远安全点、额外间距拒绝、高台开关改变实际落点；检查版本1/2迁移、版本3回读、缺字段与NaN拒绝。已有整局回读、配置事务/OP权限/过期版本/真实TOML保存、巨像高度碰撞、自然生成隔离等范围测试同时通过。日志 `logs/spawn-policy-final.log`。
- 内容审计通过，80个活动房间、5个受保护非活动定义、340个引用模板，无错误。
- JAR ZIP完整性、包含 `SpawnPlacementPolicy.class` 且不包含测试类检查通过。`git diff --check`通过。

中间一次Gradle初始化SSL上下文出现数组越界，重试后未再出现；一次把`--tests`放到GameTest任务后导致命令行选项错误，已修正。没有改系统证书或JDK。未执行默认未过滤全套JUnit/GameTest，不能称全套构建测试通过。

产物：`build/libs/saodg-0.5.4-neoforge-dev.jar`，4,109,603字节，SHA-256 `1d9b14110c86d43f687dfeb5f04e26715ddd7449e2c21d211dee0f122af2a6af`。

尚未部署到客户端或服务器。真人多客户端的刷怪距离、SAO/Cataclysm原生战斗、客户端界面视觉和实战平衡未验收；上述独立开发环境测试不证明生产验收完成。
