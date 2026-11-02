# 副本经验与中央奖励箱（2026-10-31）

后续更新：用户要求的三倍实体奖励箱见 [实体箱记录](REWARD_CHEST_ENTITY_2026-10-31.md)。本文的方块箱实现、截图和协议说明属于该调整之前的快照，经验规则仍适用。

本轮仅修改 SAODG；保留工作区中其他任务的已有改动，没有安装到客户端/服务器整合包，没有更改存档准入、奖励开关或正式经济验收状态。

## 当前规则

| 难度 | SAO 通关基础经验 | SAODG 副本经验 |
| --- | --- | --- |
| 试炼 | 90–180 | 60–120 |
| 标准 | 180–360 | 120–240 |
| 精英 | 360–720 | 210–420 |

范围对应 0–300 分，采用 `maximum × (300 + score) / 600` 整数取整。通关基础经验额外于既有原生击杀经验，不放大击杀数额，不按队伍人数平分，不随人物等级膨胀，不绑定付费箱档位。SAO 的实际经验规则、曲线、上限与同步仍由原生端口负责。

- 仅奖励启用且已预留原生经验预算的新局产生 SAO 通关经验；独立无 SAO 环境不伪造原生成长。所有现有准入与奖励开关保持，未启用奖励的开发局没有此通关奖励。
- 有效成员沿用成功结果的显式资格：达到原有出勤要求且有有效行动。失败、中止、挂机或出勤不足不产生通关经验。每个合格成员获得完整个人份额。
- 基础物品和副本经验仍经原个人基础奖励事务领取；宝箱仍只允许个人选择一次。既有代币/材料、绑定、钱包、费用和随机掉落语义保持。
- 成功结果先保存 `completion_xp_version=1`、`completion_xp_owner`、`completion_xp_amount` 与原通关资格，然后为每局每人生成稳定 UUID 的独立原生经验请求。结果与请求之间中断时可在启动重读时补建请求；已确认玩家回执不再发奖。原击杀请求的死亡链接校验仍保留，通关请求必须匹配持久成功结果。
- 自动发放要求真实在线、存活、非旁观且可处理资产；离线、容器/物品使用、其他事务或资料未就绪沿用原等待机制。接口不匹配时保留原请求，不直接修改 `SaoProgress.xp`，也不改发原版经验。

## 箱子表现与安全

- 真实房间占地按 49 格运行单元计算中央，支持旋转；高度以作者到达点的地面层为参考。优先同一中央列的安全地面，中央受阻时在半径 6 格内按水平距离寻找安全位置。
- 要求副本维度、本 Boss 房范围、完整上表面支撑、三格空气净空；不覆盖建筑、流体、方块实体或存活实体。没有安全位置时拒绝放置，不挖中央装饰、不跨实例找位置。
- 三档现有箱模保留，增加分档颜色、双层符文光环、旋转刻线、浮动晶点、上浮星芒、出场音效与更强光照。客户端符文环使用有界可见缓存，不生成实体、容器或持续服务端粒子广播；离场卸载清理缓存。
- 原开盖/合盖、个人面板、归途门、两分钟停留和区域清理保持。重入 `begin` 不重复放箱或延长倒计时。

## 修改位置

运行代码：

- `application/CompletionExperiencePlan.java`、`application/InstanceService.java`、`application/NativeExperienceService.java`、`application/ProgressionService.java`、`application/SettlementService.java`。
- `domain/reward/CompletionExperience.java`、`domain/reward/RewardProfile.java`、`infrastructure/persistence/NativeExperienceRecord.java`、`api/NativeExperiencePort.java`。
- `platform/forge/RewardChestScene.java`、`platform/forge/block/RewardChestBlock.java`、`platform/forge/SaodgCommands.java`、`client/RewardChestEffects.java`。
- 中文本地化、两份奖励表的内容版本升为 `*-dev-2`；已存储的旧奖励展开内容和散列不改，不追补没有新字段的历史通关。

验证与说明：新增 `CompletionExperienceTest`、`CompletionRewardsGameTest` 和隔离 `RewardChestScenePreview`，更新 `RewardTest` / `RewardGameTest` 的新局经验预期和 `ExitPortalGameTest` 的中央落点检查；`build.gradle` 仅增加显式场景预览属性。另更新 CHANGELOG、开发说明、内容目录及集成契约；本文不把同文件其他任务的改动算作本轮实现。

## 验证记录

初次定向 JUnit：`test --tests cn.saodg.domain.reward.RewardTest --tests cn.saodg.domain.reward.CompletionExperienceTest`，7 项通过。

服务端 c 轮：`runGameTestServer -x downloadAssets -PgameTestNamespaces=saodg_completion_rewards,saodg_exit -PgameTestRunDirectory=run/gameTestServer-completion-rewards-20261031-c --offline --console=plain`，4/4 必需夹具通过（`build/completion-rewards-gametest-c.log`）。覆盖资格过滤、固定金额/UUID、结果文件重读、未确认结果拒绝、真实在线对象检查、人物保存后未确认的回执恢复与十次重放、物品/副本经验原子领取和恢复、四个朝向的中心/阻挡回退/全阻塞拒绝，以及三个真实 Boss 房中心落点、原建筑保留、归途门与逐人回程。后续增加的维度拒绝和客户端渲染以最终验证为准。

早期失败保留：a 轮 4 项中 `RoomRewardsGameTest` 在安全怪物出生点处失败（锚点 `101,66,220`），其他 3 项通过，日志 `build/completion-rewards-gametest-a.log`。b 轮新增中心夹具起初缺少封印大厅图节点，出现 `No value present`，已修正夹具，c 轮通过。不得把早期失败日志称为全部通过。

## 最终验证与交付

最终命令（JDK 17，Forge 47.4.10）：

```powershell
.\gradlew.bat test --tests cn.saodg.domain.reward.RewardTest --tests cn.saodg.domain.reward.CompletionExperienceTest -I build/completion-rewards-tests.init.gradle --offline --console=plain
.\gradlew.bat build -x test runGameTestServer -x downloadAssets '-PgameTestNamespaces=saodg_completion_rewards,saodg_exit,saodg_room_rewards' -PgameTestRunDirectory=run/gameTestServer-completion-rewards-20261031-final --offline --console=plain
```

结果：**7 项 JUnit，0 失败；5/5 必需 GameTest 通过；构建打包成功**。首个命令的本地 init 脚本只将本次结果写入独立的 `build/test-results/completion-rewards-final`，避免共享旧 `output.bin`；不改测试选择或断言。第二条显式跳过完整 JUnit，仍编译 main / GameTest / packTest、完成打包并执行上述运行套件。最终包括新增维度拒绝、中心放置、恢复与原子领取、三套真实 Boss 房、归途门，以及早期失败的旧 `RoomRewardsGameTest` 的重新运行。客户端类未导致专用服务器加载失败。

日志：`build/completion-rewards-tests-final.log`、`build/completion-rewards-build-final.log`。本次内容快照为 `16dc3bd860f3e7acc87b02d01ee3abfac2b40b81b03b44e9936ae3d8d955b36f`；结果只对应此时共享工作区，不提升整个整合包的生产验收状态。

产物：`build/libs/saodg-0.41.65-dev.jar`，SHA256：`5b4e5a0444daab269d7563d5cc9f14c036ba0225b3af58615339361d1f8de03c`。保留当前工作区版本号，没有创建版本标签、提交、推送或安装到整合包。已打开 JAR 确认新增策略/证书/放置/客户端光环类入包，两份奖励表和中文本地化与源码一致，派生 `en_us` 含中文通关提示，新的运行测试与摄影夹具未入包。检查结果另存 `build/completion-rewards-package-verification.json`。

## 游戏内视觉检查

最终隔离开发客户端执行：

```powershell
.\gradlew.bat runClient -x downloadAssets -PrewardChestScenePreview -PrewardChestSceneWorld=completion-rewards-preview-runes --offline --console=plain
```

成功退出，日志 `build/completion-rewards-client-final.log`。实际生成鎏金王庭、调用同一个生产奖励箱放置方法，使用旁观相机拍摄；两张 PNG 已实际打开检查，中心落点、箱模、双层金色光环、刻线和浮动晶点可见。近景使用珍藏档；普通/精良档仅共用同一渲染路径和不同颜色/晶点数，本轮未逐档截图。截图不证明 SAO 原生经验、钱包支付或真人输入。

- [房间中央远景](images/completion-rewards/reward-chest-center.png)
- [箱子与符文环近景](images/completion-rewards/reward-chest-closeup.png)

预览仅在显式属性下加入 GameTest 源集，默认运行与生产包不带摄影夹具。复制的是已结束的独立 GameTest 存档，只在预览副本设置 `confirmedExperimentalSettings=1`，并复用本地开发客户端 `onboardAccessibility=false` / `pauseOnLostFocus=false` 设置；不打开玩家存档。复跑应另复制一份空闲测试世界并传入新的 `rewardChestSceneWorld`，避免覆盖已放置的预览房。

初轮无截图的证据仍保留于 `build/completion-rewards-client.log` 和 `build/completion-rewards-client-b.log`：新目录的首次引导/实验世界确认阻止自动继续；Windows 截图工具两次超时（`FrameArrived timed out`、`window capture timed out`），没有借用旧画面称为实拍。修正隔离预览设置后先取得实际截图，又因粒子环不够清晰增加客户端几何符文环，最终如上。

## 兼容与未验收

不迁移钱包，不改变 SAO 曲线，不重算已展开的旧奖品，不追溯发放旧战绩。世界主 schema 和网络包没有因本功能变化；成功结果增加可选版本字段，原生经验分片增加受上限约束的通关请求类型。旧模组可能拒绝新类型/数额，不宣称支持回退旧版。奖励表内容快照发生改变，运行中实例仍使用原冻结快照。

隔离 Forge 玩家对象与原生端口替身证明服务端账本和保存边界，不等于目标 SAO/KubeJS 整合包的实际通关奖励验收。真人双客户端、重连/硬重启故障矩阵、原生 SAO 通关跨级/上限及正式经济支付尚未执行。全量默认 JUnit 尚未运行，不声明完整项目测试全绿；统一回归由监督任务在各工作完成后执行。
