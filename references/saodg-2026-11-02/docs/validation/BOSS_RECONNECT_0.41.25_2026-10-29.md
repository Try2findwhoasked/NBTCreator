# 首领离线恢复：0.41.25

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

运行时源码 `9e91855dc32ba544519f2b7713466783f7552d16`；重连夹具 `dc0416d`，通关夹具 `2908c60`。无人可战斗时，旧逻辑只重置首领攻击，封印阶段的 `phaseStarted` 仍累计离线时间；临近阶段上限时离线重连可能立即触发 `boss_intermission_timeout`。

本版在无人可战斗时暂停首领房局部的阶段、遭遇和波次计时，同时清除旧蓄力/冲锋并重新等待当前阶段的攻击间隔。仍保留首领阶段、生命、封印和守卫事实，不重复生成；实例总时钟、硬上限和重连截止期限继续运行。原生倒地状态/计时和死亡确认不由此修改，无协议或持久格式变化。

独立 Git 导出 `.gradle/source-release-9e91855dc32b-20261029-060031-868722b8` 编译/重混淆/包内检查通过，41 个结构、482 个中文键，beta 排除。开发包 `build/verified/0.41.25-dev-9e91855dc32b-20261029-060031-868722b8/saodg-0.41.25-dev.jar`，SHA256 `777dd2b6f17f18c6c2675c6db06be1a2a13fe72dfc69f46d0ef6330e3d6dfdb9`。后续仅更新该导出的测试夹具，与最终夹具提交一致；运行时没有再修改或重新打包。

新增检查复用真实双人物大厅/生成、PlayerList 保存/移除/新身体登录。测试显式设置 BOSS_READY 并调用生产首领启动边界，省略前置探索；首领实际转场、生成、攻击调度、阈值伤害、守卫和清理仍走生产实现。实际封印大厅传送门与完整探索通关由同轮既有 combat 夹具覆盖。

- 观察实际 WINDUP 后两人真正登出；后续实际 tick 中旧攻击被取消，重连后两名新身体都回独立首领区，旧身体失去身份，保留完整新攻击间隔，总时钟继续。
- 实际伤害进入 SEALS 后，显式将阶段起点调至剩余约 10 tick，再让两人离线 15 tick。阶段起点随离线平移，敌人登记不增；实际重连后再等待 5 tick，首领仍处于封印阶段，没有把离线时间变成即时超时。
- 生产中止、回程和清理释放槽位、回程日志并保留双方库存。新增夹具使用独立返回平台并保持其区块加载，结束撤销自己增加的强制加载。

仅选择 `saodg_reconnect,saodg_combat`，不运行 JUnit 或全套回归：

```powershell
.\gradlew.bat '-Dnet.minecraftforge.gradle.check.certs=false' runGameTestServer --offline --console=plain -x downloadAssets -x downloadMCMeta '-PgameTestNamespaces=saodg_reconnect,saodg_combat' '-PgameTestRunDirectory=run/gameTestServer-boss-reconnect-04125-final'
```

结果及失败尝试均保留：

- 首次三项合跑停在回城不安全落点，整组失败；加落点诊断后两项重连单独运行通过，53 秒。日志 `logs/boss-reconnect-04125-diagnostic-20261029.log`，SHA256 `332d80c777a74ac74c36cdbc86b8089a4e354e126a6ef1afe9269725da384c93`。
- 加独立返回平台后的三项合跑，首领及探索重连两项通过，通关项在第三张地图生成时超过默认 600 tick、尚未写入方块。该次整体仍失败（70 秒），日志 `logs/boss-reconnect-04125-final-20261029.log`，SHA256 `659ab32f2d8534b6985ccabf6feba5b416855a424d1dff45fd171ebbccaf9181`。
- 通关夹具按重连夹具一样显式保留 1800 tick 区块准备上限，并在成功/异常路径恢复旧值；没有修改生产默认值。相同独立导出仅重跑 `-PgameTestNamespaces=saodg_combat`、目录 `run/gameTestServer-boss-reconnect-04125-combat`，1 项完整通关/首领/死亡和清理检查通过，76 秒、退出 0。日志 `logs/boss-reconnect-04125-combat-20261029.log`，SHA256 `44eaf971994b0ca15066d91b45e7b3354a5330b3464479116b1c851cf8ea99ef`。

三个目标检查已有分别通过的证据，不宣称一次三项合跑全绿，也不把放宽测试夹具的等待时间当作默认生成延迟达标证据。没有放宽生产安全回程检查。

未更新或启动用户客户端、原服或私有整合包；非远程客户端，也未覆盖原生 SAO 倒地、所有阶段与多队故障矩阵。F07/C06/C07/C08 及发布验收仍是部分覆盖。
