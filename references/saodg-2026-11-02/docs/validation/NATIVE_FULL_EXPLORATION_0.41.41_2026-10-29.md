# 原生试炼完整探索与300分结算：0.41.41

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

生产包保持 `654fa74e2c35` 的0.41.41，SHA256 `c6ecad77e04a64a1fcb223791800656fcc73b8abb4da999155e3d64418d6616f`。本轮新增packTest夹具和传送确认回包，未改生产规则或模板，未部署原客户端/原服。独立服在原有0.41.41上运行，入口/奖励磁盘配置保持关闭。

## 输入与实际操作

新增 `NativeExplorationProbe`，通过 `saodg.packNativeExplorationAcceptance=true` 在第一队完成封印大厅、进入首领传送门之前暂停主线，清完生成地图的全部支路。第二队保持独立运行，持有已获得但尚未使用的钥匙，探索操作不改变其完成/秘密事实。

EmbeddedChannel夹具现在真实回复ClientboundPlayerPositionPacket的传送确认，避免在未确认传送状态中投递交互。本次谜题、线索、藏物和重复点击均调用实际 `ServerGamePacketListenerImpl.handleUseItemOn`，经过原版游戏模式和Forge右键事件；不直接调用谜题输入或秘密状态方法。包对象由夹具构造并直接交给实际处理器，不证明远程字节解码/网络时延或客户端视觉。主线门、首领机关仍由既有服务驱动；不将本次22个交互包外推为所有输入路径均已测试。

初始位置和跨房移动由受控传送准备，支路必要敌人使用既有高伤害/无敌/静止敌人驱动；谜题解法从服务端规则读取。该用例验证物理交互与服务端事实闭环，不是玩家看图解谜、复杂步行可达性或数值平衡验收。

夹具 `aba0e7675e27` 独立Git导出packTestJar编译/重混淆通过，SHA256 `c9b014755087f2bcd751653e713d26982aae5e34b8e1a30dc678e86eb14e2171`，日志 `logs/native-exploration-fixture-aba0e76-20261029.log`。此前da750cc编译通过，启动前补充等待实际成员资产/状态可行动，未运行不完整准备版本。未执行JUnit或完整GameTest。

## 完整探索结果

明细 `logs/native-exploration-probe-9db0b876-ef43-442d-92be-5db97c6a54a9.json`：

- 首领转场前9个探索房间完成，含支路精英和1个实际生成的光路谜题。
- 6处秘密全部通过实际交互包发现；2处铭文藏物先尝试未读领取，确认不计发现/贡献，再由一人读线索、另一人发现，共享发现时两者各获得一次贡献。单纯阅读不获得参与。
- 6次跨tick重复领取均不增加秘密或参与，避免只靠同tick限流误判去重。
- 共22个实际UseItemOn包，探索期间另一局的完成/秘密事实保持。
- 首领完成后的规范结果为300分/S+。停服后从真实 `data/saodg/state.nbt` 再解码确认score=300、grade=S+、10个完成房间（含首领）和6处秘密；证据 `logs/native-exploration-aba0e76-disk-preservation-20261029.json`，不只读取内存结果。

最终 `logs/native-dual-trial-probe-a5c563ec-0368-4ff5-8e63-b2040460642b.json` 为true，SHA256 `3e944c96478536b1069ac73ea55894fc2428f49f545551b403705ea12cf48a12`。第一队局 `9db0b876-ef43-442d-92be-5db97c6a54a9` 因清理支路精英共有19次确认死亡/原生XP链接，实际人物文件0/480点经验；第二队局 `896e995d-d208-415d-b57a-0635431c1c32` 走原主线，17次死亡/链接、0/440经验。传送确认分别47与27次。两队都完成封印大厅全队转场、独立首领、独立历史、经验保存和回程清理；先清理第一队不影响第二队。

成功奖励保持禁用，本轮没有发放/领取个人宝箱或修改钱包；300分不等于奖励事务验收。

## 停服与保全

运行器PID54440、Java PID35796正常stop、退出0、端口关闭，终态 `.gradle/native-exploration-aba0e76-process.json`，日志 `logs/pack-native-exploration-aba0e76-20261029.log`。备份 `validation-history/native-exploration-aba0e76-f041a6de`，插件移出mods并归档为 `fixture-native-exploration-passed.jar`。

`logs/native-exploration-aba0e76-preservation-20261029.json`：1309个保护文件中1299字节保持、2个properties仅注释变化、8个指定历史恢复人物文件允许变化；629份其他人物文件保持，配置语义保持，unexpected为空。额外解码确认160个旧永久宠物名册所有者记录和133项世界规则保持，磁盘证据同上。

原隔离实体区域字节不变，SHA256仍为 `51916e76d1a69aa84a76d4d8945b0f6e81747040bf8749f68faf4b045366ac9d`，见 `logs/native-exploration-aba0e76-retained-entities-20261029.json`。未知结晶未处理，隔离槽未强制释放，最终回程和票据0，其余槽位FREE。现有开发包verification.json追加本轮报告，保留此前灵宠反例证据，JAR未改变。

只覆盖试炼、种子0、光路谜题和本局6处秘密；记忆/多人封印在原生整合服的交互包、其他难度/种子、客户端线索视觉、完整走路可达性、实际平衡、经济、真人远程和性能仍待完成。原生完整探索第一次通过不代表F/M/C全部验收完成。
