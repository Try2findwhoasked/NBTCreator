# 0.41.62 随机怪物、队伍钥匙和 SAO 奖励箱

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

本轮只修改 SAODG。用户补充的 SAO 风格、不同档位不同模型、元素居中和删除无关内容，均纳入最终界面。未安装到实际客户端/服务器整合包。

## 当前行为

- 原生普通怪池从 3 种扩至 8 种：翠绿哥布林、灰皮哥布林、灾变尸鬼、盾卫哥布林、巨口幼兽、人面魔蛛幼体、幽冥狼、骷髅武士。小首领仍使用独立 2 种池，最终首领不参与抽取。
- 原版后备池含僵尸、尸壳、蜘蛛、卫道士；构装后备池含先锋、游击者和咒术师角色外观。既有战术开关继续决定是否使用自制攻击。
- 按本局种子、房间和波次随机抽取，并在作者出生标记附近最多尝试 96 个随机位置，再尝试原标记。必须同房、有安全地面、无方块碰撞且不与本批身体重叠；无法安全生成则拒绝。
- 星标目标出生满 200 游戏 tick 后发光，普通怪不因本功能发光。
- 主路产钥匙房和封印大厅完成后，出现独立金色三维钥匙，带青色核心、上浮与旋转。优先采用最后必要敌人的安全死亡位置，否则采用房间到达点；支路不制造无用途钥匙。
- 有效本队成员在 2 格内且视线可达时拾取，否则满 100 tick 自动计入队伍。拾取前主路门仍无钥匙额度，封印大厅仍不进入首领准备状态；重复清场/拾取不会重复记账。
- `pending_keys` 日志保存房间和实体 UUID。旧日志无此字段时保留原钥匙语义；重启仍沿用原有中止/回收流程，不宣称恢复战斗。

## 奖励箱与交互

普通档为深色钢框与青色光带；精良档为银色框架、绿色核心、侧翼与顶部凸台；珍藏档为金框、紫色核心、四角冠饰与更高顶饰。三档均有独立闭合和开盖模型。几何为本项目原创，使用原版纹理。

实体结算箱的 `tier` 状态根据本局配置与成绩显示最高可用档位外观；它不替玩家选择个人领取档位。开箱保留档位，显示开盖、声音和粒子，40 tick 后合盖，不引入共享容器或方块实体。

界面只展示本局奖励类型、居中的箱模档位、实际物品、必要费用及领取/关闭。基础奖励和个人宝箱仍分别使用原有个人操作记录；历史奖励由综合菜单查询。移除背包预览、战报、返回大厅、刷新、占位格和装饰箭头，仅在确有溢出内容时翻页。

开启需要二次确认，沿用原 CLAIM 请求与服务端玩家/操作 ID/版本/固定选择校验。客户端不自行发奖或扣款；选择锁定、等待确认和冻结状态继续受到限制。未开启奖励的局不会因新界面产生奖励。

## 验证与限制

| 检查 | 实际结果 |
| --- | --- |
| 15 项定向 JUnit | 通过：随机池覆盖与可重放、原生白名单、必要死亡、主路钥匙、固定奖励选择与重复领取规则 |
| `saodg_room_rewards` Forge GameTest | 1 个组合夹具通过：4 种身体安全放置/阻塞拒绝、未拾取钥匙日志与门锁、重复清场/拾取、99/100 tick、封印大厅准备、真实 199/201 tick 发光、三档开盖与定时关闭 |
| 有效成员检查 | 同一夹具使用两个实际注册的嵌入式连接玩家，验证外队、旁观和错误实例归属不能提前拾取，正确成员靠近只记账一次；不是两个人类客户端验收 |
| 开发客户端 | 实际截图检查三档开合模型、居中界面、选择精良档与二次确认；隔离目录中使用合成展示数据，不计为真实经济支付验收 |
| 打包与夹具编译 | `assemble gameTestClasses packTestClasses` 通过；生产包不含 GameTest 或截图夹具 |
| 全量 `build` | 初次 136 项中 6 项失败。修改前 HEAD 独立快照的原 `LayoutTest` 与 `LegacyWalletAssetScopeTest` 共 11 项中复现相同 6 项失败：旧端口默认高度校验 3 项、旧钱包目录检查 3 项。本轮未改这些实现/测试，不能称全套 build 通过 |

日志：`build/room-rewards-tests.log`、`build/room-rewards-gametest-final.log`、`build/room-rewards-client.log`、`build/room-rewards-assemble.log`。基线复现：`build/room-rewards-baseline/baseline-tests.log`。

截图：`build/previews/reward-chest.png`、`reward-chest-confirmation.png`、`reward-models.png`。产物：`build/libs/saodg-0.41.62-dev.jar`。

随0.41.63-dev源码快照保存的截图：[奖励界面](images/0.41.63/reward-chest.png)、[二次确认](images/0.41.63/reward-chest-confirmation.png)、[三档模型](images/0.41.63/reward-models.png)。均来自上述隔离开发客户端的合成展示数据。

最终 JAR SHA256：`827107b49edfaa3f7d3a39b35c3148929a51a2de6f9cc5d73d3faa0e04fec94b`。已核对六份档位/开合模型均入包，测试与截图夹具未入包。最后一轮定向测试使用独立结果目录 `build/test-results/room-rewards-final`，绕过 Windows 对旧 `output.bin` 的文件占用；15 项、0 失败。

```powershell
.\gradlew.bat test --tests cn.saodg.domain.encounter.RoomEnemyRosterTest --tests cn.saodg.domain.encounter.NativeEncounterIdsTest --tests cn.saodg.domain.encounter.EncounterTest --tests cn.saodg.domain.reward.RewardTest --tests cn.saodg.domain.layout.BloodRouteTest
.\gradlew.bat runGameTestServer -PgameTestNamespaces=saodg_room_rewards -PgameTestRunDirectory=run/gameTestServer-room-rewards-new
.\gradlew.bat runClient -PrewardChestPreview
.\gradlew.bat assemble gameTestClasses packTestClasses
```

截图入口仅在显式 `rewardChestPreview` 属性下加入 `src/gameTest` 客户端夹具，使用 `run/client-room-rewards-preview`，完成截图后关闭，不打开玩家世界。

版本 `0.41.62-dev`，网络协议 20 升为 21，两端需同步更新。新增实体、图标和 `tier` 状态不作为旧版存档降级依据。

扩展 SAO 种类按本机 r234 JAR 的 `SaoMonster.IDS`、构造器和行为字节码核对，仍使用准确类名/类散列适配门禁。新增池尚未在完整 SAO/灾变整合包运行；真人联机、网络延迟、完整自然战斗、硬退出和正式经济支付仍需另验。

实现参考 [Forge 1.20.1 Screens](https://docs.minecraftforge.net/en/1.20.1/gui/screens/)，未复制 Hypixel、DimDungeons 或其他上游资产。
