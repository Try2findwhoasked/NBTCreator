# 北境冰弓其余主动阶段：0.41.36

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

生产包保持 `c666691b69ac9c43e8b84b02ea0d9a5e432dd83b` 的0.41.36，SHA256 `8a8d2cec9e2d78c956958826c1ec3ea539eed56f9f8a8be83cb6039c0b53ffb6`。本轮只改 packTest 夹具；客户端、原服、未提交 beta 结构均未修改或打包。

## 用例与输入

新增可选 `saodg.packNativeIceMatrixAcceptance=true`，在实际生成的双队主线夹具中，顺序调用原生 `Combat.cast` 验证冰雨、冰笼、普通龙击及满体力龙击。沿用实际玩家 tick，不制造 Cast、不改年龄、伤害、时间表或冷却；每个用例等待实际冷却归零再继续。瞄准和远离原目标使用受控位置变更及房间授权，不证明普通玩家能穿越关闭的门。

当前整合包额外安装 `sao-gameplay-fixes-1.20.1-1.0.0.jar`。其 `SwordProgressionMixin` 在施法入口调用 `ProgressionRules.allow`，除原生熟练度外还有等级门槛：槽1为5级、槽2为12级、槽3为20级。夹具调用实际 `CombatTuning.requirement(false, slot)` 和 `GrowthPolicy.floor(level)` 设置新测试角色的临时XP，并通过实际 `PlayerData.level` 核对等级；不会修改正式门槛或经验曲线。

这些新角色另临时设置熟练度36、连击3及原生体力上限/上限减1，以区分两种终结技。当前房间全部已登记必需敌人临时提高至512血，避免多目标效果提前致死；结束时恢复原血量/上限及角色原有XP、熟练度、连击和体力。成功断言还要求未新增确认死亡，避免把这些输入作为真实经验获取证据。完整主线另由既有驱动继续运行。

用例观察原始瞄准位置在施法者移往无直接攻击权限的另一房间后仍命中；验证原生冰霜/冻结归属、逐tick记录替换、结束及退休记录拒绝。冰雨必须出现共享末段爆发以外的实际扣血，满体力龙击必须出现第56tick之后的持续扣血；不会仅凭施法记录存在宣称全部阶段通过。

## 前序失败及保全

- `267c0c004b16`：槽1施法入口断言失败，报告 `logs/native-dual-trial-probe-53ecf8de-0c0a-4047-9b45-68faeef54e99.json` 为false，未取得后续阶段证据。保全报告 `logs/native-ice-matrix-267c0c0-preservation-20261029.json`：1117个保护文件，1099字节一致、2个properties仅注释变化、16个既定恢复测试人物文件允许变化，429份其他人物文件保持，unexpected为空。
- `8b94679d07c6`：补充入口诊断及受控瞄准位置授权，报告 `logs/native-dual-trial-probe-b1ebd354-cd9e-4376-b6b2-53ce3fccae06.json` 仍为false。原生style29、36熟练度、99体力、零恢复/前摇和副本施法权限均正确，却未创建Cast或扣费；结合当前补丁字节码定位到1级角色不满足额外等级门槛。保全报告 `logs/native-ice-matrix-8b94679-preservation-20261029.json`：1133个保护文件，1115字节一致、2个properties注释变化、16个允许变化，445份其他人物文件保持，unexpected为空。

两轮均正常stop、Java退出0、端口关闭，测试插件移出mods归档。原隔离局及未知结晶保留，实体区域 `entities/r.0.0.mca` 与各自备份字节一致，SHA256均为 `51916e76d1a69aa84a76d4d8945b0f6e81747040bf8749f68faf4b045366ac9d`；证据分别为 `logs/native-ice-matrix-267c0c0-retained-entities-20261029.json` 和 `logs/native-ice-matrix-8b94679-retained-entities-20261029.json`。

## 修正后运行

夹具 `19ec8b65fa5e` 增加实际补丁等级输入和非致死多目标保护，独立Git导出 `packTestJar` 编译/重混淆通过；未执行JUnit或完整套件。附加包SHA256 `d85bff401fc1c1ddc178819c9fdb2eba4e84f28352a81e63c6e6836dc058b231`，备份 `validation-history/native-ice-matrix-19ec8b6-c5070a4e`。运行日志 `logs/pack-native-ice-matrix-19ec8b6-20261029.log`，运行状态 `.gradle/native-ice-matrix-19ec8b6-process.json`。

该轮运行中断：再次检查时Java PID7536及运行器PID17868均已不存在、端口关闭，状态文件仍写running，日志截止19:29:12且没有最终报告或正常stop记录。不得据已推进到后续主线的日志宣称四项技能或双队终局通过。磁盘剩余 `6c0141d4-ef48-4da0-af42-224a6e95eac7` 在槽位2的CLEANING阶段，回程标记为0，两名第二队角色已在外界。中断保全 `logs/native-ice-matrix-19ec8b6-interruption-20261029.json`：1149个保护文件中1131字节相同，2个properties仅注释变化，16个既定恢复角色文件允许变化，其余unexpected为空；隔离实体区域字节保持。夹具移出mods归档，退出码未知，没有补写正常停服结论。

夹具 `39039da975f9` 新增固定上述局及两名实际人物UUID的恢复场景 `ice_matrix_interrupted_19ec8b6`，并在每项技能用例完成时使用CREATE_NEW保存独立JSON。独立Git导出编译通过，备份 `validation-history/native-ice-matrix-39039da-aaa2e19a`，附加包SHA256 `1c35f6866625eb69710003f822e1811e903773e2ed216d3aba2c51a208373e45`。实际恢复报告 `native-dual-recovery-probe-a0cff647-e53a-45d3-b715-2b55e367de79.json` 为true，原生登录、资产/成长/经验保存、生产清理及隔离记录保持通过，槽位2已释放；随后重新进入四项技能和双队主线测试。

## 最终通过范围

最终报告 `logs/native-dual-trial-probe-67791f39-f81d-4e72-aa8d-381054a0196c.json` 的passed为true，SHA256 `cc6b6c683f072610570571201b15dcfd97fc5296d5ef47ef39fc8f37b42d1f33`。四项通过且独立用例JSON已同步到logs：`native-ice-matrix-case-adbdaccc-321c-472f-ba9a-f8bc18c1b93d-1.json` 至 `-4.json`。

| 原生技能 | 实际消耗 / 冷却tick | 观察到扣血的原生年龄 | 实际总扣血 | Cast替换次数 |
| --- | --- | --- | --- | --- |
| 冰雨，槽1 | 18 / 100 | 30、60 | 17.712006 | 99 |
| 冰笼，槽2 | 25 / 180 | 22 | 18.911987 | 87 |
| 普通龙击，槽3 | 40 / 360 | 56 | 19.895996 | 145 |
| 满体力龙击，槽3 | 138（全部体力）/ 360 | 56、72、88、104、120、136 | 47.940063 | 145 |

普通终结技使用137/138体力，满体力分支使用138/138；实际原生分支标记、消耗和冷却均符合。每个用例均在角色移到房间3后观察原位置命中，此时普通直接攻击权限为false。冰雨第60tick的命中独立于第30tick共享爆发；满体力龙击的后续命中证明持续阶段实际生效。表中仅列实际扣血的tick，原生受伤无敌间隔可能合并或拒绝部分原生调用，不能解释为修改了原技能调用频率。

冰笼及两种龙击的冰霜绑定具有实际施法者和本局归属；龙击冻结截止时间分别为当前游戏时间+40/+70。每项自然时间表结束后Cast移除，退休记录再调用不改变目标完整NBT，范围作用域退出；等待原生冷却归零后恢复临时XP、体力、熟练度、连击及两只目标的原血量/上限。测试期间未新增确认死亡事实，临时经验不计作正式成长获取。重复施法拒绝未额外扣费，改绑其他实例中心的负例保持目标NBT。重复拒绝可以同时受连击或体力条件影响，不能将全部用例解释为单独证明冷却拒绝分支。

随后实例 `9cdcf97b-de71-4fab-a81b-ff41597e5011` 和 `a91c1a55-305d-4abb-9650-f180627466ed` 各完成4道主线门、封印大厅全队转场、独立首领、17次确认死亡/原生XP链接，每队由实际人物文件确认0/440点经验。两队战绩与回程独立，先结束一队不影响另一队；既有驱动仍使用受控传送与高伤害，不作为平衡或真人输入证据。

隐藏运行器PID13440、Java PID16004正常stop、退出0，端口关闭，终态 `.gradle/native-ice-matrix-39039da-process.json`。测试插件移出mods，归档到备份中的 `fixture-native-ice-matrix-passed.jar`。日志 `logs/pack-native-ice-matrix-39039da-20261029.log`，未启用JFR或增加性能结论。

保全 `logs/native-ice-matrix-39039da-preservation-20261029.json`：1165个保护文件中1155字节相同、2个properties仅注释变化，8个指定中断角色文件允许变化；485份其他人物文件保持，配置语义保持，unexpected为空。原隔离实体区域与备份字节一致，SHA256 `51916e76d1a69aa84a76d4d8945b0f6e81747040bf8749f68faf4b045366ac9d`，见 `logs/native-ice-matrix-39039da-retained-entities-20261029.json`。原未知结晶未处理、隔离槽未强制释放；最终票据及待回程为0，其余槽位FREE。

以上补齐四种施法分支的限定路径证据，未证明边界半径、所有方向/全部目标、穿透移动阶段、门边与Boss分区、换局/重启旧施法、全体FX观察者或远程真人。SK22～SK26和C01整体仍不勾选；其他技能/宠物、经济、性能及正式发布仍需完成。
