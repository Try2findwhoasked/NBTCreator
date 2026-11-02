# 原生刺客宠物自主战斗：0.41.37

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

生产包仍为 `6466ef0c803a` 的0.41.37，SHA256 `809c2845b61034c638b6c8982d093ac1e1a80c5088282632874627ba4e0198c5`。仅补充测试；客户端、原服、生产规则及未提交beta结构均未改。此前[原生召唤和直接近战调用](NATIVE_PET_0.41.37_2026-10-29.md)不等于自主战斗，本轮补充实际服务器tick中的选敌、路径与攻击证据。

夹具 `56726f946460` 使用 `saodg.packNativePetAcceptance=true`、`saodg.packNativePetAiAcceptance=true`。依旧先通过原生登记/存储接口准备一只新测试宠物，再调用原生选择/召唤；不是野外捕获。对实际 `mod_1cab0b39:pet_assassin` 开启AI、清除已有目标，不设置正例目标、不调用导航移动、不直接调用正例伤害或攻击方法。先临时将本房活着的受管敌人设为512血以观察非致死攻击；在确认选敌、导航路径、至少一格位移、伤害和主人贡献后，将实际目标血量设为1，等待原生AI完成击杀。其他目标存活时恢复原血量/上限。敌方NoAI、受控初始位置和血量输入意味着此用例不证明战斗平衡或完整寻路能力。

实际用例 `logs/native-pet-probe-fab3894c-e613-4c29-81cc-0135944f74e3.json`：原生自行选择登记敌人 `c5f907ef-5eb9-4378-a29a-b15605c611c9`，观察到非空导航路径，最大相对起点位移平方 `12.026502834339095`（约3.47格位移），实际扣血 `5.559601`，伤害贡献归主人。随后没有人工正例攻击调用，目标被原生AI击杀且死亡被确认。记录的是原生AI总体战斗，不区分这一伤害具体来自自动近战还是原生自动技能，不据位移宣称走完复杂迷宫。

原生部署及ACTIVE租约、复制实际部署的同UUID替身拒绝、同位置跨局近战拒绝继续通过。请求归还后，由生产CompanionService走原生存储，租约确认、实体移除、旧身体失去授权，名册磁盘与原生预期一致。新宠物记录 `d6a05a54-a2f3-49be-9b41-6e0ad2e871d7` 保留为已收回状态，没有为测试清除资产。

随后两队 `d6a2d3af-afb0-4cb3-a1bb-40f259ecffe0`、`60650115-e70d-475b-ae77-eda2f3b3aa91` 均完成4道主线门、封印大厅全队转场、独立首领、17次确认死亡及独立战绩/回程/清理；先清理一队不影响另一队。第一队16个玩家原生XP链接、实际0/420经验，第二队17链接、实际0/440，沿用宠物击杀没有玩家原生XP资格的既有规则，没有额外补发。

恢复 `logs/native-dual-recovery-probe-71499e01-d30d-479e-84ae-6556d836b56c.json` 与最终 `logs/native-dual-trial-probe-66efa642-d196-4e12-b8ad-2ee38b49b0f9.json` 均为true，最终SHA256 `bd847cec9cbdb89b0a246caf2ff9e8a4ce33d938faf10562adfe27b105e8d253`。独立Git导出packTestJar编译/重混淆通过，日志 `logs/native-pet-ai-fixture-56726f9-20261029.log`；未跑JUnit或完整GameTest。

备份 `validation-history/native-pet-ai-56726f9-17a233c1`；附加包SHA256 `ceb1766952add9cdba0eeac11d2f5345419c840ac713fb1bfe60cf1234382863`，已移出mods并归档为 `fixture-native-pet-ai-passed.jar`。隐藏运行器PID18348、Java PID15120正常stop、退出0、端口关闭，终态 `.gradle/native-pet-ai-56726f9-process.json`，运行日志 `logs/pack-native-pet-ai-56726f9-20261029.log`。

保全 `logs/native-pet-ai-56726f9-preservation-20261029.json`：1197个保护文件中1187字节相同、2个properties仅注释变化、8个指定恢复测试人物文件允许变化；517份其他人物文件及配置语义保持，unexpected为空。`logs/native-pet-ai-56726f9-roster-preservation-20261029.json` 逐条确认132个旧所有者名册保持，只新增本轮四个测试角色条目。原隔离实体区域字节保持，SHA256仍为 `51916e76d1a69aa84a76d4d8945b0f6e81747040bf8749f68faf4b045366ac9d`，证据 `logs/native-pet-ai-56726f9-retained-entities-20261029.json`；未知结晶未删除、隔离槽未强制释放，最终回程/票据为0。

未覆盖其他宠物、各技能分支、野外捕获、关闭门/跨房跟随、主人濒死/离线/换局、部署重启恢复、临时灵宠、真人远程与性能。C01与伴生完整兼容仍未整体完成。
