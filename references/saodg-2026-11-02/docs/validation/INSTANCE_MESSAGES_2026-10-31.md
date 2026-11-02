# 地牢实例聊天与弹窗隔离

历史独立分支记录：以下协议22及0.41.64-dev结果属于当时快照。合入现有实体箱/继电机后的版本为0.41.66-dev、协议24，当前结果见 [合并记录](MESSAGE_ISOLATION_MERGE_0.41.66_2026-10-31.md)。

基线为 `c243c96` / `0.41.64-dev`；工作在独立 worktree `D:\Documents\Codex\dungeon-message-isolation\SAODG`，分支 `codex/dungeon-message-isolation`。主目录未提交的谜题与钱包测试改动未复制到本分支。

## 行为

- 普通玩家聊天按照服务端当前准入的实例 ID 双向过滤。生成期间即开始隔离，探索、濒死等待和结算期间继续使用同一绑定；不会因为暂时不满足战斗条件而丢失同局聊天。退出并完成回程后回到局外聊天，加入新实例后只使用新实例频道。
- 两名局外玩家继续普通聊天。没有准入绑定却位于共享地牢维度的访客只能收到自己的普通聊天，不能成为局外与实例之间的桥梁。
- 接收者过滤发生在原版 `PlayerList.broadcastChatMessage` 的逐人发送处，保留原始 `OutgoingChatMessage`、聊天类型与过滤参数，不取消 Forge 聊天事件后重发为系统文本。玩家来源的 `/say`、`/me` 若使用此广播路径同样按实例过滤。
- 实例生成、入场、房间/钥匙/Boss 事件、队员死亡、秘密、结算和中止/失败通知统一进入 `InstanceService.notifyRun`。发送前逐人核对当前绑定及连接状态，冻结开局名单不再单独构成通知权限。已回程玩家仍可查看原有只读进度界面，但不会因此继续接收旧局事件。
- `DungeonNotice` 在服务端选定接收者后携带实例 ID 和原始翻译组件；客户端同时使用它和 UI 快照中的 `notification_context` 管理队列。更换实例/大厅、回程、维度切换和断线会清空旧弹窗；同实例快照更新保留当前弹窗。通知包先于周期快照到达时，也会先绑定正确实例。客户端仍经原版系统消息入口触发 Forge 聊天事件、日志及旁白；换维度的清空发生在玩家 Clone 事件，避免 tick 末尾误删刚到达的入场/回程卡片。
- 血房传送门的 action bar 提示和谜题光束还需确认本次循环中的实例与玩家当前交互实例相同；战斗预警沿用已有的实例、房间与合法目标校验。

控制台公告仍是全服公告；显式私聊、队伍命令以及其他模组/脚本自行发送的全服系统文本或 GUI 不经过此普通聊天广播路径，本次没有改写它们。这里的弹窗是 SAODG 的地牢事件卡片；不新增全服包拦截或根据文本猜测来源。

## 协议与存档

`saodg:main` 协议由 21 升为 22，新增仅服务端到客户端的消息编号 2。旧客户端不能连接本分支服务器；两端需要同时更新。状态增量使用已有 NBT 机制，新增可选 `notification_context`，没有保存格式或服务器配置迁移。

网络发送保持按玩家定向的 SimpleChannel 路径，参照 [Forge 1.20.1 SimpleImpl 文档](https://docs.minecraftforge.net/en/1.20.1/networking/simpleimpl/)。已有没有远端通道的服务端测试人物仍使用相同受众检查后的系统文本回退，不能据此声称真实客户端通知端点已经验收。

## 实际验证

指定 JDK 17：`$env:JAVA_HOME = 'D:\Java\jdk-17'`。

1. `gradlew.bat --offline compileJava compileGameTestJava test --tests cn.saodg.client.notice.GameplayNoticeTest --console=plain`：通过；6 项通知单测通过，包含实例切换时同时清空当前与待显示卡片、同实例保留以及回到局外清空。日志：`logs/message-isolation-compile-unit-2026-10-31.log`。首次夹具编译发现误调用私有 `dimension()`，改用服务端维度查询后通过。
2. `gradlew.bat --offline build test --tests cn.saodg.client.notice.GameplayNoticeTest runGameTestServer '-PgameTestNamespaces=saodg_messages,saodg_sync,saodg_lobby' -PgameTestRunDirectory=run/gameTestServer-message-isolation-scoped-2026-10-31 --console=plain`：主代码和全部夹具编译、打包及 6 项定向 JUnit 通过，运行时有 1 项消息夹具在准入阶段失败，原因是新夹具漏设死亡资产门禁所需的 keepInventory。日志：`logs/message-isolation-scoped-2026-10-31.log`。补齐仅测试世界临时设置及结束恢复，没有更改生产门禁。
3. 最终命令 `gradlew.bat --offline build -x test runGameTestServer '-PgameTestNamespaces=saodg_messages,saodg_sync,saodg_lobby' -PgameTestRunDirectory=run/gameTestServer-message-isolation-scoped-verified-2026-10-31 --console=plain`：构建成功，8 项 required GameTest 全部通过，退出 0，耗时 1 分 51 秒。日志：`logs/message-isolation-scoped-verified-2026-10-31.log`；JUnit 沿用上一条同一生产源码下已完成的 6 项结果，这次没有重新执行。

专用 `DungeonMessageGameTest` 使用六名实际 PlayerList 成员和 EmbeddedChannel 捕获出站消息：两队各两名、两名局外玩家；顺序生成两局，保持探索阶段重叠，之后第一队退出、清理、复用槽位、新 ServerPlayer 对象用同一 UUID 重新登录，再全部回程清理。每个探针检查全部六名接收者，要求应收者恰好收到一次，其他人收到零次。未准入地牢访客、局外互通、控制台公告及快照通知上下文也通过。最终三局的槽位均释放。8 项中的其余测试覆盖消息编解码/协议、状态投影及大厅行为；不是 8 次完整副本或 8 个真人客户端。

打包核对确认主 JAR 包含 `DungeonChatMixin`、`DungeonNotice`，Mixin 配置和 refmap 中保留了聊天过滤目标映射。未创建发布标签、合并主目录或部署；产物仍标为本分支 `0.41.64-dev` 开发包。

早期探索日志保留在 `logs/message-isolation-runtime-2026-10-31.log`、`logs/message-isolation-runtime-verified-2026-10-31.log`、`logs/message-isolation-runtime-final-2026-10-31.log`。首次发现正常传送不能构造未准入访客，改为测试内同步切换其 level 查询并用 finally 恢复，未放宽传送门禁；翻译参数的数字经过原版 JSON 编解码成为字符串，改为检查翻译结构、序列化内容及显示语义。旧综合 `ConcurrentInstanceGameTest` 又暴露“首间战斗房必有秘密”和“清房等于已拾取钥匙”的历史假设；已恢复该夹具原样，消息生命周期在独立 `saodg_messages` 命名空间验收，没有将综合战斗/钥匙夹具记为通过。

没有运行默认完整 JUnit 套件，不能据此将既有钱包测试失败记为修复或全量通过。没有修改原服或现有客户端；服务端测试连接不等于真实多客户端视觉、签名聊天端点、真实网络断线或重启恢复、整合包聊天插件验收，这些仍是后续联机验证范围。开发运行不代表正式开本验收。
