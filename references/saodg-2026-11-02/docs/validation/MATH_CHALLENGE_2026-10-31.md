# 挑战大积霸：精修与运行接入验收

日期：2026-10-31。分支 `codex/challenge-math-master`，当前构建版本 `0.41.66-dev`。功能说明见 [挑战大积霸](../CHALLENGE_MATH_MASTER.md)，机器可读结果见 [本次 JSON](MATH_CHALLENGE_2026-10-31.json)。

## 实际检查

| 检查 | 本次结果 |
| --- | --- |
| 未过滤 Gradle `build` | 未全绿：176 项中 173 通过、1 条旧谜题数量断言失败、2 项可选本地二进制测试跳过；没有人为过滤 |
| 布局全量矩阵 | trial / standard / elite 各 10,000 个种子，全部通过；另有各难度 512 个场地隔离检查通过 |
| 最终静态资产打包 `build -x test` | 通过；跳过整套 JUnit，未跳过编译/运行夹具编译/打包 |
| 修正后定向 JUnit | 30 项，失败 0，错误 0，跳过 0 |
| Forge 定向 GameTest | 3 项必需测试全部通过；仅 `saodg_math` 命名空间 |
| 内容审计 | 80 个活动房，5 个原有非活动功能房保留；340/340 个生产模板有引用，无错误 |
| 分层 NBT | 每单格恰好主体/墙面两份；回读、哈希和逐块重建通过 |
| 原稿与精修 | 用户查看原稿缩略图并授权后，从完整同源模型统一精修；修改 256 格，原稿保留 |
| 静态几何 | 原稿开洞前六邻接外部空气洪水检查通过；最终只保留已声明南门；精修后临时封合法门复验通过；最终 NBT 并非完全密闭 |
| 必要通路 | 原布局、神比站位、对话位置和后排铭文接近点共 9 个目标通过半格 AABB 检查；Forge 实际方块通行另通过 |
| 旋转与拼接 | 仅声明并检查 0 度；单格没有内部 49 格接缝；实际生成实例已放置并通过入口/退出及清理检查 |

随机题库单测抽样 1,000 个种子，验证三种不同基础题型、积分/微分方程分层、所有正解、互异选项和选项顺序变化。状态测试覆盖基础题重试、第三题清房、额外题一次机会、第四题答错仍可获得第五题奖励、跳过保留奖励、恢复同一题目与选项及过期操作拒绝。

验证顺序：未过滤构建的唯一失败是 `SimpleCombatRetirementTest` 仍要求谜题房数为 6，而当前新增后为 7。将断言更新为 7，并补充新房间必须存在的检查，原有六种谜题保留断言未删除。随后对谜题状态机、奖励和该内容保留测试定向复验，30 项全部通过。全量中两项 `SaoRangedItemsTest` 依赖 `SAODG_ARCHER_REFERENCE_JAR`，当前未提供而跳过。

最后只修正 NBT 中书册、进度标记、书柜和壁灯的支承，并更新制作来源路径为 `refined_05`；生产 Java 逻辑、布局占地/端口/旋转与题库未变。最终资产以 `build -x test` 打包，再运行本次全部三项 Forge 测试。没有再重复整套单测或 30,000 个布局种子，不能称默认全套构建已经重新全绿。

运行测试用两名经服务器登录的测试玩家接力作答，并同时创建另一个实例：近距离与视线校验、旧题重复点击、跨实例链接、伪造 NPC 绑定、基础清房与额外奖励隔离、持久化状态回读及重复房间记录拒绝均通过。两个实例结束后都完成回收，神比随所属实例删除。测试玩家是嵌入式连接，不据此声明真实双客户端体验验收完成。

奖励测试分别验证一道与两道额外题的固定加成（基础 120 + 30 / 60 副本经验），无资格成员不生成奖励；实际调用玩家存档事务，读回奖励日志后重复领取不增加经验；改变已冻结的数学奖励数量触发冲突。零数学奖励保持旧指纹，现有接线奖励可叠加；不修改钱包归属或 SAO 余额。

## 可复现命令

在项目根目录、JDK 17 下执行：

```powershell
$env:JAVA_HOME = 'D:/Java/jdk-17'
.\gradlew.bat build --console=plain
.\gradlew.bat test --tests 'cn.saodg.domain.puzzle.*' --tests 'cn.saodg.domain.reward.RewardTest' --tests 'cn.saodg.domain.layout.SimpleCombatRetirementTest' --console=plain
# 修正旧数量断言并定向复验后，最终资产打包：
.\gradlew.bat build -x test --console=plain
.\gradlew.bat runGameTestServer -PgameTestNamespaces=saodg_math -PgameTestRunDirectory=run/gameTestMathChallenge --console=plain
python tools/verification/content_audit.py --check
python .agents/skills/minecraft-nbt-modeler/scripts/nbt_delivery.py build/nbt_models/challenge_math_master/refined_05/delivery
```

本地原始日志：`build/math-build.log`、`build/math-focused-final.log`、`build/math-package.log`、`build/math-gametest-final.log`。未过滤结果 XML 保存在 `build/nbt_models/challenge_math_master/full_suite_before_count_update/`，不以最后一次定向单测 XML 覆盖全量结果。制作主稿、用户授权、精修前后对照及校验也保留在任务目录；全构建未清空 build。本次未改动同时存在的 `tools/structures` 工作区修改。

## 存档、产物与尚未验收项

新增可选 `math_challenges` 运行记录列表和非零数学奖励的结算指纹字段；旧记录无此列表时按空处理。题目种子生成格式固定为版本 1。真实重连沿用实例中的同一状态；服务器进程重启仍按现有策略中止未完成副本，不新增战斗恢复。已验证 NBT/奖励日志回读，未执行真实进程重启与实机断线重连。

产物：`build/libs/saodg-0.41.66-dev.jar`，SHA-256 `793f272940eb68eefb247dca164f0f814799478802e70e855c26e9e239c5e974`。已核对 JAR 包含运行类、房间定义及与最终精修交付逐字节相同的两层 NBT。

仅三项定向 Forge 测试通过，未运行默认全部 GameTest。真实双客户端聊天点击、NPC 渲染/皮肤、游戏光照、SAO 整合包倒地适配与生产准入验收尚未执行。预览来自程序化几何渲染，不能代替这些检查。未安装到活动存档、未部署生产服务器、未发布或打标签。
