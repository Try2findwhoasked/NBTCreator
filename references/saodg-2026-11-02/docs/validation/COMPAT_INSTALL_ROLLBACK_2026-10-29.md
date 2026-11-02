# 原始整合包脚本实际安装与回滚

使用现有 prepare_pack_validation.py，从只读源 D:/Documents/Coding/Game/Minecraft/SAO-server-0.7 创建独立副本 run/pack-acceptance-20261029-003817-bae61921。其 acceptance-manifest.json 记录复制 5612 个文件、121 个原始模组及已验证的 0.41.13 JAR；源/目标复制散列按工具核对。没有复制世界/人物，没有接受新副本 EULA 或启动服务；新副本保持 eula=false、准入/开发奖励关闭。已手工接入补丁的旧验收副本不参与此次安装。

执行 compat_profile_install.py --mode apply，原始 sao-server-0.7 六文件基线与精确补丁/Node 合并语法检查通过，回执先 PREPARED 后 APPLIED。独立读取安装后实际字节并确认每份 after 散列，再通过同一工具 --mode rollback 恢复；实际文件逐字节等于只读原服源文件，不仅是规范化文本相等，原始换行也恢复。

| 脚本 | 实际安装后的 SHA-256 | 回滚后的原始 SHA-256 |
| --- | --- | --- |
| sao_wallet.js | 0e127d525757465e5a6c1a9fda2155f802148c2c72874e9d24ed93f1c4d0898b | 56aa8354328d6a87a008b7dcc1f037a7944b826b140f52b0661bcb91c8a3f04a |
| sao_battle_monitor.js | b954647abf61224227097d1892738d4b54176e5f163f9ee2f25cba72f4233dec | c162b9fa83ea6c80411d1a7d4500194647f4b02cdba8215d353881ea0becafe8 |
| sao_boss_enrage.js | c7e4038cdb2e7505a9a6227c96a1f135c3a6bdb870cde9dd7198bedd68d23a3c | 1350ccfe45846ed1bb6bb1f726a8d8fd032ba4c60c43f238318724871f238fd4 |
| sao_combat_income.js | 7f123843d85399ec2ff4bec70cc4b4d154c420b440a9d00e1d6af907062be6ff | 5f2af2087baa37ce3fa4653b61bc87ce4b090a1e8e2a8515da2a6ab932a9d65c |
| sao_boss_armor_drops.js | c8ea5095eb34687cd7610898e26a8338cb0ff490276ebd260972444a7a48305b | 89a3b7059b6f298d8281096aea54db1b0bd918091b396a83fdba4263a29d2e06 |
| sao_quest_kill_history.js | 1668c450db848b0d17c9d6dbb15885458abd79858c08b9ce60f96b468a5433ab | 525a3ec8e97ba3f9c5931a51b165e8064427c4e4633dcae913049ede167a4449 |

回执最终为 ROLLED_BACK，保留于新副本 validation-history/compat-install-2e098ab2ce86436cbdaacbd64aed8124/receipt.json，六份 .original 备份未删除。前后单独比较 eula.txt、server.properties、defaultconfigs/saodg-server.toml 完全相同，确认 acceptance_world 不存在。

证据：logs/compat-rollback-copy-20261029.log、logs/compat-install-actual-20261029.log、logs/compat-install-rollback-actual-20261029.json。脚本工具命令和字节/回执断言均退出 0；没有重跑既有五项临时目录单测、Gradle 或 Minecraft。生产源码与包版本不变。

本次仅补齐 M6 的真实脚本安装/回滚演练，不能外推 Rhino/KubeJS 实际执行、JAR 升降级、原存档回滚、多文件断电恢复或正式部署完成。独立副本留作审计，不应把其未安装其他桥接/二进制兼容补丁的原始组合直接开放；原服和旧原生验收环境未改。
