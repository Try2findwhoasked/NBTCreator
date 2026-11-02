# 原生符文记忆与多人封印：0.41.41

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

生产包仍为 `654fa74e2c35` 的0.41.41，SHA256 `c6ecad77e04a64a1fcb223791800656fcc73b8abb4da999155e3d64418d6616f`。本轮只扩展packTest，没有修改生产规则、模板或原客户端/原服。沿用[光路完整探索](NATIVE_FULL_EXPLORATION_0.41.41_2026-10-29.md)的实际方块交互包、传送确认及受控位置/高伤害驱动。

## 一次进程覆盖两类谜题

启用 `packNativeExplorationAcceptance` 和 `packNativeExplorationMatrixAcceptance`。夹具从当前不可变内容快照使用实际LayoutGenerator在0～999范围内寻找指定谜题且含铭文秘密的种子，不改图、替换谜题或假造完成状态；得到符文记忆 `runes` 种子4、多人封印 `seals` 种子2。

第一队完整探索时另一队在独立实例保留已获得但未开启的门钥匙；第一队完成/清理后，第二队继续完整探索。符文顺序由服务端规则读取，位置和攻击由夹具准备；实际按钮、藏物、线索及重置经过ServerGamePacketListenerImpl.handleUseItemOn和Forge事件，不等于人工看图解题、步行可达性、平衡或远程网络验收。

## 实际结果

| 项目 | 符文记忆，种子4 | 多人封印，种子2 |
| --- | --- | --- |
| 实例 | 5076aa3b-914e-472c-a2e7-a0085e83ad65 | c183c59b-d407-4c8d-a6ba-b96d90ab74a7 |
| 完成探索房 | 9 | 9 |
| 全部秘密 / 重复领取负例 | 6 / 6 | 6 / 6 |
| 共享铭文解读 | 3 | 2 |
| 实际UseItemOn包 | 25 | 28 |
| 保存成绩 | 300 / S+ | 300 / S+ |

多人封印先让同一实际成员依次按完三个按钮，三处已激活但distinctActors=1，仍不完成。再发送实际PRESS_SHIFT_KEY命令、交互物理重置块、发送RELEASE_SHIFT_KEY，确认进度和参与者清空。之后两名实际ServerPlayer交替完成，requiredActors=distinctActors=2，完成才登记。两条潜行状态包不计入表中28个方块使用包。

两队均完成封印大厅全队转场、独立首领、19次确认死亡/原生XP链接、实际人物文件0/480点经验、独立战绩/回程/清理；各47次传送确认。探索不改变另一队的完成/秘密事实，先清理第一队保留第二队进度。未开放成功奖励，也未发放个人宝箱。

最终 `logs/native-dual-trial-probe-bd81f989-b8bd-4d5b-851a-438df5b0afbb.json` 为true，SHA256 `cb6a1ba0e409ac8d21e72fc1f60eb003215b08ab90cb0de6b07902c7b2f464d0`。两条独立明细为 `logs/native-exploration-probe-5076aa3b-914e-472c-a2e7-a0085e83ad65.json`、`logs/native-exploration-probe-c183c59b-d407-4c8d-a6ba-b96d90ab74a7.json`。停服后从真实data/saodg/state.nbt核对两条规范结果均为300/S+、10个完成房间（含首领）、6处秘密，见 `logs/native-exploration-matrix-0576b00-disk-preservation-20261029.json`。

## 构建、前序失败及保全

夹具 `0576b00ccce0` 独立Git导出packTestJar编译/重混淆通过，SHA256 `a48e16e5cc0818a49d7f342beda01ae72c8c28a62462812da461bdd03364d1cb`；日志 `logs/native-exploration-matrix-fixture-0576b00-20261029.log`。未跑JUnit或完整GameTest。

首轮9c2afb8把内容内部ID误写为memory，实际定义为runes，在1000次有界查找后停止，尚未创建实例或本轮人物；报告 `logs/native-dual-trial-probe-ef82a379-e753-48e1-b533-2669990f6797.json` 为false。错误已修正，生成器/生产数据未改变。该轮正常停服、插件归档、645份其他人物文件保持，保全 `logs/native-exploration-matrix-9c2afb8-preservation-20261029.json` unexpected为空。

通过轮备份 `validation-history/native-exploration-matrix-0576b00-9e3aafb7`，隐藏运行器PID34444、Java PID50020正常stop/退出0，端口关闭。终态 `.gradle/native-exploration-matrix-0576b00-process.json`，运行日志 `logs/pack-native-exploration-matrix-0576b00-20261029.log`。插件已从mods移至备份中的fixture-native-exploration-matrix-passed.jar，独立服仍为0.41.41。

`logs/native-exploration-matrix-0576b00-preservation-20261029.json`：1325个保护文件中1315字节相同、2个properties仅注释变化、8个指定历史恢复人物文件允许变化；645份其他人物文件保持，配置语义和unexpected检查通过。额外解码确认164个旧名册所有者及133项世界规则保持。原隔离实体区域字节保持，SHA256仍为 `51916e76d1a69aa84a76d4d8945b0f6e81747040bf8749f68faf4b045366ac9d`，见 `logs/native-exploration-matrix-0576b00-retained-entities-20261029.json`；未知结晶未处理，原隔离槽保留，最终回程/票据0。现有开发包verification.json追加本轮证据，JAR不变。

结合前次光路种子0，三类谜题各已有一次两人试炼中的原生交互包/完整探索证据。没有覆盖各类型全部旋转/种子、单人封印序列、3～4人封印、其他难度、视觉提示可读性、经济、真人远程或性能，不整体勾选全部运行时验收。
