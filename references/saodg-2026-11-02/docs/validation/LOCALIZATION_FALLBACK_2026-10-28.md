# 默认语言回退修正

2026-10-28，0.34.0-dev 开发检查。
本机独立开发客户端已启动并加载资源，其 options 中语言为 `en_us`；仓库只有 `zh_cn.json`，默认语言无法取得模组中文，存在显示原始翻译键的问题。

在 Gradle `processResources` 中从唯一中文源生成同内容的 `assets/saodg/lang/en_us.json`，使 Minecraft 的基础语言回退取得中文。
不维护第二份手写翻译；源 JSON 的更新由资源任务自动带入两份构建资源。

使用 JDK 17 和原 D 盘缓存实际执行 `gradlew.bat processResources --offline --console=plain`，9 秒通过，任务实际执行。
日志 `logs/localization-fallback-2026-10-28.log`。
逐字节 SHA-256 比较中文源、构建中文、生成的默认回退三份一致；生成 JSON 可正常解析，标题与战绩标签可读取。
共 396 个键，SHA-256 为 `ea6c48891825d08f00e900585179920806816e57de2007a2b70607f741d7e32b`。
本轮只运行资源任务，没有重新构建 JAR，也没有重复运行 Java 单测/GameTest。

窗口捕获先后返回 `FrameArrived timed out: timed out waiting on channel` 和 `window capture timed out: timed out waiting on channel`，已停止自动窗口输入，客户端由用户人工检查。
上述资源生成验证不等同于最终 GUI 已渲染正确；英文/简体中文切换、资源重载、文本布局和真实端点仍以后续客户端检查为准。
此前启动的开发客户端可通过 F3+T 重载资源进行检查，亦可切换简体中文；当前运行目录资源已更新，正式整合包未部署。
