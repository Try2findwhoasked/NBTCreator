# 原生救援真实计时、跨实例过滤和贡献

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

2026-10-29，在已授权私有测试服 `run/pack-acceptance-20261028-081137-fd148a65`，仅运行显式开关 `-Dsaodg.packNativeRescueAcceptance=true` 的一次定向夹具。运行时仍为 `saodg-0.41.16-dev.jar`，SHA256 `92e327bfbfdd19d0506c1c8a57a9e9b490d248728dbd3856493444e178d07471`；没有替换用户客户端/原服或重新打包运行时。

夹具最终源码 `5216120`（含 `a7a9867` 的双槽位修正），使用既有独立导出 `.gradle/native-rescue-4fe7d1c060d8` 仅重编译/重混淆 packTestJar。其全部 Java 与资源文本和最终提交一致，两份资源仅工作树 CRLF/导出 LF 不同。夹具文件 `saodg-0.41.20-dev-pack-acceptance.jar`，SHA256 `bc737988029fdc8771680e7ff6e77d03a2516debd6ca4bfd41ffbaa357700afc`。版本名不表示使用了 0.41.20 运行时。此轮没有 JUnit、全套 GameTest 或完整原生副本回归。

三名实际 PlayerList 临时人物通过原生邀请/接受组成同一社交队，分别属于两份测试实例。夹具通过反射预置两局 EXPLORING、持久回程标记和独立石砖站台；没有生成整张副本或从正式入场路径绕过门禁。测试服原开发入场/奖励开关均保持 false，SAO_SERVER 预设不改。

EmbeddedChannel 没有真实 socket 监听器，因此不会自动执行网络游戏处理器的人物更新。夹具在每个实际 ServerTick.END 检查本 tick 是否已收到该人物的 PlayerTick.END；缺失时执行其正常 `ServerGamePacketListenerImpl.tick()`，并断言恰好产生一次人物 tick，走原生 Forge 事件和 SocialSystem.tick。每人观察到 106 次正常人物更新，共驱动 318 次网络处理器更新；没有把 60 次处理器调用挤进一个 tick，也没有写入替代的 downed/rescue 进度。

结果 `native-rescue-probe-af761b25-fa74-45b1-aca8-e0fe87186659.json`，passed=true：

- 原生 `tryDown` 接受后人物仍存活、不能行动，两个实例死亡数均为 0、无人淘汰。
- 同社交队但属于另一实例的唯一潜行者临时靠近，实际原生候选循环拒绝该人物，进度保持 0、rescuer 为空。这个负对照显式调用一次原生 tickDowned，记录 `negative_control_handler_calls=1`；正向计时不直接调用该方法。
- 正确同局队友潜行 20 个实际 tick，进度恰好为 20；松开后下一 tick 清零，尚无救援贡献。
- 重新潜行持续 60 个实际 tick 后原生恢复至 6 点生命；没有迷宫区确认死亡。真实 success 分支钩子状态为 `SUCCESS_BRANCH_OBSERVED_UNVERIFIED`，保留原诊断状态，不把单例成功冒充整个适配器验收完成。
- 生产 `confirmParticipation` 次 tick 确认 `rescue:6a6246b9-abaa-4131-be6b-57e9f1a01a0a`，救援者行为数为 1；10 次重复候选通知及后续 tick 后仍为 1。
- 三人的库存和原生 XP 保持基线；只有原生救援者获得 SocialSystem 自身的一枚币，夹具和迷宫区未另发币。实际人物保存屏障通过。
- 通过生产回程/中止/清理释放两局；最终无人在线，runs/lobbies/pendingReturns/tickets 全部为 0，四槽 FREE，正常停服退出 0，127.0.0.1:25579 已释放。

人物 UUID：倒地者 `6a6246b9-abaa-4131-be6b-57e9f1a01a0a`、救援者 `d997db0a-f31a-469c-8ec9-4fefbf619a50`、另一局同队者 `73934796-fac1-40a3-aec1-a2a838a208c1`。实例 `e32bc79a-612f-42f6-8721-d3235667e620` 与 `1052a271-e6fe-4398-91aa-066a6ef6822d`。

备份及夹具归档目录 `run/pack-acceptance-20261028-081137-fd148a65/validation-history/native-rescue-5216120-a44737d0`。测试前受保护 797 文件中 795 字节相同，含全部既有 125 份人物/进度/统计文件；其余仅 packetfixer.properties、server.properties 时间注释变化，配置有效内容不变，unexpected=[]。夹具已从 mods 移出；原 0.41.16 运行时、其余模组、脚本和服务端配置保持。

结果 SHA256 `58dd9c0311d3cca6f20fe7d96512c1e9ded0a300c89341cab07ace63ab9b92ce`；控制台 `logs/pack-native-rescue-5216120-20261029.log` SHA256 `544ed33e9f069c0c063d812c894a3440cd5c8902a23093d7c012e26b48571e39`。原始结果已复制到 logs；保全投影 `logs/native-rescue-5216120-preservation-20261029.json`。

先前两个失败尝试保留：`3ea1004` 请求第二局时仍把预约容量写成 1，尚未进入救援；`a7a9867` 容量修正后因 EmbeddedChannel 未驱动人物 tick 超时。两次均 passed=false、正常清理/退出，没有计入通过。此次只修测试夹具。

本例补充 C06/R08 和同社交队跨实例救援过滤的有限证据。仍未证明最后一 tick 救援、救援者切换、原生复活结晶、倒计时耗尽后最终死亡、真实远程客户端输入或全部取消/掉落/重连窗口；不能据此勾选完整 C06、战斗兼容或发布门槛。
