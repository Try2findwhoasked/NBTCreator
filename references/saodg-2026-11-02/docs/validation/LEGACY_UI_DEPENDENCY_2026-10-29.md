# 旧包缺失 UI 提供器的修复与冷启动

2026-10-29，继续使用用户已接受 EULA 并授权启动的私有副本 `run/pack-acceptance-20261028-081137-fd148a65`。只补入一个服务端脚本，未修改原服、当前源码包或用户 Minecraft 进程。

## 原因与材料

旧 NPC 脚本末尾执行 `global.saoUI.registerPage`，但旧包没有任何 UI 提供器。旧启动记录为 54/55 服务端脚本加载，`sao_npc.js#177` 抛出 undefined/registerPage 错误。提高 NPC priority 无法修复缺失依赖。

从现有项目干净源文件复制完整 `sao_ui_core.js`，来源提交、文件散列及旧 NPC 基线保存在 `compat/legacy-ui/SOURCE.json`。通过 `.gitattributes` 单文件 `-text` 保留原字节，不让 Git 换行规范化使来源散列失效。没有复制商城/市场模块或改动钱包。

## 检查及实际部署

- 真实提供器 + 真实旧 NPC 脚本的 Node 夹具通过：页面注册、`/sao npc` 路由、六行菜单/玩家库存引用、目录→商人→交易确认、只委托钱包一次、命名实体事件路由。Java GUI 使用替身，因此不代表真实客户端。
- 两项安装器测试通过：添加/回滚/重复回滚、人工改动保护、已有文件和错误 NPC 基线拒绝。
- 私有副本实际执行 apply→rollback→apply；第一回执 `validation-history/legacy-ui-226edc667706421d96701ca05c1e8f3a/receipt.json` 为 ROLLED_BACK，第二回执 `validation-history/legacy-ui-1df8ddd0c207424b930cd3f733b2eec1/receipt.json` 为 APPLIED。安装文件 SHA256 `cf30717f3a3e674d2469dbef7a963b7b21087f4d5f72967b7013f06d5a2953a7`。
- 同一副本真实冷启动 JVM PID 12520，只监听 `127.0.0.1:25579`。10:32:21 记录实际 KubeJS GUI Java 类加载、framework ready、23 NPC 注册与 NPC menus ready；**56/56 服务端脚本，0 errors / 0 warnings**。10:32:34 Done。
- `list` 确认 0 玩家；`saodg admin status` 确认运行 0.41.14.2/protocol 19/SAO_SERVER，0 runs、0 lobbies、0 returns、0 tickets、四个 FREE 槽位、健康 journal。此轮不升级 JAR；已交付用户的最新开发包仍为 0.41.15/protocol 20。
- 发送 stop 后，10:33:19 日志记录停止并完成全部维度保存，终端会话 2793 退出 0，25579 不再监听。未启用任何副本入场、奖励或伪造外部资产 CLEAR。

前后核对 135 个已有文件，134 个逐字节不变，包括 EULA、SAODG serverconfig、既有脚本及 77 个人物相关文件。`server.properties` 的文件散列因 Minecraft 启动时重写时间注释而变化；非注释配置项与上一份已保存基线完全相同。未回写该文件以掩盖这次正常变化。

## 证据与边界

完整启动/退出日志：`logs/pack-legacy-ui-20261029.log`，SHA256 `9781e956152d8a8e6f4e84cd4c2d24cbd0a974b03ff360237af8fbddf9d94a89`。

前后散列：`logs/legacy-ui-before-20261029.json`、`logs/legacy-ui-preservation-20261029.json`。

这消除了真实 Rhino 加载错误。原包其他 Forge biome/coremod 与 dedicated Camera/Mixin 报错依旧保留，未宣称整包无错。`hub/shop/trade/auction` 功能页面仍缺，真实客户端胸箱布局、NPC 点击及真实交易尚未验证。正式入场、安全/经济完整故障矩阵与多人验收未完成。

工具使用和保留范围见 [说明](../LEGACY_UI_DEPENDENCY.md)。本轮不运行 Gradle，不重新打包模组。
