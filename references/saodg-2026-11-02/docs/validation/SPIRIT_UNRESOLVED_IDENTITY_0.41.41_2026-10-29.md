# 灵宠身份损坏时的身体与物品保护：0.41.41

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

## 修复与开发包

0.41.40在找不到可信灵宠绑定时直接放行原生expireSpiritPet；因此原本受管、携带物品的真实身体，只需出生nonce丢失，就可能跳过emptyAssets/能力散列保护而被删除。“无法识别”不能作为可销毁临时内容的证明。

生产提交 `654fa74e2c35efb339bb4b0be758448ba2b5fcbd`：找不到绑定时，若仍是本次出生观察中的实际对象，或是实际副本世界索引中的SaoMount身体，拒绝原生结束。保留身体供原回收/冲突流程核对，不补造nonce、主人或时限，不重新授予战斗权。正常可信绑定仍按原资产/能力散列检查结束；未被本实例出生观察追踪的普通外部世界坐骑保持原生路径，无存档schema变化。

产物 `build/verified/0.41.41-dev-654fa74e2c35-spirit-corrupt-20261029/saodg-0.41.41-dev.jar`，SHA256 `c6ecad77e04a64a1fcb223791800656fcc73b8abb4da999155e3d64418d6616f`。独立Git导出jar/reobfJar/packTestJar通过，41个结构与提交一致，无beta、夹具或世界/人物文件，本地化、版本、mixin/refmap核对通过。未运行JUnit或完整GameTest。

## 实际反例与七项正例

夹具 `b761e90ebb52` 为实际r234符文鹿 `mod_1cab0b39:stag_rune` 通过原生召唤助手取得真实出生/租约，向空手部放入一个带唯一测试标记的新铁锭，再逐项修改字段并调用实际expireSpiritPet。每项先确认该错误身份没有副本行动权，再要求身体存活、完整实体NBT与调用前一致、物品计数1、没有nativeEndObserved。每项结束由夹具恢复此前保存的原字段，生产代码不负责自动修复或重新绑定。

| 控制输入 | 0.41.41实际结果 |
| --- | --- |
| 出生nonce缺失 | 不授权；身体/物品保持，无结束凭证 |
| 出生nonce变更 | 同上 |
| saodg标记类型错误 | 同上 |
| 原生主人字段缺失 | 同上 |
| 原生主人UUID变更 | 同上 |
| 原生到期字段缺失 | 同上 |
| 原生到期时间变更 | 同上 |

旧0.41.40报告 `logs/native-dual-trial-probe-424b431c-fc66-43de-a952-7a0f84a231e9.json` 为false，在nonce_missing明确记录身体已不存活，手部仍有1件物品且无结束凭证。错误 `Unresolved spirit binding allowed native deletion of its item-bearing body: nonce_missing`。失败后仅由夹具保留其自己创建的唯一标记物，再调用原身体的原生结束并完成中止/清理；不是旧生产逻辑已成功保护物品，不涉及原有人物资产。该轮正常stop/退出0、插件归档，保全 `logs/native-spirit-corrupt-before-b761e90-preservation-20261029.json` unexpected为空、597份其他人物文件保持。

新0.41.41明细 `logs/native-spirit-probe-a1e8d457-5f0e-416c-88a8-900a17f48347.json` 七项全部通过。新旧测试插件字节码相同，SHA256 `fca434523f1623c68fb6d6a9b356b211ffbe2ef68be99a36b9f639d2ede697e5`，没有为新版删掉反例。恢复原字段后，正常物品保护、转交主人后自然60tick到期、4000tick长时灵宠在SETTLING阶段回收均继续通过，主人返回后的实际人物文件中测试物品恰好1件。复制身体不能代替原体确认结束的既有负例仍通过。

## 双队与保全

最终 `logs/native-dual-trial-probe-90cfcaa4-4f41-4c4b-bdc5-e41153e4bd1f.json` 为true，SHA256 `5fa4e0bae81213cfee3d0cc145528ea2a22e2a8a2fdd4ec866a9eaa581009f86`。两局 `bfbd3949-9d8f-42a7-9cfd-787fd11f8e62`、`5f4d56c2-c6ad-4fb2-99f6-4a7dd5271893` 各完成4道主线门、封印大厅转场、独立首领、17死亡/原生XP链接及每队实际0/440经验、独立战绩/回程/清理；第一队清理不影响另一队。主体驱动仍使用高伤害和受控传送，不是平衡或真人输入验收。

旧轮备份 `validation-history/native-spirit-corrupt-before-b761e90-ee23d90a`，运行器PID77024/Java PID77748；新轮备份 `validation-history/native-spirit-corrupt-after-654fa74-7e8fc960`，运行器PID7464/Java PID21464，均正常stop/退出0。新轮端口关闭，插件移出mods并归档 `fixture-native-spirit-corrupt-after-passed.jar`；独立服保留0.41.41，原客户端/原服未改。

新轮保全 `logs/native-spirit-corrupt-after-654fa74-preservation-20261029.json`：1293个保护文件中1282字节相同、2个properties仅注释变化、8个指定历史恢复人物文件及旧版本包为已声明变化；613份其他人物文件保持，配置语义及unexpected检查通过。`logs/native-spirit-corrupt-after-654fa74-roster-preservation-20261029.json` 确认156个旧名册所有者和133项世界GameRules保持。原隔离区域字节不变，SHA256仍为 `51916e76d1a69aa84a76d4d8945b0f6e81747040bf8749f68faf4b045366ac9d`，证据 `logs/native-spirit-corrupt-after-654fa74-retained-entities-20261029.json`；未知结晶未删除、隔离槽未强制释放，最终回程/票据0。

## 仍需完成

七项均是在同一进程中仍有真实出生观察引用的对象上执行；没有实际运行“出生缓存已丢失后仅靠世界索引保护”的分支、损坏绑定的冷重启、长期冲突/人工归还、所有装备/能力变化、其他灵宠类型或职业成本，也没有真人远程和性能证据。源码保留未知对象不等于这些分支全部验收。C01和完整伴生兼容继续保持未整体完成。
