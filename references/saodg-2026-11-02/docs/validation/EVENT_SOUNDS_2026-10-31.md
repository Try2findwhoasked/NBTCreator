# 事件音效专项验证（2026-10-31）

分支：`codex/event-sound-effects`。基于已有未提交工作区继续开发，保留原有改动；沿用工作区版本 `0.41.65-dev`。本轮范围和事件映射见 [EVENT_SOUNDS.md](../EVENT_SOUNDS.md)。

## 已验证

- JDK 17 / Forge 47.4.10 / ForgeGradle 6.0.54，未执行 `clean`。
- `test --tests cn.saodg.infrastructure.content.SoundAssetsTest`：1 项通过，核对每个注册音效的声音定义、中文字幕、Ogg Vorbis 标识、单声道格式及无孤立资源。证据：`build/test-results/test/TEST-cn.saodg.infrastructure.content.SoundAssetsTest.xml`、`logs/event-sounds-validation.log`。
- 14 个音频全部经 FFmpeg 解码为 float PCM，检查非空、有限值、无峰值削波。时长 0.16～1.47 秒，解码峰值最高约 0.778，全部音频合计 123080 字节。
- JAR 资源检查：14 个声音定义和 Ogg 文件齐全，`zh_cn` / 构建生成的 `en_us` 都有全部字幕，未包含 `SoundGameTest`。
- `runGameTestServer '-Dorg.gradle.jvmargs=-Xmx1G -Dfile.encoding=UTF-8' -PgameTestNamespaces=saodg_sound -PgameTestRunDirectory=run/gameTestEventSounds20261031Retry`：1 项运行时测试通过，`BUILD SUCCESSFUL`；证据：`logs/event-sounds-runtime.log`。测试构造三名实际加入 PlayerList 的服务器玩家，以 EmbeddedChannel 检查发送的原版声音包，覆盖以下边界：
  - 同坐标另一实例成员收不到声音。
  - 16 格以外的本实例成员收不到位置声音。
  - 共享进度提示可到达远处本实例成员，排除其他实例。
  - 淘汰成员不接收副本进度提示，但仍可接收自己的传送/返回提示。
  - 历史名单保留但当前实例成员关系已移除时，不发送位置声音。
  - 全部 14 种声音事件在专用服务器中注册成功。

第一次包含构建、JUnit 和运行时测试的组合命令在服务器启动期间失去进程，未产出完成结果；其 JUnit XML 已确认通过，运行时通过结论仅取独立重试的成功日志。

最终打包使用 `build -x test '-Dorg.gradle.jvmargs=-Xmx1G -Dfile.encoding=UTF-8'`；日志为 `logs/event-sounds-final-build.log`。产物：`build/libs/saodg-0.41.65-dev.jar`。不把同目录的 `pack-acceptance` JAR 当成正式模组。

## 验证边界

未运行默认全量 JUnit，不宣称既有钱包隔离失败已修复。运行时专项测试验证声音注册与数据包发送边界，没有穷举各业务事件的触发过程、真实网络客户端混音或实际听感。未运行真实双客户端、重连/重启声音体验或生产验收。未部署到任何现有客户端、服务器或世界。
