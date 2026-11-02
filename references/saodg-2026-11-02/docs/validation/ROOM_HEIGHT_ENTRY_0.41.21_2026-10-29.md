# 房间门高与开发入场：0.41.21

源码 `301e01bd9ed9757d5a5bee64aa87674cb63a9832`。按用户明确要求开放实例生成/启动的开发门槛，并支持手工配置模板门洞高度；这不是整合包正式发布或完整兼容验收通过的声明。

房间 schema 4 新增可选 `door_y`（默认 2），为模板局部门洞最低空气方块 Y。实际结构基底为 `66-door_y`，原始结构、到达点、刷怪、秘密、谜题和首领机关共用平移；图连接及门禁保持统一世界 Y66～70。多格连接、石砖封墙和煤炭门保持原间距。模板高度仍为 8～48，门高要求 2～height-6；不自动添加模板内部楼梯。敌人和宠物恢复边界、玩家实例边界、预览和清理同步使用真实基底。

新清单持久化 `base_y`；旧清单全缺省时为原 Y64，部分缺省、错误类型/范围及同一逻辑房间矛盾高度拒绝恢复。世界日志 writer schema 4、结构预览 writer schema 3；降级须恢复升级前完整备份，不能让旧版读取新的低基底清单。

新配置 `dungeon.unrestrictedDevelopmentEntry=true` 默认开启，既有世界载入时补入该项，优先于旧 `enableDevelopmentRuns=false`。跳过预设验收门槛、等级/前置通关、最少队员和脚本入场策略；菜单、准备和实际开始共用资格规则。保留队长、全员准备、实际成员/倒地状态、最多四人、实例容量与串行生成、非和平战斗难度、存档/回程、资产锁及原生经验适配器检查。奖励开关独立，不自动开启发奖；奖励关闭时无需钱包发奖端口。设为 false 恢复原限制。原世界/服务器未修改。

独立导出 `.gradle/source-release-301e01bd9ed9-20261029-051245-04a8fdcd` 编译/重混淆打包通过，41 个已提交结构、482 个中文键及 beta 排除检查通过。未重跑 JUnit 和完整套件。随后复用已验证的 Minecraft 1.20.1 下载元数据，执行：

```powershell
.\gradlew.bat '-Dnet.minecraftforge.gradle.check.certs=false' runGameTestServer --offline --console=plain -x downloadAssets -x downloadMCMeta '-PgameTestNamespaces=saodg_height,saodg_start,saodg_concurrent' '-PgameTestRunDirectory=run/gameTestServer-height-entry-04121'
```

3 项必要 GameTest 全部通过，进程正常退出 0，Gradle 61 秒：

- 实际解析有秘密场景的 schema 4 结构，将原门洞提高到局部 Y10、高度32；验证四个旋转的门高、到达点、刷怪坐标、世界 Y57 地下方块写入，以及真实生成图接入。持久清单往返、旧清单 Y64、损坏拒绝、地下区域移动授权及真实 CleanupJob 清理/边界保留/票据释放通过。
- 两名实际测试人物投影与服务端拒绝原因一致；关闭开放项时旧限制继续有效，开启后旧开关关闭、SAO_SERVER 预设和新人物精锐前置均不再阻断资格，存档异常仍拒绝。
- 四名实际服务端测试人物、两支队伍使用非 OP 命令启动，旧开关保持 false、开放项 true、预设 SAO_SERVER、奖励 false；双实例生成/战斗隔离、生命投影、位移身体范围、清理和槽位复用通过。

没有实际远程客户端或新结构视觉试玩，未覆盖所有原生 SAO 技能或经济兼容；此次测试不等于真人局域网验收。没有替换/启动用户客户端或原服。

日志 `logs/room-height-entry-04121-20261029.log`，SHA256 `d68b8d362d228b1736670c233a619be6e7f84c6177e66d1143477fa903ad8710`。

开发包 `build/verified/0.41.21-dev-301e01bd9ed9-20261029-051245-04a8fdcd/saodg-0.41.21-dev.jar`，SHA256 `010672dcece43ec3b6478a8bbbb947a56fcfa7b2471caf63e987e7a9de9e2813`。协议仍为 20；联机双方请使用同一开发版本。
