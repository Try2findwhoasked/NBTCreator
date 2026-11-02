# 实际离线与新人物对象重连

提交 ca5eb6777fde 的 ReconnectGameTest 在独立 Git 导出 .gradle/reconnect-ca5eb6777fde 中运行，未编译/覆盖仍运行中的 0.41.12 客户端类路径。命令 runGameTestServer -x downloadAssets -PgameTestNamespaces=saodg_reconnect -PgameTestRunDirectory=run/gameTestServer-reconnect-0412-20261029 --offline --console=plain，使用原固定 JDK/Gradle 缓存及单进程 ForgeGradle 证书自检跳过参数。

logs/reconnect-0412-targeted-20261029.log：1 项 required 通过，62 秒，正常全维度保存，退出 0。实际创建双人大厅、准备并生成完整地图（208 tick、144 票据），一人正常通过第一条开放连接，等待生产采样记录已发现的非入口房间，然后 PlayerList.remove 实际保存并移除人物。离线 5 tick 后以同 UUID 新 ServerPlayer/EmbeddedChannel 登录，自动触发真实 Forge 登录事件，回到记录房间预设落点；没有手动调用 loggedOut/loggedIn 或注入 lastRoom。旧身体不再有实例所有权，钥匙/修订/资格、两人回程与完整 NBT 物品不变。

测试将自己的重连配置临时缩至合法最小值 20 tick；第二次实际离线等待 25 tick 后登录，只能回原位置和原创造模式，标记淘汰，释放本人回程；再换一个新身体登录仍不得恢复资格。在线同伴维持本局，最后走生产中止/清理，槽位 FREE、回程恢复原值，再恢复测试配置并移除人物。日志同一 UUID 的实际实体 ID 为 137→321→328→329。

这是独立 Forge 服务器内的 PlayerList 保存/加载、新身体及实际事件验证，不是真实远端客户端网络断线、SAO 濒死、跨进程恢复或双队联机验收；没有重跑其余测试、重新打包或更新用户游戏。未发现需要修改生产代码的问题，版本仍为 0.41.12。夹具已加入默认 saodg_reconnect 命名空间。
