# 客户端第二次启动：Java C2编译器崩溃

用户启动0.41.51后仍报告退出。这次没有新的Minecraft崩溃报告，实际新增 `hs_err_pid15408.log` 与 `replay_pid15408.log`；latest.log止于10:27:32。证据已保存在忽略目录 `logs/client-startup-20261030-102733/`，未将可能含启动参数的JVM原始报告提交Git。

## 实际证据

- 新日志明确输出 `SAODG PFM palette supplier guard applied to net.minecraft.client.renderer.texture.atlas.SpriteResourceLoader`，证明0.41.51保护已经实际安装。
- 此次日志没有上一轮Image is not allocated或EffekseerManager异常；但资源重载尚未完成，因此不能据此宣布上一轮问题完全解决。
- JVM原始报告为EXCEPTION_ACCESS_VIOLATION 0xc0000005，problematic frame位于jvm.dll。当前线程C2 CompilerThread0，Current CompileTask为 `jdk.internal.math.FloatingDecimal$ASCIIToBinaryBuffer::floatValue`。
- 实际Java为Temurin17.0.20.1+1。上述证据定位这次直接退出发生在JVM编译器；没有证据认定其一定属于某个已知JDK缺陷，亦不能据此排除其他本机因素。

## 本机定向绕过

保持模组0.41.51和当前Java不变，只在SAO-0.8.json已有arguments.jvm数组末尾增加：

```text
-XX:CompileCommand=exclude,jdk.internal.math.FloatingDecimal$ASCIIToBinaryBuffer::floatValue
```

先从报告的实际加载jvm.dll路径找到同一Java运行时，以该参数执行-version：退出0，明确输出CompileCommand exclude目标及bool exclude=true。该检查证明参数可识别，不等于游戏启动通过。

修改时确认Java/Minecraft已停止，备份原JSON并核对并发修改；JVM数组从27项变为28项。回读移除新增参数后，与原JSON对象完整相等，其他配置未改变。回执与原件在：

`D:/Minecraft/.minecraft/versions/SAO-0.8/.saodg-backups/jvm-c2-4968951fcd754308b2b93d85ced12c5d/receipt.json`

回退时应先确认客户端停止、当前文件散列等于回执after_sha256，再还原同目录SAO-0.8.json.original，避免覆盖后续人工修改。未修改全局启动器配置、其他实例或服务器，未关闭整个JIT，也未重新构建模组。

## 待确认

用户退出并重新打开PCL后，实际确认已进入主菜单。新日志10:39显示PFM保护应用，方块与盔甲纹饰等图集、Effekseer与声音初始化完成，5个原资源包保留，98/98脚本加载且0错误/0警告，未出现两轮先前异常。对运行中的Java28108执行只读VM.flags查询，实际CompileCommand包含上述exclude，证明实例参数已生效。证据 `logs/client-startup-20261030-1039/verification.json` 与同目录latest-mainmenu.log、compile-command.txt。

用户进一步确认新局哥布林/尸鬼显示、星标清理后开门与跨房通行均正常，但报告画面掉帧、转视角卡顿。该反馈不能视为性能验收；目前继续采样定位。第一次计划采样时Java28108已退出，JFR未启动，不能将失败的采样当作性能证据；后续Java33068已启动，等待实际进入副本再取现场样本。绕过措施已证明这一次启动能完成，尚不能证明长期稳定或掉帧原因。
