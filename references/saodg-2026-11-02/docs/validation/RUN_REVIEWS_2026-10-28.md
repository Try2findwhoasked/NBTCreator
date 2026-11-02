# 非成功复盘与源码完整性验证

2026-10-28，Java 17 / Forge 47.4.10 / ForgeGradle 6.0.54 / Gradle 8.8，源码 `0.34.0-dev`、协议 8、内容 `ruins-dev-9`。
本轮在 `8f28905` 的复盘实现后补齐源码版本记录与兼容计数，并实际执行以下检查。正式 `SAO_SERVER` 仍阻断，没有部署或推送。

## 实际行为

挑战失败、系统中止、主动结束分别归档。复盘包含终止时的清房/谜题/秘密/已探索统计、用时、阵亡和个人参与；缺布局快照明确标记未知。
索引只在共享世界检查点确认后可查询。每局固定一份，重复回调不能覆盖；非成员看不到记录，投影不含他人档案或诊断原文。
独立 `run_reviews` schema 1 附在原主 schema 2 内；非成功记录没有评分、评级、奖励计划或合格通关凭证，不产生奖励/成功事实。
成功账本只增加可选的历史排序字段；旧成功继续显示，旧失败不追溯补写。

发现 `.gitignore` 的 `run/` 会匹配任意层同名包，导致本机存在的 `RunPhase`、`RunLifecycle`、新 `RunReview` 及测试没有进入 Git。
改为根目录 `/run/` 并纳入五份必要 Java 文件；原运行输出仍忽略，未提交世界、日志或构建产物。
旧参与版本 1 允许的非负计数保持原值，避免新增复盘的计数上限妨碍旧局中止回程。

## 命令与结果

使用 `JAVA_HOME=D:\Java\jdk-17`，`GRADLE_USER_HOME=<工程>\.gradle\user-home`，`TEMP/TMP=<工程>\.gradle\tmp`，避免已发现的 C 盘空间不足。

```powershell
.\gradlew.bat build --console=plain
.\gradlew.bat runGameTestServer -PgameTestRunDirectory=run/gameTestServer-review-final-2026-10-28 --console=plain
```

- 完整构建通过，含当前主代码、GameTest 编译与重混淆打包：最终源码快照日志见下；初轮为 `logs/build-reviews-final-2026-10-28.log`。
- JUnit：14 个套件，81 项，0 失败/错误/跳过；含三项新的复盘纯规则检查。证据为 `build/test-results/test/TEST-*.xml`。
- Forge：最终 37 个 required tests 全部通过，退出 0，用时 1 分 22 秒。证据为 `logs/gametest-reviews-fixed-2026-10-28.log`，末尾有 `All 37 required tests passed`。初轮 36 项通过记录保留在 `logs/gametest-reviews-2026-10-28.log`。
- 最终复用了同目录上一轮测试世界，没有删除先前失败数据；未操作正式世界。进程仅加载 Minecraft、Forge、SAODG，没有 SAO/KubeJS/FTB/TACZ。

`RunReviewGameTest` 用独立真实 NBT 文件检查未确认不可见、重复 staging、保存回读、成员限制、未知 schema/类型/字段注入/重复身份拒绝和输入保留；另检查旧计数原值和未知统计回读。
`InstanceGameTest` 在真实 PlayerList/传送/回程流程中检查主动退出恰一条复盘、无成绩/凭证，以及无关玩家查询不可见。
`CombatGameTest` 的敌人异常缺失与确认玩家死亡路径分别断言中止/失败分类、已知完成数、无分数/评级/资格、无奖励 offer/成功事实、重复终止不改记录。

另发现外来资产预检异常直接进入隔离而未归档，现已在同一检查点前补入系统中止复盘。
新增 `foreignAssetQuarantineArchivesAbortWithoutChangingContainer` 通过真实开局预检，断言箱子及 3 颗钻石保留、玩家原位/模式安全恢复、恰一条中止复盘；证明保全后仅移除测试自建箱子，再经管理员重检回收槽位。

中间 37 项运行有两项失败，完整日志 `logs/build-gametest-reviews-final-2026-10-28.log` 保留：回程夹具假设批次切换后的世界出生点天然有安全落脚面；入场夹具在 GameTest 加速 tick/异步区块加载下触发默认 600 tick 生成超时，剩余 414869 次写入。
回程夹具改为在自己的结构内建明确安全落脚面，临时设定出生点并在 finally 恢复，额外断言返回位置实际安全。
入场/外来资产夹具明确设置 1800 tick 生成预算，结束/异常恢复原配置；生产默认仍为 600，未修改生成、外来资产、保存或回程保护。
因此本记录不能证明默认 600 tick 对所有重用槽位/硬件负载都足够；正式环境须另测生成成本。最终在保留的同一测试世界 37 项全部通过。

## 仅提交源码的独立构建与产物

为检查误忽略源码问题，先显式暂存本轮源码，再用 `git checkout-index --all --prefix=...` 导出 Git 索引。最终主源码快照为首次创建的 `.gradle/source-validation-0.34-final-20261028/`，包含上述外来资产归档修复。
该目录不包含本机未跟踪文件、原工程 build 输出或开发世界，在此使用同一 JDK/Gradle 缓存执行：

```powershell
.\gradlew.bat build --offline --console=plain
```

全部 15 个任务实际执行，完整构建成功，用时 1 分钟；14 套件/81 项单测再次通过，0 失败/错误/跳过。
日志为 `logs/build-reviews-source-final-2026-10-28.log`，独立报告在该快照的 `build/test-results/test/`。
随后同步最终修正的 GameTest 文件，增量 build 13 秒通过，源码/JUnit 未变而复用缓存，最新夹具重新编译；日志 `logs/build-reviews-fixtures-final-2026-10-28.log`。JAR 散列前后相同。
这证明纳入 Git 的源码可独立编译，不依赖曾误忽略的本机 Java 文件；没有把第二次单测记为新增测试数量。

干净产物复制到 `build/verified/final/saodg-0.34.0-dev.jar`，1,341,840 字节，SHA-256：

```text
20d5f980c156d940bf8c990c94889a860d4513e5437152e531aa13a393e964e2
```

实际 ZIP 检查包含 41 个已跟踪结构、运行规则类、四份 Mixin 配置与 refmap，没有 `structures/beta/`。
工作区未跟踪的 beta 结构保留原位，不纳入本轮提交或上述产物；原工作区 `build/libs/` 会包含这些素材，不作为本轮交付产物。
Forge 37 项运行测试在原工程的独立测试世界执行，未在源码快照目录重复启动游戏；beta 未被当前 28 个逻辑房间引用。
复制产物没有安装到整合包，所有构建/世界/日志仍保持忽略。

## 未覆盖范围

复盘 GUI 仅编译，未启动普通客户端核对缩放、文案和交互；协议只检验接受/拒绝函数，不代表真实端点握手通过。
私有 NBT 回读不代表在每个真实进程中断边界均通过；重启混合旧局、满容量、强制中断/保存失败矩阵与多人查询仍需完整验收。
本轮没有改兼容脚本；0.33 的 Node/补丁检查结论仍限定于当时范围，没有安装到源整合包。
实局战斗仍采用已授权伤害推进，不验证真实箭飞行、冲锋命中/躲避或实战平衡。其余限制见[恢复构建记录](BUILD_RESUMED_2026-10-28.md)。
