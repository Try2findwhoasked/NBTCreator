# 开发与构建

当前分支使用 Minecraft 1.20.1 / NeoForge 47.1.106 / ForgeGradle 6.0.54 / Java 17。开发版本为 `0.5.3-neoforge-dev`，协议26；[接触器控制台定向验证](validation/CONTACTOR_CONSOLE_2026-11-01.md)。[迁移与当前验证](validation/NEOFORGE_MIGRATION_2026-10-31.md)。下方带版本号的 Forge 记录属于迁移前快照，不代表 NeoForge 或现有整合包已经验收。

CI/CD、完整单测与两组运行套件、标签发布守卫见 [CI/CD说明](CI_CD.md)。工具已统一到分类的 `tools/`，当前入口见 [工具目录](../tools/README.md)及[迁移映射](TOOLS_MIGRATION_2026-10-31.md)。本机清理仅涉及确认废弃的夹具、保留原件的字节副本和旧日志，不清理整个build；[记录](validation/CI_TOOLS_CLEANUP_2026-10-31.md)。

迁移前 Forge 测试版 `0.5.1beta`、协议25、80间活动房间、340份生产模板。新增六类36项管理员配置与开局奖励参数快照，[使用说明](SERVER_CONFIGURATION.md)及[本轮定向验证](validation/ADMIN_CONFIGURATION_2026-10-31.md)。上个 `0.5beta` 快照见 [发布记录](validation/RELEASE_0.5beta_2026-10-31.md)。`0.41.66-dev` 的实例聊天与通知隔离见 [历史记录](validation/MESSAGE_ISOLATION_MERGE_0.41.66_2026-10-31.md)。下列分版本记录保留各自范围，不累计为一次默认完整套件验收。

接触器控制台采用 KM1 主接触器、KMY 星形接触器和 KMD 三角形接触器。初始 KM1 断开、KMD 闭合；断开 KMD 后合上 KMY 即清房，可以直接离开。可选右键启动台（或合上 KM1）进行星形启动，等待100 tick后断开 KMY，再等待10 tick合上 KMD，成功后每名合格成员通关基础奖励默认增加60副本经验/房。星形/三角形互锁；过早操作被拒绝，无爆炸或雷击。KM1可停机，保留清房；停机后重新准备星形可重启，重新计算加速时间。追加成功后锁定，每房一次；保留原有奖励资格和事务。 详见[玩家操作说明](CONTACTOR_ROOM.md)。

0.41.65-dev 引入三倍等比实体结算箱，当时协议23；当前协议以本页顶部为准，两端需同步更新。实体点击仍进入原个人奖励事务。见[实体箱实现和验证](validation/REWARD_CHEST_ENTITY_2026-10-31.md)。

本轮奖励调整：奖励启用的新局为有效参与成员增加独立 SAO 通关经验；基础副本经验按难度/评分调整，结算箱优先放在实际首领房中央并增加分档光环。旧记录不追补，原生等级曲线和钱包所有权不变。实际验证与限制见 [奖励调整记录](validation/COMPLETION_REWARDS_2026-10-31.md)。

0.41.65-dev补上独立 `sao_archer 0.6.0` 职业弓的精确准入，修复右键在职业免箭拉弓前被白名单拦截。定向二进制测试与实机限制见[验证记录](validation/ARCHER_BOW_ADMISSION_0.41.65_2026-10-31.md)。

0.41.64-dev删除15间简易普通原型及其24份NBT，活动房池76间；旧精修、未选房与功能房保留。[删除范围与本版验证](validation/SIMPLE_COMBAT_RETIREMENT_0.41.64_2026-10-30.md)。

前版0.41.63-dev的固定鸟居安全房、符文封印大厅、三套2×2 Boss及传送门生成的构建命令、实际验证和兼容边界见[历史验收](validation/BOSS_SHRINE_RUNE_0.41.63_2026-10-30.md)；完整JUnit的已知钱包失败仍需单独处理。

0.41.62 的随机怪物、延迟发光、可见钥匙与三档 SAO 奖励箱验证及隔离截图入口，见[运行记录](validation/ROOM_REWARDS_0.41.62_2026-10-30.md)。

私有packTest的 `-Dsaodg.packNativeTrialAcceptance=true` 执行原生双人队伍、真实大厅与生成、主路钥匙/封印大厅/独立首领/成功历史及原生XP、回程清理链路。仅授权私有目录、入口/奖励关闭且无玩家/实例时可用；一次同步测试准入临时开放并立即恢复配置，不允许在原服启用。使用房间传送/高伤害，不代表真人与完整内容验收；夹具已归档、私有服已停。[结果和限制](validation/NATIVE_GENERATED_TRIAL_0.41.32_2026-10-29.md)。

0.41.20 的 `SkillMovementPolicy` 在既有路径检查后验证最终身体范围。仅 `-PgameTestNamespaces=saodg_concurrent` 已通过四人实际对象的合法落点／身体越顶断言及原双实例流程；SAO/TACZ 的实际原生施放仍需单独验收。[记录与开发包](validation/MOVEMENT_VOLUME_0.41.20_2026-10-29.md)。

0.41.19 传送门的只读注视提示使用专用 OUTLINE 射线，其他机关沿用碰撞射线。`-PgameTestNamespaces=saodg_combat` 的 1 项完整通关夹具已通过新增瞄准／遮挡／无状态改变断言，客户端视觉未验收。[记录与开发包](validation/PORTAL_WARNING_0.41.19_2026-10-29.md)。

0.41.18 的队友生命展示使用可选状态字段、沿用协议 20；单独运行 `test --tests cn.saodg.client.PartyMemberViewTest` 和 `-PgameTestNamespaces=saodg_concurrent` 已通过。后者增加同实例实际人物生命投影检查，首次元数据超时及离线缓存复用均保留记录。[行为、命令与开发包](validation/PARTY_VITALS_0.41.18_2026-10-29.md)。

0.41.17 的 `-PgameTestNamespaces=saodg_start` 可只运行一项双人物开始环境诊断检查：真实 UI 快照与真实开始拒绝相同，四种环境检查不改变队伍或创建实例；已通过，包含在默认套件中，[记录与产物](validation/LOBBY_START_DIAGNOSTICS_0.41.17_2026-10-29.md)。

私有 packTest 的 `-Dsaodg.packNativeXpRestartAcceptance=true` 仅在既有授权私有目录核对上轮成功实际击杀报告，重新登录同一已领取人物并用生产服务检查 10 次去重、人物保存及原 commit。正常重启检查已通过，测试服已停、夹具已归档；不覆盖未确认/硬退出窗口，[记录](validation/NATIVE_XP_RESTART_2026-10-29.md)。

私有 packTest 的 `-Dsaodg.packNativeXpPipelineAcceptance=true` 建立一份隔离活动战斗场景，后续使用真实伤害、生产下一 tick 死亡确认/世界检查点、原生经验服务、Rhino 门禁、人物文件保存和正常退出清理。已有 0→13、重复十次不再发放证据；仅允许既有授权私有目录、入口/奖励关闭的 SAO_SERVER、无真实玩家/原有实例，不属于默认套件或完整真人副本验收。夹具已归档、测试服已停，[证据与限制](validation/NATIVE_XP_PIPELINE_2026-10-29.md)。

私有 packTest 的 `-Dsaodg.packLegacyWalletFenceAcceptance=true` 验证真实 Rhino 旧钱包所有者、内存/磁盘市场回执拒绝及资产保持，仅允许既有授权私有目录、零真实玩家/实例、SAO_SERVER 且入口和奖励关闭；不能用于原服。已正常执行并停服，夹具已归档，[证据与范围](validation/LEGACY_WALLET_FENCE_NATIVE_2026-10-29.md)。

私有 packTest 的 `-Dsaodg.packNativeDamageXpAcceptance=true` 补充真实 Zombie.hurt/Forge 事件链的原生经验捕获检查，含晚取消后再杀、独立固定数额、未确认拒绝领取及原生首次攻击奖励保护；只在既有已授权私有目录且无玩家/实例时运行，不能在原服使用。实际编译、执行、失败调查与范围见[记录](validation/NATIVE_DAMAGE_XP_2026-10-29.md)，没有证明生产持久死亡确认和端到端发放。

`python tools/verification/verify_process_recovery.py --java-home D:/Java/jdk-17 --checkpoint reward_response` 显式检查 T08：真实非 OP 领奖命令及成功消息丢弃、立即注销/关闭通道，再硬退出并以同 UUID 重登；检查原资产/回执、十次去重、待领奖服务端投影和完整清理。独立 EmbeddedChannel 传输不等同真实远程网络，[实际结果](validation/REWARD_RESPONSE_RECOVERY_2026-10-29.md)。不进入默认套件，不需重打模组。

`python tools/verification/verify_process_recovery.py --java-home D:/Java/jdk-17 --checkpoint reward_unsaved` 显式运行原生免费奖励 T06 两进程夹具：真实内存应用、公共保存静默未写入、实际文件回读拒绝确认，重复保存及容器转出保护，再持久保存世界待确认状态并硬退出；新进程检查原人物重登补发、去重和完整清理。仅新建专用实验世界，不进入默认套件，实际结果及首次启动中断见[记录](validation/REWARD_UNSAVED_RECOVERY_2026-10-29.md)。

0.41.13 按最新确认：谜题房只能是支路尽头，安全房保留主线；未探索一层改为 1×1 问号，进入后展开真实形状，主线房间/连线橙色高亮。协议 18，内容 ruins-dev-19，新布局仅作用于新开局。构建/定向测试在独立导出目录完成；用户随后明确保存关闭，已确认旧进程结束并启动新版原开发环境。[范围与产物](validation/MAP_LAYOUT_0.41.13_2026-10-29.md)。

0.41.12 增加已探索房间外一层未知轮廓、房内细分坐标/朝向、阵亡回城后的只读地图；试炼/标准/精锐至少 2/3/4 个多格房间，主线仍有多格房，唯一封印大厅路线不变。协议 17，两端需同时更新；内容 ruins-dev-18，只影响新生成布局，旧局不重新拼图。详情与定向证据见 [地图和布局更新](validation/MAP_LAYOUT_0.41.12_2026-10-29.md)。

0.41.11 源码新增房主移出本次大厅成员（含离线成员），名单变化清空准备状态，不改 SAO 社交队伍；成员行“移出”按钮仅房主可见。新意图使用协议 16，客户端/服务端须同时更新；运行中的 0.41.10 测试窗口保持原版本。此轮在独立源码导出目录验证，不覆盖当前客户端类路径。

0.41.9 源码新增 `/saodg admin metrics`，记录有界调度耗时及分位数。[统计范围和比较方式](PERFORMANCE_MEASUREMENT.md)。两项统计单测通过，未进行真实负载采样或部署。

需要汇总已提交修复供人工测试、且本轮不重复单测时，可用 `python tools/release/build_verified_release.py --java-home D:/Java/jdk-17 --package-only`。仍从干净 Git 导出编译/reobf 并核对结构、语言、版本、Mixin/refmap 和测试夹具排除；报告明确写 validation_scope=packaging_only、junit_passed=null、JUnit/运行时测试未执行。默认不加此参数仍执行原完整 build/JUnit，不得把仅打包报告当发布验收。

领奖执行边界可单独运行 `runGameTestServer -PgameTestNamespaces=saodg_reward_boundary -PgameTestRunDirectory=run/自定新目录`；该命名空间最近一次 4 项通过，[范围](validation/VANILLA_NATIVE_XP_2026-10-29.md)。战斗集成夹具为 saodg_combat，大厅名单/新意图夹具为 saodg_lobby，替换命名空间即可定向验证。未指定命名空间时默认包含 saodg、saodg_reward_boundary、saodg_combat 和 saodg_lobby。

0.41.8 新增 OP 2 级只读命令 `/saodg admin member <在线玩家>`，控制台也可指定玩家：显示 SAO 资料查询值/失败状态、社交队伍在线及未解析人数、当前实例阶段/淘汰状态/冻结名单人数。它不替目标办理入场或改动成员身份。`admin status` 中的固定阻断项现在明确标为“待完成正式验收”，避免与已绑定接口的健康诊断混淆。仅 `compileJava processResources` 验证通过（`logs/member-diagnostic-compile-20261028.log`），未做客户端或运行时命令复测、未部署。

当前源码 `0.41.8-dev` 修复可选门禁下遗漏 KubeJS 市场回执的问题，仅相关两项定向测试通过，未部署；下方全量结果属于 0.41.7 及历史版本。[修复范围](validation/ASSET_HISTORY_2026-10-28.md)。

同版补齐旧服五份受管实体/历史精确补丁，实际验证旧击杀策略 false/true、受管收益隔离与野外伪造标记对照。[证据与边界](validation/LEGACY_KILLS_2026-10-28.md)；正式开本仍关闭。

同版另完成真实 FTB 两人队伍事实投递、重复/同局去重、换队冻结与正常重启重放；修复准入脚本的不可变列表互操作。正式入口和奖励保持关闭。[范围与限制](validation/FTB_FACTS_2026-10-28.md)。

0.41.7 修复钱包脚本的持久数据命名空间和 Rhino 列表互操作，已在私有整合包中实际验证一次扣款、物品/经验发放、文件回读与重复应用拒绝；正式奖励仍关闭。[实测范围与限制](validation/LEGACY_WALLET_2026-10-28.md)。

0.41.6 修复 KubeJS 冷启动漏绑和重载撤销新接口的问题，已在授权整合包副本中验证旧接口失效、新接口有效且入场仍关闭；100 项 JUnit / 43 项 GameTest 通过。[证据与剩余限制](validation/KUBE_BINDING_2026-10-28.md)。

0.41.1 修复个人奖励页返回/翻页按钮重叠，详情支持裁剪和滚动；见[本轮记录](validation/REWARD_UI_2026-10-28.md)。

0.41 首领房奖励箱与两分钟结算停留，未领奖励可在外界通过 `/saodg rewards` 打开个人奖励页；见[本轮记录](validation/SETTLEMENT_2026-10-28.md)。

0.40.2 修复自有敌人入场注册顺序，新增四名服务端人物的双实例隔离/槽位复用验收；见[本轮证据与限制](validation/CONCURRENT_INSTANCES_2026-10-28.md)。

0.40.1 安全房入口开放，钥匙门改在安全房到下一间房的出口，仍使用前一战斗房的清房钥匙；见[验证记录](validation/SAFE_EXIT_2026-10-28.md)。

0.40 首领场地移出探索网格独立生成，封印大厅传送门将全队送入；实际实现与验证见[本轮记录](validation/DETACHED_BOSS_2026-10-28.md)。

0.39.1 按最新要求保留封印大厅多轮：普通房固定一批，精英房和封印大厅分轮生成；规则与验证见[本轮记录](validation/BLOOD_WAVES_2026-10-28.md)。

0.38 多格房间地图和封印大厅全队传送门的实际验证见[本轮记录](validation/MAP_PORTAL_2026-10-28.md)。

0.37.1 最新主路规划、原版敌人、石砖封墙/煤炭门与实际试玩结果见[本轮记录](validation/SPINE_VANILLA_2026-10-28.md)。

此前源码：`0.41.7-dev`。2026-10-28 最新变更见[原钱包事务验证](validation/LEGACY_WALLET_2026-10-28.md)，此前界面和主路记录保留。
0.41.7 的历史完整构建、100 项 JUnit 和干净隔离世界的 43 项 Forge GameTest 通过；后续改动的实际验证范围见各定向记录，不能将此历史全量结果外推到当前源码。兼容整合包与客户端视觉/联机验收仍待完成。
新增复盘的保存格式与验证范围见[复盘记录](validation/RUN_REVIEWS_2026-10-28.md)。
范围见[实现状态](IMPLEMENTATION_STATUS.md)与[内容清单](CONTENT_CATALOG.md)。
[战斗记录](validation/M2_COMBAT_2026-10-27.md)只证明对应历史版本，不覆盖本轮新增部分。
本轮实测范围及失败修正见[恢复验证记录](validation/BUILD_RESUMED_2026-10-28.md)；下文分批开发时写下的“暂停/未运行”保留为历史背景，不能覆盖新记录，也不能把局部通过外推到完整发布。
正式副本仍未开放。

## 环境

可用 `python tools/compat/prepare_pack_validation.py --server-source <本机发行目录> --mod-jar <已验证开发JAR>` 准备完整整合包的独立验收副本；该工具只复制并校验，不启动服务、不接受 EULA、不复制玩家世界，入场和奖励保持关闭。[已准备的具体副本与基线](validation/PACK_PREPARATION_2026-10-28.md)供后续逐项验收使用。

需要不夹带工作区临时素材的开发测试包时，先提交已跟踪改动，再运行 `python tools/release/build_verified_release.py --java-home D:/Java/jdk-17`。
工具把当前 Git 提交导出到全新私有目录并执行完整离线 build，保留源码 ZIP、日志、JUnit 结果和原输出；复制通过检查的重混淆 JAR 到 `build/verified/<版本-提交-时间>/`，同时生成 `verification.json` 与 `SHA256SUMS.txt`。
未跟踪的 beta 素材不会进入导出；工具不删除世界/缓存，不部署其他整合包，不上传或推送，失败也保留证据。它会确认结构文件集合、Mixin 配置/refmap、版本与中文默认语言回退，明确标记产物仅为 development_only。
该工具执行 JUnit 并编译 GameTest，不执行运行时或真实客户端/整合包验收；不能用包装检查宣称正式开本或全部经济故障已通过。

独立的两进程中断/重启验收可执行 `python tools/verification/verify_process_recovery.py --java-home D:/Java/jdk-17`。
目标整合包中的原生映射行为夹具使用单独 packTest 源集；已实际验证 `gradlew.bat packTestJar` 会生成并执行 `reobfPackTestJar`。附加 JAR 仅供已授权的私有环境，必须显式 `-Dsaodg.packAcceptance=true` 且目录匹配才创建临时角色；不要装到玩家服务器或客户端。默认 build 只编译它，不把测试模组打入主 JAR。[实际范围](validation/NATIVE_OWNER_BEHAVIOR_2026-10-28.md)。
加 `--checkpoint settlement` 可走完实际挑战，在首领房奖励箱出现且方案保存后硬退出再恢复；实际证据与限制见[结算恢复记录](validation/SETTLEMENT_RECOVERY_2026-10-28.md)。不加参数仍验证入口中断。
加 `--checkpoint reward_receipt` 则在实际领取的玩家文件已确认、世界确认尚未写入时硬退出；重启核对原固定选择、完整资产/回执、10 次旧请求去重和场景清理。仅显式 recovery 参数运行，未加入默认套件；[实际记录](validation/REWARD_RECEIPT_RECOVERY_2026-10-29.md)。
加 `--checkpoint reward_intent` 则在第一次领奖意图真实保存后、资产尚未应用时硬退出；重启检查按原方案发放一次、独立预期库存/成长和 10 次旧请求去重。原来 `reward_receipt` 的时间边界保留；[本次实际记录](validation/REWARD_INTENT_RECOVERY_2026-10-29.md)。
该工具新建 `run/gameTestServer-recovery-*`，故意让第一个专用测试 JVM 以 73 退出，再启动同目录恢复验证；不会对运行中的客户端执行此动作。
默认 GameTest 不包含该故障夹具，范围与实际结果见[进程恢复记录](validation/PROCESS_RECOVERY_2026-10-28.md)。

本模组中文以 `src/main/resources/assets/saodg/lang/zh_cn.json` 为唯一源。
`processResources` 同时生成内容相同的 `en_us.json`，作为 Minecraft 默认语言及其他未翻译语言的基础回退，避免显示 `saodg.*` 翻译键。
新增/修改中文只维护源文件，构建同步回退；开发客户端可重载资源检查，新安装产物随包包含两份资源。

- 64 位 JDK 17。默认系统 Java 25 不适用于此工程，请在当前 PowerShell 中指定 Java 17。
- Gradle Wrapper 8.8，ForgeGradle 6.0.54，Minecraft 1.20.1 官方映射，NeoForge 47.1.106。
- 现有 `SAO-0.76` / `SAO-server-0.7` 是历史 Forge 整合环境，迁移分支不修改它们的加载器、模组、存档或启动脚本。完整整合兼容需另行验收。
- 初次构建需要联网访问 Gradle 分发、NeoForged Maven、Forge Maven（传递依赖）、Maven Central 和 Mojang 下载服务。
- 不需要全局安装 Gradle，不需要安装 SAO、KubeJS 或任何参考模组即可构建和运行基础测试。

在工程根目录执行：

```powershell
$env:JAVA_HOME = 'D:\Java\jdk-17' # 调整为实际的 JDK 17 路径。
.\gradlew.bat build             # 编译、JUnit、编译 GameTest、重混淆打包。
.\gradlew.bat test              # 单独运行 JUnit 纯规则测试。
.\gradlew.bat runGameTestServer # 运行独立 NeoForge 1.20.1 GameTest 专服，测试结束后退出。
.\gradlew.bat runClient         # 启动开发客户端。
.\gradlew.bat runServer         # 启动普通开发专服，无图形管理界面。
```

以上任务名已实际验证存在，build 和 runGameTestServer 有历史执行证据；当前改动是否通过应以相应版本验证记录为准。
历史构建通过不等于本轮源码已通过，普通客户端与目标整合包也仍待统一验收。
普通专服首次启动会要求开服者自行阅读并接受 Minecraft EULA 后再启动。

当前人工客户端为 0.40.1，0.40.2 修复需下次重启加载；历史 `saodg-0.34.0-dev.jar` 的源码快照路径/散列见上述复盘记录，不包含本轮修复。开发运行目录按配置隔离：
`run/client`、`run/server`、`run/gameTestServer`，均不应纳入版本控制。
测试使用独立生成的世界，不指向现有客户端存档或实际服务器目录。

JUnit 报告位于 `build/reports/tests/test/index.html`。
GameTest 结果位于 `run/gameTestServer/logs/latest.log`；可保存 Gradle 标准输出到 `logs/`。
可用 `-PgameTestRunDirectory=run/新的测试目录` 隔离新世界；本次实际使用 `run/gameTestServer-validation-2026-10-28`，对应日志在该目录。
`build` 只编译 GameTest，执行运行时测试需要另跑 `runGameTestServer`。

## 当前入口与配置

0.41.26 补齐安全回程的公共大厅回退。在房主存档或服务器世界的 `serverconfig/saodg-server.toml` 配置：

```toml
[safeReturn]
hubEnabled = true
hubDimension = "minecraft:overworld"
hubX = 100.5
hubY = 70.0
hubZ = 100.5
```

坐标是玩家脚部的世界坐标；请按实际建好的大厅填写，修改后重启加载。`hubEnabled` 默认 false，不会自动建平台。顺序为安全的原返回点、启用且安全的公共大厅、原有世界出生点搜索；大厅维度不存在、配置错误、落点堵塞或有危险时继续回退，不能将大厅设在 `saodg:dungeon`。全部候选都不安全时保留待回程记录，管理员修好落点后再重试。回退保留原朝向和原游戏模式，不修改出生点/全服死亡规则。[验证范围](validation/SAFE_RETURN_HUB_0.41.26_2026-10-29.md)。

- `/saodg`：说明当前工程状态。
- `/saodg admin status`：OP 2，显示版本、协议、预设、人数/并发上限和开本阻断原因。
- 网络通道：`saodg:main`，源码协议 `24`。界面操作意图、完整投影与增量同步要求两端版本相符；握手规则夹具通过，真实端点仍待验收。
- 配置：各世界 `serverconfig/saodg-server.toml`，默认 `STANDALONE`。
- 服务端配置包含人数 1～4、并发 1～2、大厅/生成超时、重连窗口和每 tick 方块预算，实例服务按开局及运行阶段读取。
- `SAO_SERVER` 额外要求资料、濒死、队伍、钱包和死亡资产能力。源码已加入查询与注册桥接，但实际适配未验收，正式预设仍阻断开本。

### 内容优先开发中的新增部分

- 0.41.32 起，清理作业在原方块/扫描上限内，每64位置检查3ms协作时间片，跨tick保留游标；单次区块加载/回调和最终同步保存不受硬时间限制。完整试炼采样、首次JVM崩溃及成功重试见[记录](validation/TRIAL_CLEANUP_TIMING_0.41.32_2026-10-29.md)。
- 0.41.31 起，面板退出确认随大厅/实例 ID 或修订号变化失效，点击时也重新核对，服务端拒绝旧修订的 LEAVE；命令 `/saodg leave` 仍直接退出当前上下文。大厅定向验证与客户端/战斗流程的未验证边界见[记录](validation/LEAVE_CONFIRMATION_0.41.31_2026-10-29.md)。
- `/saodg` 的客户端入口已接大厅、地图、奖励和战绩页面；面板不暂停服务器。
- `/saodg history`：显示自己最近 10 条成功战绩或非成功复盘，不接受指定其他玩家的参数。
- 0.41.29 起，面板“战绩”页的评分、失败/中止原因、进度和个人资格为可滚动详情；底部翻页与个人奖励入口固定，收到新记录时按局 ID 保留当前阅读记录。奖励入口优先选中该局当前可见的待领奖，没有该局待领奖时展示个人奖励列表，不额外发奖。
- `/saodg ready`、`/saodg start`：可省略内部版本号，服务器读取当前上下文；0.41.15 起开始由队长操作，不要求 OP，全员准备与开发存档开放条件仍保留。原显式版本/种子形式继续支持。0.41.10 起旧 `/saodg bossready [修订号]` 仅提示前往封印大厅传送门，不积累准备状态、不消耗钥匙、不启动转场；旧网络请求同样处理。
- 0.41.28 起，`/saodg` 页右上角“显示设置”或 Mods → SAODG → 配置可调整 HUD/小地图开关、50%～200% 缩放及水平/垂直位置，并恢复默认。设置只保存到本机 `config/saodg-client.toml`；关闭小地图仍显示队友，小窗口会临时缩小 HUD 以保持完整，保留配置的首选缩放。快捷键默认不绑定；所有客户端渲染/缓存类隔离于 client 包。
- 服务端每 10 tick 发送玩家自己的投影变更，带 streamId 与修订基线；客户端不能提交分数、价格或掉落。
- 活动目录新增波次/Boss 配置，普通战斗准备/波次/超时与首领预警/范围/间隔从快照读取。
- 0.41.30 起，已登记副本敌人取消原生实体转化并延迟重试，保留波次所需的精确 UUID；原版僵尸测试模式不会因转成溺尸而丢失星标。未登记生物和伪造实例 NBT 不改变原生转化行为。
- 模板快照以私有压缩字节保存，读取时展开为独立 NBT，减少多格房间目录长期持有的对象数量；尚无性能测量。
- 结构素材现为 28 个逻辑房间、41 个分片文件，详见内容清单。新增素材与现有测试夹具的固定数量假设将在统一验收时一起更新。
- 守门者使用自制石像模型、发光阶段核心、三类蓄力姿态、限定参战者的阶段血条和原版音效，客户端尚未渲染验收。
- 新版参与资格证据按目标去重，伤害需在下一 tick 确认实际生命降低，成功谜题记录参与者；自动完成入口/安全房不计有效行为。
- 原生持久宠物通过原台账证明主人/记录/部署/实体四项身份，入场前安全收回、局内获得租约，归还仍由原台账执行；回读未确认时保留实例及资产锁。
- 临时灵宠以新对象的原生 begin 调用产生出生 nonce，按原生 expire 调用记录结束；既有坐骑、带装备/乘客或变化能力数据的对象不能被当成无资产临时物。
- `PetSkills` 在原生目标谓词与伤害、效果、燃烧、击退/速度调用处增加实例过滤；玩家其他技能和投射物完整生命周期仍待接入。
- 职业与呼吸法新增逐目标治疗/状态/伤害/速度、闪现路径检查；火球、图腾和持续施法按创建实例绑定，旧延迟效果不能转到新局。其余剑技/枪械继续单独接入。
- 投射物新增原版 `setOwner` 观察、对象/nonce/父链/轨迹/闭门检查。弓、箭类弩弹、三叉戟接预算及发射扣除凭证，可回收原物品先托管再按固定回执归还。

奖励事务代码也已加入：`/saodg rewards` 预览，`/saodg claim <operation> <choice> <revision>` 领取，
`/saodg admin recover <operation>` 只重试已有选择和回执，不替玩家选档位或强制额外发奖。
`enableDevelopmentRewards=false` 为默认值，仅新开局显式启用后准备免费测试物品与迷宫区 XP。
原生事务不读写 SAO 钱包；付费/珂尔变更在内容加载和事务入口均拒绝。
未确认保存时，原生背包点击、主动丢物与相关包入口持有资产锁；源码还加入 Forge 物品自动 tick、持续使用物品和 EpicACG tick 暂停。
物品自动回调与 EpicACG cast/tick 执行期间，嵌套领奖/归还不能取得资产基线，宠物收回延后；异常退出使用 finally 释放同步作用域。
新发奖/归还要求结束物品使用，已有回执仍能确认；全部新增暂停/恢复边界未构建运行，其他直接资产写入仍需对应整合包审计。

Mixin 构建声明使用固定的 MixinGradle `0.7-20230803.124500-15` 与 Mixin AP `0.8.5`，
只作为构建依赖，不将它们作为内嵌 JAR 打包；当前源码不重新执行构建。

可选 KubeJS 编译声明固定为 `2001.6.5-build.26`，插件类仅由 KubeJS 插件发现器加载；无 KubeJS 的通用入口不引用其类型。
SAO 适配使用隔离包内的反射，只调用本地 r234 已读取到的公开查询签名，不复制 SAO 等级公式、不写主线、不调用原生币余额。
本轮接口、预览命令及脚本桥接的使用范围见[集成实现说明](INTEGRATION_IMPLEMENTATION.md)，均属于待构建源码。

### 管理员开发原型

仅在独立测试世界，将 `enableDevelopmentRuns` 明确设为 `true`，保持预设 `STANDALONE`。
来源世界与迷宫区维度必须继承原生 `keepInventory=true`；引擎只检查，不修改全服规则。
开本、地图、战斗、资产安全与整合包验收尚未全部完成，默认保持关闭。

```mcfunction
/saodg create trial
/saodg invite 玩家名
/saodg join 队长名
/saodg difficulty standard
/saodg ready 修订号
/saodg start 修订号
/saodg leave
/saodg puzzlereset
/saodg admin validate
/saodg admin inspect 实例UUID
/saodg admin abort 实例UUID 原因
```

0.41.15 起 `create` 对普通玩家开放，`invite` 仅发邀请，被邀请者点击接受或使用 `join` 后加入。`start` 由全员准备后的队长操作，不要求 OP；名单或难度变化清空全部准备。完整交互见 [副本队伍](PARTY_USAGE.md)。
`start <revision> <seed>` 可指定复现用地图种子；省略时使用服务端随机源。
当前原型支持普通/精英房登记敌人、清房开门、两波前哨、三类谜题与秘密交互。
前哨要求普通/精英战斗目标完成，完成后发出首领准备提示；所有在线存活成员按修订号确认后，
共享钥匙消费一次、全员传送到首领场地，探索交互冻结。

首领在 70% 进入两座封印与守卫的转场，35% 进入最终阶段；超额伤害不能跳过机制。
技能由服务端计时，提供粒子预警；冲锋检查路径与落点。必要敌人消失会诊断中止，不当作击杀或无限补刷。
死亡事件延迟到下一服务器 tick 检查最终取消状态与实体；原生玩家确认阵亡计数一次，重生后回程。
重生恢复等连接绑定到新玩家对象后执行，回程日志在玩家文件确认前保留。

未开启开发奖励的原型局保存评分与 `prototype_completed` 结果，标注 `reward_status=NOT_IMPLEMENTED`，不补发奖励。
新局若明确开启开发奖励则保存 `OFFERS_PREPARED` 与固定个人方案；这仍不代表奖励已领取，不写珂尔。
结果保存在世界日志的可选 `prototype_results` 分区，原运行记录新增敌人登记、死亡事实与遭遇诊断。
0.2 的 schema 1 日志允许这些新增字段；旧记录缺省为空，损坏或未知结果条目拒绝覆盖。
运行记录新增 `reward_port`（旧记录缺省原生端口）、`participation_version`（旧记录为 1，新局为 2），
每名成员新增有界 `action_proofs`。旧战绩不按版本 2 重新判资格，已发奖励与回执不改写。
FTB 接收器使用独立 schema 1 的 `quest_facts.nbt`，其路由哈希绑定本工程迷宫区与新增任务，改路由需显式迁移。
运行记录新增可选 `companions` 列表，最多 128 项租约，旧日志缺省为空。每项有独立 schema、端口/令牌、用途和归还状态，
新日志在清图前要求全部归还确认；租约不授予删除宠物的权限。管理员 `inspect` 可查看，原 `cleanup` 会重新尝试冲突归还及现场检查。
原生宠物回读使用既有 `sao_pet_roster.dat`，只调用台账原生保存，不直接覆盖该文件。保存 IO 与联机性能仍未测量。
运行记录新增可选 `projectiles` 列表，最多 16384 项身份历史、每实例最多 256 个已加载的在场/保留弹体，父链最多八层。
旧日志缺省为空；类型/字段/父链不一致拒绝覆盖。纯临时弹体需当前对象、nonce、无库存、能力指纹和不可回收条件同时吻合才能清除。
可拾取箭与三叉戟新增自动托管归还；数据、扣除凭证或原生资产形状不明时仍保留实体，不发放简化替代品。
原物品日志位于 `world/data/saodg/item_returns/`：独立 schema 1 manifest 与按 UUID 前缀分片的操作文件。
每项由来源/实例/nonce 固定 ID，保留原生拾取 ItemStack 的完整 NBT/ForgeCaps，确认后只留去重墓碑，避免完整物品负载无限积累。
最多 100000 项去重历史、8192 项待处理记录；新发射预留在场弹体容量。每 tick 最多托管两件、最多处理两笔归还，自动投递每五 tick 调度。
玩家可用 `/saodg itemreturns` 查看自己的记录，`/saodg itemreturns retry` 重试；奖励页提供同样入口。
OP 2 的 `/saodg admin recoveritem <id>` 仅重试原收件人和原 payload，不强制清除冲突或重建物品。
归还使用单玩家原生保存入口，再回读实际玩家文件；不改钱包/经验，不投递奖励或任务完成事实。
原版发射动作结束时按“实例＋真实玩家对象”分组核对扣除进度。重登分组不能覆盖旧动作，缺少旧凭证的弹体保留现场。
备份或恢复需同时包含玩家文件、`data/saodg/` 全部日志和原生资产台账；不声明这些多个存档文件天然原子。
结果归档只保存投射物数量，不把整段瞬时弹体历史重复复制进每局战绩；运行中的权威记录仍保存到实例清理结束。

默认全服每 tick 仅处理一个大型世界写入作业，最多 2048 个方块变更；
空气检查等扫描也有上限。生成与清理均持有自己的有限区块票据并在关闭/隔离时释放。
持久预约与回程日志位于 `world/data/saodg/state.nbt`，使用强制写入、原子替换与回读确认；
`saodg_runtime.dat` 为 SavedData 镜像。未知 schema、损坏或镜像存在但主日志缺失时拒绝初始化，保留原文件。
返回后回读玩家文件中的维度、位置和游戏模式，成功前不删除世界回程记录。
清理先检查整个占地清单；未知实体、物品、容器或其他方块实体触发槽位隔离，不直接删掉。
隔离槽位可用 `admin cleanup <runUUID> <reason>` 请求重新检查；仍不允许强制删除未知资产或直接标记为空闲。

客户端玩家文案统一位于 `assets/saodg/lang/zh_cn.json`。
专服控制台未加载客户端中文语言资源时可能显示翻译键；启动日志同时提供可检索的诊断键。

## 源码边界

| 路径 | 当前职责 |
| --- | --- |
| `bootstrap` | 模组入口、配置/事件装配、启动健康日志 |
| `domain/lobby` | 不可变大厅、房主权限、名单/难度/内容版本变更清除准备、固定名单快照 |
| `domain/run` | 完整阶段转换守卫、修订号、紧邻重复转换识别、战斗阶段失败出口 |
| `application` | 大厅用例、实例/玩家索引、入场/回程/重连、恢复与清理调度、能力阻断诊断 |
| `infrastructure/content` | 数据包候选集合、结构安全校验、不可变活动目录、失败保留旧目录 |
| `infrastructure/persistence` | 带 schema 的运行记录、占地清单、回程、槽位、原子 NBT 日志屏障及 SavedData 镜像 |
| `domain/layout` | 稀疏房间占地、统一旋转、闭区间端口、有限尝试布局生成、钥匙与可达性检查 |
| `domain/instance` | 带 UUID 所有权的槽位状态机 |
| `domain/score` | 评分、评级与参与资格纯规则，接到完成结果与奖励准备 |
| `platform/forge` | Forge 配置、命令、协议、分批结构放置/清理、基础保护事件、自有敌人/材料注册 |
| `client` | 玩家面板、HUD、小地图、投影缓存与隔离的怪物渲染注册 |
| `integration` | SAO 只读查询、代际化 KubeJS 门面、钱包所有者事务参与者、FTB 接收器 |
| `compat` | 未部署的服务端脚本、钱包/受管实体补丁、独立 FTB 章节及 ID/来源清单 |
| `src/test` | JUnit；领域代码不引用 Minecraft、SAO、KubeJS |
| `src/gameTest` | 独立运行时夹具与自制空结构，不进入发布 JAR |

`Lobby.freeze` 是不可变快照；`InstanceService` 在主线程重新检查在线/占用/预设/死亡资产条件，
先持久预约槽位及回程，再消费大厅、放置和入场。SAO 濒死查询已装配但未实机验收，正式预设仍拒绝开始。
成员房间与交互节流按“实例 UUID＋成员 UUID”分键，旧局延迟清理不会清掉新局状态。
实例回程循环只处理自身 run 标记；旧隔离局不读取成员后来新开的局的回程。重生恢复未完成时拒绝新开局，
地图生成结束及原生宠物收回后还会重新检查在线对象、濒死、资产锁、原世界和背包保留条件。这些复用/延迟路径尚未运行验收。
`RunLifecycle` 只决定转换是否允许，不提供保存屏障、不触发清房或发奖，不能把它的重放识别当作奖励事务。

## 下一步

双实例夹具现可单独用 `-PgameTestNamespaces=saodg_concurrent` 运行，仍包含在默认套件；2026-10-29 已通过当前一格连接下的四人双实例煤炭门、旧局意图拒绝与槽位复用检查，见[记录](validation/CONCURRENT_SPACING_2026-10-29.md)。它使用服务端人物，并非真实四客户端或原生整合包验收。

`tools/verification/verify_process_recovery.py --java-home D:/Java/jdk-17 --checkpoint transfer` 是显式两人入场中断检查：使用实际维度切换事件截住第一人入场、第二人未移动的 READY 窗口。2026-10-29 两进程已通过各自回程/库存保留及完整清理，见[记录](validation/TRANSFER_RECOVERY_2026-10-29.md)。这不是远程多人或原生钱包验收。

清理阶段的独立两进程检查现可通过 `tools/verification/verify_process_recovery.py --java-home D:/Java/jdk-17 --checkpoint cleanup` 执行；只运行这一项，使用全新专用世界。2026-10-29 已实际通过部分清理硬退出、重启完整清空及释放检查，范围见[记录](validation/CLEANUP_RECOVERY_2026-10-29.md)，不等同完整阶段故障矩阵。

1. 继续补齐其余剑技、目标枪械及直接资产写入；职业/呼吸法、投射物隔离/归还有源码，所有新增接入材料未安装，保留原生资产所有权。
2. M1/M2：真实双队、断线与进程崩溃恢复、完整实例 50 轮、濒死/救援适配、宠物/召唤物归属和主动丢物前置限制。
3. M4/M5：多格真实模板、谜题与 Boss 的表现/可读性、HUD、小地图与正式结算界面。
4. M6：目标整合包、兼容脚本、性能/经济采样、升级与回滚及全部发布验收。

当前谜题 JSON 还需 `puzzle_controls` 三个局部坐标，Boss 房需 `boss_seals` 两个局部坐标；
均检查位于实际占用单元内，并与结构/其他标记使用同一旋转函数。
光路原型使用固定三镜面有限网格：钻石入射标记、金接收标记，白色镜面表示 `/`，黑色镜面表示反斜线。
符文与单人封印按提示顺序；多人封印要求在 100 tick 窗口内由不同成员共同激活。
遭遇/Boss JSON 格式已加入源码与素材；敌人数值、两波前哨和首领技能仍为原型参数，格式兼容及实战平衡尚待统一验收。

历史原型可通过 `python tools/legacy/generate_ruins.py` 确定性导出到 `build/legacy_room_fixtures/data/saodg`。
该命令不再改写模组资源或活动房池，不读取参考资产。
当前模板导入策略只接受无方块实体、无实体、单 palette、完整显式体积的原版方块模板，
并拒绝命令方块、结构方块、刷怪笼、传送门等；复杂模组方块/容器需独立审核后扩展，不能静默放入。


## 迷宫区成长、解锁与指南（新增源码，未运行）

从 `ruins-dev-4` 起，迷宫区定义使用 `schema_version=2`，为各难度增加可选 `admission` 与 `guide`。
新读取器仍接受不含新字段的 schema 1 定义，保持等级 1、无首通前置；schema 1 中写新字段会明确拒绝。
旧版 SAODG 不支持 schema 2，不能把新前置当成可忽略字段而加载。房间、Boss 与奖励格式保持原 schema；新增波次行为使用单独的 schema 2，见下节。
本轮遗迹回廊数据明确设置试炼起点、一次合格试炼解锁标准、一次合格标准解锁精锐；不以 OP、队长或队友的通关代替其他成员。
这些只作用于开发预设，`SAO_SERVER` 门槛保持；现有 FTB/SAO 任务条件仍由已注册脚本额外校验，不杜撰原任务 ID。

```json
"admission": {
    "minimum_dungeon_level": 1,
    "requires_clears": [
        {"dungeon": "saodg:ruins_01", "difficulty": "trial", "count": 1}
    ]
},
"guide": {
    "overview": "saodg.guide.ruins.standard",
    "preparation": "saodg.guide.ruins.preparation",
    "rewards": "saodg.guide.rewards_default"
}
```

每条前置使用确切迷宫区/难度，最多 8 条并同时满足；次数为 1～10000，等级为 1～20。
新字段中的未知键、非整数数值/字符串整数、缺失引用、重复前置、自环/多节点循环、无可起步难度都会拒绝本次数据加载，保留先前有效目录。
当前奖励公式只支持 trial/standard/elite，内容加载也明确限制这三个难度 ID；不能借指南暴露不可结算的新难度。
人数读取 dungeon.party 的 min/max（1～4），开局实际人数仍同时受服务器 maxPlayers 限制。

新合格通关在现有 prototype_results 中写 progression_schema=1 和逐成员 progression_eligible；由最终在场/有效目标计算，与结果在同一 checkpoint 保存。
检查点确认后才加入内存索引，重启从明确凭证重建，同一 runId 的相同凭证不双计，冲突保留并拒绝加载/计入。
计数独立于领奖与开发奖励开关，不改变迷宫区 XP 事务、SAO XP、珂尔或 FTB 任务；旧记录缺少 schema 不重新判定或补证。
升级前的通关不会自动解锁新版标准/精锐；开发者需要重新完成前置，或明确修改开发数据包的 admission，不能隐式以管理员身份绕过。

攻略等级从玩家保存的 long 型 dungeon_xp 推导，累计阈值 100*(L-1)^2、上限 20；不信任旧 level 缓存，不叠加战斗属性。
资产待确认、日志不可用或格式错误给未知状态，不能用尚未确认的经验入场。准备、脚本入场回调前后、实际传送前复查，活动局使用其快照规则。
指南是第五个页面并作为默认入口，可滚动阅读时限、推荐准备、死亡继承、奖励是否开启与个人前置次数；大厅显示未解锁成员并限制准备/开始按钮。
/saodg progression 提供本人只读文字查询。新增 profile/guide 投影不包含奖励随机源、未发现坐标或他人经验明细。

本轮没有执行 Gradle、JUnit、GameTest 或客户端。
新增 DungeonLevelTest、AdmissionRequirementsTest、ProgressionGameTest 只是待运行夹具；凭证编码测试不代替真实 Boss 结算、保存故障、重启和多人入场验收。


## 三类普通敌人（0.26 新增源码，未运行）

遗迹内容版本为 ruins-dev-5，六份波次使用 schema_version=2 / ruins-encounters-2。
每波可添加 behaviors 列表，按生成序号循环取配置，列表最多与 count 一样长；省略/空列表沿用基础近战。
旧 schema 1 波次不接受 behaviors；旧读取器不支持 schema 2，不会忽略新配置后开放另一套攻击。
当前原生 Boss 转场守卫不在这次波次角色改造内，保留已有基础近战。

```json
"behaviors": [{
    "role": "channeler",
    "windup_ticks": 40,
    "recovery_ticks": 40,
    "engage_range": 14,
    "extent": 2.75,
    "half_width": 0.8,
    "half_angle_degrees": 50,
    "damage_scale": 1.1,
    "movement_speed": 0.18,
    "interruptible": true
}]
```

role 为 vanguard / duelist / channeler：extent 分别为扇形长度、直线长度或圆环半径；half_width 只用于直线，half_angle_degrees 只用于扇形。
所有字段仍须显式提供有效数值，未知字段/角色、错误布尔、非整数计时、非有限数值及模式过长均拒绝重载。
生命和基础攻击仍按原波次生成，人数倍率只应用一次，行为 damage_scale 在该次命中应用一次；不改变玩家 SAO 武器/职业公式。

EnemyCombatService 只为权威注册过的自有敌人创建控制器，角色/状态同步字段用于外观，不从 NBT 推断攻击许可。
原版 doHurtTarget 在新角色上停用，保留基础导航追击；蓄力与恢复暂停自主 AI 和水平惯性，不传送、冲刺或新建投射物。
形状固定在起手位置/朝向，圆环固定原目标当时脚下位置。命中重新检查源、当前成员、阶段、房间、有限占地路径与碰撞方块视线。
咏唱者依据实际 hurt 前后生命变化序号及当前生命下降观察打断，不用取消事件或猜测伤害值作为证明。
已经解析的原生冻结来源由 integration/sao 查询，不在调度器导入 SAO 内部类或改写其期限；普通缓速/定身不被擅自当成全身冻结。

每局最多 6、全服最多 12 个控制器蓄力，等待者按准备时间排序；管理表上限 512，仍受每局 64/全服 160 活敌预算限制。
每次初始预警须至少发送给一名合法同房成员，后续每 4 tick 刷新边界；每个图形最多 21 点，收件人至多原名单 4 人。
预警使用粒子/提示/音效，实际伤害仍仅服务端执行；此上限不是性能已通过，需采样目标整合包网络、粒子和调度耗时。

外部已有 NoAI 暂停不会由调度器直接认领并清除；自己的暂停只在自己的恢复路径解除。
实体重新加载按原运行注册表和固定定义接回新身体，但撤销旧攻击并等待恢复；服务器重启仍由原实例恢复策略中止，不能重放旧伤害。
保存的 saodg_combat_role 只保留外观/关闭原版近战，不能从持久外观恢复控制器或攻击时间。

客户端新增 RuinsEnemyModel / RuinsEnemyRenderer，使用原版方块材质的自制几何与发光核心；武器不是可掉落装备。
新增 SynchedEntityData 字段要求网络协议 3，两端都需更新；现有基线协议夹具同步改为接受 3、拒绝 1/2。
新增 EnemyBehaviorTest 与 EnemyBehaviorGameTest 仅为未执行的夹具；还未证明真实调度/命中、重连、双队、视觉、平衡与性能。


## 原生击杀经验确认（0.27 新增源码，未运行）

新增 NativeExperienceService / NativeExperiencePort / SaoExperiencePort，不把原生击杀经验混进通关 RewardPayload。
在 ExternalKillXp.onDeath 原本调用 PlayerData.xp 的确切位置捕获原生接收者/数额，保留原资格与 amount() 计算；范围仅为权威受管怪及实例中待恢复的自有怪。
外界普通击杀继续原调用与 note；副本即时 note 停止，保存确认后用本模组中文提示，不重放整个死亡事件，不创建离线玩家替身。

准备请求先写 data/saodg/native_xp/manifest.nbt 和按 UUID 前两位分片的操作文件，状态为 WAITING_DEATH。
真实死亡后，managed_entities[].native_xp 链接与 confirmed_dead 在世界 state.nbt 同一检查点保存，再把请求保存为 READY。
READY 落盘前保持来源运行记录；READY 后其固定义务独立于地图。重启未确认的已知死亡意图取消，未知/孤立来源不被猜成空记录。
每个 runId+enemyUUID 仅一个请求，接收者、原数额、实体类型、encounterUUID 与所有者固定。同 tick 多个候选按事件身份保留，取消后再死亡不复用旧候选；冲突来源/数额中止对应实例。

人物处理顺序：核对真实在线对象与原生资料 → 保存/读盘 before 基线 → 持久 INTENT → 持久 APPLIED_UNCONFIRMED → 调用原生 PlayerData.xp → 自有回执 → 原生人物保存/读盘 → 世界 CONFIRMED → 解锁与临时回执清理。
回执在 PlayerPersisted.saodg.native_xp_receipts，和 ForgeData.SaoProgress.xp 保存在同一人物文件。
投影只校验 xp 与已知曲线迁移字段，不把体力/水分等周期数据当成经验事务字段；原生属性、跨级治疗与体力由原函数处理，不在迷宫区复制曲线。
匹配回执允许同一曲线下其他原生正 XP 单调增加；经验下降、曲线改变、库存改变和异常回执停止自动重试。
缺回执的应用只在重启恢复且当前人物与实际读盘均匹配持久 before/库存基线时允许重做；其余未知结果保留，不靠余额差猜测。

已读取 r234 PlayerData/ExternalKillXp 与本地 sao-gameplay-fixes 的 LevelCurveMixin、ProgressionDataMixin、GrowthPolicy。
原生 r234 与补丁曲线 v2 使用不同冻结所有者 ID；原始类散列只用于限定引用，不能证明运行时变换钩子、额外补丁或实际经验语义已经通过。
参考 JAR/类散列与静态调用方清单见 compat/native_xp/SOURCE_REFERENCE.json；静态方法引用清单不是运行调用链证明。
不同版本/曲线不会自动重解释旧请求，需另行兼容迁移。SaoProgress 错误字段不由本适配器猜测修复。

经验目录最多 100000 条，未完成最多 8192 条；开局按实际图的全部波次、Boss 与转场守卫预约最坏数量，仍受每局 512 个受管实体预算限制。
每 tick 最多两次处理，准备队列/每人计数单独索引；确认后保留持久去重墓碑，已确认人物回执可清理。
记录不要求领取通关宝箱，也不因本局开发奖励开关而丢弃原生击杀 XP；离线、濒死与旁观等待，对象必须是当前真实在线人物。
当原玩家处于另一局时等待，防止旧局延迟的升级治疗进入新局；原副本内或副本外仍可处理，断线后不伪造角色。

/saodg experience、/saodg experience retry 查询/重试本人固定记录；奖励页在有积压时提供重试按钮。
/saodg admin recoverexperience <operation> 仅由 OP2 重试已有接收者与原请求，记录操作者；不提供强制改数、换人或重复发放。
资产未确认时沿用既有背包/使用物品/自动 tick 保护，世界日志或来源缺失时保留；其余直接资产写入与原生进度恢复仍须审计。

世界主日志 schema 从 1 升为 2，阻止旧版本忽略新死亡链接后清图。没有新经验文件/字段的一致旧 schema 1 会在完整运行时检查点升级；旧头混入新文件/字段拒绝加载。
主日志丢失但已有物品归还/原生经验日志也拒绝创建新账本。备份/回滚必须作为一组恢复世界主日志、经验分片、物品归还和人物文件，不能单独降级版本号或删除凭证。

本轮没有执行构建、JUnit、GameTest、客户端或部署。NativeExperienceGameTest 是隔离目录/注入端口的未执行夹具，仅覆盖意图、证明、离线身份与编码边界，不冒充真实 SAO 曲线/保存/双队验证。
实际钩子、原生跨级副作用、断线/重启/人物文件故障、额外 KubeJS XP 跳过补丁和全部直接资产写入仍未统一验收，正式预设继续关闭。


## 房内交互与谜题表现（0.28 新增源码，未运行）

默认内容版本 ruins-dev-6，三个谜题房使用 schema_version=2，并新增 puzzle_scene：

```json
"puzzle_scene": {
    "clue": [23, 2, 28],
    "reset": [25, 2, 28],
    "emitter": [14, 2, 24],
    "receiver": [28, 2, 24]
}
```

emitter/receiver 仅用于 light，其他谜题省略。线索、重置、入射、接收端分别必须匹配实际模板中的青金石、红色陶瓦、钻石、金块。
加载时检查足迹、与控制点/秘密/出生/到达点的分离、轴对齐镜面与相同高度、2～12 格偶数间距，以及有界光路高度的空气通道。
房间 schema 1 仍支持，不能放新 puzzle_scene 字段；没有场景元数据的旧谜题保留原提示/重置兼容路径。
生成器本轮实际执行了一次，只写本仓库原创内容：房间数仍为 28、结构数仍为 41，三份谜题结构增加标记，其他模板内容不变。没有执行构建或测试。

PuzzleProgress 增加 revision、有限 BeamTrace、自动封印 advance 和最多一次的 failureRecorded。
100 tick 到期清除当前点亮、持有者与未完成贡献，重置保留失误历史；仅成功后的最终参与者仍可写入原去重行为证据。
线索、重置、光路、出口提示都不产出贡献、物品或经验，不改变当前评分公式，不给出隐藏房/秘密坐标。

RoomInteractionService 从实际在线对象、实际维度/合法位置和已探索房间生成公开 room_objective，包含可见进度、当前镜面/点亮、倒计时和瞄准装置标签。
不包含 sequence、地图种子或目标镜面答案。新模板的完整线索只有靠近、视线可达且合法请求时通过原提示消息返回；普通状态更新不重复发送线索。
GUI 的 ROOM_ACTION 只接收 hint/reset/exit、当前 roomId 与 puzzle revision，外加原 runId/run revision，重新验证真实上下文与距离；没有遥控世界中的镜面或符文按钮。
新意图要求协议 4，基线协议夹具同步更新；旧协议 1/2/3 拒绝，两端更新后才具备新交互。

当前房间页的重置需第二次确认，谜题变化/换房/不再靠近时清除旧确认；物理重置需潜行右键。
房间页支持滚动，大地图标号，HUD 显示剩余目标/波次和瞄准标签。出口 BFS 仅遍历本实例已探索且未锁的图边；不传送，实际走路仍受门与实例权限控制。
出口粒子仅发送给原请求者，5 秒到期、换房、关门、Boss 开始或实例结束立即失效。光束仅同房可见，每 5 tick、每人至多 64 粒子点。

新增纯规则及 RoomInteractionGameTest 是未运行夹具；数据/投影边界测试不能代替实际方块点击、旧包、视觉、多队或性能验证。
全部新源码、三个 NBT、缩略图、GUI 缩放与服务器时序仍待内容完成后的统一验收。


## 绑定材料和条件奖池（0.29 新增源码，未运行）

内容版本 ruins-dev-7 声明 development_material_reward_profile=saodg:ruins_materials_dev，默认 reward_profile=saodg:ruins_01 保持原凭证表。
需要 enableDevelopmentRewards=true 与 developmentMaterialRewards=true 才为新局选择实验表；无声明时拒绝开始，不回退为另一个奖励集。
RunRecord.reward_profile 保存实际选择，活动局继续持有完整不可变目录；换配置、重载或之后领取不会变更已固定方案。
材料本身已注册，新的 BoundMaterialItem 只用于遗迹碎片/封印核心，不绑定原 SAO 武器，不发第二套货币；试验表无正式兑换和属性用途。

reward_profiles 的 schema 2 Drop 增加 bound、chance 和 only_difficulties，默认分别 false、1 和三难度。
概率要求有限且 0<chance<=1，过滤难度必须是非空的已知集合；所有字段类型与重复项检查，不把新字段放入 schema 1。
保证掉落不额外消耗 chance RNG，随机仅在原服务器专用奖励源滚动，全部宝箱方案在完成时展开并固定，领取不重掷。
自有材料必须显式 bound=true，profile 的 SNBT 不能提供 saodg_bound_material。生产数量/概率仍需采样，当前实验表不代表正式经济。

RewardPayload.Item 增加可空 boundTo。无绑定载荷保留旧散列；有绑定载荷使用明确 v2 前缀和每件接收者进入散列，RewardCodec 使用 payload schema 2。
旧代码不能解释新绑定散列；不要直接用旧版本打开有新载荷的存档，升级/回滚仍须整组备份。
NativeRewardTransactionPort 在原主背包一次性暂存流程中构造完整绑定 NBT，校验操作的真实接收者；钱包继承端口同样保存完整栈。
RewardTransactionPort.supportsBoundMaterials 默认 false，当前原生端口明确支持，代际代理转发声明；失效/不支持时不改为发无绑定材料；已匹配的应用回执仍可做保存确认，不因能力声明变化而再次应用。

绑定元数据为 stack.tag.saodg_bound_material={schema:1,owner:UUID}，仅归属真实在线人物有原版拾取/取用资格。
容器点击/快速转移/交换/拖拽/双击、基础 Slot 和 ItemEntity 入口增加保护，拒绝不删除原栈；错误持有人已有物品可在原丢物规则允许时丢回供归属者取回，不自动重签或送背包。
RecipeManager 的普通/缓存/列表入口禁止材料进入标准加工，MerchantOffer 的检查/扣料和菜单结果槽同时保护，避免只拦扣料却先给产物。
运输/存储需保留 NBT；第三方 ItemHandler、直接 Recipe.matches、自有机器、脚本商店/回购等不因此自动被宣称覆盖。

新增 SaodgApi.isBoundMaterial/mayUseBoundMaterial 和 ScriptBridge 对应只读方法，只作为额外约束，绝不能代替消耗模块原来的权限/价格/保存流程。
脚本未知物品包装不能从 mayUse 返回允许；当前适配只解包实际 ItemStack 或已知 getter 形状，仍需目标 KubeJS 实测。
预览与指南显示绑定/实验模式；协议 5 要求相应客户端的 tooltip、配方显示与界面，拒绝旧 1/2/3/4。

新增纯规则与 BoundMaterialGameTest 只是待执行夹具，包含散列兼容、绑定篡改、合成/缓存选择、村民扣料和普通物品回归。
未构建、未运行、未部署；未审计的其他资产路径、经济采样、实际钱包/机器与多人转移均仍阻止正式发布。

## 普通商店与市场材料限制（0.30 待安装补丁，未运行）

本轮只运行 `tools/compat/generate_compat_patches.py` 生成本工程内的文本补丁，没有构建、启动游戏、检查语法或执行测试。
源目录为只读的本机整合包，所有适配来源散列位于 `compat/patches/SOURCE_MANIFEST.json` 的 material_trade_patches。
新增材料策略脚本 priority 97，先于 assets priority 96 公开约束；桥按原生命周期装配，未加载的必需约束不允许市场新意图。
中文提示集中于 `compat/kubejs/config/sao_dungeon_materials_zh_cn.json`。

钱包合并补丁在原 source 上一次性包含旧 freeze/transaction 与新增材料约束；不能再叠加两个旧补丁或重复注册参与者。
assets 补丁覆盖当前直交易/旧 AH 共享 take/add 与 writeInventory；commerce 补丁限制新 AH/BZ，异常材料订单自动到期时原样保留。
ui-data 补丁在持久意图前按每名实际玩家主背包比较材料单位完整 SNBT 的总量，并比较受保护订单/待领数据；不允许货币化或跨收件人迁移。
合法迷宫区发放仍使用独立保存屏障/钱包所有者参与者，不调用普通 saoWalletCommit 或共享 add 来绕过保护。

现有异常订单和待领保留；当前未提供自动归还/删除命令。已应用旧市场意图、旧回执、市场反向持久互斥以及原市场本身的保存故障仍需独立审计。
`compat/tests/material_policy_test.cjs` 是未执行的策略夹具，假的 Tag/Stack 不覆盖真实 SNBT、Rhino、脚本优先级、源补丁应用、存盘、升级和多人行为。
协议仍为 5，世界主日志 schema 2、迷宫区内容 ruins-dev-7 不变；这些脚本没有提供正式开本许可。

## 外部资产所有者检查（0.31 新增源码，未运行）

ExternalAssetFence 提供只读 CLEAR/BUSY/UNKNOWN 状态，ScriptBridge.externalAssets 注册到当前代际。
BridgeRegistry 在服务端查询一次，随后返回只验证相同注册/代际的检查对象；递归、缺注册、未知/错返回值与回调内重载拒绝继续。
注册过的要求在 beginReload 保留，注册钱包也要求外部检查；默认 KubeJS 存在即要求，SAO_SERVER 始终要求，人物市场回执也使移除 KubeJS 不能自动免除约束。
默认纯独立没有 KubeJS/市场历史时可使用原生事务；配置的独立实验例外不替代正式预设的硬门槛。

RewardService 在预检前持有玩家锁，新的 OFFERED 预检拒绝会释放临时锁；既有持久意图/匹配回执/未知应用仍保留原锁。
RewardService、ItemReturnService、NativeExperienceService 在准备/基线、应用和人物确认到世界 ACK 的边界检查当前代际。
市场/钱包活跃事务期间返回待处理原因，不更改固定奖品/收件人，也不追加猜测发放。

新增资产 fence 脚本 priority -89，桥在 finish 前注册它。owner=market 使用更新的同代钱包 busy 查询和市场查询，owner=none 只适用于没有相关模块的明确独立存档。
市场只读查询来自同作用域 .inc，不用降级 load 结果：两份有效一致数据是 CLEAR 的前提；未完成参与者即使 saved=true 也仍 BUSY。
临时 building/busy 用 finally 结束；新市场提交前比较实际完整主背包和余额基线，以免准备中被回调改写后覆盖。
不会自动修复副本或初始化空账本；新建市场需由原所有者建立可确认的双副本，混合旧意图需要整组核对。

新增私有注册状态 GameTest、原奖励 GameTest 的预检持锁/拒绝释放断言及脚本逻辑夹具均未运行。
只再次运行内容补丁生成器，未构建、未做语法检查、未执行 Node/JUnit/GameTest，也未修改源整合包或部署。
协议 5、世界主日志 schema 2 和 ruins-dev-7 不变；真实生命周期、重启/断电、多人及市场原有持久化故障仍待验收。

## 守门者移动与组合动作（0.32 新增源码，未运行）

SentinelCombatService 接管预警/命中/移动/恢复，EncounterService 继续拥有阈值、封印、守卫及确认死亡。没有从原生 SAO Boss 继承楼层/奖励行为。
SentinelCadence 定义顺序与恢复，SentinelCharge 只允许连续 server tick 的有限距离；错过 tick 取消，重复调用同 tick 不重复移动。
每条冲锋保留固定目标、原点、方向、上限与各成员的一次尝试；实际移动不沿客户端坐标，不追踪目标或重放旧动作。

boss JSON schema 2 要求 cadence={charge_ticks,second_charges,chain_recovery_ticks,final_window_ticks,targeted_slam}。
当前为 12/2/35/90/true；原 30 tick 预警、6 格距离和 1.5 格半宽保留，速度不允许超过每 tick 1 格。
第一阶段劈砍/冲击；第二阶段劈砍/冲击/冲锋/冲锋，链内恢复 35，其他恢复 80；最终阶段劈砍/冲击/冲锋，恢复 60/60/90。
定点冲击在起手固定目标脚下；旧 schema 1 仍用单冲锋/首领自身中心冲击默认，但移动也走新的逐 tick 安全路径，不再瞬移整段。

起手只选择合法可见成员，初始粒子发送至少成功一名成员才激活动作。点数上限 24/观众，5 tick 刷新，声音/提示定向发送。
预警后的源锚点位移超过 .25 格取消；原生冻结仅接受既有来源绑定。阶段改变、实体替换或无人可战斗取消，不补打错过的预警/冲锋。
安全路径先按 .25 格限定上限，再每 tick 重检全身位的房间/实例边界、已加载区块、落脚和碰撞。伤害还有独立房间路径/碰撞视线与本局身份检查。
每条冲锋每人只尝试一次原生 mobAttack，不给额外伤害倍率/强控，也不手动增加伤害贡献；原事件管线仍决定实际降血与濒死。
首领无论 NoAI 如何改变都不退回原版 Zombie.doHurtTarget。移动/休整模型姿态只作表现，管理员攻击诊断每 10 tick 更新内存，未引入额外逐 tick 写盘。
自有守门者基础击退抗性 1 且不可身体挤推，防止普通近战/贴身推挤永久取消预警；普通敌人与玩家抗性保持原值，原生授权的冻结或直接位移仍按原管线判断。

协议升级 6（旧 1～5 拒绝）、内置内容 ruins-dev-8 / ruin-sentinel-2；世界主日志 schema 2、奖励格式及房间模板不变。
模板生成脚本只更新源代码，本轮没有执行它。新增纯时序/几何规则测试、实体/定义 GameTest 及握手变更均只写入未运行；没有构建/语法检查/游戏启动。
源定义、模型、所有实际命中/可见性、冻结合法性、1～4 人、两队、重启/保存与性能/平衡仍待统一验收。

## 地标与协作铭文秘密（0.33 开发时记录；基础验证见文首）

SecretProgress 是纯 Java 的固定名单/共享线索/一次发现状态；SecretService 负责真实玩家、活动实例、定义身份、发现房间、6 格与方块视线检查。
EncounterService 的公共方块交互也补充实际在线对象/成员/已发现房间检查。没有客户端提交秘密 index、答案、奖励或世界坐标的专用新请求。
限频内对已知机关的重复/副手交互仍消费为已处理，避免掉回普通磁石指南针/物品使用；不推进状态或刷证明。
cache 可直接调查，提示是可选项；inscription 需本队一名成员真实读取金纹黑石。只读不记参与，确认发现后才给首次解读者和发现者记录同一 secret:room:index 证据；已解读后的重复阅读不算推进。
cache 的可选提示读者不因此获得协助证明。所有实际贡献仍使用现有参与 schema 2/资格时长，没有新伤害比例、分数或经济产出。

房间 schema 3 要求 secret_scenes 完整覆盖 secrets：index、kind(cache/inscription)、clue 三整数、text 翻译键。
每房最多 32 个、index 唯一且在界内；新标记/头部净空/已有谜题/光路/控制/落点不重叠，实际模板须对应 gilded_blackstone 和 lodestone。
schema 1/2 保留原直接秘密，新字段不能混入旧 schema；活动局持有旧完整快照，新加载场景不会移动旧局的目标或重判旧资格。

生成器已执行，22 个秘密结构分片改为海晶灯、青苔、封蜡铜砖或断墙地标，并配置不同角落；金纹石碑清楚提示观察目标。
谜题地标在光路板之外，稀疏房间只有第一个已占用分片拥有该逻辑秘密；整体仍是 28 个逻辑房间、41 个分片。
试炼/标准/精锐秘密总数 6/11/13，标准至少 4 个精英/谜题槽位的铭文目标，不重分配原探索分或调整目标时间。

读取线索仅保留本局运行时状态，断线重连可继续；世界重启仍中止未完成实例，不冒充恢复任意进行中的阅读。
先把共享发现/贡献写检查点，再改变已知磁石表现。异常替换不覆盖或删物，不给玩家背包发物品；重复发现也不反复产生证明。
当前房间页只增加总数/发现数，注视提示基于服务端实际射线，不输出隐藏位置、未读文本或读者列表。
协议 7 要求相应中文内容/界面，拒绝旧 1～6；世界主日志 schema 2、秘密键与奖励格式不变，内容版本 ruins-dev-9。

本轮只运行内容生成器。SecretProgressTest、SecretSceneGameTest 和修改后的实局/握手夹具均未执行；没有构建、语法检查或启动游戏。
实际读碑/观察/点击、四旋转可达性、联机分工/去重、保存故障、视觉、GUI 和性能仍需内容完成后统一验收。

## 非成功战绩复盘（0.34）

`RunReview` 为纯 Java 的冻结记录；`RunReviewCodec` 使用独立 schema 1，严格校验字段、类型、名单和完成数。
`RunReviewLedger` 附在世界主日志的可选 `run_reviews` 列表，主 schema 仍为 2，不修改奖励/成长格式。
共享检查点确认后才建立个人查询索引；每局一条，重复终止不覆盖，不把失败补成成功。
新成功战绩只增加可选 `history_sequence` 排序字段，仍由原成功账本管理；旧成功记录继续显示，旧失败不追溯补写。

挑战失败、系统中止与主动结束分开显示，玩家只取得自己的参与投影与本局完成统计，不取得其他成员档案、隐藏位置或原始诊断。
非成功记录没有分数、评级、成功宝箱或通关凭证；不会推进难度解锁。
重启沿用原中止/回程/清理策略，无布局快照时显示统计未知，不重新生成并猜测旧完成数。
旧参与版本 1 的非负计数保持原值，信息归档不因新增上限阻止本来可读的旧局回程。

复盘容量 10000，新开局预留最坏非成功归档空间，已有记录不自动淘汰；不能通过删历史解锁重复奖励。
两端要求协议 8，拒绝旧 1～7；房间 ruins-dev-9、首领定义、评分公式和经济行为保持。
旧二进制不具备新复盘的索引与容量预约，回退需要停服并恢复一致备份，不承诺跨版本热回退。

81 项 JUnit、37 项隔离 Forge GameTest 已通过，包含实际失败/中止/退出投影、原文件回读、字段注入和重复回调检查。
不把私有日志回读当作真实进程崩溃恢复；客户端视觉、混合旧存档/强制中断、多客户端及目标整合包仍待验证，正式预设保持阻断。

独立 packTest JAR 调用自有实体继承的 Minecraft 方法时，应使用已映射的原版静态接收类型，或另行验证完整继承重混淆配置；不可只以开发环境编译成功为依据。实际案例与原生注册结果见[发布时序验证](validation/SPAWN_PUBLICATION_2026-10-28.md)。

## 可选完整副本耐久夹具

`saodg_endurance` 不在默认命名空间中。使用全新的独立源码导出和 `gameTestServer-endurance-*` 运行目录，执行：

```powershell
.\gradlew.bat runGameTestServer -x downloadAssets -PgameTestNamespaces=saodg_endurance -PgameTestRunDirectory=run/gameTestServer-endurance-<unique-id> --offline --console=plain
```

该夹具复用实局战斗驱动，先用三种谜题的种子，再补足 50 个不同种子的完整试炼通关；每局在场外实际领取基础材料、重复领取检查去重，最后各执行一次必要敌人消失中止和确认死亡失败。每次生产清理后检查原背包/钱包、回程、FREE 槽位、放置/清理票据计数、登记敌人与成员/实体/重连索引、房间运行状态，并逐局记录日志。未领取的个人宝箱和成功历史属于有意持久化数据，不作为运行状态泄漏删除。

这是独立 Forge 服务端的受控 PlayerList 人物检查，不等同于目标整合包、真实双队联机、脚本闭包或基线性能验收。当前源码增加夹具，运行结果另见验证记录；不据此修改正式入场门禁。只改测试源集，不需要重启当前开发客户端。

## 房间间隔与中间门（0.41.14）

模板坐标保持每格 48，运行时网格间距为 49；每个相邻模板外墙之间新增一格有地板、侧墙和顶板的短连接。实际钥匙门只放在中间新增层，两边原墙面开口；未用出口仍用石砖封墙，支路自由通行，多格房内部连接不设门。封印大厅仍通过既有室内传送门去独立首领房，没有新增步行走廊。地图、标记、开门射线与出口指引统一使用物理坐标。

新实例和预览清理清单显式保存 `stride=49`，无该字段的旧清单按 48 读取，非法值拒绝。旧局重启后仍按既有中止/回程/清理流程处理，清理范围不按新间距猜测。世界日志 writer schema 3（读取 1/2/3），预览 schema 2（读取 1/2）；旧二进制无法安全处理新间距，回退须停服恢复一致备份。协议 19、内容 ruins-dev-20，新间距只影响新生成。

定向夹具 `saodg_spacing` 检查新旧清单读写、未知间距拒绝、两种实际清理范围及范围外方块保留；完整 `saodg_combat` 驱动同时检查中央唯一门层、多格内部连接、实际锁门/开门碰撞和后续通关清理。测试结果见单独验证记录，不能只以编译成功宣称通过。

现有 112 个模板/旋转放置、碰撞遍历及交互射线夹具移至 `saodg_traversal` 命名空间，可单独选择；默认套件仍包含它。清理范围与遍历单元统一按新间距处理，模板中的旋转坐标仍为 48。

## 首领区占地修正（0.41.14.1）

49 格间距下，旧预留单元 (10,2) 的首领房会超出文档 512×512 的占地限制。新局改放 (9,2)，首领模板实际 x=441～488，含预留清理边缘至 489；与 6×6 探索区仍有空隔，保持只通过封印大厅传送门进入。历史 (10,2) 的 48/49 格清单继续按其原位置读取、回收，不迁移已写世界。世界日志 schema 3、协议 19 均不变，内容版本 ruins-dev-21。

独立 `saodg_boss_arena` 命名空间可单独检查生成写入的实际占地、传送边与石砖封墙、旧位置清单回读；默认套件仍包含该现有夹具。

## 生成中断的独立恢复夹具

`tools/verification/verify_process_recovery.py --java-home D:/Java/jdk-17 --checkpoint generation` 在全新专用世界运行两个进程：实际放置到剩余写入不超过一半、仍为 GENERATING/RESERVED、人物尚未入场时，确认实例/人物/部分结构保存后执行 `Runtime.halt(73)`；第二进程重登同一人物，检查原模式/库存/钱包、一次重启中止、无成功奖励、全部持久区域及连接清空、FREE 槽位与回程/票据释放。不会在默认测试中运行，也不使用外部杀进程命令。运行器现在遵循显式传入的 `GRADLE_USER_HOME`，独立 Git 导出可复用根缓存；无图形测试跳过 downloadAssets。

这是已确认保存边界后的 JVM 硬退出，不是任意文件写入中断或系统断电。三种 checkpoint 使用不同新目录，不能覆盖/重用旧实验世界。
