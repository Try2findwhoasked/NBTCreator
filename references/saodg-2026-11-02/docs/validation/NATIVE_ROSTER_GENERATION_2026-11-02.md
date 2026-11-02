# 原生怪物优先、显示指令与生成优化

2026-11-02。Minecraft 1.20.1 / NeoForge 47.1.106 / Java 17，产物版本 `0.5.4-neoforge-dev`。在工作区原有难度、准备和 JSON 配置修改之上继续；保留其他未提交修改。

## 行为

- AUTO 模式在现有 SAO + Cataclysm 原生适配通过核验时，只抽取对应角色的原生怪：普通池与小首领池分开，最终 Boss 不参与随机。普通怪不再被自制弓手、重装兵或巨像挤占。JSON 可按已批准实体 ID 调权重和属性。
- 默认四档 JSON 按阶段重新配置原生权重。已有 JSON 文件不覆盖；即使旧池主要包含自制怪，原生模式也会回退既有原生池。关闭原生适配或缺少依赖时过滤原生条目，使用 AUTO 后备路线；固定类型 / CONSTRUCTS 仍优先。
- 实际检查客户端 `SAO OATH-NeoForge对比/mods` 的 SAO r234 NeoForge 与灾变 3.31 JAR，现有适配涉及的 `SaoEvents`、`SaoMonster`、Draugr、Royal Draugr、Prowler、追踪导弹类均匹配源码固定哈希。不放开任意实体工厂，不修改登记、出生装备和实例隔离边界。这是静态核验，不是整合包原生战斗实测。
- 新增客户端指令 `/saodg display`、`/saodg config display`，直接打开本机 HUD 设置，无需管理员权限。服务端规则仍用 `/saodg admin config`。核对了当前 NeoForge 的 `ClientCommandHandler.mergeServerCommands` 字节码，客户端子命令通过加载器的合并机制加入，不替换服务端队伍、开局等指令。

## 生成优化

1. 每次生成只为每模板/旋转编译一次形状、门口、排序几何与入口映射，供全部候选共享。保留原字符串排序规则、搜索上限、优先级与回溯规则。
2. 建筑计划复用每房原点和一次坐标旋转；用 long 键按区块归集检查点，避免逐方块分配 ChunkPos，并使检查顺序匹配预加载顺序。不会跨资源快照保留 NBT/世界数据缓存。
3. 预加载后续区块时检查已经加载、实体 IO 就绪的区块；完整异物预检依然在任何方块写入前完成。未预加载区块不能绕过每 tick 加载预算。保留全部最终空气位置的检查、最终状态去重、流体最后写入、碰撞及外来实体检查。
4. generation plan 日志分开记录 `layoutMs` 和 `preparationMs`，入场日志继续给出分 tick 放置的总 generationTicks。

## 同进程布局对照

`LayoutGenerationBenchmarkTest` 每档 16 个实际内容种子，并检查资源池反转不改变结果。通过临时 Gradle init 脚本，将 git HEAD 的旧生成器编译成忽略目录中的对照类；在同一个测试 JVM 中逐个断言新旧 Layout 完全相等，64 个全部通过。临时对照类不打入模组，也不写入生产源码。

单位毫秒，以下是这台机器的小样本观测，不是完整建筑生成或多人实战的加速比例。P95 使用 16 个样本的最近秩上界（最大值），未设机器速度断言。

| 难度 | 旧均值 | 新均值 | 旧 P95 | 新 P95 |
|---|---:|---:|---:|---:|
| trial | 9.33 | 9.03 | 21.00 | 39.95 |
| standard | 8.24 | 6.26 | 26.90 | 18.34 |
| elite | 212.71 | 132.70 | 693.36 | 430.62 |
| extreme | 196.53 | 42.00 | 681.97 | 120.49 |

## 验证

- JUnit：遭遇、进度、奖励与布局基准共 41 项，全部通过，无跳过。含原生普通/小首领权重池分离、无原生依赖时不选不存在实体、旧配置后备、快照可读性等。
- Python 共享工具测试 35 项通过。
- 生产内容审计保留 80 个活动房间、5 个非活动功能定义、340 个引用模板，无错误。
- 最终独立新世界 `run/nativeGenerationValidation_20261102_grouped` 的 13 个范围运行测试全部通过，命名空间为 `saodg_config,saodg_generation_opt,saodg_foreign,saodg_boss_arena`。
- 实际生成夹具：原始写入 1,745,286、检查点 1,744,386、最终非空气写入 914,818，在 587 个服务 tick 完成；通过原有 `<600` 断言。默认 2048 方块/tick 的吞吐仍限制大型建筑的总时间，不能把布局均值改善称为总生成时间改善相同比例。
- 外来内容拒绝、完整最终空气预检、最终写入去重、角色属性/箭矢、纪念品、Boss 区域隔离等范围测试通过。`git diff --check` 通过。
- `build -x test runGameTestServer` 最终成功，随后相关过滤 JUnit 41 项单独成功。JAR ZIP 完整性检查通过，包含更新后的原生权重 JSON、客户端指令类和生成器。

产物：`build/libs/saodg-0.5.4-neoforge-dev.jar`，4,102,295 字节；SHA-256 `7a565671d0621103032302ed4e0ca9dea1f0a741d41f98de205270b2d72d185f`。

本次没有运行默认未过滤全套 JUnit；构建先使用以上过滤测试，最终打包使用 `build -x test`，不能称全套构建测试通过。首次在游戏占用约 7.7 GB 时遇到 Windows 提交额度不足（错误 1455），编译/测试 JVM 内存分配失败；资源恢复后以单 worker 和较低 Gradle 堆重新验证。中间一次旧测试世界的运行测试中，生成夹具超过原有 600 个服务 tick 断言；随后补充检查/加载流水线并在新世界复测得到 605 tick，仍未通过；再将检查点按预加载区块顺序分组，最终新世界为 587 tick 并通过。两次都没有放宽断言，也没有提高每 tick 方块预算。

日志：`logs/native-generation-focused.log`、`logs/native-generation-validation.log`、`logs/native-generation-final.log`、`logs/native-generation-python.log`；最终结果为 `logs/native-generation-final-grouped.log`、`logs/native-generation-unit-final.log`。上述同进程布局对照 JSON 归档为 `logs/layout_generation_same_process.json`，常规基准输出为 `build/reports/layout_generation_benchmark.json`。运行测试仍为独立开发环境；客户端指令窗口、真实模组技能、多客户端与端到端生成耗时需整合包验收。没有部署至用户客户端/服务器，也没有修改游戏配置或系统分页文件。

使用说明：[DIFFICULTY_JSON.md](../DIFFICULTY_JSON.md)。
