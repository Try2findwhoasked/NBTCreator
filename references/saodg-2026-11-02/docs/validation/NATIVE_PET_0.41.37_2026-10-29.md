# 真实SAO宠物召唤、近战归属与保存：0.41.37

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

生产包为 `6466ef0c803a1527259e5b54a582974f38506298` 的0.41.37，SHA256 `809c2845b61034c638b6c8982d093ac1e1a80c5088282632874627ba4e0198c5`，沿用[对象身份修复产物](COMPANION_IDENTITY_0.41.37_2026-10-29.md)。本轮只新增packTest用例，没有进一步改生产规则；仅独立兼容测试服升级，原客户端与原服未修改。

## 准备与实际调用

新增 `NativePetProbe`，通过 `saodg.packNativePetAcceptance=true` 在双队生成主线的首个战斗房执行。夹具提交 `8ce8f2bc03f7` 独立Git导出 `packTestJar` 编译及重混淆通过，未执行JUnit或完整GameTest。附加包SHA256 `a1c57157dfd027faf5937726af9c167032cb61409546764d8ce96154d5f86858`；前一提交 `4a5426f` 也编译通过，启动前修正名册比对应排除新测试所有者的空条目，没有运行错误比对版本。

使用实际r234注册类型 `mod_1cab0b39:pet_assassin`。新测试角色的名册必须为空；先用实际 `SaoPet.begin` 和 `PetLedger.store` 准备一只新的已收回宠物，不直接伪造Owner、Deployment、名册NBT或实例标签。该准备步骤不证明野外击败/收服过程。随后调用原生 `PetSystem.select(player, 0)` 和 `PetSystem.summon(player)`，由原生逻辑创建新身体、恢复记录、生成部署令牌并加入世界。

本次玩家及宠物使用受控位置，宠物NoAI，实际攻击由 `SaoPet.doHurtTarget` 调用；致死阶段将一只现有必要敌人血量设为1，再执行同一原生近战。没有改写攻击数值、直接生成死亡事实、调用奖励发放或向玩家补经验；不作为AI寻路、战斗平衡或真人输入证据。

## 实际通过内容

独立结果 `logs/native-pet-probe-04404402-9fe8-41b3-9952-58edfd935ab1.json`：

- 原生召唤后实际世界索引中存在宠物，新部署取得ACTIVE实例租约，归属于本局及其真实主人。
- 从实际宠物完整保存数据加载同UUID替身，原生适配器可确认其复制的部署凭证，但它不是服务器索引对象：实例归属、贡献成员和攻击许可均拒绝。此项补充了0.41.37 GameTest之外的真实r234部署数据证据。
- 将实际宠物放到另一局敌人旁执行原生近战，目标完整NBT不变，跨局攻击许可拒绝。
- 回到本局目标旁，原生近战实际扣血 `5.559601`，目标存活，后续真实伤害确认将贡献记给主人。
- 一次受控致死攻击产生原生死亡事件，必要敌人UUID `676a18c2-5f65-4cf6-85c0-063a3d1d5e80` 被确认；没有为该宠物击杀创建玩家原生XP链接。
- 请求伴生资产归还后，生产CompanionService调用原持有人存储接口，租约CONFIRMED，实体已移除、名册Deployed=false、旧身体失去行动许可。实际 `data/sao_pet_roster.dat` 解码后与原生SavedData预期完整一致；其他名册所有者记录保持。新测试宠物记录 `31912acd-956c-4eff-a665-fdc720ec49f3` 以已收回状态保留，未为清理测试而删除资产。

原生 `ExternalKillXp.onDeath` 只接受DamageSource中的ServerPlayer，宠物直接近战不满足该入口。最终第一队17次确认死亡但16个原生XP链接、人物文件实际0/420点经验，第二队17次死亡/17链接、实际0/440点经验。少的20点来自该宠物击杀沿用原生资格规则；没有按玩家击杀经验替宠物补发。贡献归属与玩家XP资格分别核对，不能把贡献登记视为原生XP发放。

## 双队结果、升级与保全

恢复报告 `logs/native-dual-recovery-probe-f0ce62f2-c5ad-4e6d-84cd-924469c47f8f.json`、最终报告 `logs/native-dual-trial-probe-d5dd9b69-bd4d-499e-bc63-a3bc9066eccc.json` 均为true，后者SHA256 `3c09e845e7058c1fe84258d12c2ab0f321df6d304b4e2e5eadb027af310ea89d`。两局 `082e1abd-fe65-4a10-80b5-a66ddf1d5c68`、`ceeeffc0-224d-4557-85e0-58b4ca954cb1` 各完成4道主线门、封印大厅全队转场、独立首领、战绩、原生经验保存及正常回程/清理；第一队清理保留第二队进度。

备份 `validation-history/native-pet-8ce8f2b-ee6fa72f` 包含升级前0.41.36、世界和配置。隐藏运行器PID26328、Java PID12580正常stop、退出0，端口关闭；终态 `.gradle/native-pet-8ce8f2b-process.json`，日志 `logs/pack-native-pet-8ce8f2b-20261029.log`。测试插件移出mods，归档为备份中的 `fixture-native-pet-passed.jar`，独立服保留0.41.37，入口/奖励测试门禁和配置语义保持。

`logs/native-pet-8ce8f2b-preservation-20261029.json`：1181个保护文件中1170字节保持，2个properties仅时间注释变化；8个指定恢复测试人物文件和旧0.41.36包为预先声明变化。501份其他人物文件保持，unexpected为空。

额外从运行前备份与停服后真实名册文件解码逐所有者比较：128个既有所有者条目全部保持，仅新增四个本轮测试角色的条目，新宠物已收回。证据 `logs/native-pet-8ce8f2b-roster-preservation-20261029.json`，unexpected为空。原隔离实体区域与备份字节一致，SHA256仍为 `51916e76d1a69aa84a76d4d8945b0f6e81747040bf8749f68faf4b045366ac9d`，见 `logs/native-pet-8ce8f2b-retained-entities-20261029.json`。未知结晶未删除，原隔离槽保持；最终回程/票据0，其余槽位FREE。

## 未覆盖范围

只证明上述刺客宠物的原生召唤、受控近战、一次击杀归属、拒绝跨局/替身及同进程存储。尚未验证野外捕获、所有宠物类型及技能、AI/跨门跟随、主人濒死/离线/换局、部署重启恢复、灵宠临时召唤、玩家远程输入或性能。C01与完整伴生兼容仍不整体勾选，不能用该单一路径替代其余要求。
