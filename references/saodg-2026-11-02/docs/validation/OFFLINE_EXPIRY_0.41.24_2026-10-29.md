# 有效成员全部离线：0.41.24

源码 `8d2538bb41d113b27d7fcfc81055e6f5b99a724c`。修复已有淘汰成员在线回城时，最后有效成员离线到期被判为 `party_defeated` 的问题：离线到期判断只检查未淘汰成员，且要求至少还有一名此类成员；全部淘汰仍按团灭，不因空集合误报离线。窗口内保留资格、窗口后系统中止和离线回程日志规则保持。无协议或持久格式变化。

已从提交独立导出、编译和重混淆打包，41 个已提交结构、482 个中文键，未包含 beta。开发包 `build/verified/0.41.24-dev-8d2538bb41d1-20261029-055435-a1fc4781/saodg-0.41.24-dev.jar`，SHA256 `d3227588c2f3da0d1b9912ecdcab534e2f405e06cb814e4daf80cf77e43e0858`。

仅扩展并运行既有 `saodg_reconnect` 的 1 项 GameTest，50 秒、退出 0，全部通过。使用实际 PlayerList 保存/移除及新身体登录事件；无手工伪造 logout/login 回调。先完成原有可信房间重连、watchdog 计时、成员超时回城和旧身份拒绝，再验证：

- 淘汰成员实际在线留在外界，最后有效成员实际离线 5 tick，实例时钟继续、已注册敌人数不变。
- 最后有效成员在窗口内用同 UUID 新身体登录，恢复本实例，原身体不重新获得身份、库存保持；随后再次离线。
- 有效成员离线期间未生成另一批敌人，窗口后及时以 `reconnect_window_expired` 终止。
- 生产清理释放实际槽位，仍为离线人物保留一份持久回程；其在清理后实际登录，回原位置、原模式、原库存，回程日志释放且无旧玩法身份。

命令在独立导出执行，复用已验证 1.20.1 下载元数据：

```powershell
.\gradlew.bat '-Dnet.minecraftforge.gradle.check.certs=false' runGameTestServer --offline --console=plain -x downloadAssets -x downloadMCMeta '-PgameTestNamespaces=saodg_reconnect' '-PgameTestRunDirectory=run/gameTestServer-offline-expiry-04124'
```

日志 `logs/offline-expiry-04124-20261029.log`，SHA256 `9ae2c51136902a27d7632c3d3184f502fa06f84babfd992c504a681052747a34`。没有运行 JUnit、全量套件、原生 SAO 倒地或真人远程客户端；没有更新用户客户端、原服或授权私有整合包。此证据只补 F07/C07 的上述流程，完整首领离线/重连、濒死和多人兼容仍待验收。
