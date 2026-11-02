# 旧击杀计数与重复收益隔离

2026-10-28，运行时仍为 `0.41.7-dev`。仅修改已授权私有副本 `run/pack-acceptance-20261028-081137-fd148a65`；原 `SAO-server-0.7` 五个源脚本复查散列不变。入场、经济奖励与外部资产门禁保持关闭/UNKNOWN。

## 精确补丁

现有较新整合包的战斗监控、收益和历史补丁不能直接套用到该旧服。本轮在 `SOURCE_MANIFEST.json` 的 `sao-server-0.7` profile 中增加五个独立源散列与补丁：

- `sao_battle_monitor.js`：受管实体不进入旧调血、战斗记录和结算入口。
- `sao_boss_enrage.js`：受管实体不进入旧狂暴处理。
- `sao_combat_income.js`：受管实体不登记旧伤害参与者、不发旧战斗珂尔或额外 XP。
- `sao_boss_armor_drops.js`：受管实体不发旧护甲掉落。
- `sao_quest_kill_history.js`：在排队和直接历史入口查询运行实例冻结的 legacyKillObjectives，不以 NBT 作为授权；保留正常统计迁移和原奖励声明。

`python tools/verify_compat_patches.py <原服目录> --profile sao-server-0.7` 对该 profile 全部六个文件（含已存在的钱包）完成源散列、精确合并及语法检查。只将本轮五个新合并脚本复制到私有副本，逐文件备份及散列写入 `legacy-kill-installation-20261028.json`；不修改原文件或套用其他 profile。

Node `legacy_entity_guard_test.cjs` 对七个实际合并事件回调检查：受管时在旧业务读写前返回，非受管或没有桥时仍进入原业务体；历史的冻结 false 阻止排队与直接入口、true 保留原排队。测试使用读写哨兵，不证明真实服务器身份或 Boss 数值效果。

## 实际原生/API/脚本验证

新增 `LegacyKillProbe`，仅 `-Dsaodg.packLegacyKillAcceptance=true`、指定私有目录、无真实在线玩家/运行实例时执行。使用一个临时 PlayerList 成员与真实原版僵尸。为原生 FTB KillTask 配置单独的测试章节，ID `5A0D6F1E00000001/2/3`，100 个僵尸目标、无奖励；未修改原任务或使用原账号。

身份测试在同一个同步调用内将临时 RuntimeRun 接入服务，调用正式 registerEnemy 登记世界中的同一实体对象，调用完成即撤销运行映射/实体索引。未分配槽位、生成结构、给玩家办理入场或传送。测试切换该临时记录的 false/true 值只为覆盖两个策略分支，不证明实际开局快照流程。

最终日志 `logs/pack-legacy-kill-marker-20261028.log`，结果 `legacy-kill-probe-17683a54-9cd1-4ee2-b6af-5b17d97ea174.json`：passed=true、无 cleanup_error。人物 `3382026a-8513-40c3-9307-6ed26fbdc6e6`。

| 检查 | 实际结果 |
| --- | --- |
| 冻结 false 调用原生 killedEntity/awardKillScore | 类型击杀统计、分数不变 |
| 冻结 false 调用实际 FTB KillTask.kill | 测试任务保持 0 |
| 冻结 true 调用同一原生/API 路径 | 类型统计 +1、分数 +7、FTB 任务 +1 |
| 对受管僵尸投递未取消的真实 Forge LivingDeathEvent，等待 4 tick | 旧钱包入账 0，没有旧收益/历史已处理标记 |
| 完整复制当前 saodg 复合标记（schema/run_id/encounter_id/room_id/role/reward_policy/starred）的野外僵尸 | isManaged=false，旧计数允许；投递死亡通知后原钱包 +3，旧收益与历史标记均成立 |

此前 publication 日志中也有一次通过，但野外对照只放了旧式 saodg_run 字段；它不作为完整标记伪造证据。最终 marker 日志使用当前完整复合标记重新通过全部对照。

这些是受控通知与直接原生 API 对照，没有伪造成功击杀结果来给实际挑战清房。没有使用真实伤害链打完整副本，不证明取消/复活、原生 SAO XP、实际 Boss 调血/狂暴/护甲掉落或完整两队战斗验收。

## 身份发布与未通过尝试

最初同一 addFreshEntity 调用之后立即查询 UUID，世界尚未返回该对象，严格身份检查拒绝（`pack-legacy-kill-20261028.log`）；区块预热后的同 tick 检查仍失败（`pack-legacy-kill-loaded-chunk-retry-20261028.log`）。未放宽运行时身份校验。

夹具最终先给测试区块临时票据并预热、插入实体，再于下一 tick 检查世界 UUID 查询确实指向同一对象后才开始登记。首次下一 tick 检查成功；JSON 中 publication_wait_ticks=0 表示没有再额外等待，不代表插入当 tick 已可见。记录了未移除、已加入世界及原版 Zombie 确切类。票据仅当原来没有时添加，完成后撤销。

该记录尚未覆盖自有战术敌人。后续专项验证确认自有实体同 tick 查询及严格注册均成功，保留现有生产流程；见[原生注册验证](SPAWN_PUBLICATION_2026-10-28.md)。

`pack-legacy-kill-loaded-chunk-20261028.log` 中另有一次 JVM 在加载阶段退出，没有完整崩溃原因。通过验收的那次进程也在停服命令处理前已退出，未产生正常保存尾部；这些日志保留，不冒充正常停服证据。

之后未开启任何夹具开关重新启动同一副本，`logs/pack-legacy-kill-cleanup-20261028.log`：管理状态 runs/lobbies/pendingReturns/tickets 均为 0、四槽位空闲、journal=true，测试区块 [3,3] 不处于强加载。正常 stop、全维度保存完成、退出 0，25579 端口释放。保存后的 dungeon/entities 四个 region 文件均为空，没有持久化实体区记录；不使用静默 selector 命令作为额外成功证据。

## 构建与限制

夹具/reobf 编译及本轮完整 build 成功；Node 七个回调、精确合并及语法检查通过。规则层未改，build 的 JUnit 沿用同版既有 100 项结果；本轮未重跑默认 43 项 GameTest。临时夹具与测试章节在停服后移入 validation-history，审计人物/存档和结果不删除。

正式门禁仍关闭。市场、完整事件伤害链、真实客户端多人、技能/枪械、完整故障与性能验收仍未完成。

最终完整复合标记那轮也直接执行 status/validate/forceload query/stop，marker 日志确认无运行/票据、测试区块未强加载、全维度保存完成、退出 0；保存后实体区文件仍全部为空。
