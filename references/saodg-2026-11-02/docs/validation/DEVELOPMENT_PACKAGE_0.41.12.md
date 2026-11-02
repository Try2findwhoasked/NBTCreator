# 0.41.12 开发测试包

源码提交 885b4c79ec683551b7e0b7573e49723d7e677568（feat(map): reveal adjacent outlines and diversify merged rooms）。从 Git archive 的独立目录编译/reobf，未混入 beta 素材、测试夹具、世界或运行数据。

- 产物：build/verified/0.41.12-dev-885b4c79ec68-20261029-002537-580d8874/saodg-0.41.12-dev.jar
- SHA-256：cd79e890604b0c2e8e4374f800fef04f474b07983f41774c02be33273002495a
- 源码目录：.gradle/source-release-885b4c79ec68-20261029-002537-580d8874
- 日志/报告：产物同目录 build.log、verification.json；汇总 logs/package-0412-20261029.log。

使用 tools/build_verified_release.py --java-home D:/Java/jdk-17 --package-only。本步骤只是 packaging_only，没有重复 JUnit 或运行时测试；该修改已有根工程的 8 项布局定向 JUnit（30,000 种子）及 1 项地图投影 GameTest，通过范围见 [记录](MAP_LAYOUT_0.41.12_2026-10-29.md)。包内 41 个结构、456 个语言键的中英文回退、版本、Mixin/refmap 等检查通过。未部署原整合包或私有兼容服，正式准入仍关闭。

协议 17，两端同时更新。内容 ruins-dev-18；新大房分布只对新开局生效，不重拼现有活动局。客户端可重点查看：未知轮廓只延伸相邻一层；进入房间后显色；自己/队友不再固定在格心且有朝向；试炼至少两个大房，标准至少三个，精锐至少四个。阵亡地图需要其他成员继续维持本局，单人团灭会结束，不能据此测试观战。

打包后再次确认没有 Minecraft 客户端进程，使用原 runClient 环境启动，未自动进入世界或注入按键。会话 40621，日志 logs/client-04112-manual-20261029.log；08:26:43 纹理资源完成，实际 PID 10344 存在 Minecraft* Forge 1.20.1 窗口。日志记录 saodg 0.41.10-dev → 0.41.12-dev 版本变化及既有 Realms 提示，未宣称已经目测新地图或验证实际存档升级。客户端使用工程开发输出，不将其启动外推为独立 JAR 部署/联机验收。窗口交用户操作，不主动关闭或重启。
