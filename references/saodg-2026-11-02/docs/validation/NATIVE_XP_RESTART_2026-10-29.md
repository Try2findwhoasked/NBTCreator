# 原生经验正常重启后的已领取去重

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

夹具提交 `da2f3ca`；生产包仍为原 0.41.16，没有重新编译生产模组。仅编译独立 Git 导出的 packTestJar，17 秒通过；使用显式 `-Dsaodg.packNativeXpRestartAcceptance=true`，不进入默认套件。

## 真实保存链路

沿用[上轮实际击杀及生产服务发放](NATIVE_XP_PIPELINE_2026-10-29.md)的真实人物文件、世界、native_xp 分片和原请求；没有新建资产基线或写入经验。读取并核对上轮成功报告的固定 SHA256，保证重新登录的是实际领取过 13 XP 的同一人物，而非新生成的成功样本。

在同一已授权私有整合包目录正常冷启动，真实生产服务重新加载原 CONFIRMED 请求，匹配 run/enemy/player/owner/amount/expectedXp；随后用相同 UUID 正常 PlayerList 登录。人物载入时原生 XP 为 13，完整库存与重启前真实文件一致。

连续 10 次生产 claim 均返回 `saodg.native_xp.already`，XP 保持 13；pending=0，待领列表为空。正常保存并读取真实人物文件后，XP、完整库存、钱包余额和迷宫区成长保持一致。原操作全部字段、commit 身份及磁盘分片均未改变。没有重新制造击杀、回执或死亡链接。

人物 `0213ed7a-d04a-4670-a0f4-eb40352fc12f`；run `36a3efff-e39c-484e-9ae7-9f404dfa415c`；请求 `0dba6bf4-2262-4340-85f0-9ef6f0131279`；commit `0085f976-b0ff-47b9-b180-83cd953b1c5c`。

## 环境、保存核对与证据

只使用既有授权私有 `pack-acceptance-20261028-081137-fd148a65`、127.0.0.1:25579、SAO_SERVER，入口/奖励关闭；原服、客户端和 beta 结构未改动。启动前完整世界、配置、脚本及当前模组备份于 `validation-history/native-xp-restart-da2f3ca-7dbe55c6`。

原生进程 7352 正常停服，退出 0；56/56 KubeJS 脚本，0 脚本错误/警告。真实 admin status 为 runs/lobbies/pendingReturns/tickets 全 0、四个 FREE、journal=true，在线 0 人。附加夹具已归档移出 mods，私有服已停、122 个 JAR、原关闭配置，无后台待运行测试。

原 773 个保护文件：767 字节不变；4 个明确重登的测试人物文件由正常登录/保存更新，资产由实际人物文件独立核对；其余 97 个人物/进度/统计文件全部字节不变。server.properties 与 PacketFixer 仅时间注释变化且键值一致。生产 native_xp 的 2 个文件与启动前逐字节一致，没有新请求或再次写入已确认操作。

| 证据（位于 logs/） | SHA256 |
| --- | --- |
| native-xp-restart-probe-34e9ce3c-391f-4e56-a5ea-c47f919587e4.json | 26bd8a36084ff2af7b00174f4116e61a7eb7c6e0c6b03e3276fb3f78fd34422f |
| pack-native-xp-restart-04116-20261029.log | bd01a9532bea3430f2697a1dd0fa251d9625dd607195a94671f3861c3fcc5b25 |
| native-xp-restart-04116-preservation-20261029.json | 2be9989c014cbbd06050c9eb15a18343e5571a2594d48afb39d27e0df57c7e19 |

夹具 SHA256：`0de93a38163f46f2a104186aa37b1f373bca68b321f303dab0bb9fa6ca7c7775`。

本例只证明已 CONFIRMED 原生经验经正常停服/重启/同 UUID 重登后不重复发放。未覆盖 WAITING/READY/INTENT/APPLIED_UNCONFIRMED 硬退出窗口、写盘失败或真实远程客户端；不能宣称原生经验完整故障矩阵或整合包总体验收通过，正式入口保持关闭。
