# 北境冰弓主动施法与固定爆发位置：0.41.36

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

生产提交 `c666691b69ac9c43e8b84b02ea0d9a5e432dd83b`。原生 r234 的 `IceBowArts.step` 除穿透、冰雨、冰笼和龙击之外，还直接调用两处 `area`，用于末段及持续爆发；此前这两处没有进入已记录瞄准中心的作用域，逐目标权限会回退到施法者当前位置，使合法的原位置爆发被拒绝。

新增这两处调用的 Redirect，通过当前实际 Cast 身份、出生实例/维度和原始瞄准中心进入 `SkillAreaPolicy`，并核对中心与半径。未知、退休记录及改换中心不取得权限；调用以 finally 退出作用域。普通外部世界沿用原生行为，未修改伤害、半径、消耗、冷却或时间表。

## 构建与运行包

独立 Git 导出打包通过，41 个已提交结构及资源检查通过；未跑 JUnit 或完整套件，未提交 beta 素材未打包。

运行包 `build/verified/0.41.36-dev-c666691b69ac-20261029-105529-7893a044/saodg-0.41.36-dev.jar`，SHA256 `8a8d2cec9e2d78c956958826c1ec3ea539eed56f9f8a8be83cb6039c0b53ffb6`。默认开放实例生成/启动及 `door_y` 等既有功能保留。

只将授权私有服 `run/pack-acceptance-20261028-081137-fd148a65` 更新为该包，127.0.0.1:25579；该验收环境的四个入口/奖励磁盘开关继续为 false。客户端和原服未更新。

## 实际施法证据

新增可选 `saodg.packNativeIceCastAcceptance=true`，由双实例夹具在实际生成并进入首个战斗房后执行。最终夹具提交 `2f76a91a14c2`，独立导出 `.gradle/native-dual-fixture-2f76a91a14c2-72deb94a` 执行 `packTestJar --offline --console=plain -x downloadMCMeta` 成功，15秒；日志 `logs/native-ice-cast-fixture-2f76a91-20261029.log`。

实际装备已注册的北境冰弓，从原生 `Combat.cast(player, 0)` 入口施放，既不直接构造正例 Cast，也不直接调用正例伤害/爆发方法；后续年龄由真实玩家 tick 驱动，没有加速时间表。检查通过：

- 消耗原生12点资源并设置原生60 tick冷却；同 tick 再次请求不产生第二条 Cast，也不重复扣费。
- 原生射线产生距实际受管敌人3格以内的瞄准中心，Cast 出生记录有效。将另一实例目标的位置传给本 Cast 的爆发桥接后，该目标完整 NBT 不变；这是显式中心改绑负例，不是另一实例内的真实完整施法。
- 通过夹具受控传送及房间授权，把施法者移到本局房间3，离原目标超过32格，且普通 `canHarm` 已为 false。此操作用于区分原位置与当前位置权限，不证明玩家可绕过门禁行走或施法瞬移。
- 原生 Cast 每 tick 实际更换对象，共观察61次替换；原对象失去授权，新对象保留同一出生记录和原始中心。
- 在原生年龄22发生末段爆发：原目标保持存活，实际扣血 `13.776001`，具有原生等级2缓慢；施法者仍不能直接攻击该目标。爆发没有随施法者移动，也没有丢失合法命中；调用结束后不存在残留范围作用域。
- 正常时间表结束，Cast 被移除，冷却递减至0。再次使用最后一条退休 Cast 调用爆发，目标完整 NBT 不变，作用域保持为空。

恢复报告 `logs/native-dual-recovery-probe-47923d6c-9a07-42ef-890a-d7d9a0c748a8.json`、最终报告 `logs/native-dual-trial-probe-48889bee-8e28-403c-9a65-7821eff82b5e.json` 均为 true；后者 SHA256 `24d876252ba25dda37548fc03b0832ffd5bc6d1c6f3970c9ba7912c0a97f279c`。

本次覆盖普通技能槽0的实际入口、自然时间表和末段爆发。没有逐一验证冰雨、冰笼、普通/强化龙击、持续爆发、同维度换局、重启后旧技能、全部FX观察者或远程真人输入。源码对两处 area 的补齐不能替代其他阶段的运行证据，SK22～SK26及C01整体不勾选。

## 前序夹具失败

`6230e8c` 首轮已通过入口、消耗、冷却和中心负例，但夹具只临时改坐标、未同步房间授权，未找到满足条件的移动对照位置；报告 `native-dual-trial-probe-92c260b2-9dfb-4d5f-a28a-78153f6aa24d.json` 为 false。修正选点为实际图关系判断，再执行受控传送与房间授权，没有放宽生产门禁。

`842c76f` 第二轮完成移动对照后，读取非公开内部 Cast 类的年龄缺少显式反射访问权限；报告 `native-dual-trial-probe-118caaa6-8c94-4b15-86a8-d1640c7639de.json` 为 false。仅在夹具中补充读方法访问权限，生产包未改变。此前把清理日志误判成通过的临时进度说明已更正，以最终报告为准。

两轮均正常中止、回程清理及 Java退出0，附加包已归档；保全报告 `logs/native-ice-cast-6230e8c-preservation-20261029.json`、`logs/native-ice-cast-842c76f-preservation-20261029.json` 的 unexpected 均为空。另有一次夹具编译前将错误的 START 枚举修正为 ENTRANCE，未运行错误版本。

## 双队后续与保全

成功轮实例为 `2b93e932-0f3c-4a3b-8f66-581c96d37bb1`（槽位1）和 `f91fcdf2-3b3d-4595-bf4c-42f7868f0351`（槽位2）。主动技能检查后，两队各完成4道主线门、封印大厅全队转场、独立首领、17个确认死亡/原生经验链接、440点原生XP、独立战绩、正常回程和清理。先结束一队不影响另一队。此主线驱动仍使用高伤害与传送，不作为难度平衡或远程真人验收。

运行前完整备份 `validation-history/native-ice-cast-2f76a91-3ac34e05`；隐藏运行器PID11244、Java PID14440，正常stop、退出0、端口关闭，终态收据 `.gradle/native-ice-cast-third-process.json`。附加包已移出mods，归档为备份中的 `fixture-native-ice-cast-passed.jar`，SHA256 `9eb07915222fb810d6079fdd5ee7f077ca51cf228d38ae4524c15c0d4b798f2c`。日志 `logs/pack-native-ice-cast-2f76a91-20261029.log`；JFR已保存，未据此声明性能验收通过。

`logs/native-ice-cast-2f76a91-preservation-20261029.json`：1101个保护文件中1083字节相同，2个properties仅时间注释变化，16个既定恢复测试人物文件为预先声明的变化；413份其他人物文件保持，配置语义保持，unexpected为空。

原隔离局 `f99ebe03-0e35-4e73-822a-063b6b01c318` 及未知结晶保留；最终回程/票据为0，槽位0仍QUARANTINED，其余FREE。原实体区域 `entities/r.0.0.mca` 与备份字节一致，SHA256 `51916e76d1a69aa84a76d4d8945b0f6e81747040bf8749f68faf4b045366ac9d`，证据 `logs/native-ice-cast-retained-entities-20261029.json`。未知资产未处理，隔离状态没有被强制解除。
