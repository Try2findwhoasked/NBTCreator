# 消息隔离合入 main：0.41.66-dev

2026-10-31。将 `origin/codex/dungeon-message-isolation` 的 `115b587282e0a512ed6ea74af4f6cec375c8e960` 合入原 main `1297cbbb5c626608795ab4a51e811d0d372d909a`，保留双亲合并历史。未改写已发布的 `v0.41.65-dev`。

## 冲突处理

- 保留现有实体奖励箱、归途门及安全回退；结算提示改用 `notifyRun` 按当前绑定发送，仍区分有门与无门提示。
- 保留通关经验结果索引、原生经验请求排队和胜利/失败音效；实例生命周期通知使用当前注册实例及真实连接筛选，冻结名单不单独构成权限。
- 保留继电机 Y/Δ 追加奖励和接线绘制；光束、接线和门提示均校验本轮遍历实例与玩家当前实例相同。
- 合并默认 GameTest 命名空间，同时保留 `saodg_foreign` 和新增 `saodg_messages`，不恢复过时的固定协议断言。
- 保留实体渲染器、原有客户端布局与注册，加入通知接收、快照上下文和 Clone/断线清空逻辑。
- 原版普通聊天仍走 `PlayerList.broadcastChatMessage`，只在逐人发送处筛选接收者，保留原始聊天对象、签名/过滤路径。控制台公告和其他不经过此路径的私聊/模组系统消息仍按原逻辑处理。

新增通知包占用服务端到客户端消息编号2。为同时区别已发布的协议23实体箱版本和旧分支协议22，本次使用 **0.41.66-dev / 协议24**，客户端和服务端需一起更新。新增 `notification_context` 仅为状态投影字段，没有世界日志或服务器配置迁移；正式准入、奖励和资产保护不因本次合并开放或放宽。

## 验证命令与结果

固定 Minecraft1.20.1、Forge47.4.10、ForgeGradle6.0.54、Gradle8.8、JDK17。所有构建输出及测试世界独立，未执行 `clean`，未修改玩家世界或参考仓库。

```powershell
$env:JAVA_HOME = 'D:\Java\jdk-17'
.\gradlew.bat -I logs/message-merge-validation.init.gradle --project-cache-dir .gradle/message-merge-validation --offline test runGameTestServer build -x downloadAssets '-Dorg.gradle.jvmargs=-Xmx1G -XX:ActiveProcessorCount=2 -Dfile.encoding=UTF-8' '-PgameTestNamespaces=saodg_messages,saodg_sync,saodg_lobby,saodg_circuit,saodg_rune_portal,saodg_sound,saodg_completion_rewards,saodg_exit,saodg_room_rewards,saodg_population,saodg_miniboss' -PgameTestRunDirectory=run/gameTestMessageMerge20261031b --console=plain
```

init 使用 `build/message_merge_validation` 独立输出，并限制 JavaExec 为2GB、2处理器；当前 JUnit 过滤仅排除 `LayoutTest.tenThousandActualContentSeedsAreReachableAndKeysPrecedeLocks*`。这三个已通过的重型参数用例（各10,000种种子）的布局实现、测试及房间/副本输入未被此次合并修改，保留0.41.65-dev的既有证据，不当作本次重新执行。

- **JUnit：166项，0失败、0错误、2跳过**。两项跳过是未设置外部职业弓参考JAR的可选二进制检查；不是一次默认完整单测套件全绿。
- **Forge：26/26必需GameTest通过**。包括六名真实PlayerList测试对象的双队/局外聊天、通知受众、生成/探索重叠、回程、重连与槽位复用；消息编解码、协议与状态增量；大厅；实体箱/归途门/经验恢复；Y/Δ挑战与防重；符文门效果、声音、原生数值、装备保护及68个战斗房间布点。
- **BUILD SUCCESSFUL（6m11s）**：主代码、GameTest与packTest编译，重混淆打包完成。`test` 在同一次调用中实际执行，未使用 `-x test`；上述三个重型用例的过滤仍需明确保留。

日志：`logs/message-merge-validation-retry-2026-10-31.log`。JUnit XML：`build/message_merge_validation/test-results/test/`。

首轮在编译前的 `extractSrg` 阶段遭遇 JDK17.0.12 原生 `EXCEPTION_ACCESS_VIOLATION`，Gradle守护进程退出；日志 `logs/message-merge-validation-2026-10-31.log`、`hs_err_pid3776.log` 保留。没有把它当作源码验证通过；限制验证进程资源后重试完成，未更改机器JDK、正式配置或生产代码以绕过检查。

## 开发包检查

`build/message_merge_validation/libs/saodg-0.41.66-dev.jar`，3,980,155字节，SHA256：

`2f1a174b9a3e99588ed9d8c5efa13c90c635d7f48f905d5267e96fbb51517f22`

已核对 `DungeonChatMixin`、`DungeonChatPolicy`、`DungeonNotice` 及现有实体箱/渲染/原生经验/符文类齐全。Mixin配置包含聊天拦截，refmap有两处对应SRG映射（广播与逐玩家发送）；中文和派生默认语言相等，不包含GameTest、packTest或beta模板。检查结果：`logs/message-merge-verification-2026-10-31.json`。开发JAR仍保留本地，不入Git。

## 范围限制

EmbeddedChannel服务端测试不等于真人多客户端或实际签名聊天端点验收；客户端卡片/旁白、聊天插件、真实延迟断线、重启恢复、完整SAO/KubeJS整合包和经济支付仍待实机确认。未部署至客户端或服务器，不将开发验证称作正式开本验收。原独立分支的协议22结果保留为历史记录，不覆盖本次版本与合并范围。
