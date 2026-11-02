# 遗留ACTIVE宠物部署的即时恢复锁：0.41.39

后续已取得[真实活动宠物两进程恢复证据](NATIVE_PET_RESTART_0.41.39_2026-10-29.md)。下文“未运行整合服”保留本次定向GameTest时的范围，不代表后续两进程实验未执行。

## 问题与修复

启动时InstanceService把非清理阶段的遗留副本转为RETURNING，创建运行对象后调用CompanionService.restorePending，再保存恢复状态；CLEANING局保持清理阶段。宠物租约仍可能是原先ACTIVE，实体和区块此时尚未加载/核对。

此前restorePending只恢复RETURN_INTENT/CONFLICT的资产锁。遗留ACTIVE部署要等CompanionService的周期回收把它改成RETURN_INTENT才冻结，其间人物已可能登录/回到外界，玩家主动召唤、选择、喂食或复活等名册入口没有该恢复锁。此处区分尚未证明归还的旧部署与正常战斗中的ACTIVE部署，不将所有ACTIVE一概冻结。

生产修复 `d3110fe2a8476ff3f290e3049c16bf6f48c2ee35`：restorePending对RETURNING/CLEANING局中的ACTIVE租约也立即恢复原有AssetGuard锁，无须先加载玩家、宠物或区块。既有pendingFor锁归属分支会呈现未确认资产；原生宠物主动操作沿用已有SaoPetAssetHooks冻结检查。没有重写名册、部署令牌、租约状态或存档schema，后续核对/原生存储/磁盘确认及解锁仍由原回收流程执行。

正常EXPLORING/BOSS_READY/BOSS_ACTIVE中的ACTIVE部署保持原访问规则，CONFIRMED历史不新增锁，RETURN_INTENT/CONFLICT沿用原保护，其他未完成事务的锁不会被抢占。此修复针对启动恢复前的窗口，不据此宣称所有退出和并发资产事务已完成验收。

## 实际定向验证

新增CompanionRecoveryGameTest，使用从NBT保存/加载的ACTIVE租约、无布局/快照的恢复运行对象和未在线的所有者UUID。夹具适配器在任何名册/部署/原生存储/区块位置访问时直接抛错，确认冻结不依赖这些操作；不伪称加载了实际SAO宠物。

- 修复前 `24fdf7c09f45` 的独立Git导出实际运行复现：`Recovered ACTIVE deployment must freeze owner assets before the first scan or login`，恢复锁测试失败，Java/Gradle退出1。日志 `logs/companion-recovery-before-24fdf7c-20261029.log`。
- 修复后 `d3110fe2a847` 的独立Git导出，`saodg_companion_identity`命名空间两项必需测试全部通过：既有真实实体索引身份回归，以及新恢复锁测试。后者覆盖正常三个战斗阶段、RETURNING/CLEANING的立即锁/待处理呈现、租约保存内容保持、已确认历史、原回程/冲突锁及其他事务锁。正常保存并退出0，随后jar/reobfJar通过；日志 `logs/companion-recovery-after-d3110fe-20261029.log`。

本轮只运行这两项Forge GameTest，未执行JUnit、完整套件或原生整合服。没有实际两进程停启、SAO名册操作/部署实体回收、重复召唤或真实客户端输入证据；这些仍需单独验证，不把本次恢复状态夹具当作整服重启通过。

## 开发产物与部署状态

产物 `build/verified/0.41.39-dev-d3110fe2a847-companion-recovery-20261029/saodg-0.41.39-dev.jar`，SHA256 `517d6d50d6ba4bb0e3d8fda20cc282d2cc045812713554ced012dc241e44a2d3`。同目录verification.json记录源码与归档哈希、构建日志和仅两项隔离测试的范围。41个结构与已提交资源严格一致，无beta/测试插件/人物或世界数据；本地化、版本与mixin/refmap配置核对通过。工作树用户.gitignore、结构与建模工具等改动未修改、提交或带入产物。

原客户端、原服及独立整合测试服本轮均未启动或更新；独立整合服保留此前验证的0.41.38及原隔离现场。C01、伴生实际重启恢复和整体验收仍未完成。
