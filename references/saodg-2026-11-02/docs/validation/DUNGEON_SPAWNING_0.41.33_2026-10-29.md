# 副本自然刷怪扫描：0.41.33

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

源码 `3cd243e694e306f46d784cd4a5740951b60c7663`。仅在副本维度每次服务端 level tick 开始时关闭区块自然刷怪标志，避免强加载区块继续执行自然刷怪候选搜索；普通维度与 `doMobSpawning` 游戏规则不变。难度更新会重设标志，因此每 tick 重新应用。显式生成的副本敌人不依赖该标志，后续原生主线重跑结果见下文。

独立源码导出打包成功，41 个结构、496 个中文键，未包含 beta。随后在同一导出运行 `runGameTestServer packTestJar --offline --console=plain -x downloadAssets -x downloadMCMeta -PgameTestNamespaces=saodg_spawn -PgameTestRunDirectory=run/gameTestServer-spawn-04133`：1 项必要 GameTest 通过，Gradle 正常退出，43 秒。验证真实 level tick 关闭副本标志、普通维度及游戏规则保持，以及同难度强制刷新标志后再次应用。没有重跑 JUnit 或完整套件，也未替换用户客户端或原服。

日志 `logs/dungeon-spawn-04133-20261029.log`，SHA256 `94e484280e50be6fbebc458dafe8ddb0a405b23cc9fc6143cf05d482a8570a15`。

开发包 `build/verified/0.41.33-dev-3cd243e694e3-20261029-075710-0ee47e44/saodg-0.41.33-dev.jar`，SHA256 `0167436130aa956398bae9cf14b1c375c959597c2d3342bb0ea26b255680de84`。包含此前的 `door_y` 和默认开放实例生成/启动设置，详见 [门高与入场配置](ROOM_HEIGHT_ENTRY_0.41.21_2026-10-29.md)。

修改前另对 0.41.32 在已授权私有测试服采集 JFR：原生双人主线再次通过，17 个死亡/经验确认、合计 440 XP，回程/清理成功。进程正常停服，夹具归档，217 份既有人物相关文件保持，配置未变；保全记录 `logs/native-trial-profile-preservation-20261029.json`。本次未复现此前约 19 秒延迟，不能宣称已定位或解决。控制台秒级试炼窗口内记录的 GC 最长约 27ms、主线程等待最长约 73ms；这些是采样/阈值事件记录，不代表所有耗时上限。原记录 `logs/native-trial-profile-20261029.jfr`，摘要 `logs/native-trial-profile-summary-20261029.json`。

## 原生整合包主线回归

随后仅升级已授权目录 `run/pack-acceptance-20261028-081137-fd148a65` 到上述 0.41.33 包；旧包、完整世界与配置备份于 `validation-history/native-trial-04133-d2e0dd75`。复用内容相同的 packTest 夹具，SHA256 `17b45fea281610c4d5bdeaaebb6f242829e282615330ddd330a216f08b5c4e7b`；私有服磁盘生成/启动与奖励开关保持 false，仅夹具同步开始请求期间暂时开放入场并立即恢复。未修改用户客户端或原服。

真实原生队伍邀请/接受、两人物大厅准备、种子 0 正式生成与入场通过：832012 次放置写入、215 个生成 tick、176 张票据；4 道钥匙门、封印大厅多轮、封印大厅传送门全队进入独立首领、首领成功和各自历史、回程与生产清理通过。17 个确认死亡对应 17 个原生 XP 确认链接，人物经验分别增加 0 与 440，没有未决经验或成功奖励 offer。清理后 `runs/lobbies/pendingReturns/tickets=0`，所有槽位 FREE。仍使用无敌、高伤害和逐房传送，不证明远程客户端、战斗平衡、两队并发、支路内容或奖励资产验收。

进程 20720 正常退出 0，端口关闭，夹具已移入备份；897 份受保护文件中 894 份字节一致、2 份 properties 仅时间注释变化，另 1 项为预先声明的旧运行包替换。225 份既有人物相关文件保持，配置语义保持，没有意外变更。保全记录 `logs/native-trial-04133-preservation-20261029.json`。

- 报告 `logs/native-trial-probe-5ad79424-ad2d-43e9-b390-040e31eda998.json`，SHA256 `e9fd2257f8b0b0d1b5ce64b11948db90f2725b2b1a9b2c1589f6b187155ebdaf`。
- 控制台 `logs/pack-native-trial-04133-20261029.log`，SHA256 `789346b7644ff5f04583f97a9170948bc54f4217a6836267d2630e7f78f1e40a`。
- JFR `logs/native-trial-04133-20261029.jfr`，SHA256 `938cd240fd916c13df7315f6f4ea5f003779f790d3057932a4088715da8b4b61`。
- 只读 metrics 导出 `logs/native-trial-04133-metrics-20261029.json`，背景范围见同名前缀 context 文件。

性能记录不是达标结论：活动调度 406 样本 P95 18.224ms、放置 215 样本 P95 9.757ms、纯清理 209 样本 P95 3.605ms，释放前区块保存仅 1 样本 63.054ms，检查点 79 样本 P95 15.399ms；全服最后 100 tick P95 12.637ms 只覆盖局尾。此次仍未复现约 19 秒卡顿，保留启动附近 3030ms 警告。

JFR 按预约到完成的控制台秒级窗口流式读取，0.41.32 为 15:50:04～15:50:46，0.41.33 为 16:05:34～16:06:16。主线程执行采样分别 455/431，包含原版 `NaturalSpawner.spawnForChunk`（SRG `m_47029_`）的栈分别 93/56，GC 最大暂停约 26.619/34.645ms。映射来自本地 1.20.1 `server_mappings.txt` 与 MCP tsrg；计数文件 `logs/native-trial-profile-samples-20261029.tsv`、`logs/native-trial-04133-samples-20261029.tsv`。整服采样不能区分维度或换算固定加速比；普通维度仍可自然刷怪，不要求所有此类栈归零。副本标志行为由上述实际 level tick GameTest 证明，不用采样差异替代正确性证据。
