# 原生恢复、月光结晶与 0.41.34

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

后续：既有第二队回程/生产清理和四人物完整双队主线回归已通过，原隔离记录与未知物品 NBT 完整保留。[后续运行、失败保留及范围](NATIVE_DUAL_RETAINED_0.41.34_2026-10-29.md)。以下现场描述为各次检查当时的状态。

## 上次中断的恢复已通过

测试夹具提交 `831573740730`，独立导出 `.gradle/native-dual-fixture-831573740730-bce60152` 执行 `packTestJar --offline --console=plain -x downloadMCMeta` 成功，15 秒。附加包 SHA256 `8bd3bc47fd03e3a2d5d9afdba1a60f7c76d30e94e720aab97cd9a95f442ce4ed`，生产模组仍为 0.41.33 / `0167436130aa956398bae9cf14b1c375c959597c2d3342bb0ea26b255680de84`。

只在已授权的私有目录 `run/pack-acceptance-20261028-081137-fd148a65` 启动 PID 24940，127.0.0.1:25579，入口与奖励磁盘开关未改。完整运行前世界、配置和旧包备份于 `validation-history/native-dual-recovery-8315737-7f16daf4`。先运行 `saodg.packNativeDualRecoveryAcceptance=true`，成功后才允许同进程的双队夹具开始。

生产恢复读取旧局 `df65c463-3a47-4083-9d93-135091f73606`，原阶段 BOSS_ACTIVE、28 个登记实体、2 条回程标记。实际登录四个上轮新建测试人物，处理回程；库存/末影箱、玩家持久迷宫区字段（除活动局/回程标记）、钱包余额保持，人物原生 XP 分别 0、440、0、320，均无待处理经验且没有重复发放。玩家回程保存读回成功；生产清理后 `runs/lobbies/pendingReturns/tickets=0`，全部槽位 FREE。没有手改或删除旧局日志。此为一次已知场景恢复证据，不代表所有崩溃窗口或所有资产字段均通过。

报告 `logs/native-dual-recovery-probe-c2bcfa55-3a48-45c4-9a43-cea2a056a891.json`，`passed=true`，SHA256 `2f890e5daf5873f87069715b9b4166de27070839b02227c44bb1531fe4d23457`。恢复阶段连接驱动 1080 次、保活回复 0 次（阶段较短），不能以此证明长时保活修复。

## 新双队运行遇到未知掉落隔离

同进程开始的新两局均完成 832012 次放置、215 个生成 tick、176 张票据，槽位分别 0、1。第一队通关进入清理时，`CleanupJob` 检测未知实体 `5807e079-af9f-4057-92de-000f4bfec4c6`，按原保护规则隔离第一局 `f99ebe03-0e35-4e73-822a-063b6b01c318` / 槽位 0；第二局 `ba19b52d-c38c-44bd-a024-51fcddee274d` 仍留在场内。没有最终双队报告，因此不标为双队通过。

通过运行器的停止请求正常发送只读状态/metrics 和 `stop`，进程退出 0、端口关闭、JFR 正常落盘，附加包已归档。当前世界仍保留隔离局、未知物品和第二队回程状态；这次正常停服不等于这些状态已清理。

- 控制台 `logs/pack-native-dual-recovery-8315737-20261029.log`，SHA256 `7bf588326994243d0106f0a8eff4f56d53dff33a0c99f8836c71d2f1e70e28bb`。
- JFR `logs/native-dual-recovery-8315737-20261029.jfr`，SHA256 `ed00240d81aff00575db6f81c3fed062529a704689b406dcfb3894f28b224eac`；含恢复、生成及隔离等待，不用于宣称两队性能达标。
- 保全 `logs/native-dual-recovery-8315737-preservation-20261029.json`：937 份受保护文件中 919 份保持、2 份 properties 仅时间注释变化，预先允许四个上轮测试人物的 16 份文件因恢复登录/保存更新；其余 249 份人物相关文件保持，没有意外变更。`passed=true` 明确只对应恢复报告，`dual_trial_completed=false`。

停服后只读解析实例实体区块，未知对象为 `minecraft:item`，物品 `mod_1cab0b39:moonlight_crystal` ×1，位置约 (226.43,66,80.14)，没有 Owner/Thrower 或 SAODG 标记。证据 `logs/native-dual-foreign-entity-5807e079-20261029.json`，SHA256 `18f643c0526017200e14e9046fb186486ee51fdd885d9c73a870e8fe01ec7aee`。未删除、改写或猜测归属发放此物品。

本轮新人物：`dg_dual_a0`/`dc0d6305-a9e1-437d-8eac-9d14d3b7fa89`、`dg_dual_a1`/`2c54cead-ee69-4ff4-8d12-648871da25d6`、`dg_dual_b0`/`e9e995cc-fd3b-4469-896f-c66c824beead`、`dg_dual_b1`/`3bd04084-0a5c-48de-9718-1d6f8c301b72`。原恢复夹具固定匹配上轮四人物/两回程标记，不能直接当作当前现场恢复工具重跑。

## 0.41.34 的限定修复

只读检查实际安装 r234 JAR 的 `cn.blockforge.generated.mod1cab0b39.MoonlightCrystalDrops.onDeath` 字节码：它在死亡回调内直接 `addFreshEntity(ItemEntity)`，不经过普通 `LivingDropsEvent`；原版夜间生物概率为 0.003。这解释了结晶与清理保护的冲突。完整类 SHA256 `cebc0fba735c981e420fd3b081a8e150906e03bc17c34a08910f7159a7eafbd8`，只读输出 `.gradle/moonlight-crystal-drops-javap.txt`。

修复提交 `9e3ddc4e979389cfb5e690d5ba634bce1e16924b` 新增该类的精确散列匹配与可选注入：仅跳过已登记且实际身体匹配的副本敌人的额外结晶回调。死亡事件、原生 XP、普通世界与未登记实体不改，既有物品和未知资产保护保持。管理员诊断新增 `moonlight-drops`。详细政策见 [集成契约](../INTEGRATION_SPEC.md)。

独立导出 `.gradle/source-release-9e3ddc4e9793-20261029-093142-0994c2e0` 打包成功，41 个结构、496 个中文键，beta 排除；未运行 JUnit。随后只运行 `runGameTestServer --offline --console=plain -x downloadAssets -x downloadMCMeta -PgameTestNamespaces=saodg_native_drop -PgameTestRunDirectory=run/gameTestServer-native-drop-04134`，1 项实际实体作用域 GameTest 通过，Gradle 41 秒正常退出：必杀/普通登记目标命中，伪造 NBT、同 UUID 非当前身体、其他世界和冻结原版替代策略不匹配均不命中；事件不被取消，也不授予死亡、经验或房间完成事实。

日志 `logs/native-drop-04134-20261029.log`，SHA256 `5cd09891fb6d0f071c1cf9f957e6278fde3f1dbab71babc6dbf566223f3f6627`。此测试运行于独立 Forge，只证明作用域逻辑；实际 r234 注入由下方确定性回调检查补充。

开发包 `build/verified/0.41.34-dev-9e3ddc4e9793-20261029-093142-0994c2e0/saodg-0.41.34-dev.jar`，SHA256 `7f2fda3eace26417750cd0d62d9ef52f3d51690ea5a896cf6ed4269231727286`。未更新用户客户端或原服；下次定向检查仅将私有服升级至该包。

## 实际 r234 确定性回调检查通过

夹具提交 `13e8ae66bf34`，独立导出 `.gradle/native-dual-fixture-13e8ae66bf34-6532035a` 的 `packTestJar --offline --console=plain -x downloadMCMeta` 编译通过，15 秒。仅在原授权私有服运行 PID 20064，磁盘入口/奖励四个开关仍为 false。运行前完整备份 `validation-history/native-crystal-13e8ae6-081fa163`，只将原 0.41.33 运行包更换为上述 0.41.34。

夹具反射调用实际已变换的 `MoonlightCrystalDrops.onDeath`，显式构造死亡事件，固定随机种子 5156 触发普通僵尸的 0.003 分支。普通世界、带伪造副本 NBT 的未登记僵尸产生一枚结晶；新测试人物 `dg_crystal` / `a69b519d-a4b5-4f16-be83-fa7506830b8a` 正常拾取新物品 `717b89dc-b59c-4dba-9cca-a494c6cc38b8`，玩家保存后读回库存增量为一。对现存精确登记的实际副本敌人 `c1efef37-7f7a-4eac-8b05-3b3faa891b65` 使用同一种子和回调，没有额外掉落；事件未取消，目标存活/血量、确认死亡与经验链接保持。实际注入状态为 `HOOK_OBSERVED`。

原未知结晶 `5807e079-af9f-4057-92de-000f4bfec4c6` 的身体和物品栈保持，槽位 0 仍 QUARANTINED。恢复原强制加载标记，没有删除或分配原物品。停服前状态仍为两局、两条回程标记、46 张票据，槽位 1 为 CLEANING；不能宣称已清空现场或完成双队通关。正例产生的新结晶保存在新测试人物文件中，不冒充原未知物品的处理。

报告 `logs/native-crystal-drop-probe-95806c29-6c65-41a4-85e2-ad7acc975c3b.json`，`passed=true`，SHA256 `0c7f270d9c04e0fd5d699bdf00743d0081c0dd628a71d4ec4e576ad9c4f64da0`。范围是实际原生注入回调的正反例，不是真实击杀全事件链、长连接或完整双队验收。

- 控制台 `logs/pack-native-crystal-13e8ae6-20261029.log`，SHA256 `f4a5bc5768fba1d2ec1c25a13c9fbde93f2cc7ae2499b20112bf5195688b1b40`；正常 stop，进程退出 0，端口关闭。
- JFR `logs/native-crystal-13e8ae6-20261029.jfr`，SHA256 `fb3c120d1c753bf55a8d135ae78fd60cad51c561dfeb37ee07f391cead342d68`，仅作运行记录，不作性能达标证据。
- 保全 `logs/native-crystal-13e8ae6-preservation-20261029.json`：953 份受保护文件中 950 份字节保持、2 份 properties 仅注释变化，另 1 份为预先允许替换的旧运行包；281 份原有人物文件保持，无意外变更，配置语义保持。
- 测试附加包已移至备份目录 `fixture-native-crystal.jar`，SHA256 `3daace16ad774da686ba57e7ee5a705db13149b3d468b8c37d4a8008c1a7993f`。私有服当前已安装 0.41.34 且停服，用户客户端/原服保持。

后续仍需保全处理原隔离资产、完成第二队回程和完整双队回归。双队夹具提交 `55bd7ccf9f4f` 补充隔离快速失败：只中止非隔离局并等待其生产清理，保留隔离局及资产，在失败报告记录遗留局/槽位/回程数；不自动重试隔离清理或释放槽位。独立导出 `.gradle/native-dual-fixture-55bd7ccf9f4f-d59d3aa7` 的 `packTestJar --offline --console=plain -x downloadMCMeta` 编译/重混淆成功，15 秒，未重跑 JUnit、GameTest 或原生服。日志 `logs/native-dual-quarantine-fixture-20261029.log`，SHA256 `419581483290f0183d48263982a5976c1aaedfd348ff9d8574d4a7fc10baa169`；附加包 SHA256 `56811ca4b06bb7daf6f7bdc91258cbeac950740311e01d30757badf0ee65da80`。实际隔离路径仍待复验，未部署此夹具。
