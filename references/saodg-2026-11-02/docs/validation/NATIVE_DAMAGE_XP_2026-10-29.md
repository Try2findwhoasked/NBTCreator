# 原版敌人实际致死伤害的原生经验捕获

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

2026-10-29，在已授权的私有副本 `run/pack-acceptance-20261028-081137-fd148a65` 执行。最终测试源提交 `53c0e02f26b1`，从独立 Git 导出编译 `packTestJar`/reobf，通过（17 秒）；未构建或替换生产模组，私有运行端仍为 0.41.14.2，用户当前开发包仍为 0.41.15。经验 hook/service/port 相比该运行版本没有源码变化。

显式开关 `-Dsaodg.packNativeDamageXpAcceptance=true`；只有确切私有目录、没有真实在线玩家或活动实例时才运行。原服、静态整合仓库、用户客户端均未改动。正式入场、经济奖励、市场所有者声明保持原配置。

## 场景与实际边界

真实原版 Zombie 在目标维度的合法入口占地生成，等世界实体索引发布后，再临时登记人物、敌人和完整图快照；人物通过受控传送到同一房间，断言正常成员/房间伤害策略允许攻击。没有放置房间结构、分配槽位或通过正式准入。这些临时登记与独立经验日志只在同一段同步测试调用中接入，finally 恢复原服务、人物位置和全部索引，不让临时局进入正式运行 tick。

本次通过 `Zombie.hurt(playerAttack, ...)` 触发原生伤害与完整 Forge 死亡事件链，未反射调用 ExternalKillXp.onDeath，也未手工发布死亡事件。

1. 第一次实际致死伤害在 LOWEST 监听器晚取消，未移除敌人、未立即增加 SAO XP、没有死亡链接或待处理请求。
2. 恢复该实验敌人的生命后再次实际致死，获得另一个未取消的死亡事件；生产捕获清除旧取消事件，生产 `seal` 固定一个 WAITING_DEATH 请求。原生数额 13、玩家/敌人身份正确，人物 XP 仍为 0。
3. 没有伪造持久死亡确认。实际 `claim` 返回 `saodg.native_xp.death_pending`，XP 仍为 0；立即经验提示标记未写入。
4. 新记录按当前服务器配置冻结 `legacyKillObjectives=false`。完整库存与独立预期一致：原 7 个带标记 NBT 的铁锭，加一次拔刀剑首次攻击进度的原生奖励；迷宫区成长未改变。

最终人物 `3a6378ca-e072-4a7a-b83c-93f82ea56a12`，临时 run `05ab8998-2bb1-409b-aacb-3f8aa9610c1e`，敌人 `e62a9bd9-e380-44c6-8ee8-0f7afcb26d55`，请求 `2730b619-f0ac-4993-8267-beccecc24018`。所有者 `saodg:sao_xp_curve_v2_1731657`，结果 `native-xp-probe-e307a9c1-de41-41b4-8c88-c7639876e1d3.json` 为 passed=true、无清理错误。

## 调查中修正的夹具假设

最初两次分别为 `e07a2efd134d` 与诊断提交 `13580339dc7d`。敌人在已发布后移到房间，原生异步索引尚未重新发布：enemy_lookup=false、enemy_owner=null，而人物濒死/成员/位置正常；正常伤害策略正确拒绝。没有放宽登记检查，改为在最终合法位置生成并等待发布。结果 `9473c62e-39e8-4307-9743-f83e03463936`、`8d3c48e1-79a1-4f16-9f59-712daf050db9` 及对应失败日志保留。

第三次 `608e855560c6` 已通过实际伤害和原生捕获，但“库存完全不变”断言失败。只读解析该临时人物文件，发现多出一枚 `slashblade:proudsoul_tiny`，SAO XP 仍为 0，迷宫区数据未增加。检查已安装 SlashBladeResharped-1.20.1-1.9.65.jar 的实际数据：`data/slashblade/advancements/root.json` 使用 `minecraft:player_hurt_entity`，并通过 `data/slashblade/loot_tables/rewards/first.json` 发放一枚微小耀魂。这是首次攻击进度的合法一次性奖励，晚取消死亡不撤回已发生的攻击；没有据此删除原生进度或奖励。

最终夹具断言首次攻击进度原先未完成、后来实际完成，并独立构造“原完整库存＋一个原生首次攻击奖励”的预期，既不拿实际库存反填预期，也不把此奖励计为 SAODG 发奖。第三次结果 `d502cc2f-c3fc-4e75-901d-5c69d5c03d6a` 同样保留。

## 证据、保存与退出

- 正式模组 SHA256：`1d77fec327514ed7551c19408172ec337c0ba849e12c019f0118e243b3e29034`。
- 最终夹具 SHA256：`978b4f3d6861c1244c0cd1bb4a1580d13c712fce7731e917d92711bff6163096`；已从 mods 移至 `validation-history/native-damage-xp-e07a2efd134d-20261029`，恢复原 122 个 JAR。
- 最终日志 `logs/pack-native-damage-xp-native-reward-20261029.log`，SHA256 `ce2836afaa62c5d3b24ec6e123d35b517641944092c98fd046c74c9af8624713`。
- 最终结果已原字节复制至根 logs，SHA256 `a01ae75a691b1eab6f430da229c9b2e0ee9cfa1132d0946234be4468aeba6e9e`。
- 启动前保护 749 份原有文件，747 份逐字节不变，包含全部 77 份原有人物相关文件和原模组/脚本/服务端配置。server.properties、config/packetfixer.properties 仅保存注释时间变化，解析后的配置键值均相同；没有强行恢复或重写这些文件。证据 `logs/native-damage-xp-preservation-20261029.json` 与 `logs/native-damage-xp-poststop-20261029.json`。
- 每次实验均正常 stop、全维度保存并退出 0；最终 list 为 0 玩家，25579 释放。辅助控制脚本误用了不存在的 `saodg status`，该命令未通过，不把它记为成功检查，也未为此再启动服务。改为只读检查停服后的实际世界日志：runs=0、returns=0、四槽位 FREE，运行中的夹具也断言临时登记已移除。

## 范围限制

新增证据覆盖原版敌人实际致死事件、晚取消后再杀、真实原生回调捕获和未确认拒绝发放；它补充[旧回调/端口记录](NATIVE_XP_PORT_2026-10-29.md)，没有把两份不同边界证据拼接成端到端发放通过。

本次没有通过生产下一 tick 的 EncounterService.confirmDeaths 形成持久确认链接，没有让正式 NativeExperienceService 完成实际发放；独立日志中的 WAITING_DEATH 不属于真实副本战绩。市场外部资产所有者仍未获完整验收，没有伪造 CLEAR。真实副本完整击杀→确认→发放、跨级治疗/体力、全部故障恢复、多人和完整 SAO 兼容仍待验证。未重跑 JUnit、默认 GameTest、旧原生端口检查或经济性能采样；不需替换当前模组。
