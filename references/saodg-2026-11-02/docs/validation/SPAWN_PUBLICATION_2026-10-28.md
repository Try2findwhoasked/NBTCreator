# 自有战术敌人原生注册时序

2026-10-28，真实私有整合包、运行时 `0.41.7-dev`。入场与奖励保持关闭，没有创建大厅、生成结构或传送玩家。原服未修改。

## 验证目标与结果

上一轮观察到原版僵尸插入后当 tick 尚不能按 UUID 查询。这不是自有战术敌人延迟发布的证据，因此先用真实 `saodg:ruins_enemy` 检查生产调用顺序，没有直接增加等待队列或放宽身份校验。

新增仅显式 `-Dsaodg.packSpawnPublicationAcceptance=true`、私有目录且无人/无实例时运行的 `SpawnPublicationProbe`。私有区块预热后创建自有实体，在同一同步调用内接入临时运行记录、调用正式 registerEnemy、原生 addFreshEntity 和当前 EnemyCombatService.register，结束立即关闭控制器并撤销索引；下一 tick 再按同一对象做严格登记和注册。没有让这个临时记录进入正常实例调度。

首次修正夹具后的日志 `logs/pack-spawn-publication-mapped-20261028.log`、结果 `spawn-publication-probe-511103c1-3a52-4e13-bf40-8e8d3db85c6f.json` 通过。随后启用与波次一致的 AI（setNoAi=false），写入当前完整 saodg 复合标签再复测：

- 日志 `logs/pack-spawn-publication-wave-shape-20261028.log`。
- 结果 `spawn-publication-probe-5d9bae04-ab0c-4877-836f-73d9c3eb504c.json`，passed=true、无 cleanup_error。
- 实体 `5964043d-3f64-43eb-9497-eb667166a65a`。
- 当 tick 世界 UUID 查询即指向同一对象，strict register=ACCEPTED。
- 下一 tick 查询仍是该对象，strict register=ACCEPTED，实际实体设置为 VANGUARD 角色。

当前证据支持保留自有战术敌人的即时注册流程，运行时规则未修改。夹具使用无重力将实体保持在未建结构的测试位置；没有调用控制器攻击 tick，也没有验证寻路、实际警示/伤害、三种角色的完整战斗或真实多人。

## 夹具失败与修正

初版独立 packTest JAR 通过自有类静态类型调用继承的 Minecraft 方法，重混淆后仍留有未映射 setPos/discard，原生运行 NoSuchMethodError；清理的第二次异常逃逸，随后触发 60 秒看门狗。日志 `logs/pack-spawn-publication-20261028.log`、崩溃记录 `crash-2026-10-28_19.22.02-server.txt` 保留，没有当作生产注册失败。

夹具现在通过原版 Zombie 静态接收类型调用继承方法，仅自有 combatRole 等方法保留 DungeonEnemy 类型；同时捕获清理异常，仍写出失败报告。检查实际生产 JAR 的 EnemyCombatService 字节码，继承方法已经是原生映射名；没有用测试问题推导生产 JAR 也损坏。

## 票据清理与正常保存

首个失败夹具在清理异常前留下测试区块 [3,3] 强加载。该点在前轮测试结束时明确没有强加载，属于本次夹具创建的已知资源。初次无夹具复启动中，提前排队的 execute 命令携带空世界上下文，forceload 清理失败，日志 `pack-spawn-publication-cleanup-20261028.log` 保留；未将保存成功误称为票据清理成功。

增加独立的 `-Dsaodg.packSpawnPublicationCleanup=true` 模式，只对同一私有目录、无人/无实例下的这个已知测试区块操作，不创建实体或控制器。`pack-spawn-publication-owned-cleanup-20261028.log` 与 `spawn-publication-probe-8ce4367f-38bd-4fff-8e2b-5cb7abb89f18.json` 确认强加载 true→false，之后在启动完成后提交的控制台查询也返回 not marked for force loading，正常保存退出。

最终 AI/完整标签复测结束后再次确认：runs/lobbies/pendingReturns/tickets=0、四槽位空闲，区块 [3,3] 未强加载，全维度保存完成、退出 0，端口释放。临时 JAR 移入 validation-history，不留在 mods。

## 构建与范围

本轮 packTestJar/reobf 与完整 build 成功；test 复用同版既有 100 项 JUnit 结果。本轮没有运行默认 43 项 GameTest，因为生产规则未修改；也没有据此宣称完整整合包战斗、取消/复活、技能/枪械、市场、经济故障、真实客户端多人或性能验收完成。正式开本和奖励仍关闭。
