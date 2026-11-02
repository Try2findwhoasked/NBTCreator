# 0.41.17 局域网开本原因与房主指引

源提交 `1d676accc228f708fd9be4198ec0173e604d3042`。针对“开始挑战”统一显示未启用、两人不清楚谁需修改的反馈，区分 STANDALONE 测试开关、整合服预设、和平难度及保存异常。提示给出开世界的人应修改的存档 serverconfig 位置和重新进入步骤，队长与成员都能看到环境原因；环境允许后再提示队长权限。修正原队长提示只提“选择难度”的不完整文字。

界面快照和实际 startLobby 复用同一个服务端环境检查，保存异常时开始按钮也会禁用。允许条件与原先保持一致，没有自动启用测试、修改世界配置或开放正式预设。协议仍 20，状态字段和世界日志格式不变；界面文字需使用新版客户端。操作步骤见 [队伍说明](../PARTY_USAGE.md)。

## 实际验证

从提交独立导出 `.gradle/source-release-1d676accc228-20261029-042724-38eaf1dc`：

- `tools/build_verified_release.py --java-home D:/Java/jdk-17 --package-only` 通过，编译、重混淆、41 个结构及 476 项中文回退/映射检查通过；未打包 beta 结构。
- 只运行 `runGameTestServer --offline --console=plain -x downloadAssets -Dnet.minecraftforge.gradle.check.certs=false -PgameTestNamespaces=saodg_start -PgameTestRunDirectory=run/gameTestServer-start-diagnostics-04117-20261029`。实际日志确认 1 项必需 GameTest 通过，进程退出 0，Gradle 54 秒；没有重跑原大厅或其他命名空间。
- 该项使用两名真实 PlayerList/EmbeddedChannel 人物及同一邀请加入的大厅；切换四种环境，分别比较队长/成员真实 UI 快照和真实 startLobby 的精确拒绝原因。模拟保存状态不健康只修改测试实例内字段，finally 恢复；所有配置、难度和人物也恢复/清理。拒绝期间大厅/准备状态不变、无实例创建，恢复健康配置后环境提示清空。

日志 `logs/start-diagnostics-04117-20261029.log` SHA256：`45d6851d889e8b77e7dc09d853e545549a79bb7884fbfce9d4c9171d3b2e6f4d`。

没有运行全量 JUnit、全量 GameTest、真实客户端渲染或远程联机；没有修改/启动原服、私有整合包或用户客户端。不能以此宣称全部开始条件或整包正式验收通过。

## 开发包

`build/verified/0.41.17-dev-1d676accc228-20261029-042724-38eaf1dc/saodg-0.41.17-dev.jar`

SHA256：`ea84729271a81a5b148ad7e370bc8b7ae9d4ab1e48e29ad3d6b3bd277b0c13db`。
