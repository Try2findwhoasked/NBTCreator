# 0.41.50 原生攻击与运行端更新

生产来源 `b9c575304114a909bf215651161a744091173f6d`，版本0.41.50-dev。保留0.41.47的schema 5主体/墙层、7间精选refined房间，以及0.41.49的六类原生阵容、星标小首领、最终首领、原生经验与出生装备记录。

## 本轮变化

- 原生Boss只恢复SAODG自己设置的无人暂停，不再每tick覆盖其他系统或测试夹具的NoAI状态；绑定冻结期间也不抢先恢复。
- 更新玩家指南、首领阶段名称及旧存档入口提示，避免继续指引已默认关闭的自制怪物技能。
- 新增仅验收夹具中的NativeAiProbe：从本局实际生成的普通怪中，各选一只SAO哥布林和灾变尸鬼，释放AI。只安排合法近距离玩家位置，不调用setTarget、导航请求、doHurtTarget或人工hurt。以真实LivingDamageEvent来源和实际生命下降共同判断攻击成功；恢复临时玩家生命上限、生命及位置。
- 技能说明与房间指南同步schema 5。墙层合成已实现，独立门NBT尚未实现；门洞连接、石砖封墙、煤炭块主线门仍由程序处理。

## 实际运行证据

首轮来源25e14c7的夹具错误地只选绿色哥布林，但首房没有符合条件的该类型，因此失败。报告 `logs/native-dual-trial-probe-47999565-51d4-4374-8a37-0de0c8bc49d6.json` 保留；两局正常中止清理、服务器正常退出0，旧隔离区域保持，无意外保护文件变化。修正为选择实际生成的普通哥布林，不放宽两种模组均须真实攻击的要求。

修复后报告 `logs/native-dual-trial-probe-ad30743b-57d4-47ff-8454-79468538c048.json` passed=true，SHA256 `33fe1afe8b7688a206ec07170de2008e96fe24130e639dcd9dcb53bd94a3bac6`：

| 自然AI实体 | 玩家生命变化 | 开放AI后实际伤害tick |
| --- | --- | --- |
| `mod_1cab0b39:gray_goblin` | 200 → 197 | 2 |
| `cataclysm:draugr` | 200 → 177 | 22 |

之后四人、两人两队均完成完整受控副本流程：观察六类原生实体，各确认3个星标小首领、17死亡/原生经验链接，独立最终首领、10房/5秘密、300/S+、两队隔离、回程和清理。60个生成身体的生命预算检查共17,950次。最终首领仍由徘徊者担任本副本角色，不代表灾变全部Boss已支持。

离线解析实际存档及34份原生经验日志，均CONFIRMED且关联本局实际死亡；六名玩家最终经验分别448、553、336、383、924、685，与各自归属金额之和一致。两局各有3个非旧基底区域，确认精选refined模板实际放置。220个旧宠物名册所有者、133项世界规则保持，保护文件无意外变化，两个旧隔离区域字节保持，无新增隔离。

证据：`logs/native-ai-b9c5753-disk-validation-20261030.json`、`logs/native-ai-b9c5753-preservation-20261030.json`。私有Java33916正常stop退出0，25579关闭，夹具归档至 `run/pack-acceptance-20261028-081137-fd148a65/validation-history/native-ai-b9c5753-e19dfdd3/fixture-native-ai-passed.jar`。

## 产物与安装

`build/verified/0.41.50-dev-b9c575304114-native-roster-20261030/saodg-0.41.50-dev.jar`，SHA256 `f9207144acaffba7bd7cd331c274799f502be20f81b5428077353ccd89db298b`。定向JUnit 1项、编译及重混淆通过，75份正式NBT，未含用户beta或验收夹具。构建日志 `logs/native-ai-build-b9c5753-20261030.log`。

在确认Java/Minecraft进程均已关闭后，以精确文件指纹检查和备份事务更新两运行端，每端19项（包括内容不变的角色专用脚本/关闭奖励配置和旧JAR替换）：

- 服务器 `D:/Documents/Coding/Game/Minecraft/SAO-server-0.7/.saodg-backups/e9a2b9fd649b4ba09362f94d4057c35e/receipt.json`。
- 客户端 `D:/Minecraft/.minecraft/versions/SAO-0.8/.saodg-backups/1352730deaa94cd9a9fc9a6b931ed98b/receipt.json`。

暂存清单 `build/integration/native-0.41.50-b9c5753-20261030/rollout.json`；开发、服务器、客户端三个角色的源脚本基线均匹配。开发仓库既有桥接提交继续沿用，不覆盖其用户NPC/任务/商店修改。正式奖励经济继续关闭；客户端测试存档已有unrestrictedDevelopmentEntry=true，没有替换人物或存档。

## 尚待验证

服务器本体使用其自带Java17.0.15与Forge47.4.10，创建 `saodg_native_smoke_20261030_ebca7d9c` 独立世界，仅监听127.0.0.1:25580；到达Done，管理命令确认35房内容散列、journal=true、0活动局/回程/票据、4槽空闲，随后save-all flush/stop退出0。没有玩家加入，此项只证明实际服务器启动、加载及保存，未证明服务端人物实战。既有EULA字节未变，server.properties已恢复原始字节，新测试世界保留。报告 `logs/server-body-native-050-20261030.json`。

冷启动还暴露服务端原包的NPC依赖缺口：`sao_npc.js#177` 调用未定义的global.saoUI，服务端缺少sao_ui_core.js，50/51脚本加载、1错误。该NPC脚本不在SAODG更新的19项内，没有覆盖它或复制客户端整套UI/经济脚本。报告区分startup_passed=true与整包脚本检查passed=false，不能称整包无报错。该缺口仍需按服务端自身版本补齐依赖。

追加夹具740bc86在相同生产包上实际完成最终首领自然攻击。报告 `logs/native-dual-trial-probe-68f3d2df-8216-4e1f-8330-5db6bc700c3b.json` passed=true，SHA256 `40b278169833a3be46c48a8b6478c05f48143a297665ff38df84ab38a48c3ab2`：第一队实际生成的徘徊者自行索敌，22 tick后玩家生命210→207，真实伤害来源匹配；没有人工指派目标或触发攻击。两只普通怪也再次自然攻击成功，随后两队仍各确认3小首领/17死亡XP链接、300/S+并返回清理。60身体/18,377次生命预算检查通过，34份实际XP日志再次CONFIRMED，226个旧宠物所有者和133项规则保持，无新增隔离或意外保护文件变化。私有Java79956正常退出0、端口关闭，夹具已归档；生产JAR未改变。

追加证据 `logs/native-boss-ai-740bc86-disk-validation-20261030.json`、`logs/native-boss-ai-740bc86-preservation-20261030.json`。这证明当前最终首领可以自然攻击；其余完整流程仍使用受控位置、高伤害和其余怪物AI冻结，不代表已遍历最终首领全部原生攻击/导弹、实战平衡、性能、所有房间旋转/路线或真人联机。新版客户端新局渲染与门洞实际通行已请求用户检查，尚无反馈；服务端原包NPC依赖缺口仍保留，完整目标继续进行。
