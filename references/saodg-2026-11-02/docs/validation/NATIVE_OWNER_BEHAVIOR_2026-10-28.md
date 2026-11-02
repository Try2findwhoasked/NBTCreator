# 原生映射的治疗/伤害行为探针

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

新增独立 packTest 源集与测试专用附加模组，不打入 SAODG 主 JAR。已实际确认 Gradle 提供 packTestJar/reobfPackTestJar 并重混淆成功；默认 build 只编译该源集，生成附加 JAR 需显式任务。
附加模组只在用户已授权的固定私有目录及 `-Dsaodg.packAcceptance=true` 下创建临时人物；没有真实玩家或活动实例才运行，不启用副本或奖励。计划调用实际合并的自疗/伤害方法，记录健康值与 Forge 伤害事件，未登记迷宫区对象作为拒绝对照。

## 首轮实际发现

`logs/pack-native-owner-behavior-20261028-081137-fd148a65.log` 显示人物尚在 PlayerLoggedInEvent 时即失败：FTB Teams TeamManagerImpl.syncToAll → ClientTeamManagerImpl.forSyncing 引出 LocalPlayer 的专服类加载异常。此时未调用任何治疗或伤害，不记录为行为通过。
当前目标 JAR 的 ClientTeamManagerImpl 原始 class SHA-256 为 `91d42c27d520148452bc335b29b47f58b47bc84d6933b87417c087e0250c8277`，其中存在私有 `saoConnectedPlayerId(Minecraft)` 方法体，直接读取 LocalPlayer。只根据本机实际二进制做判断，不把该问题归因于全部 FTB 上游版本。
初版探针登录异常发生在 Actor 返回前，可能留在线测试人物；已将构造与正式登录分开，在 finally 保留并清理部分登录对象，清理失败会明确记录。报告改成每次唯一文件，未观察到的攻击用字符串表达，不因 NaN 丢失失败证据。

## 专服兼容修复

0.41.5 对精确匹配的上述 class 且仅 DEDICATED_SERVER 生效，把仅供客户端使用的私有 UUID 辅助方法改为显式不可用，移除其 LocalPlayer 访问和帧/调试局部信息。共享队伍同步/序列化方法不修改；客户端环境原逻辑保留，未替换或改写第三方 JAR。
新增检查覆盖同步方法体保留、未知签名/缺少预期访问/重复 helper 不做部分修改。

## 复测实际结果

主包与附加包从同一固定提交 `a4a3fceaed7f47195ecb658f609dd09d86790e79` 的干净导出构建，完整 build 与 100 项 JUnit 通过，1 分 22 秒；测试附加包另外执行 packTestJar/reobfPackTestJar 成功，10 秒。主 JAR 独立检查不含 cn/saodg/packtest 类，附加包不作为正式模组发布。
主 JAR 为 `build/verified/0.41.5-dev-a4a3fceaed7f-20261028-091922-bd4534fc/saodg-0.41.5-dev.jar`，SHA-256 `1a07e67c8d059a1eeb3fa0288d09c91c922a57a93adfdedf45c0f9d852c800cb`。
同一授权私有副本仅更换 SAODG 和测试附加包，121 个原模组保留，开本与奖励仍关闭。`logs/pack-native-owner-fixed-20261028-081137-fd148a65.log` 在 17:23:06 Done，17:23:10 得到 SAODG_NATIVE_OWNER_PROBE_PASS。
临时人物 UUID 为 `e8851252-f949-4f12-acd8-88ee407bb7c9`。正式 PlayerList 登录与 FTB 队伍同步完成，复测不再因该 LocalPlayer 方法体导致专服登录失败。

此次具体数值：

| 场景 | 预期/观察的原生事件数值 | 实际生命变化 |
| --- | --- | --- |
| 自疗，最大生命 200，输入 2 | 原补丁六百分比最低值 12 | 50 → 62 |
| 剑技处理方法，输入 5，测试角色当前等级 | 攻击事件 5，与原 GrowthPolicy 计算一致 | 僵尸 2000 → 1995.08 |
| 职业处理方法，输入 5 | 攻击事件 2，与原 ProgressionRules 计算一致 | 僵尸 1995.08 → 1993.1599 |

另实际调用处理方法对未登记迷宫区僵尸伤害，返回 false 且生命不变；未登记的迷宫区玩家对象自疗也不改变生命。拒绝对照不是两支真实副本队伍，不以它替代完整跨实例技能验收。
唯一报告 `native-owner-probe-c77edf43-5e81-43e3-8a22-df036c1152cd.json` 的 passed=true、无 cleanup_error。控制台 list 确认在线 0 人，临时目标已 discard；17:24:35 stop，17:24:36 全维度保存，进程退出 0、端口释放。附加包移入副本 validation-history 保留，后续普通启动不会自动带入行为探针。

## 仍未覆盖

这是已合并处理方法的实际调用，含正常 PlayerList 人物和真实 Forge 伤害事件，不是完整技能施放/消耗/蓄力/冷却/网络演出测试。固定角色和数值不证明全部等级、职业、队伍治疗、被动、灵魂伤害状态、真实客户端或完整资产矩阵。
人物使用嵌入 Netty 通道，不能称为真实渲染客户端联机验收；所有角色和档案仅在用户授权的私有世界中创建，原服玩家未参与。FTB 客户端分支按代码保持不改，但客户端功能尚未复测。
默认无可选模组回归执行 `gradlew.bat build runGameTestServer -PgameTestRunDirectory=run/gameTestServer-native-owner-regression-2026-10-28 --offline --console=plain`，日志 `logs/native-owner-regression-2026-10-28.log`：完整构建、100 项 JUnit、42 项 required GameTest 全部通过，112 个房间旋转场景全部完成，4 分 28 秒。
