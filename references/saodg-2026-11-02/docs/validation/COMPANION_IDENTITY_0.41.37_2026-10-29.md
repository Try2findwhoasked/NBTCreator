# 宠物租约的实际实体身份：0.41.37

## 问题与修复

`CompanionService.runId` 原先依赖实例租约及适配器 `matches` 的部署证明。持久宠物的原生适配器核对名册、实体UUID和部署令牌，但这些数据不能单独证明传入对象就是服务器当前索引中的实体。未加入世界的对象，或携带同UUID和部署数据的另一对象，可能取得实例归属与成员贡献；`legalPosition` 同样只看租约UUID和房间。

生产修复 `27c98ed` 增加 `currentBody`：必须在服务端主线程、对象未移除、位于当前服务器的副本维度，且 `ServerLevel.getEntity(UUID) == entity`。`runId` 与房间权限均先检查该条件。现有部署证明、租约、实例阶段和淘汰检查继续执行，合法索引实体仍取得原有实例和贡献成员。仅身份证明不够的对象不会获得战斗权；没有修改宠物名册、重建资产或改变原生收回操作。

`tracked` 仍是旧租约的兼容抑制查询，不作为实时战斗权；入场/出生/回收流程未新增相同限制，避免在实体加入索引前阻断原生资产登记。

## 定向运行证据

新增 `CompanionIdentityGameTest.onlyTheIndexedCompanionBodyReceivesLeaseAuthority`，命名空间 `saodg_companion_identity` 已加入默认套件，并提供独立empty模板。

夹具使用真实Forge世界/实体索引和僵尸对象，适配器刻意仅核对UUID/类型以模拟可复制的部署凭证，不加载或假装测试真实SAO宠物：

- 未加入世界的对象即使有匹配租约，也不能取得归属。
- 实际加入世界且被索引的对象取得实例、贡献成员和合法房间权限。
- 同UUID的另一对象通过夹具适配器的部署匹配，但实例归属、成员贡献和房间权限均拒绝。
- 租约退休、所有者淘汰后不再授权；已移除的原对象也不再取得归属和房间权限。

修复前源码 `4047116` 的独立导出，仅补入相同测试模板后实际运行失败：`Unindexed body must not gain authority from a matching lease`，1项必需测试失败，退出1。日志 `logs/companion-identity-before-template-4047116-20261029.log`；证明原代码确实对未索引对象授权，非仅静态猜测。

完整修复及模板提交 `6466ef0c803a1527259e5b54a582974f38506298` 的全新Git导出，运行同一命名空间，1项必需测试全部通过，正常保存/退出0；随后jar/reobfJar通过。日志 `logs/companion-identity-after-template-6466ef0-20261029.log`。命令使用JDK17、Forge47.4.10、离线模式与独立运行目录，未运行JUnit或其他GameTest。

前两次尝试分别在修复前 `4047116` 和修复后 `27c98ed` 缺少该命名空间empty模板，运行在创建测试结构时中止，不能作为正/反例；日志 `logs/companion-identity-before-4047116-20261029.log` 和 `logs/companion-identity-after-27c98ed-20261029.log` 保留。`6466ef0` 补齐模板后才取得上述有效运行证据。

## 开发产物与范围

产物 `build/verified/0.41.37-dev-6466ef0c803a-companion-identity-20261029/saodg-0.41.37-dev.jar`，SHA256 `809c2845b61034c638b6c8982d093ac1e1a80c5088282632874627ba4e0198c5`；同目录 `verification.json` 记录完整源码、归档哈希、构建日志及验证范围。

包中41个NBT与提交内容严格一致，无beta、测试夹具、世界/人物数据或引用仓库，中文与fallback本地化一致，版本及refmap/mixin资源检查通过。工作树另有用户的 `.gitignore` 修改及未跟踪结构/工具；均未更改、提交或带入产物。为保留这些改动，本轮直接核对已提交Git导出的产物，没有绕过原发布工具的工作树检查或伪称工作树干净。

没有部署/重启原客户端、原服或独立整合测试服；私有整合测试服仍保留0.41.36。没有真实SAO宠物召唤、AI/技能攻击、击杀XP、名册保存/收回、重载部署或多人远程证据；C01及宠物整体验收仍未完成。本修复仅关闭已经复现的实时对象身份缺口，不据此宣布全部兼容完成。
