# 客户端画面卡顿：死亡水晶特效

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

用户确认0.41.51主菜单、新局哥布林/尸鬼显示、清理星标后开门及跨房通行正常，但画面掉帧、转视角卡顿。首次采样时旧Java28108已经退出，没有取得样本；用户重新进入副本并保持打开后，对实际Java33068完成两次25秒JFR。

## 现场证据

首次 `logs/client-lag-20261030-33068.jfr`：渲染线程503个Java执行样本中，224个包含 `dev.james.sao.forge120.CrystalFacets.render`（44.5%）；SAODG相关栈11个。主要落在水晶碎片顶点提交、CrystalMesh.emitShards及DirectByteBuffer，不能将此热点归因于副本HUD。

实际类来自 `sao_interface_pack-0.1.0.jar`（SAO Interface / Pack Edition），该模组的客户端配置已有deathEffects开关，控制死亡镜头、水晶碎裂与死亡提示整组。字节码确认关闭后CrystalDeaths.tick调用reset，能够清除正在播放的死亡视觉序列。该步骤只涉及客户端表现，不改击杀、奖励或宠物归属。

## 修改与结果

在当前客户端热更新 `config/sao_interface_pack-client.toml`：

```toml
deathEffects = false
```

原件与回执：`D:/Minecraft/.minecraft/versions/SAO-0.8/.saodg-backups/crystal-fps-5be5cf5f74474380b66571fa3048b284/receipt.json`。解析前后TOML，除deathEffects外完全相等；队伍栏、生命值界面、低血量警报、治疗和拾取界面维持原值。

第二次 `logs/client-lag-no-crystal-20261030-33068.jfr` 中死亡水晶绘制样本为0，用户明确反馈“流畅了”。两段采样的平均JVM CPU占全机比例分别约41.6%和11.1%，但实体/场景构成不同，后段主要为原生宠物渲染，因此这不是受控帧率基准，不能宣称固定倍数的FPS提升。没有直接测量FPS；不继续扩大已改善问题的优化范围。

汇总 `logs/client-crystal-fps-comparison-20261030.json`。本次未重新构建模组，保持两端0.41.51及JVM单方法启动绕过。实际客户端配置保留关闭状态，今后若要恢复死亡特效，应在该配置重新启用并复核负载。

## 本轮目标核对

| 要求 | 已检查的证据 |
| --- | --- |
| 拼接房间墙模板 | schema 5加载器实际合成主体/墙层；精选7房17分片34层；分层/目录GameTest与实际放置记录见REFINED_LAYERS_0.41.47文档 |
| SAO、灾变原生怪物 | 六类显式阵容实际生成；灰哥布林/尸鬼自然AI真实伤害、原生经验确认；customEncounterSkills默认关闭 |
| 星标小首领 | 两种小首领纳入必要清房目标；四人/两人局各确认3个，原生XP与死亡链接核对通过 |
| 独立最终首领 | 徘徊者作为本副本最终首领；封印大厅只传送本队，独立首领场地，自然攻击、实际死亡、结算、返回与清理通过 |
| 整合包接入与体验 | 三角色适配来源清单，两运行端同一0.41.51散列；服务端54/54、客户端98/98脚本无错误；用户确认新局原生怪、开门、通行正常；启动两项问题已处理，本次死亡特效关闭后用户确认流畅 |

核心运行证据沿用 `logs/native-dual-trial-probe-68f3d2df-8216-4e1f-8330-5db6bc700c3b.json`、`logs/native-boss-ai-740bc86-disk-validation-20261030.json`；实际安装散列再次核对为 `7d010dc9c30bdaa96708dd541724afd355140e2edb982453fc40a798b3f2b76c`。旧隔离资产保持，不以删除未知物品换取清理通过。

本轮功能接入目标完成。仍为开发版：没有宣称灾变全部Boss接入、独立门NBT、正式奖励经济开放、所有难度/人数/房间种子的真人联机或长期性能认证；这些不是本轮已交付功能的替代证明。
