# 0.41.9 开发测试产物

来源提交 9ebf0ccbf67cb889686571ef7ba01a9fc2739960，通过 git archive 导出干净目录，以 tools/build_verified_release.py --java-home D:/Java/jdk-17 --package-only 编译/reobf。该进程临时 JAVA_TOOL_OPTIONS 仅关闭 ForgeGradle 联网证书环境自检以保持离线；无全局配置修改。

产物 build/verified/0.41.9-dev-9ebf0ccbf67c-20261028-234156-312d0e83/saodg-0.41.9-dev.jar，SHA-256 为 974c61c85161fc16864a2d26128bb71af6caa4fa57e736dac264e06d35a76dd1。同目录 verification.json 明确 packaging_only、JUnit 未执行、运行时测试未执行。包内 41 个已提交结构、441 个语言键，排除用户 beta 素材、夹具与运行数据。

包含原收件人端口约束、管理员有界性能窗口/分阶段及作业计时、临时原版僵尸的原生 XP 延后捕获修复。各定向测试范围见相应记录，不表示当前全部代码重新通过全量回归。

仅装入已授权私有副本 run/pack-acceptance-20261028-081137-fd148a65，安装前确认无 Minecraft 进程/25579 监听。旧 0.41.8 JAR 保留在 validation-history/native-xp-0419-20261029，安装回执记载前后散列及临时 pack-acceptance 夹具散列；正式入场和奖励均为 false。没有更新原整合包、原服或开发客户端，不是正式发布。
