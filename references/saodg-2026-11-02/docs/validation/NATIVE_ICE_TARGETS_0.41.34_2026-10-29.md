# 原生冰弓逐目标效果：0.41.34

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

夹具提交 `6b18e484d8c8`，生产代码/运行包仍为 `9e3ddc4e9793` 的 0.41.34，SHA256 `7f2fda3eace26417750cd0d62d9ef52f3d51690ea5a896cf6ed4269231727286`。只在授权私有服 `run/pack-acceptance-20261028-081137-fd148a65`、127.0.0.1:25579 运行，磁盘入口/奖励四个开关保持 false。客户端、原服、未提交 beta 结构未改。

## 检查范围与实际结果

新增可选 `saodg.packNativeIceTargetsAcceptance=true`，由已有双队夹具在两局实际生成、进入第一战斗房后执行。反射调用当前安装 r234 的已变换 `IceBowArts.addFrost`、`freeze` 和私有 `damage`，双向各检查一次：

- 本局精确登记且存活的目标具有正常伤害权限；实际调用后冰霜叠层为 1、到期为当前世界 tick +100、原生 owner 为实际施法者；冻结到期为 tick +40、缓慢等级 6/持续 40。两类效果的 SAODG 绑定均含实际施法者与本局 ID，并通过正式 `boundEffect` 查询。
- 原生 `damage(..., 1F)` 实际各扣血约 0.94，保持目标存活；不把名义伤害当作最终伤害，不修改原生伤害公式。
- 将施法者临时放到另一局目标附近，实际调用以上三种原生方法后，目标完整序列化 NBT 不变；之后恢复施法者位置。
- 本局坐标中创建一个未加入世界的负例僵尸，带伪造 run_id/required_enemy 标签；同样三种调用前后完整 NBT 相等，不允许靠标签取得权限。未向世界插入额外未知实体。
- 同步的非致死检查不新增死亡/原生 XP 链接；合法冰霜和冻结留给正常游戏计时，不人工清除后冒充兼容。

这证明指定原生效果方法的合法路径与逐目标隔离边界。没有模拟真正拉弓、装备选择、箭矢出生/飞行/命中回调、连续施法、所有剑技/TACZ/宠物；C01/C05 等兼容整项保持未完成，不以反射方法调用替代实际完整施法验收。

## 后续双队流程与现场保护

实际原生邀请建立两队、准备/开始后，生产生成的实例为 `031b30b0-cb48-4a0c-8231-1e30dbca3f8c`（槽位 1）和 `c68f2308-d688-4e27-9b95-81230f62fd60`（槽位 2）。效果检查后两队继续主线，各完成 4 门、封印大厅全队转场、独立首领、17 个确认死亡与 XP 链接、合计 440 原生 XP、独立战绩、回程和生产清理。第一队清理期间第二队钥匙/门/进度/票据保持，跨队伤害/开门与传送隔离检查仍通过。保活回复分别 10、8 次。

最终报告 `logs/native-dual-trial-probe-15dd8d5c-f9d6-400f-92de-b1d17b48d60b.json` 为 true，含 `native_ice_targets` 双向结果；SHA256 `3a03271696dbf1b723e2099023afb7dd218bbf406d3526823eefae119e3f05eb`。恢复基线报告 `logs/native-dual-recovery-probe-1b7afc25-1a94-4515-b601-7fd2823005f0.json` 亦通过。

原隔离局 `f99ebe03-0e35-4e73-822a-063b6b01c318` 的记录和租约保持，最终 `runs=1, lobbies=0, pendingReturns=0, tickets=0`，槽位 0 QUARANTINED，其余 FREE。停服后原隔离实体区域 `entities/r.0.0.mca` 与本轮运行前备份字节一致，SHA256 均为 `51916e76d1a69aa84a76d4d8945b0f6e81747040bf8749f68faf4b045366ac9d`，证据 `logs/native-ice-targets-retained-entities-20261029.json`。既有未知结晶未处理，不宣称所有槽位已清空。

## 构建、运行与证据

独立 Git 导出 `.gradle/native-dual-fixture-6b18e484d8c8-639025c0` 执行 `packTestJar --offline --console=plain -x downloadMCMeta` 编译/重混淆成功，15 秒；未跑 JUnit 或其他完整套件。日志 `logs/native-ice-target-fixture-20261029.log`，SHA256 `5299dfd78cb2b10b85a49dfa37ba2a9bebe4385ca790226336a922ffdf2bce4f`。

运行前完整备份 `validation-history/native-dual-detached-6b18e48-2fbd6c7d`；隐藏独立运行器 PID 8280、Java PID 3032。正常 stop、Java 退出 0、端口关闭，终态收据 `.gradle/native-ice-targets-process.json`。测试附加包已归档至备份目录 `fixture-native-ice-targets.jar`，SHA256 `95a0f79b8741be3d2de8b08c6e569e220a4c0135e0bccc39a1acc1756ae20ab8`。

保全 `logs/native-ice-targets-6b18e48-preservation-20261029.json`：989 份受保护文件中 971 份字节保持、2 份 properties 仅时间注释变化、16 份为预先允许的旧测试人物保存文件；301 份其他人物文件保持，无意外变化，配置语义保持。

- 控制台 `logs/pack-native-dual-detached-6b18e48-20261029.log`，SHA256 `d172a174f62413d54825b025dd2887dc1fc61979b8bb9bd8be555a1c17a7bae7`。
- JFR `logs/native-dual-detached-6b18e48-20261029.jfr`，17908303 字节，SHA256 `485b0a96551f419e2dcfbdc11b1bd2733d007f96a644f7ace78566b178f28d83`，未分析为性能验收。

使用 EmbeddedChannel、无敌、高伤害及逐房传送驱动，不替代真人远程操作、战斗平衡或奖励经济验收。没有新生产功能，因此未重新打包或部署运行模组。
