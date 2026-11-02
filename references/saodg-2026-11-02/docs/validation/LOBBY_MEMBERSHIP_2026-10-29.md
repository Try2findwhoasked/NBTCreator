# 房主调整本次大厅名单

0.41.11-dev 新增 InstanceService.removeLobbyMember 和成员行“移出”按钮。只有当前实际在线房主对象、匹配大厅修订且目标仍在名单时允许；房主本人通过既有退出关闭大厅，不能把自己移出后留下无房主大厅。目标可以离线，操作只改 Lobby，不调用 SAO 社交队伍写入入口，不操作副本运行成员/背包。

名单编辑通过原 Lobby.configure 清空全部准备、修订 +1；剩余成员收到重新准备提示，在线被移出者收到说明。滚动名单时重建成员按钮，避免行内容变了而旧按钮仍指向原人物；名字/状态为移出按钮预留宽度。协议新增 REMOVE_MEMBER 为末尾枚举，升级为 16，拒绝旧 15；存档 schema 未变。

## 定向验证

在提交 4b6615f 的干净导出目录运行，未重编译用户 0.41.10 开发客户端所在根工程的 classes/resources：

```powershell
.\gradlew.bat '-Dnet.minecraftforge.gradle.check.certs=false' runGameTestServer -x downloadAssets -PgameTestNamespaces=saodg_lobby -PgameTestRunDirectory=run/gameTestServer-lobby-0411-20261029 --offline --console=plain
```

logs/lobby-0411-targeted-offline-20261029.log：只运行 saodg_lobby 的 2 项 required，全部通过，38 秒，正常全维度保存并退出 0。

第一项使用两个真实 PlayerList/EmbeddedChannel 人物，实际创建大厅、邀请、分别准备，然后验证非房主、同 UUID 复制对象、过期修订、移出本人、目标不在名单均被精确拒绝且状态不变。把客人从 PlayerList 正常移除后再执行名单移出，确认其确实离线；房主/选择保留、只剩房主、准备清空、修订 +1、被移出者不再占大厅且测试人物库存快照未变。旧准备拒绝，新修订可再次准备。第二项验证意图编码往返的上下文/修订/成员 UUID，以及协议 16 接受、15 拒绝。

首次 logs/lobby-0411-targeted-20261029.log 在 downloadAssets 因 et_ee.json 下载/校验失败而退出 1，尚未运行测试。该任务由 ForgeGradle 给运行配置附加，专服 GameTest 不需要客户端语言资源；确认原进程已终止后，重试单次排除此任务，保留编译、数据包/结构资源处理和服务端运行。没有降低游戏校验或更改全局网络/TLS 设置。

新夹具加入默认命名空间 saodg_lobby，后续全量运行仍包含它。本轮没有执行其余 GameTest、JUnit、全量 build、真实网络客户端或带 SAO 的多人 UI 验收。实际原生社交队伍未在此独立环境实测；“不改原队伍”来自实现只写 Lobby 的边界，不是伪造 native 测试通过。当前新按钮尚未人工目测，开发包未部署。[产物](DEVELOPMENT_PACKAGE_0.41.11.md)。
