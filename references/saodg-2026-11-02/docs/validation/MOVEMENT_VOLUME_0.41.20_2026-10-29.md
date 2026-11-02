# 技能位移落点身体范围：0.41.20

源码 `3471c1e3f6ffc0d9cbd1a5cbcc2bcdabc55049ff`。原 `SkillMovementPolicy` 对实例路径仅检查脚点，传送额外检查最终碰撞；脚点位于 y=111、身体超出实例上界 112 时，速度预测路径仍会返回允许。原实现没有完整身体范围判定。

现在在原有路径检查后检查最终身体四角的底面和顶面（最大面减去浮点容差）：全部必须位于本局持久区域，跨入相邻房间还必须满足同一门禁。传送继续执行原碰撞检查，速度预测仍由原生碰撞处理物理障碍。没有新增落地要求，没有改技能位移公式、原生伤害、冷却或消耗。外部世界仍走原路径，协议 20 和存档格式不变。

在本提交全新独立导出 `.gradle/source-release-3471c1e3f6ff-20261029-044717-2bb86250` 运行：

```powershell
.\gradlew.bat '-Dnet.minecraftforge.gradle.check.certs=false' runGameTestServer --offline --console=plain -x downloadAssets -x downloadMCMeta '-PgameTestNamespaces=saodg_concurrent' '-PgameTestRunDirectory=run/gameTestServer-movement-volume-04120-20261029'
```

复用已验证 id=1.20.1 的下载元数据。1 项四人双实例 GameTest 通过，66 秒正常退出；原实例隔离、生命投影、煤炭门、清理和槽位复用断言通过。每次两方实际人物快照检查增加：当前位置速度权限允许；y=109 的完整身体空中落点允许；脚点 y=111 但身体越顶时速度和传送均拒绝；查询不改变位置或本局身份。验证的是公共权限策略，没有实际调用所有 SAO 位移技能或 TACZ 爆炸击退，也没有专门测量水平边角、巨大实体及性能；不能据此完成全部 SK/TACZ 兼容验收。

运行日志 `logs/movement-volume-04120-20261029.log`，SHA256 `1f9cd4a92e25a19c3e5cbb11144cecd516205a38714dabfa4dba1c07fe2fc137`。

开发包：`build/verified/0.41.20-dev-3471c1e3f6ff-20261029-044717-2bb86250/saodg-0.41.20-dev.jar`，SHA256 `09683d5791dcb3bc1d83f3203506ea85df1b5c49a406e95729d06daf0450f280`。package-only 的独立编译／重混淆、结构／文本和 beta 排除检查通过，GameTest 随后另行执行；没有重跑 JUnit 或原生整合包。没有替换或启动用户游戏／原服，正式开本门禁不变，完整目标仍未完成。
