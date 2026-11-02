# 原生经验生产死亡确认与领取链路

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

最终夹具源码 `6dbb3629fbc3985bd36c54ac33caeed86083f653`，入口 `-Dsaodg.packNativeXpPipelineAcceptance=true`。生产模组仍为原 0.41.16（SHA256 `92e327bfbfdd19d0506c1c8a57a9e9b490d248728dbd3856493444e178d07471`），没有重打生产包。

## 场景与结果

仅使用已授权的 `run/pack-acceptance-20261028-081137-fd148a65`、127.0.0.1:25579，保持 SAO_SERVER 和入口/奖励关闭，使用已验证的真实 legacy_wallet。原服及客户端未动。

夹具建立真实 PlayerList 非 OP 人物、正常 RESERVED→ACTIVE 槽位、冻结名单、返回位置及活动普通战斗房，首波数量取实际定义，为 4 个真实 Zombie。反射仅用于建立活动场景；没有执行大厅入场、结构生成或真人穿门。从伤害开始，不替换生产经验服务/确认谓词/所有者/持久化目录，不手工写入 confirmedEnemyDeaths/nativeExperienceLinks，不直接调用 seal/confirm。

- 第一次实际 Zombie.hurt 致死在 LOWEST 晚取消，没有确认或经验；第二次实际致死未取消，当帧确认集合、链接仍空，XP 仍为 0。
- 正常后续 tick 的 EncounterService.confirmDeaths 确认必需敌人、共享检查点及经验 READY。读取实际 state.nbt，经正式世界校验器和 RunRecord.load 确认精确死亡/请求链接；真实 native_xp 分片为 READY。
- 打开容器时自动重试及显式 claim 均未支付，显式结果 close_container。下一 tick 关闭容器后，正常生产 claim 将 XP 0→13；未越过每 tick 两次发放预算。
- 生产内存和分片 CONFIRMED；真实人物文件 UUID 与 ForgeData.SaoProgress.xp 独立读取相符。连续 10 次旧请求均 already，XP 保持 13。
- 完整库存为原 7 个带 NBT 标记铁锭，加一次合法 SlashBlade 首次攻击 tiny proud soul；没有额外材料或迷宫区成长。
- 正常 returnPlayer 保存确认、abort、CleanupJob、槽位释放后，真实世界日志无 runs/returns，四个槽位 FREE；场景以 ABORTED 复盘收尾，没有伪造通关奖励。

run `36a3efff-e39c-484e-9ae7-9f404dfa415c`；人物 `0213ed7a-d04a-4670-a0f4-eb40352fc12f`；敌人 `d2ee9d57-bd5f-4ee7-8ee4-1aa521fe2961`；请求 `0dba6bf4-2262-4340-85f0-9ef6f0131279`。击杀 tick 46，检查确认/领取 tick 49。诊断 can_act/can_damage/player_legal/enemy_legal/enemy_lookup 全 true，operator=false，濒死状态已知且 false。

## 失败、清理与证据

首版 `204ba40` 使用房间原点定位，在伤害授权断言失败，未发 XP，仍完成正常清理。首轮未记录分项授权结果，不能倒推具体哪项失败。最终版改用实际 occupied 格中心并补足诊断；没有改变生产策略或取消权限断言。两版独立 Git 导出仅编译 packTestJar，17/18 秒通过；两原生进程 172/17772 均正常停服、退出 0，首轮夹具、数据快照、人物及失败证据保留。

启动前完整存档、配置、脚本和当前模组备份于 `validation-history/native-xp-pipeline-204ba40-cb6e8e0e`。原 765 文件中 763 字节不变，含全部 93 个人物/进度/统计文件；server.properties、PacketFixer 仅时间注释变化且键值一致，没有意外修改。新增测试人物、经验分片、复盘和清理结果正常保留。最终 56/56 KubeJS 脚本、0 脚本错误/警告；真实 admin status 为 0 人、0 runs/lobbies/pendingReturns/tickets、四个 FREE、journal=true。其他整合包已有加载警告不因此视为通过。

最终夹具已归档并移出 mods；私有服已停、122 个 JAR、仍为原 0.41.16 和关闭配置，无待运行后台测试。beta 结构未编辑或打包。

| 证据（均在 logs/） | SHA256 |
| --- | --- |
| native-xp-pipeline-probe-844d5d06-b8a6-4620-b441-d2733794a16a.json（成功） | 96a55e9ef9d0f1851fbd8c6d3b13c893521ea6243862372387780a9b713e3b10 |
| pack-native-xp-pipeline-04116-occupied-cell-20261029.log | 770da6626b6e9b8b2ef409a2e4eb3e8bfd96b11d08632fa760072e799f5ba12f |
| native-xp-pipeline-probe-6f74de1e-5dc7-4400-acf7-1b0c02975abb.json（失败） | 48d17b21c24ab98253b5bdf9484045a0ce625f3f0c9287f5aff671b300db5e52 |
| pack-native-xp-pipeline-04116-20261029.log | 4516d6ae30fcbcee66f62306a668f3949695d59c9a856a312792afdca2cb0430 |
| native-xp-pipeline-04116-preservation-20261029.json | c57f29ecb3644115f0b1709b309d67d22477bce4cffebdddc619c8bb7a5ec311 |

最终夹具 SHA256：`d15448ce2ca1e65f77faf3fe585e4b70d2690456976392fc66c1d3586a42b11a`。

本例证明普通原版敌人的实际击杀→生产持久死亡确认→原生 XP 服务领取及同进程去重。没有真人客户端输入/网络、完整房间通关、首领/精英多轮、重启/硬退出恢复、全原生经验故障矩阵和并发团队证据。正式入口继续关闭，桥仍 BOUND_UNVERIFIED，不提升整合包总体验收状态。
