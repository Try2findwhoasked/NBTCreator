# 活动原生宠物两进程恢复：0.41.39

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

生产包仍为 `d3110fe2a8476ff3f290e3049c16bf6f48c2ee35` 的0.41.39，SHA256 `517d6d50d6ba4bb0e3d8fda20cc282d2cc045812713554ced012dc241e44a2d3`。沿用[即时恢复锁修复](COMPANION_RECOVERY_FENCE_0.41.39_2026-10-29.md)，本轮只增加packTest，没有进一步更改生产规则。仅独立兼容服从0.41.38升级，原客户端和原服未改。

## 实验输入与中断现场

夹具 `66bec4774b2f` 独立Git导出packTestJar编译及重混淆通过，附加包SHA256 `b22f568774a7e2e2e59fc246cc4bcbd711345ea09b2c34efd7e40f05d3028c36`；日志 `logs/native-pet-restart-fixture-66bec47-20261029.log`。新测试角色通过既有双队驱动实际生成两局，在原生刺客宠物召唤并取得ACTIVE租约后，确认人物文件和原生名册、保存副本日志、flush全部世界，写入检查点，再显式Runtime.halt(73)，跳过停服/回程回调。不是任意IO中途崩溃，也不证明野外捕获。

实验ID `native-pet-restart-66bec47-20261029`；准备运行器PID70364、Java PID75724，实际退出73且未发送stop，终态 `.gradle/native-pet-restart-66bec47-20261029-prepare-process.json`。日志 `logs/native-pet-restart-66bec47-20261029-prepare.log`。

重启前只读磁盘核对 `logs/native-pet-restart-66bec47-20261029-checkpoint-inspection.json`：

- 局 `ccb144cd-974a-4c2d-a03b-bfc984f764e4` 实际仍为EXPLORING，宠物租约仍ACTIVE；另一局为 `c512b68e-e10b-4068-95c6-3b3ba6fa4563`。
- 原生名册仍Deployed=true，部署令牌与日志一致；实体区 `r.2.0.mca` 中恰好保存一只实际 `mod_1cab0b39:pet_assassin`，UUID `15431694-efa1-4121-92bc-24e8898baa22`。不是已收回后再验证空记录。
- 原隔离实体区字节保持。检查点SHA256 `7afebd031ea4d1b715595bd497eed90e3febff213d65732f8e78111f1b31dd14`，准备清单SHA256 `511c54d24207013fa559c3bb6d42aa2a44cfa77f02c98ae559a3b336e6203645`。原始checkpoint.nbt和prepared.json均复制到logs。

## 第二进程实际恢复

恢复运行器PID53932、Java PID66312使用同一世界，按准备清单及检查点散列校验来源。原生固定人物UUID从实际保存文件登录，不重建库存。最终 `logs/native-pet-restart-66bec47-20261029-recovered.json` 的passed为true，SHA256 `4d4b17c880c1e2c4d69579f9f6b19ab2efad22d7ad4080f38d1b44319620cbea`：

1. ServerStarted阶段、人物登录或实体扫描前，日志重新加载同一ACTIVE租约，副本已按生产策略转入恢复，AssetGuard和pendingFor保护已存在。
2. 原四人物实际PlayerList登录后返回外界。宠物主人在回收未确认时保持冻结，调用实际PetSystem.summon不改变原生名册，没有利用空窗口重新部署。
3. 生产回收/清理完成后，旧实体在所有已加载世界消失，名册只有一条相同Id、Kind、Level和Xp的已收回记录，主人解除冻结；两局释放槽位，无回程/票据残留。
4. 主人在外界再次调用原生召唤，得到不同实体UUID的新部署，未继承旧副本行动权。对旧绑定执行10次SaoCompanions.recall，均确认旧租约结束，但新部署完整记录及实际身体不受影响。
5. 再按原生接口收回新部署，原生名册磁盘与SavedData完整一致；四个人物保存文件的库存、末影箱、Kol、原生XP及迷宫区成长与中断前基线一致。此比较不外推为所有模组能力/Curios或任意人物字段均已覆盖。

停止后只读扫描10个副本实体区域文件，旧部署UUID出现0次，证据 `logs/native-pet-restart-66bec47-20261029-retired-body-disk-scan.json`；既证明当前索引中已消失，也核对了已保存区域未残留该旧身体。

## 停服、保全与发布范围

第二进程正常stop、退出0、端口关闭，终态 `.gradle/native-pet-restart-66bec47-20261029-recover-process.json`，日志 `logs/native-pet-restart-66bec47-20261029-recover.log`。退出73仅属于第一阶段显式实验，不能写成两阶段均正常停服。测试插件已从mods移至备份 `validation-history/native-pet-restart-66bec47-08bdf81e/fixture-native-pet-restart-passed.jar`；旧0.41.38及运行前世界/配置在同一备份中保留。

保全 `logs/native-pet-restart-66bec47-preservation-20261029.json`：1229个保护文件中1218字节保持、2个properties仅注释变化、8个指定历史恢复人物文件及旧版本包为已声明变化；549份其他人物文件保持，unexpected为空，配置语义及133项世界GameRules保持，包括keepInventory始终为true。`logs/native-pet-restart-66bec47-roster-preservation-20261029.json` 确认140个旧所有者名册逐条保持，仅新增本轮四个测试角色条目，原宠物记录最终已收回。

原隔离局 `f99ebe03-0e35-4e73-822a-063b6b01c318` 和未知结晶保留，实体区域SHA256仍为 `51916e76d1a69aa84a76d4d8945b0f6e81747040bf8749f68faf4b045366ac9d`，证据 `logs/native-pet-restart-66bec47-20261029-recover-retained-entities-20261029.json`。最终只有原隔离槽QUARANTINED，其余FREE，待回程和票据0。

开发包仍为 `build/verified/0.41.39-dev-d3110fe2a847-companion-recovery-20261029/saodg-0.41.39-dev.jar`，verification.json追加本轮实际两进程报告及范围，保留此前两项GameTest证据。私有服保留0.41.39，入口/奖励配置不变。本轮未跑JUnit/完整GameTest，也未重复整场通关；首次进程实际生成后中断，恢复按生产规则中止并清理。

该证据只覆盖一只原生刺客宠物、完整flush的指定探索检查点和EmbeddedChannel人物。任意写入中途故障、其他宠物/灵宠、全部中断阶段、远程客户端与长期性能仍未覆盖；L01与完整伴生/C01验收不整体勾选。
