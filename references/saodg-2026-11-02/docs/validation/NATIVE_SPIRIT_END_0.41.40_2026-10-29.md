# 原生临时灵宠结束凭证：0.41.40

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

## 缺口与修复

SaoSpiritCompanions.known原先允许从日志按UUID、出生nonce及原生字段确认对象，没有在日志回退时检查当前世界索引。复制真实灵宠完整数据的另一对象因此可能通过原生expireSpiritPet回调，把仍存活的真实身体所对应租约标记为nativeEndObserved。中央战斗归属虽已拒绝替身，不能代替结束凭证的对象身份核对。

生产提交 `eb1a38b7e5016dffd015db54eb02eede9f685c03`：实际出生WeakReference匹配仍保留，以支持加入世界前的合法出生/撤回；日志回退只接受当前副本维度索引中的实际身体。observedEnd先核对同一对象确已移除，再删除结束记录，避免错误对象的回调消耗其他身体的待确认凭证。原生时限、nonce、资产/能力散列与回收规则保持；不把永久宠物名册规则套给临时灵宠，没有存档schema变化。

产物 `build/verified/0.41.40-dev-eb1a38b7e501-native-spirit-20261029/saodg-0.41.40-dev.jar`，SHA256 `cb197773ba2f13252c3d4f431a317ad4f882df0d89c6e1294c4cb14d21798029`。独立Git导出jar/reobfJar/packTestJar编译通过，41个结构与提交一致，无beta、测试插件、世界或人物文件；本地化、版本与mixin/refmap核对通过，verification.json附实际报告范围。未执行JUnit或完整GameTest。

## 相同夹具的新旧对照

使用实际r234 `SpiritPets.summon(player, 0, duration)`，由原生 `beginSpiritPet` 和真实出生钩子产生实例租约。实际类型 `mod_1cab0b39:stag_rune`。直接调用的是召唤助手，不证明职业入口的解锁、体力消耗或冷却；人物与初始位置由既有EmbeddedChannel双队驱动准备。

夹具 `93cb21844487` 的新旧包字节码相同，SHA256均为 `4956a2dea898c9fec70bb53ac3d63e025e601610948b4fdcb019b67a8c9ea53c`。将真实身体完整保存数据加载到一个未加入世界的同UUID替身，对它调用实际expireSpiritPet：

- 旧0.41.39报告 `logs/native-dual-trial-probe-3345c2db-3004-4dbd-8bcf-fcf45db7d644.json` 为false，明确记录真实身体仍存活、真实租约的结束标记却变为true，错误 `Copied spirit body forged native end confirmation for the live original`。该轮正常中止并清理、退出0，插件已归档；保全 `logs/native-spirit-before-93cb218-preservation-20261029.json` 的unexpected为空，565份其他人物文件保持。
- 新0.41.40报告 `logs/native-dual-trial-probe-904b3e1d-b614-42d3-a52c-ab7e062ac865.json` 为true：替身调用结束后原身体仍存活、结束标记保持false，实际世界索引中的出生身体仍有本局及主人归属。最终报告SHA256 `7f351c523304fb15ed16cfa173ba06b804a48dc303b49ebb0df8eaa53a1f3b3f`。

旧轮备份 `validation-history/native-spirit-before-93cb218-4654f31c`，运行器PID74692、Java PID70200正常stop/退出0；新轮备份 `validation-history/native-spirit-after-eb1a38b-74570244`，运行器PID49012、Java PID46528正常stop/退出0。两轮日志分别为 `logs/pack-native-spirit-before-93cb218-20261029.log` 和 `logs/pack-native-spirit-after-eb1a38b-20261029.log`。并非先在旧版验证全流程通过。

## 正常时限、物品保护与结算

新轮独立明细 `logs/native-spirit-probe-0262c0aa-2bfa-4e6a-be18-b59dff5b4488.json` 通过：

1. 真实出生记录带正确主人、实例和nonce，时限等于原生当前游戏时间+60。
2. 只向原先为空的手部放入一个带唯一测试标记的新铁锭，再调用实际原生结束。身体不被移除、完整实体NBT不变、结束标记不产生。随后将该测试物品转交主人，避免在临时身体中留下资产，不删除或覆盖既有玩家物品。
3. 清空已转交物品的手部后，等待真实tick自然到期；实际原生结束被观察，租约CONFIRMED，退休身体失去实例权，没有人工推进时钟。
4. 再通过原生助手召唤4000tick长时灵宠。实际观察其在SETTLING阶段、自然时限之前结束，并完成租约确认、主人回程和本局清理。结束发生在结算，不假称专门验证了战斗中主人单独离开或离线。
5. 主人返回外界后的真实人物文件中，唯一标记铁锭计数恰好1；保护测试物品没有丢失或复制。

两队 `fb007923-9134-4699-aead-a34166d7ee8b`、`9bba694f-3778-481b-9fce-fb52370bf583` 随后各完成4道主线门、封印大厅全队转场、独立首领、17次确认死亡/原生XP链接、实际人物文件0/440点经验、独立战绩和回程/清理。先结束一队不影响另一队。主体战斗驱动仍使用高伤害/受控传送，不作为平衡或真人输入验收。

## 保全与未覆盖范围

新轮端口已关闭，插件已移出mods并归档为备份中的 `fixture-native-spirit-after-passed.jar`，独立服保留0.41.40；原服/客户端未更新。`logs/native-spirit-after-eb1a38b-preservation-20261029.json`：1261个保护文件中1250字节相同、2个properties仅注释变化、8个指定历史恢复人物文件及旧版本包为预先声明变化，581份其他人物文件保持，配置语义及unexpected检查通过。

`logs/native-spirit-after-eb1a38b-roster-preservation-20261029.json` 确认148个旧永久宠物名册所有者记录逐条保持，仅新增本轮四个角色的条目；世界GameRules保持。原隔离实体区域字节保持，SHA256仍为 `51916e76d1a69aa84a76d4d8945b0f6e81747040bf8749f68faf4b045366ac9d`，证据 `logs/native-spirit-after-eb1a38b-retained-entities-20261029.json`；未知结晶未删除，原隔离槽未强制释放，最终回程/票据0。

本次没有验证其他灵宠类型/技能、职业施法成本、所有装备/能力变化、缺失或损坏的绑定、战斗中主人单独退出/濒死、临时灵宠重启、全部结束回调重入、远程真人或性能。C01和完整伴生兼容仍未整体完成。
