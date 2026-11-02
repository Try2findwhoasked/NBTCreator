# 0.41.8 开发测试产物

来源提交 `9f848296aaf43de7c26ff0d5e3b2819832b40ecb`，通过 `git archive` 导出干净目录，执行 `python tools/build_verified_release.py --java-home D:/Java/jdk-17 --package-only`。19 秒编译/重混淆成功，未执行本轮 JUnit、GameTest 或整合包验收。

产物：`build/verified/0.41.8-dev-9f848296aaf4-20261028-121209-c74b2eba/saodg-0.41.8-dev.jar`。

SHA-256：`9c8576fb8546ab5ef46df8b1d530481d8f181cfd08cd4bf84f00227875709465`。

同目录含 `verification.json`、`SHA256SUMS.txt`、`build.log`、`READ_ME_ZH.txt`。报告明确为 packaging_only、junit_passed=null，运行时测试未执行；不把历史定向测试当作这份包全量验收通过。检查了 41 个已提交结构、中文/默认语言一致、版本、四份 Mixin 配置/refmap，排除 beta、packTest、世界和运行输出。

汇总的实际改动：资产门禁读取 KubeJS/Forge 双命名空间、FTB 接收器代际撤销、领奖/归还旧快照冲突及容器提交复检、原生经验容器复检、管理员 `/saodg admin member <玩家>`。各项已执行及未执行的测试见本目录相应记录；外部 KubeJS 脚本/配置不在 JAR 内，仍需按 compat 材料审查安装。

打包时未部署。后续仅更新已授权私有副本至 0.41.8，原服和客户端未部署，见[合并验收](JOINT_0.41.8_2026-10-28.md)。正式入场/奖励不开放，市场、真实客户端视觉/多人、完整技能/经济故障与性能验收仍待完成。
