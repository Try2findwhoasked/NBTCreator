# 原生倒地断线与新身体重连：0.41.27

测试夹具提交 `359a4b48cc32471235d4638bcf336c909afbfef9`；运行时代码仍为 `4c35d3aca4dba39d7db454a3b310ca3366933f19`，本轮没有修改生产规则或重新发布运行包。补充 0.41.23 离线异常计时修复在真实原生倒地数据上的证据。

## 环境和执行范围

仅使用已授权的 `run/pack-acceptance-20261028-081137-fd148a65`，绑定 `127.0.0.1:25579`，启动参数 `-Dsaodg.packNativeRescueReconnectAcceptance=true`。备份后从 0.41.22 升级至既有验证包 0.41.27；原服和用户客户端没有改动，也没有启动客户端。

四个临时人物经实际 PlayerList 登录，组成同一个原生社交队；夹具预置一个 EXPLORING 实例和目录中真实入口到达点处的安全平台，没有生成完整地图或走正式入场。EmbeddedChannel 在真实服务器 tick 按需驱动正常游戏连接处理器，并检查每次只产生一个 PlayerTick.END；离线人物被排除，不能继续驱动已移除的旧身体。

在原 0.41.27 Git 导出 `.gradle/source-release-4c35d3aca4db-20261029-062940-fff4b264` 中只更新已提交的 `NativeRescueProbe.java`，执行 `packTestJar --offline --console=plain`，编译和重混淆通过，9 秒。运行包不变；未重跑 JUnit、GameTest 或完整套件。夹具 JAR 的 SHA256 为 `d7c31aaed8663dab2ab7ac3a3e9afa0f541f43162567ed76485f85dfdc312da4`。

## 实际结果

结果 `native-rescue-probe-4f682594-85b4-4386-9291-e1b877f2160d.json`，`passed=true`：

- 调用原生 tryDown 后，实际经历 10 刻，生产服务已观察到倒地；倒计时剩余 190。真实注销并保存人物，离线 420 个服务端刻，超过旧的原生倒地 200＋异常宽限 200 刻界限，仍在既有 2400 刻重连窗口内。
- 离线期间旧身体没有收到任何 PlayerTick，原生倒计时未变。用同 UUID、同名称的新 ServerPlayer 和新连接实际登录，读取磁盘保存的原生数据，倒计时仍为 190，没有写入或重置倒地/救援字段。
- 生产倒地看门狗起点恰好平移 420，保留此前累计在线时间；新身体恢复本实例身份，仍不能行动，但可被同实例队友救援。旧身体的实例身份为空。
- 原生救援完整持续新的 60 刻，恢复至少 6 点生命；下一 tick 生产贡献记录一次，十次重复候选不增加贡献。未计作死亡。
- 再次原生倒地，无人救援时在第 200 刻发生实际最终死亡；生产确认死亡与淘汰各一次。实际 PlayerList 重生并重新绑定连接后，生产回程将其送到实例外。
- 再次真实注销、同 UUID 新身体登录，保持淘汰，只有只读复盘，实例归属为空；未重新加入战斗。
- 两次重登、救援、死亡和重生后，全部夹具人物的完整库存 NBT 与原生 XP 保持基线；仅成功救援者获得原生系统的一枚币。死亡配置显式采用 keepInventory=true，结束恢复原值，不代表其他掉落配置已验证。

共驱动 2640 次正常连接更新。原生钩子诊断为 `FINAL_DEATH_OBSERVED_UNVERIFIED`，不据此将整个原生适配器标为验收完成。生产回程、中止和清理完成，最终在线人数 0，runs/lobbies/pendingReturns/tickets 均为 0，四个槽位均为 FREE；正常停服退出 0，端口关闭。

## 保全与证据

备份为 `validation-history/native-rescue-reconnect-359a4b4-2fbb7736`。857 个受保护文件中 853 字节相同，包括全部 185 个既有人物相关文件；两个 Java properties 文件仅时间注释变化。另两项为明确升级的旧运行包和服务端配置：新配置仅增加默认关闭的 safeReturn 大厅字段，原有配置语义保持，`unrestrictedDevelopmentEntry=false`、开发入口和奖励开关仍关闭。源代码默认开放开发入口的用户设置未改动。`unexpected=[]`，夹具已从 mods 移入备份。

- 运行包 SHA256：`7de7323b238eb3624fc7702ccbd786f36ba6b51a905a4c8708b37b89a3f07aac`。
- 结果 SHA256：`41a2a071e998a6b55cbbbbac163a68d31312f31177eec254a776aebe035ec271`，副本位于 `logs/native-rescue-probe-4f682594-85b4-4386-9291-e1b877f2160d.json`。
- 控制台 `logs/pack-native-rescue-reconnect-359a4b4-20261029.log`，SHA256：`3af0b9cc6a4157099fbecb956dc79c81ad68f28653f58a4e6e811ea26729d1f5`。
- 保全记录 `logs/native-rescue-reconnect-359a4b4-preservation-20261029.json`。

这是 C06/F07/C07 的原生倒地重连边界证据。未覆盖真实远程输入、倒地时整服重启、全部取消/掉落配置、四客户端或目标整合包多队完整通关，不勾选整个验收项。
