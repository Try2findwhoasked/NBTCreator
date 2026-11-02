# 公共大厅安全回程：0.41.26

源码 `cc3a417ce0ce74ebf3e0e8026bf505ea0958268a`。实现设计 3.3 和 F06 的缺失步骤：原安全返回点优先；原点不可用时尝试启用的配置大厅，再使用既有世界出生点搜索。大厅默认关闭，配置位于 `[safeReturn]`：`hubEnabled`、`hubDimension`、`hubX`、`hubY`、`hubZ`。坐标是脚部世界坐标，配置不会创建地板或清除障碍。

不存在/错误的大厅维度、非有限坐标、危险或堵塞的落点不作为目的地；即使物理安全也禁止 `saodg:dungeon`。保留原朝向/模式，以及现有传送后玩家文件回读、回程日志确认机制。没有安全目的地时仍保留待回程，不修改全服出生点或死亡规则。无协议、世界/回程日志 schema 变化，旧配置补入默认关闭的新项。

独立 Git 导出 `.gradle/source-release-cc3a417ce0ce-20261029-061542-73084fed` 编译/重混淆/包内检查通过；41 个已提交结构、482 个中文键，beta 排除。开发包 `build/verified/0.41.26-dev-cc3a417ce0ce-20261029-061542-73084fed/saodg-0.41.26-dev.jar`，SHA256 `6825c157a882aabb7edbc240bc3a377bc7cd20914db06d8f6f57330afb9c98c6`。

仅选择新的 `saodg_return` 运行检查，无 JUnit 或全量套件：

```powershell
.\gradlew.bat '-Dnet.minecraftforge.gradle.check.certs=false' runGameTestServer --offline --console=plain -x downloadAssets -x downloadMCMeta '-PgameTestNamespaces=saodg_return' '-PgameTestRunDirectory=run/gameTestServer-safe-return-04126'
```

夹具检查原点/大厅/出生点优先级，默认关闭路径、缺失或错误大厅维度、物理安全但禁止的实例维度、熔岩与头部堵塞；保留原角度和模式。随后实际 PlayerList 登录临时人物，显式安排持久回程标记（省略入场生成），执行生产 returnPlayer，检查真实传送、模式/朝向、日志释放及内存/实际人物文件完整库存一致。结束恢复配置、出生点和测试方块并移除临时人物。

1 项检查通过，43 秒、退出 0。日志 `logs/safe-return-04126-20261029.log`，SHA256 `4b1624fdaa092888ad1f0752ae31f0da6e75e6a759486951837e8fcb3986d67b`。未修改/启动用户客户端、原服或私有整合包；不代表真实远程多人、全部自定义维度或完整 F06 故障矩阵通过。
