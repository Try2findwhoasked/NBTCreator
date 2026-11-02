# 0.41.58 启动期间 JVM 垃圾回收线程崩溃

用户报告启动后闪退。当前新报告为客户端 `hs_err_pid46176.log`：Temurin 17.0.20.1+1，`EXCEPTION_ACCESS_VIOLATION`，当前线程 `GC Thread#1`，故障帧位于 `jvm.dll+0x30c049`，VM 正处于 safepoint。Minecraft 没有生成新的普通崩溃报告，末尾仍是模型/资源加载；没有发现本次新增 PointsOrb Mixin 的注入失败记录。此证据说明退出发生在 JVM 原生层，不能仅据此断言底层问题的唯一根因。

先切换到本机已有的 `D:/Java/jdk-17`（Oracle Java 17.0.12），它已完成本工程构建及同一原生属性点测试服检查。保留原 Temurin 安装、模组 0.41.58、JVM 单方法编译绕过和存档。没有以回退副本代码掩盖待验证的回收问题。

`tools/start_sao_client.ps1` 增加 Java 17 路径参数，默认使用上述本机路径。CheckOnly 不修改任何文件；实际启动时只在 PCL 自己的 LatestLaunch.bat 中替换唯一的 Java 可执行文件 token，并用独占文件访问检测缓存并发变化。账号参数仍留在原启动缓存，不复制进仓库或备份日志；日志只记录原/新 Java 路径。PCL 再次生成缓存后，通过本脚本启动仍会重新选择此 Java。手动在 PCL 启动时使用哪个 Java，取决于启动器自己的选择设置。

本次 CheckOnly 通过，实际进程 39356 的 ExecutablePath 已核实为 `D:/Java/jdk-17/bin/java.exe`。启动、存档载入及旧实例回收仍须依据后续运行结果确认；一次成功启动也不构成对 JVM 长期稳定性的保证。

后续日志于 16:22:53 记录游戏启动完成（约 68 秒），进程仍在运行，没有本次 PID 的新 JVM 致命错误文件。启动/客户端脚本分别为 23/23、19/19，均无加载错误。原测试存档载入及旧槽位回收仍待确认。

随后进入存档仍发生原生崩溃，报告 `hs_err_pid39356.log` 显示 Oracle 17.0.12 的 C2 CompilerThread0 在编译原版 `LootPoolSingletonContainer$Serializer::m_5921_` 时访问冲突。换 Java 未解决问题，不将前述主菜单启动记为修复完成。

已备份修改本实例 JVM 参数，加入 `-XX:TieredStopAtLevel=1` 临时禁用 C2，保留 C1 编译。实际进程参数已核对。参考 [OpenJDK 分层编译说明](https://cr.openjdk.java.net/~iveresov/tiered/Tiered.pdf)。这是一项诊断绕过，可能降低峰值性能，未据此断言崩溃的唯一根因。C1 默认编译缓存实测为 48 MiB、已用约 43 MiB，因此随后加入 `-XX:ReservedCodeCacheSize=256m`，防止整合包加载后很快耗尽缓存。实例 JSON 原件保存在客户端 `.saodg-backups/jvm-c1-1a4263633c` 与 `.saodg-backups/c1-cache-d56d8a23`。

系统随后发生重启，旧进程与工具会话已终止，未发现这轮进程的新 hs_err 文件；不将它当作程序正常退出或故障已解决。恢复测试时启动脚本增加可选 `-World` 参数，使用当前 1.20.1 原生支持的 `--quickPlaySingleplayer` 自动进入已存在的测试存档。普通脚本启动会移除之前缓存的 Quick Play 选项，不把它变成永久自动入档行为。依然不复制启动凭据。新的 C1/256 MiB 缓存进程及实际旧场地回收结果继续根据运行日志确认。

实际进程 4164 已核实 `TieredStopAtLevel=1`、`ReservedCodeCacheSize=268435456`。该轮成功自动载入原存档，17:41:08 人物实际登录，随后可继续游玩副本，未生成该 PID 的新致命错误报告。13 条遗留属性点来源已成为 PAID，并有一局正常清理释放槽位。其余旧局暴露的装备空槽与旧箭矢问题另由 0.41.59 处理，未将部分回收成功外推为全部旧局已完成。
