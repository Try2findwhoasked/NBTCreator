# 多任务交付后的统一检查（2026-10-31）

历史快照：本记录截至当天约02:57、协议22。后续原生数值取舍、协议23实体奖励箱、继电机追加挑战及符文门效果不在这份快照的验收范围内；当前集成与版本归档见 [Git维护记录](GIT_MAINTENANCE_0.41.65_2026-10-31.md)。以下保留当时实际结果，不追改历史测试结论。

范围：SAODG `0.41.65-dev` / Forge 47.4.10 / Java 17 / 网络协议 22。最初三个任务均已交付后，统一检查共享工作区；随后将同项目中新增并已完成的 NBT 转换工具任务一并纳入。没有撤销已有改动、清理整个 `build/`、修改参考仓库、部署整合包、提交、推送或打标签。

## 交付与修复范围

已接收“检查并注册房间结构”“完善怪物生成与成长曲线”“完善副本经验与奖励箱”的交付。当前运行目录加载 **79 个房间**，内容哈希为 `16dc3bd860f3e7acc87b02d01ee3abfac2b40b81b03b44e9936ae3d8d955b36f`。各自实现、视觉证据和未验证范围仍见相应交付记录。

本轮监督检查发现并修复的是**回归夹具、测试组织和当前文档的错误**；没有为迁就测试放宽生产权限、伤害归属、资产保护、内容加载或奖励防重规则。

| 问题 | 修复 |
| --- | --- |
| 协议夹具仍写死 20 | 从实际协议常量读取，并检查全部旧协议、下一版本及缺少模组的端点仍拒绝；README 与开发说明同步当前版本/协议。 |
| 门口夹具直接使用 48 格模板坐标 | 转为 49 格运行坐标，检查整个物理门面；作者声明的独立首领传送场景由专用夹具覆盖。 |
| 旧秘密点/谜题数量假设失效 | 普通战斗房按实际声明检查，精英和谜题房仍必须有铭文目标；退役检查保留 15 个旧原型移除断言，并明确保留原三种及新增三种谜题。 |
| Boss 重连测试等待默认关闭的脚本攻击 | 仅在该夹具中显式开启并恢复开关，避免超时遗留活动实例、连锁影响后续测试。 |
| 开本夹具仍要求 OP | 验证已准备队长可按现有规则以普通权限开本，不再先创建实例再因错误断言退出。 |
| 完整通关夹具拒绝新弓手/巨兽 | 接受精确支援实体类及已审核的小体型替代，同时核对实际服务器登记和冻结实体类型；不接受任意模组子类。 |
| 双队测试假定第一战斗房有秘密，清房即有可消费钥匙 | 选择实际声明的秘密点；等待实体钥匙的正常拾取/自动拾取使其可用后，再验证独立开门与单次扣除。 |
| 清理夹具与其他生成作业并行，400 tick 上限不适配协作时间片 | 两项清理分别放入独立批次，保留边界/资产/票据断言，使用 4000 tick 有界超时；生产清理预算未改。 |
| 外来资产夹具返回点依赖批次测试场地 | 拆出 `saodg_foreign` 命名空间并加入默认套件，保留独立空模板；返回平台改到测试场地以外，入场前验证安全，失败信息包含实际位置/模式。仍严格验证原位回程、容器及完整内容保留。 |

主要文件：`BaselineGameTest`、`LobbyMembershipGameTest`、`RouteGateGameTest`、`SecretSceneGameTest`、`ReconnectGameTest`、`InstanceGameTest`、`CombatGameTest`、`ConcurrentInstanceGameTest`、`RoomHeightGameTest`、`RoomSpacingGameTest`、`SimpleCombatRetirementTest`；另有 `build.gradle` 默认命名空间、测试空模板、README 和开发说明。

## 实际验证

所有命令均在根目录执行，使用 `D:\Java\jdk-17`，未执行 `clean`。忽略目录中的 init 脚本将输出、编译目标和资源目标分别放入 `build/supervisor_validation`、`build/supervisor_runtime`、`build/supervisor_combat`，并使用独立项目缓存和测试世界。

### JUnit 与打包

```powershell
.\gradlew.bat -I logs/supervisor-isolated.init.gradle --project-cache-dir .gradle/supervisor-validation --offline build --console=plain
.\gradlew.bat -I logs/supervisor-isolated.init.gradle -I logs/supervisor-final-tests.init.gradle --project-cache-dir .gradle/supervisor-validation --offline test --console=plain
.\gradlew.bat -I logs/supervisor-isolated.init.gradle --project-cache-dir .gradle/supervisor-validation --offline build -x test --console=plain
```

- **首次完整 JUnit：166 项，1 失败，2 跳过**。唯一失败是旧谜题数量断言 3，实际为 6。三档各 **10,000 种布局种子**全部通过；试炼/标准/精英对应 XML 用例 `[1] trial`、`[2] standard`、`[3] elite`。完整命令因该断言失败，不能称其为成功构建。日志 `logs/supervisor-full-build-2026-10-31.log`。
- **修正后：163 项，0 失败、0 错误、2 跳过，BUILD SUCCESSFUL**。最终单测 init 脚本明确排除上述三个已通过、输入与实现均未改变的重型参数用例，未减少每档种子数或放宽断言。因此本轮合计覆盖当前 **166 项，其中 164 项实际执行通过、2 项跳过**，这是分批验证结果，不是一次默认 `test` 全绿。日志 `logs/supervisor-junit-final-2026-10-31.log`；最终 XML/HTML 为 `build/supervisor_validation/test-results/supervisor-final/` 和 `build/supervisor_validation/reports/tests/supervisor-final/`。
- 两项跳过均为 `SaoRangedItemsTest` 的可选职业弓二进制检查：本轮未设置外部参考 JAR，不能用跳过证明原生组件兼容。钱包资产范围的 5 项单测在本轮最终结果中通过，不追溯改变历史版本的验证结论。
- 最终 **`build -x test` 成功**，编译当前主代码、GameTest、packTest 并完成重混淆打包；没有将其冒充完整 JUnit 命令。日志 `logs/supervisor-package-final-2026-10-31.log`。

### Forge 运行检查

```powershell
.\gradlew.bat -I logs/supervisor-runtime.init.gradle --project-cache-dir .gradle/supervisor-runtime --offline runGameTestServer -x downloadAssets -PgameTestRunDirectory=run/gameTestSupervisor20261031e --console=plain
.\gradlew.bat -I logs/supervisor-runtime.init.gradle --project-cache-dir .gradle/supervisor-runtime --offline runGameTestServer -x downloadAssets -PgameTestRunDirectory=run/gameTestSupervisor20261031f --console=plain
.\gradlew.bat -I logs/supervisor-combat.init.gradle --project-cache-dir .gradle/supervisor-combat --offline runGameTestServer -x downloadAssets '-PgameTestNamespaces=saodg_population,saodg_miniboss,saodg_completion_rewards,saodg_exit,saodg_room_rewards,saodg_circuit,saodg_sound' -PgameTestRunDirectory=run/gameTestSupervisorFeatures20261031a --console=plain
.\gradlew.bat -I logs/supervisor-combat.init.gradle --project-cache-dir .gradle/supervisor-combat --offline runGameTestServer -x downloadAssets -PgameTestNamespaces=saodg_combat -PgameTestRunDirectory=run/gameTestSupervisorCombat20261031a --console=plain
.\gradlew.bat -I logs/supervisor-runtime.init.gradle --project-cache-dir .gradle/supervisor-runtime --offline runGameTestServer -x downloadAssets '-PgameTestNamespaces=saodg_foreign,saodg_concurrent' -PgameTestRunDirectory=run/gameTestSupervisorIsolation20261031a --console=plain
```

| 范围 | 实际结果 | 日志 |
| --- | --- | --- |
| 默认套件 e 轮 | **67/67 必需测试通过，BUILD SUCCESSFUL** | `logs/supervisor-runtime-e-2026-10-31.log` |
| 返回平台加固后的最终默认 f 轮 | **67/67 必需测试通过，BUILD SUCCESSFUL（7m 3s）** | `logs/supervisor-runtime-f-2026-10-31.log` |
| 新增功能组合 | **11/11 通过**，逐个覆盖 68 个生产战斗房间，并检查经验恢复、防重、中央箱子、归途门、短路及声音范围 | `logs/supervisor-features-2026-10-31.log` |
| 独立完整通关 | **1/1 通过**，六种谜题对应 6 次成功流程及 2 次故障流程，结束 `runs=0`、`pendingReturns=0` | `logs/supervisor-combat-flow-2026-10-31.log` |
| 外来资产与双队隔离 | **2/2 通过**，包括实例清理、槽位复用、旧实体/旧请求失效和资产保留 | `logs/supervisor-isolation-a-2026-10-31.log` |

最终当前默认套件 67 项，加上未列入默认命名空间的新增组合 11 项，共 **78 项不同的必需运行用例通过**。上述独立通关和隔离夹具也属于默认套件，不能将它们重复累加为额外独立用例。f 轮完成后未再修改源码。

前期失败日志按 a/b/c/d 保留，分别出现 10/5/3/3 项失败，包含旧断言、未拾取钥匙及清理时间片的级联问题。另两次临时调试包装运行注册了 0 项测试，已排除，不能作为通过证据。外来容器夹具曾有一次原位返回断言失败；本轮没有修改生产安全回退逻辑，而是加固隔离测试平台并保留严格检查与具体失败上下文。

## 产物与限制

### 后续 NBT 工具交付

已追加审查“规范 NBT 生成与转换工具”的 `tool/structure_world.py`、`tool/nbt_world.py`、测试、示例与存放规范。源世界只读，输出必须是新目录，回导不能写入源世界内部；结构/分片 ID 校验和映射重叠检查保留。

实际执行 `python -m unittest discover -s tool -p 'test_*.py' -v`，**10/10 通过**。再使用 `tool/examples/structure_layout.json` 创建 `build/supervisor_tool_review_20261031/world` 并回导到其同任务下的新 `exports/r01`，用单独的 nbtlib 遍历代码比较原始主体/墙层与回导结果，**39,939 个非空气方块及每层归属全部一致**。日志 `logs/supervisor-nbt-tools-2026-10-31.log`、`logs/supervisor-nbt-world-create-2026-10-31.log`、`logs/supervisor-nbt-world-export-2026-10-31.log`；脚本哈希与比较结果在 `logs/supervisor-nbt-tool-review-2026-10-31.json`。未发现需要额外修改此工具的可复现错误；未验证 Minecraft 实际加载该制作世界。

### 模组开发包

开发 JAR：`build/supervisor_validation/libs/saodg-0.41.65-dev.jar`，3,943,933 字节，SHA256 `a7d00143fea9f0a5833d4fb1afaa4200c52e4de8a6a871f152d3a81760820dad`。包装检查验证新增实现类、refmap、版本、中文默认回退，338 个生产模板文件与源码集合一致，不包含 GameTest、packTest 或本地 beta 模板。84 份房间 JSON 中当前房池引用 79 份，不能把全部入包定义都称为活动房间。检查清单为 `logs/supervisor-package-2026-10-31.json`。

最终源码清单为 `logs/supervisor-final-source-2026-10-31.json`，聚合 SHA256 `9dd9e626ad33faa8c3308428c4963d85cfee979d3e8c7587f187be7a5e5dfd3f`。已核对 `src/main` 相对监督审查快照没有后续变化；最终单测范围与三项重型用例的去重汇总见 `logs/supervisor-junit-summary-2026-10-31.json`。

仍是开发验证：运行中的玩家是隔离 Forge 服务端的测试连接；未执行真人双客户端、实际 SAO/KubeJS 整合包通关、原生经验跨级/上限、完整断电重启故障矩阵或长期性能验收。原 agent 的客户端截图仍是相应源码范围的视觉证据，本轮没有重新进行真人交互或发布验收，也没有开放正式副本。
