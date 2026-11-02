# 原生北境冰弓发射链路：0.41.35

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

生产提交 `0c8a6fafdd7f21461726dd0038f9b6a8b9486abf`。副本物品使用和射击扣费检查此前只接受原版弓/弩/三叉戟与已适配枪械，导致原生 SAO 弓在发射前被拒绝；逐目标反射检查无法发现这个入口问题。

`SaoRangedItems` 将当前安装 r234 的 `SaoBow`、`ElementalBow` 纳入已有远程武器规则。按精确类名、继承关系及原始类资源 SHA256 识别，不扩大为任意 `BowItem`，不硬链接可选模组类。普通弓基类保留原版箭矢与扣费路径；当前包实际注册的武器为其北境冰弓子类。沿用弹药类型、玩家保存、弹体登记、实例授权与原生冰弓效果检查，不修改原生伤害公式。

- `SaoBow.class`：`283352c0516fb24e3b0c8184dc6c9653f8ff3b493ae5870372ab8aa30ef2ace3`。
- `ElementalBow.class`：`1f07f1415ec246fd5efc13f41509b7b2abe9414b28baaea504e8ef6f3e886eeb`。

## 构建与产物

独立 Git 导出打包成功，运行包为 `build/verified/0.41.35-dev-0c8a6fafdd7f-20261029-103226-e615f67a/saodg-0.41.35-dev.jar`，SHA256 `809492bcb8bd4e7aa265ff94beab4971b6f2aa1a492c36443f3cbdad123358d4`。41 个已提交结构与资源检查通过；未跑 JUnit 或完整套件，未提交 beta 内容未打包。默认开放实例生成/启动及 `door_y` 功能继续包含在此包中。

仅授权私有服 `run/pack-acceptance-20261028-081137-fd148a65` 更新为此包；保留磁盘四个入口/奖励开关为 false 的验收环境配置。客户端和原服未更新。

## 定向夹具与前序失败

新增 `saodg.packNativeBowFlightAcceptance=true`，在双队实际生成的第一战斗房中，由服务端使用物品包、真实玩家 tick 蓄力、物品释放、实际箭矢飞行和实体碰撞驱动。跨局负例显式调用箭矢伤害与命中桥接，不能解释为物理跨局飞行；EmbeddedChannel 也不等于远程真人输入。

首轮 `0c8a6fa` 夹具误将未注册的 `SaoBow` 基类当注册物品查找，发射前失败；第二轮 `723c375` 的负例临时构造物品触发冻结注册表限制，同样在发射前失败。两轮报告分别为 `native-dual-trial-probe-4907e9b5-3c86-4a6f-8d95-c97278e0d854.json`、`native-dual-trial-probe-75cf2f44-b47d-405c-a5ff-67ed372a45bf.json`，均 false。已修正为实际注册的北境冰弓及现有原版物品检查。两次 Java 均正常退出 0，实例按生产路径中止、回程并清理，测试附加包归档；保全报告 `logs/native-bow-flight-0c8a6fa-preservation-20261029.json` 与 `logs/native-bow-flight-723c375-preservation-20261029.json` 的 unexpected 均为空。生产运行包未因夹具问题改变。

第三轮 `83d35cca2af7` 已通过实际北境冰弓的准入识别，但整合包新人物默认快捷栏没有空格，夹具为保护物品在发射前停止。报告 `native-dual-trial-probe-268f8f72-7bd1-4bfa-9cdc-4fa62b5f6f09.json` 为 false；Java 正常退出，实例清理、附加包归档及保全报告 `logs/native-bow-flight-83d35cc-preservation-20261029.json` 通过，349 份其他人物文件保持。新版夹具改为将原快捷栏物品移入空背包格，结束后与测试弓换回，完整保留两件物品。

第四轮夹具提交 `865c07d626d4`，独立导出 `.gradle/native-dual-fixture-865c07d626d4-16146d92` 执行 `packTestJar --offline --console=plain -x downloadMCMeta` 成功，16 秒；日志 `logs/native-bow-flight-fixture-865c07d-20261029.log`。以下实际运行检查通过。

## 实际发射及后续双队结果

实际注册物品 `mod_1cab0b39:northern_icebow` 经服务端 `ServerboundUseItemPacket` 开始使用，真实玩家 tick 蓄力 25 tick，确认使用时间至少 20 tick 后调用正常释放。观察到唯一新箭矢 `d4ed8c77-a376-4f03-ab8f-10f0062ecf58`，其射手、实例租约、原生冰弓/蓄力标签正确，射手临时蓄力标签已复位；弹药减少 1，弓损耗 1，生产弹药消耗凭证通过实际人物文件读回证明。

箭矢从出生位置实际飞行超过一格，实体碰撞事件命中本局登记敌人，最终扣血 `13.776001` 且目标存活；原生冰霜 owner 为射手，冰霜和冻结的施法者/实例绑定有效，冻结仍在正常时限内。跨局负例调用箭矢伤害及原生命中桥接后，另一局目标完整 NBT 不变。这覆盖正常蓄力射击及命中效果，不等于所有主动弓技、连续施法、其他技能/TACZ/宠物或物理跨局飞行已验证。

后续两队继续完成生产主线：实例 `036e14e9-cb2b-4013-bca4-2b8a41bcf84b`（槽位1）和 `5e64b73f-c321-44ac-b9b7-7416d8eef0df`（槽位2），各开启4道主线门、封印大厅全队传送、独立首领、17个确认死亡及原生经验链接，每队440点原生XP、独立战绩、正常回程和清理。先结束一队期间另一队状态保持；保活回复分别10/8次。这里的主线驱动仍使用高伤害和传送，不作为平衡或真人远程验收。

恢复报告 `logs/native-dual-recovery-probe-a088f311-9fb4-4b27-bbcc-ff0c3851c3f0.json` 及最终报告 `logs/native-dual-trial-probe-abf5d3ca-7afa-4b21-a8ff-94f7688e31ee.json` 均为 true；后者 SHA256 `38c164beb793e4166b021aba49c0018c5e6e2d87d856762b4317b3ede4545aae`。日志 `logs/pack-native-bow-flight-865c07d-20261029.log`。此结果补充之前逐目标反射检查未覆盖的实际发射链路，不据此勾选整项兼容或发布验收。

## 现场保全

运行前完整备份 `validation-history/native-bow-flight-865c07d-a5cbb41d`；隐藏运行器 PID22848、Java PID13492，正常 stop 后退出0，端口关闭，终态收据 `.gradle/native-bow-flight-fourth-process.json`。附加包已移出 mods，归档为备份内 `fixture-native-bow-flight-passed.jar`，SHA256 `cfc5da7080341fa0d469220a6b64fd722faf2e1f2e2bf22b1e029b7f3d98b8bf`。生产0.41.35保留在私有服中。

`logs/native-bow-flight-865c07d-preservation-20261029.json`：运行前1053个保护文件中1035字节相同，2个 properties 仅时间注释变化，16个既定恢复测试人物文件为预先声明的变化；365份其他人物文件保持，`unexpected=[]`，配置语义保持。

原隔离局 `f99ebe03-0e35-4e73-822a-063b6b01c318` 及未知结晶保留；最终 runs=1、lobbies=0、pendingReturns=0、tickets=0，槽位0仍QUARANTINED，其他槽位FREE。其实体区域文件 `entities/r.0.0.mca` 与运行前备份字节相同，SHA256 `51916e76d1a69aa84a76d4d8945b0f6e81747040bf8749f68faf4b045366ac9d`，证据 `logs/native-bow-flight-retained-entities-20261029.json`。未处理未知资产，不宣称隔离问题已解除。
