# 特殊房替换与三类新谜题：本会话交付

本记录针对共享工作区的定向验证，版本显示为 `0.41.65-dev`；不是新发布标签、默认完整测试套件通过或生产整合包验收声明。最终稳定快照的统一回归由用户指定的监督会话负责。

## 实际结果

- 替换原有入口 1、精英 4、谜题 3，保留这 8 个房间 ID。入口采用用户对比选择的另一会话 B「起誓之门」最终精修 `refined_02`，出生脚位 Y=6、北门 Y=2、仅声明 0 度。
- 其余 10 间按 `minecraft-nbt-modeler` 初稿流程创作、实际查看整体/未剖切入口/完整顶部/主题节点后接入。其中 `elite_hall` 是一个完整 96×42×96 主模型，先密闭和开门，再机械切成四片，不在切面添加分房墙。
- 11 间最终建筑共 14 个占用单元、28 份主体/墙面稀疏 NBT；运行时按 schema 5 合成完整分片。旧 8 间特殊房独占的 11 份完整 NBT 已移除；[删除清单及旧文件哈希](SPECIAL_ROOM_OLD_TEMPLATES_2026-10-31.json)保留追溯证据。
- 增加 `special/balance`、`special/flow`、`special/circuit`；活动房池 79 间，其中普通 63、精英 4、谜题 6、入口/安全/血房各 1、Boss 3。先前精选、旧精修、未选普通房及固定鸟居、符文血房、三套 Boss 的资产保持原样。
- 新房具有中文名称、来源、形状、主题和连接分类。分流归为 `waterworks`，光路归为 `crystal`，符文谜题归为 `runes`；房型仍由定义的 `type` 决定。

完整源目录、模型指纹、定义及 28 份活动层文件哈希见[资产清单](SPECIAL_ROOM_ASSETS_2026-10-31.json)。本会话未选 A 入口保存在 `build/nbt_models/special_rooms_20261031/entrance_01/`，未接入房池。B 的原稿和精修稿均未覆盖。

## 谜题和故障修复

- 砝码配平：三组质量 2/3/5、数量 0～3；服务端判定总质量是否达到公开目标。
- 三池分流：三支路流量 1/2/3，分别选择池编号 0/1/2；服务端判定各池接收量。池体、衡梁等是静态建筑，未实现流体/机械运动模拟。
- 星三角接线：初始跨接 U2–V1、V2–W1、W2–U1；三末端须接同一个 STAR 星点，三个首端彼此分离。四档为原 Δ、断开、星点、自身绕组首端。连通分量判定完成和短路，不能靠普通开关数量完成。
- 短路立即产生爆炸效果并伤害触发者，12 tick 后对仍在本房且可行动的触发者雷击。只作受控伤害和视觉效果，方块不破坏；不对邻房或其他实例玩家施加伤害。
- 短路将本房记为失败，普通复位无效。`completed` 允许离开已处理房间，新增 `failed_puzzles` 区分失败与成功；计分、战报、参与证据不把失败当解谜成功。地图显示失败颜色。重复点击及潜行使用失败复位点不会重复惩罚或把整局中止。
- 用户提出的复位消耗品是后续待办，本次未新增道具。后续扣道具、恢复状态和防重入须共用持久化事务。
- 修复镜面恢复原状态仍留有效参与者的问题；新状态题也仅记录最终有效控制状态的编辑者。
- 刷怪保留 96 次随机散布，再遍历同一半径 6 范围，并回退到其他作者标记；保持标记原 Y、房间范围和实体碰撞约束。修复随机采样遗漏狭窄地面导致中止的情况。
- Windows 正向钱包 fixture 改用 `toRealPath()`，同时单独验证未解析 8.3 别名不可作为可信资产根；生产 `LegacyWalletAssetScope` 防护未放宽。
- 更新已过时的 28 房/41 片/112 朝向测试假设；实际遍历改为 Forge 碰撞形状、0.6×1.8 玩家、连续支撑和半格踏步，并检查每个遭遇的最大整波能容纳七种独立运行怪物类型。

## 实际验证

JDK 17，Forge 47.4.10，Gradle 8.8，使用离线缓存。共享构建曾因其他编译更新导致类缺失，相关失败轮次不计通过。后改用本地 init 脚本将 classes/resources 明确隔离到 `build/special-room-validation`；没有执行整个项目 `clean`。

```powershell
$env:JAVA_HOME = 'D:\Java\jdk-17'
.\gradlew.bat --offline --init-script build/nbt_models/special_rooms_20261031/isolated-build.gradle test --tests 'cn.saodg.domain.puzzle.*' --tests 'cn.saodg.integration.kubejs.LegacyWalletAssetScopeTest' runGameTestServer '-PgameTestNamespaces=saodg_selected,saodg_height,saodg_circuit,saodg_special_runtime' -PgameTestRunDirectory=run/special-rooms-delivery-20261031 --console=plain
```

- `logs/special-rooms-delivery.log`：18 项 JUnit，0 失败/错误/跳过；6 项必需 GameTest 全部通过。
- 其中 69 个带识别信息的建筑、105 个声明朝向通过生产 49 网格计划的封闭与实际碰撞形状检查；3 个难度各 32 个布局通过。
- 本次 11 间建筑的 41 个声明朝向全部实际放置、行走、检查最大整波刷怪空间并清理，票据归零；包含最新炉口凹腔和测绘仪器。
- 短路 fixture 验证实际爆炸/延迟雷击伤害、其他房间队员不受伤、全房方块不变、失败日志回读、不计成功、普通复位拒绝和重复操作幂等；末轮重试补充见下方日志。
- 自定义门高 fixture 使用组合后的当前模板创建独立抬高资源，不再依赖已移除的旧单层 NBT 路径。
- 该轮目录哈希为 `07e0e985965249e5866e885c1c45fdd57e1e4d7a9ecddf8dda9aba71a93dc1bd`。之后三个主题分类和界面文案发生过修正；该哈希仅代表记录中的测试快照。并行奖励等改动也使最终目录需重新回归。

另有 `logs/all-six-puzzles-isolated4-runtime.log`：六种谜题实际完整通关 + 两条故障清理路径通过，末尾 `runs=0,pendingReturns=0`；该轮尚未换最终入口。`logs/special-rooms-final-geometry.log` 的全目录实际遍历完成 115 个朝向，其中整波怪物空间检查通过；该次组合有一项额外入口站位选在家具内而失败，不能把整轮称为全绿，之后已按作者的有效站位修正并通过上述交付轮次。

[碰撞检查记录](SPECIAL_ROOM_COLLISION_2026-10-31.json)与[定向测试摘要](SPECIAL_ROOM_TESTS_2026-10-31.json)保存对应范围。

最终补充命令（仍使用同一 JDK/init 脚本）：

```powershell
.\gradlew.bat --offline --init-script build/nbt_models/special_rooms_20261031/isolated-build.gradle test --tests 'cn.saodg.domain.puzzle.*' --tests 'cn.saodg.integration.kubejs.LegacyWalletAssetScopeTest' runGameTestServer '-PgameTestNamespaces=saodg_circuit,saodg_room_rewards' -PgameTestRunDirectory=run/special-circuit-retry-final-20261031 --console=plain
```

`logs/special-circuit-retry-final.log` 构建成功。该轮补充输入节流窗口之后的再次点击与延迟无重复雷击，并实际执行刷怪随机采样遗漏、其他标记回退和共享钥匙/奖励箱 fixture。短路 fixture 使用独立 batch，避免与其他改变入本开关的 fixture 同时执行。最终保留断开提示的可翻译组件，不在服务器提前转换为本地语言字符串。

## 界面与素材证据

```powershell
.\gradlew.bat --offline --init-script build/nbt_models/special_rooms_20261031/isolated-build.gradle runClient -PpuzzlePreview --console=plain
```

`logs/special-puzzle-ui-final.log` 构建及客户端退出成功。已实际查看 1280×720、GUI scale 2 的六种投影状态截图：

| 状态 | 截图 |
| --- | --- |
| Δ 初始接线 | [图](images/special_rooms_20261031/circuit_delta.png) |
| 部分星点 | [图](images/special_rooms_20261031/circuit_partial.png) |
| 星形完成 | [图](images/special_rooms_20261031/circuit_star.png) |
| 短路失败 | [图](images/special_rooms_20261031/circuit_failed.png) |
| 配平 | [图](images/special_rooms_20261031/balance.png) |
| 分流 | [图](images/special_rooms_20261031/flow.png) |

这些是真实客户端渲染的公开投影 fixture，没有连接服务器或导入存档；不能代替真实多人或建筑光照验收。建筑的程序预览、坐标、密闭记录、分层重建及逐件 `design_review.json` 在 `build/nbt_models/special_rooms_20261031/`；B 入口证据在 `build/nbt_models/sao_spawn_oath_1x1_20261031/refined_02/`。

## 本任务文件与统一回归边界

- 规则：`domain/puzzle/PuzzleProgress.java`、新增 `DeltaStarWiring.java`。
- 运行接入：`application/EncounterService.java`、`RoomInteractionService.java`、`InstanceService.java`；`infrastructure/content/ContentCatalog.java`、`DungeonContent.java`；`infrastructure/persistence/RunRecord.java`；`platform/forge/RoomSpawnPlacement.java`、`SaodgNetwork.java`（协议 22）、`UiSyncService.java`。这些共享文件含其他会话的局部修改，本报告只负责上述房间/谜题/失败计分改动。
- 客户端：`client/DungeonScreen.java` 的状态面板/接线图/失败地图色、`assets/saodg/lang/zh_cn.json` 的本任务文本；新增 `src/gameTest/java/cn/saodg/client/PuzzlePreview.java` 和 `build.gradle` 的可选 `puzzlePreview` 参数。
- 资源：`rooms/ruins/{entrance_01,elite_01,elite_02,elite_03,elite_hall,puzzle_01,puzzle_02,puzzle_03}.json`、`rooms/special/{balance,flow,circuit}.json`、`structures/special/**` 的 28 层 NBT、活动 `dungeons/ruins_01.json` 的 3 个新引用；删除清单见前。
- Fixture：新增 `CircuitFailureGameTest`、`SpecialRoomRuntimeGameTest` 及两个命名空间的 empty 模板；修改 `CombatGameTest`、`ProcessRecoveryGameTest`、`SelectedRoomsGameTest`、`RoomTraversalGameTest`、`RoomHeightGameTest`、`RoomRewardsGameTest`、`RoomInteractionGameTest`、`InstanceGameTest`、`LayeredRoomGameTest`；新增两个谜题单测文件，修正钱包 fixture。
- 文档：本记录、相关资产/测试/碰撞/删除清单、`SPECIAL_ROOM_REPLACEMENT_PLAN.md`、`CONTENT_CATALOG.md` 与 `ROOM_BUILDING_GUIDE.md` 的本任务段落。未把源码生成器、世界、日志或 JAR 纳入发布提交。

默认完整 JUnit、默认完整 GameTest、最新并行修改的联合快照与打包发布未由本会话宣告通过；这些交由监督会话执行。新增的目录计数/部件引用、房池优先级、全六题场景 fixture 已编译，`saodg`/`saodg_layers` 等更广命名空间需由统一回归执行。没有真人双客户端、原生 SAO/灾变整合包、实际房间光照或新增失败字段专门的崩溃恢复验收。
