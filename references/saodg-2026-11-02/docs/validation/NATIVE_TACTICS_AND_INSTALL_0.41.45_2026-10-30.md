# 新怪实战与服务器/客户端安装：0.41.45

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

生产JAR仍为fada4d3a2ad0，SHA256 `5078ca78fe5e2d14f35bc4aeb117453c7376223154b58619a3a3c0b029083680`。本轮增加packTest实际攻击观察，不修改生产数值、模板或成功奖励开关。

## 独立整合包实际运行

夹具提交2d5dd5afb037。在用户授权的 `run/pack-acceptance-20261028-081137-fd148a65` 备份后从0.41.42升级至0.41.45，保留原有已接入旧服脚本及通用缩放补丁；未将开发市场脚本覆盖给旧服。绑定127.0.0.1:25579，原有EULA保持，奖励/正式入场磁盘开关保持关闭。测试以已有同步开发入场方式创建四人和两人队伍。

主报告 `logs/native-dual-trial-probe-7fe5362a-1fda-4ce0-acbd-bfcd493ee8e8.json` passed=true，SHA256 `8381451133c0d81ff24a6e30649d51fcef6425e53c1c86d80b5a7d9ee372ce8d`。恢复报告98cfd460-1db7-4cbc-9b9b-b58e3bd1cdd9通过。实际结果：

- 从生产生成的第一战斗房选中实际原版Zombie重卫，单独放开其AI；目标玩家取消无敌，站位由夹具准备。没有直接调用伤害或强制推进攻击周期。
- 直接原版近战调用被拒绝；调度器的预警在tick490出现，tick514由同一实际受管敌人产生LivingDamageEvent并使生命20→16.55，实际24tick起手与配置一致。随后恢复测试角色血量和夹具无敌，不把本次检查当作自然续航/倒地平衡验收。
- 两队都在精英末轮实际生成并确认击败遗迹冠军，每队各1个小首领，持久日志中required=true、boss=false、miniboss=true、confirmed_dead=true，且有唯一原生XP链接。
- 两队分别完成封印大厅、全队传送、独立最终Boss、10房/6秘密和300/S+，各19个确认死亡及XP链接。小首领没有替代最终Boss或产生第二份成功结算。
- 四人实际人物XP从0变为0、273、0、238，两人140、210；非均分安排，不给未参与击杀的角色补造正收益。实际人物文件、世界结果和回程标记再次离线解析确认。
- 64个身体出生身份检查、18,838次生命预算检查通过，包含小首领独立预算与人数倍率。双向跨实例伤害、另一队门操作拒绝，第一队清理保留第二队进度/钥匙/票据。

实际存档核对 `logs/native-tactics-2d5dd5a-disk-preservation-20261029.json`（复用验证器的文件日期后缀为29，实际执行于30日），196个旧宠物名册所有者、133项世界规则保持。保护报告 `logs/native-tactics-2d5dd5a-preservation-20261030.json`：1,453项预先保护文件除旧JAR替换、8份已知恢复演员文件与2份属性注释外无意外变化，765份非恢复人物文件保持。隔离未知物品实体区域散列仍为 `51916e76…6ac9d`。

Java46284正常stop退出0，端口关闭；夹具已归档到 `validation-history/native-tactics-2d5dd5a-8c995e57/fixture-native-tactics-and-miniboss-passed.jar`，SHA256 `8740c08f0814583ffecac3e38d387916fb800af1a533033b25757a18560690d4`。独立服已保留0.41.45生产JAR。

只证明重卫一次实际预警伤害，以及两个试炼种子2的受控完整流程。其余战斗仍冻结/高伤害推进；不证明游击者/咏唱者的整合包主动攻击、守卫型普通房小首领本轮出现、全部难度/种子、真人网络/画面、正式奖励经济或性能。

## 服务器本体与客户端实际同步

用户已授权开始接入同一整合包的三端，并确认客户端为SAO-0.8。`tools/install_staged_pack.py`先按 `build/integration/0.41.45-ready-20261030/rollout.json` 中的目标和逐文件前后散列核对，再确认本机没有Java/javaw进程；支持默认plan、显式apply和回执rollback，不启动Minecraft。

实际安装：

| 角色 | 目标 | 文件操作 | 回执 |
| --- | --- | --- | --- |
| 服务器本体 | `D:/Documents/Coding/Game/Minecraft/SAO-server-0.7` | 18项，含新增0.41.45 JAR | `.saodg-backups/4b28b92498f04ef391fbcc3f27e4a724/receipt.json` |
| 客户端本体 | `D:/Minecraft/.minecraft/versions/SAO-0.8` | 19项，含0.41.45 JAR与移出0.41.15 | `.saodg-backups/6ec202cd9e044f3b8d88dc390b9eab38/receipt.json` |

旧脚本和旧JAR在替换前备份原字节及散列；新增文件也登记为原来不存在。两端当前mods都只含一个SAODG 0.41.45，不交换各自r234核心。各端脚本、旧钱包、竞技场排除和楼层限制按独立精确补丁保留；配置使用已审查的disabled模板，未开放正式成功奖励经济。

安装器只允许该清单中的mods/saodg-*.jar和KubeJS脚本/JSON文件，不操作世界、玩家数据、EULA、服务器启动或Java参数。安装后逐项散列/缺失状态复核通过，服务器核心/属性/EULA3份、客户端核心1份散列保持；这组保护样本没有发现世界/人物文件，不能将计数误写为已遍历验证全部存档。汇总 `logs/runtime-role-install-20261030.json`，前置保护清单 `logs/runtime-role-install-protected-before-20261030.json`。

安装/回滚工具2项临时目录测试通过：替换/新增/旧JAR移出可精确、重复回滚；手改冲突时不进行任何恢复。回滚示例（需关闭Java进程）：

```powershell
python tools/install_staged_pack.py --mode rollback --receipt "D:/Minecraft/.minecraft/versions/SAO-0.8/.saodg-backups/6ec202cd9e044f3b8d88dc390b9eab38/receipt.json"
```

两端尚未启动，新安装的客户端画面、完整旧服冷启动和真实客户端连接仍待检查；独立测试服通过不替代它们。开发源码保留1581a80/2081609两个本地接入提交及全部用户NPC/商店修改，未push。
