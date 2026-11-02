# 0.41.15 副本队伍与普通队长开本

源提交：`5c44ea33162f2776b17dfd6f235e7b16f9dcc6c7`。用户要求创建/加入队伍，并反馈双人局无法开始。

## 行为

普通玩家可通过队伍页和命令创建副本队伍。邀请改为被邀请者明确接受后加入；聊天提供接受/拒绝按钮，队伍页提供同样入口。邀请令牌绑定接收者与大厅，120 秒内有效，每人同时一份；接受时重新检查名额、队长在线和占用。队伍关闭、邀请过期或处理过后，旧令牌不能再加入。发送邀请不改变名单；真正加入后清空全部准备。

移除客户端、网络请求和命令层对创建/开始的 OP 限制。开始仍由队长发起，要求全员准备、当前内容和进度条件满足、服务器启用开发运行且为 STANDALONE 等已有安全条件。界面显示队长身份，开始不可用时提供原因。正式预设和默认关闭配置保持。

协议 20；两端必须更新。无世界日志格式变化。副本大厅与邀请均为会话内状态，未改动 SAO 社交队伍与原服。使用方式见 [副本队伍](../PARTY_USAGE.md)。

## 实际验证

从提交创建独立 Git 导出 `.gradle/source-release-5c44ea33162f-20261029-022413-1ff0b9dd`，未修改运行客户端输出或 beta 结构。

- `tools/build_verified_release.py --java-home D:/Java/jdk-17 --package-only`：编译、重混淆及打包检查通过，41 个结构、中文回退和 Mixin/refmap 检查通过。
- 仅执行 `runGameTestServer --offline --console=plain -x downloadAssets -Dnet.minecraftforge.gradle.check.certs=false -PgameTestNamespaces=saodg_lobby,saodg_concurrent -PgameTestRunDirectory=run/gameTestServer-party-04115-20261029`；5 项必需测试通过，进程退出 0，Gradle 总用时 1 分 10 秒。
- 4 项大厅检查覆盖：原有离线踢人/修订确认；非 OP 创建和命令加入、邀请同意/拒绝/旧令牌/他人令牌/四人上限/关队/期限检查；普通玩家 UI 创建和接受意图；新动作编码及协议 19 拒绝。过期检查仅将目标邀请截止时间置于过去，不改全局时钟或配置。
- 双队检查使用 4 个真实 PlayerList/EmbeddedChannel 服务端人物；3 次双人开本均通过普通队长的 `/saodg start <revision> <seed>` 命令树发起，显式断言无 OP。继续验证两队隔离、居中钥匙门、退出清理、过期 UI 上下文和槽位复用。

三局实例：`8b5baf45-2810-4021-98af-1475df8a77c0`、`287d377e-46b4-4efd-83ee-31e70d69a784`、`b4ce9f57-d979-4d51-b4e6-9581aed20485`，均记录进入与清理释放。

日志：`logs/party-04115-targeted-20261029.log`，SHA256 `9f31d86f3f47c0dfde501d4d5ae100534a2057ffdc9244d147e8d1b2ea8fa29c`。

未重复全量 JUnit、全量 GameTest 或整合服验收；尚无真实远程双客户端、手动按钮布局和聊天点击反馈。本轮没有启动或重启用户客户端，也没有更新原整合服。

## 开发包

`build/verified/0.41.15-dev-5c44ea33162f-20261029-022413-1ff0b9dd/saodg-0.41.15-dev.jar`

SHA256：`4c1638f3033a86f3dac7365b04b7745197627b58d4236ac8557ba5295e1567c3`。
