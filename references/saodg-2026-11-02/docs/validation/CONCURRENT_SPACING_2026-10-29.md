# 一格连接下的双实例门禁与旧局请求（2026-10-29）

测试提交 `40b75c3bd9c8`，生产逻辑仍为 0.41.14.1 / 协议 19。将现有四人双实例夹具移至 `saodg_concurrent`（仍包含在默认命名空间），补充实际煤炭门和序列化操作请求检查。独立 Git 导出 `.gradle/concurrent-spacing-40b75c3bd9c8` 中只运行 `runGameTestServer -x downloadAssets -PgameTestNamespaces=saodg_concurrent -PgameTestRunDirectory=run/gameTestServer-concurrent-spacing-retry-041141-20261029 --offline --console=plain`，未执行完整 build/JUnit、重打包或替换当前客户端类路径。

1 项 required GameTest 通过，正常全维度保存，退出 0，耗时 1 分 6 秒；日志 `logs/concurrent-spacing-retry-041141-20261029.log`。真实运行 ID：第一局 `79e38f4f-3457-4543-b8bd-62ea858f3bba`、第二局 `5b746d5b-cd19-4f30-99af-5e7b4aee04ce`、复用第一槽位的新局 `e541be25-5b4e-40ec-9610-6c00c1e79287`。

除保留此前夹具的双向实际伤害/投射物/秘密拒绝、独立名单投影、星标确认/钥匙和另一队清理期间继续战斗外，本轮证明：

- 外队玩家实际移动到另一队居中煤炭门的可触及/可见位置，交互被拒绝，门仍为煤炭，openedRouteDoors 与 revision 不变。
- 本队实际杀星标取得钥匙，从合法已探索房内点击自己的一格间隔中央门，门方块实际清空，只消耗一次本队钥匙；立即重复点击不再消费或推进 revision。另一队的门与日志不变，清理第一槽位后另一队门仍在。
- `ClientAction.LEAVE` 经真实 encode/decode 送入服务端 UI 意图处理器：另一局 context，以及第一局关闭/原槽复用后的旧 context 都得到明确 stale_context。检查前确认序列号和频率门槛放行，避免把节流跳过误算成权限拒绝；拒绝后各局成员归属保留。这不等同真实网络传输。
- 四名成员各自回程后，完整物品 NBT/数量和测试钱包字段保留；三次 run 的实例租约/实际生成与清理作业票据均释放，受管敌人清除。

首轮 `d8cd189b9fec` 日志 `logs/concurrent-spacing-041141-20261029.log` 在 stage 5 失败：新增测试把 UiSyncService 的 long 时间戳按 int 反射读取，已修正为 getLong；不算首轮通过，不是生产门禁故障。首轮独立世界与日志保留。

仍使用四名 EmbeddedChannel/PlayerList 服务端人物、提高生命并暂停敌人 AI，不证明四个远程客户端、原生 SAO 技能/钱包、实战平衡或性能。未解除正式入场限制，开发包无需更新。
