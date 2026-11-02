# 领奖计划执行前复检

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

0.41.8-dev 修复 NativeRewardTransactionPort 的两处执行前缺口，共用该协调器的钱包端口同样适用：

- 原来 prepare 检查容器/光标，Plan.apply 只重查物品使用。现在 apply 也要求当前为自身库存菜单、光标为空；拒绝时不改动光标物品，不扣/发任何资产。
- 原来提交前只比较库存、成长和额外钱包的经济指纹，以及本操作回执是否缺失。另一笔零物品/零经验/零货币事务可以在经济状态不变时增加回执；旧计划会用旧 afterDungeon 覆盖它。现在还要求完整当前迷宫区子树与 prepare 时快照一致，任何其他回执或迷宫区状态变化都返回 conflict，保留新状态。

新增隔离命名空间 saodg_reward_boundary 的 RewardBoundaryGameTest，使用真实 ServerPlayer、库存菜单、ChestMenu、光标栈和物品使用状态，不使用正式账号或存档。测试以已初始化 0 经验/1 级基线构造两笔经济状态相同的计划，证明第二笔不擦除第一笔回执；也验证关闭短暂交互后未过期计划可以正常提交。保存适配器会在意外访问时直接抛错，因此拒绝阶段不能保存/读盘。

实际执行：

```powershell
.\gradlew.bat runGameTestServer -PgameTestNamespaces=saodg_reward_boundary -PgameTestRunDirectory=run/gameTestServer-reward-boundary-20261028 --offline --console=plain
```

日志 `logs/reward-boundary-targeted-20261028.log`：实际只注册并运行 1 项必需测试，全部通过，正常退出 0，53 秒。没有重跑其余 43 项，也没有运行整合包或重新部署产物。默认未传 namespace 时会同时包含原 saodg 和新奖励边界命名空间，保证后续全量回归不会漏掉它；本轮不声称默认完整套件已重新通过。

未改变回执/存档格式或内容版本。实际网络并发、跨模组钱包保存失败与完整崩溃矩阵仍需相应验收；正式入场和奖励继续关闭。

## 同类物品归还与经验边界

随后检查 NativeItemReturnPort，确认同样在 prepare 捕获整棵迷宫区状态，但 apply 只比较库存和本次回执。修复为提交前复查库存菜单/光标，并要求当前整棵迷宫区状态仍与 prepare 快照一致。SaoExperiencePort 在原生经验应用前也新增菜单/光标检查；它原本在调用原生经验所有者之后读取当前迷宫区状态再合并回执，没有同样的旧子树覆盖行为，故未改其合并方式。

同一独立命名空间新增第二项真实 ServerPlayer/菜单/库存测试：归还计划建立后打开容器或持有光标物品均拒绝；其间完成一笔零物品奖励后，旧归还计划返回 conflict，不发箭且不擦除奖励回执；重新预检后恰好归还一支箭、保留两个回执，重复提交不再发物品。没有访问人物文件或世界账本，不能外推完整归还保存故障通过。

实际运行 `runGameTestServer -PgameTestNamespaces=saodg_reward_boundary -PgameTestRunDirectory=run/gameTestServer-return-boundary-20261028 --offline --console=plain`，日志 `logs/return-boundary-targeted-20261028.log`：只运行上述两项，全部通过，正常退出 0，54 秒。原生经验改动编译通过，但未在带 SAO 的原生环境复测；其事务保存/调用钩子仍待联合验收。未跑其余默认套件，未部署。

## 收件人约束补充（0.41.9 源码）

服务层已有原收件人校验。本轮在 NativeItemReturnPort 和 SaoExperiencePort 自身也约束 entry.recipient/entry.player 必须与当前人物 UUID 一致，防止内部调用遗漏时把同一记录作用于另一人物。检查位于预检、回执访问、重放基线读取、确认和回执清理前；经验保存基线和应用前同时校验正确的原生所有者。已有服务授权规则不变，没有宣称之前存在玩家可直接利用的网络入口。

新增第三项定向 GameTest，使用另一收件人的真实记录调用六个物品归还入口、八个经验入口，均返回精确 reward.not_owner；注入屏障若被读取/保存会立即失败，最终库存/迷宫区子树仍为空。原两个有效收件人用例也通过。此测试在无 SAO 环境检验经验端口在可选所有者调用之前拒绝错收件人，不证明正确收件人的原生 XP 实际发放。

命令 `runGameTestServer -PgameTestNamespaces=saodg_reward_boundary -PgameTestRunDirectory=run/gameTestServer-recipient-boundary-20261028 --offline --console=plain`，日志 `logs/recipient-boundary-targeted-20261028.log`：3 项 required 全部通过，54 秒，退出 0。测试时版本元数据仍为 0.41.8，随后仅升源码版本为 0.41.9-dev 区分运行中的旧客户端，未重复构建/测试。新修改未打包或部署；用户客户端与私有已安装包保持 0.41.8。
