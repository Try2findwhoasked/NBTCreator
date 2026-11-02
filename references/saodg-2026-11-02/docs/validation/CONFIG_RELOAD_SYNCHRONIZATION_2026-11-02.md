# 配置值写入与自动重载同步

2026-11-02，Minecraft 1.20.1 / NeoForge 47.1.106 / Java 17。基于已完成完整回归的0.5.4开发修改继续，未修改房间模板、实体属性、刷怪预算、存档格式或配置键。

## 已确认的问题及修复

此前两轮完整默认GameTest均出现NightConfig `Table with path [difficulty] has been declared twice`。本轮用实际NightConfig 3.6.4的 `WriteSyncFileConfig`、`TomlParser`、自动保存包装和双线程重现：重载线程持有文件锁并清空/解析配置时，未保护的 `set` 先修改共享表，再在保存时等待同一文件锁，导致解析器看到提前出现的difficulty字段并报重复表。

新增 `ReloadSafeFileConfig`，让SAODG通过ForgeConfigSpec进行的读取、设置及保存使用底层同步文件加载器的同一把锁；等待重载完成后再改数据，而不是先改数据再等待保存。首次加载和后续重载事件都接入包装。保持原文件对象、文件路径、注释、自动保存、文件监听和Forge校验，不复制到另一份配置，也不关闭自动重载。

兼容代码仅针对项目固定的NightConfig 3.6.4同步文件实现：隔离反射读取已知包装中的底层锁，最多解包8层，遇到未知文件实现明确拒绝。无文件的内存配置保留原对象。未将此反射适配扩展为任意NeoForge/Forge版本承诺，未修改依赖版本或系统JDK。

## 已完成验证

- `ReloadSafeFileConfigTest`三项全部通过：原实现必现重复表；修复后同样的调度下写入等待解析、其他表及最终布尔值完整保存；非文件配置不变、重复包装幂等，普通保存/回读正常。日志 `logs/config-reload-guard-focused-20261102.log`。
- 首次集成运行 `saodg_config`八项通过，证明同步包装在实际NeoForge模块/类加载环境中可安装，既有配置事务及权限等检查通过。
- 新增真实文件监听夹具后，最终新世界 `run/config-reload-watcher-single-write-20261102` 九项全部通过。实际编辑服务器TOML，等待重载及同步包装重新安装；连续128次写入后检查最终值及独立解析；恢复原值并等待再次重载后才结束。日志 `logs/config-reload-watcher-single-write-20261102.log`。
- 上述成功运行未记录 `ConfigLoadingException` 或重复表错误；没有以直接调用重载回调代替真实文件监听。

## 文件监听夹具发现的独立限制

NightConfig 3.6.4的文件监听器忽略 `MODIFY` 合并计数大于1的事件。在这台Windows机器上，用原生WatchService探针连续两轮观察到：截断后写入的事件计数为2，同长度原位写入为1。首轮真实监听夹具因截断保存事件被忽略而超时；更换事件计数观测方式仍超时。最终夹具使用不截断的单次同长度写入；自动保存突发事件排空后，必要时再用单次原位写入触发实际监听。该方式没有改变要验证的值，也没有绕过解析、重载或属性恢复。

此限制不由本次锁修复解决，不能据此承诺任意外部编辑器保存方式都能自动重载。游戏内管理员配置直接写入生效；JSON遭遇配置在新开局主动重读，与此TOML监听限制无关。探针源码与输出位于忽略目录 `build/config-reload-event-probe/`，不是生产组件。

## 中间失败与最终完整检查

- 第一次单元运行在回读断言处遇到泛型重载导致的类型转换错误；修正显式Boolean类型后，三项通过。没有改变复现或加锁断言。
- 一次重跑在进入测试前，Oracle JDK17.0.12的javac JIT发生访问冲突，Gradle进程终止；崩溃记录 `hs_err_pid19112.log`。重试成功，没有把它归为业务断言失败，也没有修改系统Java。
- 修复后的未过滤完整构建通过，耗时15分40秒；JUnit194项，192通过、2项可选原生二进制测试跳过，失败/错误为0。日志 `logs/config-reload-full-build-20261102.log`，完整XML及统计归档在 `logs/config-reload-unit-verified-20261102/`。跳过项仍来自未提供参考JAR的SaoRangedItemsTest，不代表该原生弓二进制已验收。
- 新世界默认套件首轮在进入测试前发生JVM访问冲突，位置在jvm.dll的GC线程，未得到业务断言结果。崩溃日志 `run/config-reload-core-20261102/hs_err_pid12584.log`。曾尝试现有JRE17.0.2作专服启动器，但Gradle工具链一致性检查拒绝混用，未启动游戏；没有修改系统安装。随后沿用原JDK17在新世界 `run/config-reload-core-retry-20261102` 重试，86项全部通过，耗时10分21秒，日志 `logs/config-reload-core-retry-20261102.log`；未记录重复表或ConfigLoadingException。
- CI功能组17项全部通过：`run/config-reload-features-20261102`，日志 `logs/config-reload-features-20261102.log`，未记录重复表或ConfigLoadingException。

启动完整构建时的源码/资源哈希为 `logs/config-reload-source-before-20261102.json`；此后只调整了真实监听GameTest的观测/写入方式，生产代码未再变化。上一轮191项JUnit及85+17项运行测试的结果属于修复前快照，见[历史完整回归](FULL_REGRESSION_0.5.4_2026-11-02.md)，不能代替本轮最终结果。

未部署、推送或发布。真实整合包、多客户端和生产经济验收仍不由独立开发测试证明。

当前新快照产物：`build/libs/saodg-0.5.4-neoforge-dev.jar`，4,112,548字节，SHA-256 `920c51fd13e65f9301b0f7cb64906a330fbdf3c33fbb29ca5469651cac5ab01a`。ZIP完整性、340份生产模板与源码逐字节一致、中文/默认语言一致、含同步包装类且不含GameTest类检查通过，记录 `logs/config-reload-artifact-20261102.json`。默认86项和功能17项均已结束并通过；两项可选单元测试跳过及外部编辑器监听限制仍按本文范围保留。

最终开发验收矩阵见[模组优化与配置扩展验收清单](IMPROVEMENT_ACCEPTANCE_0.5.4_2026-11-02.md)。本轮工具35项及内容审计亦已复核通过；没有将开发验收替代正式整合包验收。
