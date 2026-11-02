# 符文传送门开启效果（2026-10-31）

基于已有未提交的 `0.41.65-dev` 工作区修改；保留其他聊天的改动，不提交、切换分支、推送或创建标签。

## 改动范围

- `EncounterService.updateDoors` 在实际尖拱门面从全空变为开放时触发一次；先执行既有外来方块检查。已有门面刷新、部分修复、关闭不重播。
- `RunePortalEffects` 从实际旋转后的完整门面计算底边中心，向附近本局成员发送一个原版闪电生成包、门面电弧及扩散气流。服务端不添加闪电实体，避免伤害、点火、雷击实体事件和跨实例实体追踪。
- `DungeonSounds` 新增 `rune_portal_open`，使用独立 48 格接收范围，其他空间声音仍保持 16 格。视觉和声音共用当前成员、在线、同维度、未淘汰、距离检查。
- 新增原创单声道风啸 `sounds/events/rune_portal_open.ogg`、声音定义与简体中文字幕。`generate_event_sounds.py --only rune_portal_open` 可单独重生成，保留其他 Ogg。
- 存档格式、现有自定义网络协议 23、门框资源、开门条件、钥匙消耗与全队传送规则不变。客户端和服务端需同步更新含新增注册音效的 JAR。

## 验证记录

运行环境：JDK 17、Forge 47.4.10、ForgeGradle 6.0.54、Gradle 8.8；未执行 `clean`。

- `gradlew.bat --offline test --tests cn.saodg.infrastructure.content.SoundAssetsTest compileGameTestJava '-Dorg.gradle.jvmargs=-Xmx1G -Dfile.encoding=UTF-8'` 成功；1 项 JUnit 检查全部 15 种声音的注册对应、字幕、Ogg Vorbis 标识、单声道、无孤立文件及风声的 48 格资源衰减配置。日志：`logs/rune-portal-effects-compile-20261031.log`。
- 新音频经 FFmpeg 解码为 float PCM，时长 1.65 秒、20803 字节，解码样本全部有限，最大绝对峰值约 0.647，无削波。
- 首轮运行时共 3 项测试，原有符文四向放置/回收与声音隔离通过；新增夹具错误使用槽位 5 和五名成员，触发现有快照校验。夹具已调整为合法槽位 2 和四人队伍，未放宽生产校验。首轮日志：`logs/rune-portal-effects-runtime-20261031.log`。

- 第二轮新增夹具直接跨维度传送，被既有准入保护拒绝，未收到预期落雷包；改为复用运行时测试的受控传送工具，未绕过生产保护。日志：`logs/rune-portal-effects-runtime-retry-20261031.log`。
- 后续共享目录编译因 `build/tmp/compileGameTestJava/compileTransaction/stash-dir` 文件占用失败，未执行测试；未删除目录、停止其他聊天的客户端或运行 `clean`。日志：`logs/rune-portal-effects-runtime-final-20261031.log`。
- 最终改用本地忽略的 `logs/rune-portal-validation.init.gradle` 在配置前设置独立 `build/rune-portal-verification`，配合 `--project-cache-dir build/rune-portal-project-cache` 隔离编译缓存。该文件仅改变本轮构建输出位置，根构建配置未改。

独立目录最终复测：

```powershell
.\gradlew.bat --offline -I logs/rune-portal-validation.init.gradle --project-cache-dir build/rune-portal-project-cache test --tests cn.saodg.infrastructure.content.SoundAssetsTest runGameTestServer '-Dorg.gradle.jvmargs=-Xmx1G -XX:ActiveProcessorCount=2 -Dfile.encoding=UTF-8' '-PgameTestNamespaces=saodg_rune_portal,saodg_sound' -PgameTestRunDirectory=run/gameTestRunePortalEffectsIsolated20261031
```

`BUILD SUCCESSFUL`，1 项 JUnit 和全部 3 项必需 GameTest 通过。日志：`logs/rune-portal-effects-isolated-validation-20261031.log`；JUnit XML：`build/rune-portal-verification/test-results/test/TEST-cn.saodg.infrastructure.content.SoundAssetsTest.xml`。

- 新增 `RunePortalEffectsGameTest`：在合法四人快照和实际 PlayerList/EmbeddedChannel 上，四向实际开启门面；近处与 30 格本局成员各收到恰好一个正确落点的闪电包、一个指定风声包和粒子包；同坐标非成员、60 格外、跨维度及近处淘汰成员收不到表现。验证服务端不存在对应闪电实体、重复刷新/部分门面修复/关闭/外来方块失败无重播、钥匙数量不变。
- 既有 `RunePortalGameTest`：四向实际建筑放置、完整门面、门框保护、伪造入口拒绝、Boss 四格场地回收和票据释放仍通过。
- 既有 `SoundGameTest`：原有 16 格空间提示、当前实例成员隔离、队伍提示与个人传送提示边界仍通过，新增声音在专用服务器注册成功。

最终打包：

```powershell
.\gradlew.bat --offline -I logs/rune-portal-validation.init.gradle --project-cache-dir build/rune-portal-project-cache build -x test '-Dorg.gradle.jvmargs=-Xmx1G -XX:ActiveProcessorCount=2 -Dfile.encoding=UTF-8'
```

`BUILD SUCCESSFUL`；JUnit 结果取上方独立定向运行，未把 `-x test` 打包写成全量测试通过。日志：`logs/rune-portal-effects-isolated-build-20261031.log`。

产物：`build/rune-portal-verification/libs/saodg-0.41.65-dev.jar`，3975751 字节，SHA256：`c2cdda5acd4ff9b1be0226062bcec7455b5fa6e0fa79377f85d65a62a4bc58a2`。这是隔离目录下的正式模组 JAR，不使用 `pack-acceptance` 测试附加包。

包内检查通过：`RunePortalEffects.class`、全部 15 个声音定义、新增 Ogg、48 格声音衰减设置、`zh_cn` 与构建生成的 `en_us` 字幕均齐全，不包含 GameTest 测试类。机器可读检查结果：`logs/rune-portal-effects-artifact-20261031.json`。源码改动已停止，Git 收尾交由维护聊天统一处理。

## 验证边界

没有运行默认全量 JUnit，不宣称原有钱包隔离问题已修复。服务器测试玩家与数据包检查不等同于真人双客户端、音量混音/实际听感、客户端雷击渲染或重连/重启体验验收。未部署至现有客户端、服务器或世界；未修改忽略的参考仓库及作者资产。
