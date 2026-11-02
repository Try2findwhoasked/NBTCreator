# 0.41.16 旧钱包资产检查原生验证

生产源码 `5b2456d306c2c81ebd8a48502418f01b5cc8c12e`；原生测试夹具 `d1ae0c809906`。只使用用户已接受 EULA 并授权的 `run/pack-acceptance-20261028-081137-fd148a65`，绑定 `127.0.0.1:25579`；原服、其他包体和客户端未改动。

## 实际行为

新增仅由 `-Dsaodg.packLegacyWalletFenceAcceptance=true` 启用的 packTest 夹具，要求准确私有目录、零真实玩家和零实例、SAO_SERVER、开发入口及奖励关闭。创建正常 PlayerList 人物，经真实原生人物保存后，调用生产 `BridgeRegistry.externalAssets`，不替换所有者注册或制造 CLEAR。

- 干净人物：Java 范围检查通过，真实 Rhino 钱包所有者返回 CLEAR，生产资产检查及其代际校验通过。
- 内存 ForgeData 市场回执：范围检查拒绝，生产资产检查返回 `saodg.external_assets.unavailable`。
- 内存 KubeJSPersistentData 市场回执：同样拒绝。
- 由正常人物保存写入真实文件，再仅移除内存回执：磁盘历史继续阻止放行。
- 恢复测试人物原始命名空间并正常保存后：真实 Rhino 检查再次通过。库存、末影箱、原生 XP 三字段、ForgeData 和 KubeJSPersistentData 与独立保存的基线一致。
- 注销人物后，旧 ServerPlayer 引用不能再提供钱包范围证据；通道正常释放。

人物 UUID：`67de4cd4-466d-433a-9cc0-7b51c56039a9`。原生报告 `logs/legacy-wallet-fence-probe-112be0e7-6045-45cf-8043-a6e54788edb3.json` 的 passed、real_rhino_clear、restored_rhino_clear、assets_preserved、actor_removed 均为 true。

## 运行、备份与保存核对

先从提交独立导出 `.gradle/legacy-wallet-native-d1ae0c809906`，仅编译 `packTestJar` / 重混淆，19 秒通过。生产模组直接采用已验证的 0.41.16 包，没有因测试再打包或改动生产代码。

独立服原 0.41.14.2 升级前已完整备份 acceptance_world、配置、脚本和旧模组到 `validation-history/legacy-wallet-fence-04116-d1ae0c809906-5abfbd33`；installation.json 固定前后哈希。钱包原文件必须与旧精确补丁输出完全匹配，不能覆盖人工改动。仅此私有副本明确选择 legacy_wallet；默认分发配置仍 market。降级须恢复完整一致备份，不能只换旧 JAR。

原生进程 13756 正常结束，退出 0；56/56 KubeJS 脚本，0 脚本错误/警告。真实 `saodg admin status` 显示 runs=0、lobbies=0、pendingReturns=0、tickets=0、四个 FREE 槽位；在线人数为 0，正式入口继续关闭。存在的其他整合包加载警告不代表整包零错误。

保护清单 761 个原有文件：754 字节不变，含全部 89 个人物数据/进度/统计文件；4 项为明确升级内容（旧 JAR 替换、钱包、资产检查脚本及配置）；server.properties 与 PacketFixer 配置只有时间注释变化，键值一致；SAODG 配置只更新 0.41.15 引入的队长说明注释，所有值不变。初次严格比对抓到了该注释变化，核对精确差异后记录，未放宽配置值检查。

测试附加 JAR 已移出 mods 并归档到上述备份目录；私有副本停服，保留 122 个 JAR、0.41.16 和经过本次验证的 legacy_wallet 配置。没有后台待运行测试。

## 证据与限制

- 原生报告 SHA256：`a9db3685f8756ae98ed7f17c46dbed4239d573b82e9ad682b00cc9316c421bdd`。
- 控制台 `logs/pack-legacy-wallet-fence-04116-20261029.log`：`fc7cb09f4c27fa3d458c8d497766607a06025b16584be50335c4ab223074a790`。
- 保护核对 `logs/legacy-wallet-fence-04116-preservation-20261029.json`：`b6b5f3ede39c0b5970aa280757b1cdabab9a1982379cec9f47a1aa013d12315a`。
- 夹具 JAR SHA256：`aaee9effc50f6f1bfe768f6d17469a91f8ae266bdb5f030305f029d37dbfcab6`。

这证明真实旧钱包所有者与历史回执门禁，不能替代钱包锁故障矩阵、真实副本持久死亡确认、原生经验生产服务完整领取、其他市场实现或真人双客户端。桥诊断仍是 BOUND_UNVERIFIED，没有改为正式验收通过。
