# 临时原版敌人的原生经验路径

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

0.41.9-dev 修复临时原版僵尸未进入 SAO 经验延后结算的问题。实际 r234 的 ExternalKillXp.onDeath 对符合资格的 Mob 调用 PlayerData.xp；旧 scoped 判断只接收 DungeonEnemy，而当前普通/精英/封印大厅默认使用原版 Zombie，因而会直接走即时经验入口。

现在精确的原版 Zombie 类及 minecraft:zombie 类型也进入迷宫区作用域检查。迷宫区内未登记的僵尸不直发经验；真正捕获仍要求服务端线程、同服务器、战斗阶段和权威实体登记。普通世界的伪造 saodg 标签不能抑制原生经验。经验日志仅额外允许 minecraft:zombie，不放宽到所有原版生物，既有 schema 和指纹格式不变。

在独立 saodg_reward_boundary 命名空间新增一项 GameTest，验证迷宫区僵尸作用域、野外伪造标签对照、未登记迷宫区实体不调用缺席的原生所有者，以及僵尸日志往返/任意原版类型拒绝。连同既有领奖、归还、收件人用例，共 4 项 required 通过，BUILD SUCCESSFUL in 48s，服务器正常保存退出。日志为 logs/vanilla-xp-boundary-offline-20261028.log；日志时间为 2026-10-28，记录整理于次日。

```powershell
.\gradlew.bat '-Dnet.minecraftforge.gradle.check.certs=false' runGameTestServer -PgameTestNamespaces=saodg_reward_boundary -PgameTestRunDirectory=run/gameTestServer-vanilla-xp-boundary-20261028 --offline --console=plain
```

首次离线命令卡在 ForgeGradle EnvironmentChecks.testServerConnection，尚未执行测试，确认线程栈后仅停止本次 Gradle daemon。重试单次关闭 ForgeGradle 联网证书环境自检，未修改全局 TLS 或下载信任设置。未重复全量构建或启动整合包，未打包部署；此独立环境没有 SAO，不能证明实际已登记击杀的原生数额、确认死亡、落盘发放或崩溃恢复全部通过。正式入场/奖励仍关闭。
