# 0.41.11 开发测试产物

来源提交 4b6615f8f705469df154a0a5cb0d522e6a2fbf94，tools/build_verified_release.py --java-home D:/Java/jdk-17 --package-only 从 git archive 的独立目录编译/reobf；没有覆盖运行中 0.41.10 的工程 build/classes 或 build/resources。

产物 build/verified/0.41.11-dev-4b6615f8f705-20261029-000841-fcafe402/saodg-0.41.11-dev.jar，SHA-256 为 e026383f5c543120364ef5f7680535be350c30b7363d089d926741af7660ba6e。报告为 packaging_only，JUnit/运行时测试未由打包器执行；包内 41 个已提交结构、455 个语言键，不含用户 beta、测试夹具、世界或运行数据。

新增房主移出本次大厅成员的服务端用例与按钮，可处理离线成员。名单变动清空准备并增加修订，不修改 SAO 社交队伍。新增 REMOVE_MEMBER 意图采用协议 16，旧 15 客户端被拒绝，两端须同时更新；世界/奖励格式不变。原有客户端操作意图枚举位置保留。

此 JAR 尚未安装任何运行环境；用户开发客户端仍留在 0.41.10，私有兼容测试服仍为 0.41.9，原服未改。大厅交互尚未用户目测，正式入场/经济开放条件仍未完成。定向服务器验证另行记录，不与打包器结果混为全量通过。
