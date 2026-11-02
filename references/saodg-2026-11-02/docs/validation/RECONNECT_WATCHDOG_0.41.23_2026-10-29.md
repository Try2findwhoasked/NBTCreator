# 重连期间的成员状态计时：0.41.23

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

源码 `933a3016e3cd486e2e5466cff2a8516b9af240ac`。原生人物离线时不更新倒地倒计时，但迷宫区保留的 `downedSince` 和 `uncertainSince` 仍以服务器时间计算。窗口内重连后，离线时间可能被当作异常在线时间，引发 `downed_state_timeout` 或 `member_state_unknown` 整局中止。

本版按实例记录实际登出时点；成功回到服务端确认的检查点后，将上述两项已有计时起点平移实际离线 tick 数，保留此前累计的在线时间。没有清除原生倒地状态、增加生命或授予救援贡献。重复登出通知不延长原重连截止时间；超时、淘汰及实例结束仍按原流程回城，返回完成移除离线标记。记录仅存在于当前进程，重启仍中止旧局；无协议、数据包或持久存档格式变化。

独立已提交源码导出 `.gradle/source-release-933a3016e3cd-20261029-055017-ebb78b13` 编译/重混淆/包内检查通过；41 个已提交结构、482 个中文键，排除 beta。开发包 `build/verified/0.41.23-dev-933a3016e3cd-20261029-055017-ebb78b13/saodg-0.41.23-dev.jar`，SHA256 `f79eb5a517976cc17d2989bfbd62c695b0315bed74ee1d2be3a5b7fe8f965cc8`。未运行 JUnit 或全套回归，未修改/启动用户客户端、原服或私有整合包服。

必要运行检查仅选择既有 `saodg_reconnect` 夹具：实际双人物准备/生成，PlayerList 保存和移除，窗口内同 UUID 新身体重登可信房间，超过窗口回原位置/模式、重复重登拒绝旧身份，资产与生产清理。新增断言显式预置两项 watchdog 起点，通过真实登出/登录事件验证只排除离线时间，且过期回城撤销离线标记；不伪装成原生 SAO 倒地或真实远程客户端覆盖。

```powershell
.\gradlew.bat '-Dnet.minecraftforge.gradle.check.certs=false' runGameTestServer --offline --console=plain -x downloadAssets -x downloadMCMeta '-PgameTestNamespaces=saodg_reconnect' '-PgameTestRunDirectory=run/gameTestServer-reconnect-watchdog-04123'
```

1 项必要 GameTest 通过，Gradle 53 秒、退出 0；生产清理完成并释放真实槽位。日志 `logs/reconnect-watchdog-04123-20261029.log`，SHA256 `9d85f3ca6dc4680255f9262df70f3883cf1bfc33a9172c82b092c85a36841602`。完整 F07/F08/C06/C07 与目标整合包倒地断线重连、远程网络和故障矩阵仍待验收。
