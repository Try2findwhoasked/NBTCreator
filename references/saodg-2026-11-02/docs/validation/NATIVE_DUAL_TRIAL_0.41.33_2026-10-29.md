# 原生双队试炼：未完成

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

后续：本文中断局已通过实际登录、资产保持与生产清理恢复；随后新双队遇到原生结晶掉落的保护隔离，整体仍未完成。当前现场与0.41.34限定修复见[后续记录](NATIVE_CRYSTAL_DROPS_0.41.34_2026-10-29.md)，不要再次对新现场运行本文固定旧人物的恢复夹具。

运行模组仍为 0.41.33，源码 `3cd243e694e306f46d784cd4a5740951b60c7663`，SHA256 `0167436130aa956398bae9cf14b1c375c959597c2d3342bb0ea26b255680de84`。本轮只改 packTest 夹具，没有更新生产逻辑、客户端或原服。仅使用已授权的 `run/pack-acceptance-20261028-081137-fd148a65`，127.0.0.1:25579；磁盘入口与奖励开关保持关闭。夹具与单队检查一样只在同步开始请求期间临时放开入场，并立即恢复。

新增 `NativeDualTrialProbe`，显式系统属性 `saodg.packNativeDualTrialAcceptance=true` 才注册。四个新建原生人物、两个原生社交队伍，经大厅准备和正式入口生成到不同槽位；生成保持串行，两局同时存在。复用单队的主线、封印大厅与首领驱动，测试双向同位置跨队攻击拒绝、持有实际主线钥匙时的跨队开门拒绝、只传送本队的封印大厅入口、第一队清理时保留第二队进度/门/票据，以及两局独立历史/经验/回程。人物无敌、高伤害、逐房传送；这不是远程客户端、完整技能兼容或战斗平衡测试。

## 首次运行：夹具失败并正常清理

初始源码 `01299ad` 编译失败：门交互方法的受检 IOException 未声明，修复提交 `e5c02255ffb8` 后独立导出 `packTestJar` 通过。分别保留日志 `logs/native-dual-fixture-01299ad-20261029.log` 与 `logs/native-dual-fixture-retry-20261029.log`，没有把首次编译视为成功。

`e5c0225` 附加包 SHA256 `206ddabe1f697be020a676b0245017ea30da8b1761acbc20b3cac62a26d0ae64`，运行 PID 15832。两队入场、双向同位置跨队伤害拒绝在报告中为 true，随后夹具错误读取 `RunRecord.keys` 导致中止；此字段是封印大厅的首领钥匙，主线钥匙应由 `BloodRoute.keys(completed, openedRouteDoors)` 计算。两局均按生产中止/清理路径结束，进程正常退出 0、端口关闭。未将整体双队检查标为通过。

- 报告 `logs/native-dual-trial-probe-7ee0f976-1422-45d4-925a-612985321d48.json`，`passed=false`，SHA256 `9446c8dbb5739145203a886a40553148782292d45b38546dfddbcb40deed1459`。
- 控制台 `logs/pack-native-dual-e5c0225-20261029.log`，SHA256 `9233e8d88ec9792304ec24ebfd2d24c3b062f8b5740fdb225e787f7e0ac062da`。
- 保全 `logs/native-dual-e5c0225-preservation-20261029.json`：905 份受保护文件中 903 份保持、2 份 properties 仅时间注释变化，233 份既有人物相关文件保持，无意外变更；附加包归档于 `validation-history/native-dual-e5c0225-d0bc6c98/fixture-attempt1.jar`。

## 修正重跑：保活超时且运行中断

`b4b93a321346` 改为读取主线钥匙，并从 keySources 定位真实门面，包括安全房出口；独立导出 `packTestJar` 通过。附加包 SHA256 `f607ae44748db1a8ca6118715a433f3c55af84a7eff5d9d87cf5d6531a707577`，运行 PID 5596。两局均生成 832012 次写入、215 个生成 tick、176 张票据。日志到达第一局正常清理和第二局首领守卫阶段；但测试连接没有回复保活包，四人物先后 Timed out，没有最终双队报告，不能将这次视为通过。

后续观察时会话 37816 已不存在，PID 5596 不存在且端口关闭；控制台末尾为 16:21:54，无正常停服记录，JFR 为 0 字节。中断原因未知，不推断正常退出，也不认为预设停止流程已执行。

- 控制台 `logs/pack-native-dual-b4b93a3-20261029.log`，SHA256 `5c91802ab306870ae1504c045fe9c22dafa946eefe603dd8a345929f1c06eb35`。
- 保全 `logs/native-dual-b4b93a3-interruption-20261029.json`：921 份受保护文件中 919 份保持、2 份 properties 仅时间注释变化，249 份运行前既有人物相关文件保持，无意外变更。此结论不包含本次新建人物，也不证明它们已回程或活动日志已清理。
- 附加包归档于 `validation-history/native-dual-b4b93a3-50d77ca4/fixture-attempt2-interrupted.jar`，完整运行前世界/配置仍保留在同一备份目录。未回滚或手动擦除当前恢复日志。

本次新建人物为 `dg_dual_a0`/`d9fa0e7c-1db4-4198-8aaa-bacc7d625ddf`、`dg_dual_a1`/`de52aae3-623e-45e9-94dd-d677716b4fa6`、`dg_dual_b0`/`e2ece7fa-ab6d-4694-8bd9-e0fd5b24a2d0`、`dg_dual_b1`/`a1f0d0c9-e0f5-4aea-b25f-8dc3c821eeb5`。下次应先通过生产恢复与实际测试人物登录处理遗留回程，再检查槽位和返回标记；不能用改日志或重置存档冒充恢复成功。

## 保活修复与剩余工作

后续 0.41.34 已取得实际双队完整主线报告，各队保活回复 10 次、独立通关/回程/清理通过，原隔离现场保留。此页的失败/中断为历史记录，未删除或改标通过。[后续结果与限定范围](NATIVE_DUAL_RETAINED_0.41.34_2026-10-29.md)。

提交 `1489ad97445c` 仅修改夹具：读取 EmbeddedChannel 发出的保活包，通过实际 `handleKeepAlive` 回复对应 ID，并释放已读出站消息；记录回复计数。双队驱动在人物断线时立即失败并走清理，不再等到整个试炼超时。独立导出 `.gradle/native-dual-fixture-1489ad97445c-0c993c33` 的 `packTestJar` 编译/重混淆通过，18 秒；日志 `logs/native-dual-fixture-1489ad9-20261029.log`。尚未运行此修复包，保活行为和双队完整终局仍未验收。没有重跑 JUnit 或其他完整套件。
