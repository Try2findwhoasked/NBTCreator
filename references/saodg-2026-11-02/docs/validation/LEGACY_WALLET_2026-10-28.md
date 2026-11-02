# 原钱包事务与持久数据命名空间

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

目标为已授权私有副本 `run/pack-acceptance-20261028-081137-fd148a65`，原 `SAO-server-0.7` 目录只读。原钱包源码 SHA-256 为 `56aa8354328d6a87a008b7dcc1f037a7944b826b140f52b0661bcb91c8a3f04a`，不能套用较新整合包的钱包/市场补丁。

## 实现

新增确切旧版补丁 `compat/patches/saodg-wallet-sao-server-0.7.patch` 和清单 profile。`python tools/verify_compat_patches.py <原服务端目录> --profile sao-server-0.7` 只校验散列、精确合并并语法检查，输出到忽略的 build 目录，不安装。原有较新 profile 仍独立验证。

补丁为原钱包提供当前代际事务端口；护甲强化、普通提交、战斗入账、旧币存入、商店、任务发款、任务补领七个写入口先检查资产冻结。普通交易拒绝迷宫区专属材料，并在库存提交前比较完整绑定材料快照；不迁移余额，也不为旧钱包新增市场状态豁免。

## 实际失败与修复

初次日志 `logs/pack-native-wallet-20261028.log`：端口已登记，但真实回调中的 `player.getUUID()` 不存在。改用原钱包已有的 `player.uuid`，库存写入使用原脚本的 `inventory.setStackInSlot`。修复同步到较新钱包补丁及共享扩展。

随后日志 `logs/pack-native-wallet-fixed-20261028.log`、`pack-native-wallet-baseline-20261028.log`、`pack-native-wallet-extra-20261028.log`：无回执基线检查拒绝，未继续应用。只读记录确认 UUID、库存和原持久字段相同，但回调余额为 0、错误读盘余额为 500。

实际 KubeJS 2001.6.5-build.26 的 `core.mixin.common.EntityMixin` 字节码表明，Rhino 的 `getPersistentData()` 映射到 `kjs$getPersistentData`，另存为玩家文件顶层 `KubeJSPersistentData`；Java/Forge 的同名方法使用 `ForgeData`。因此原脚本钱包保持在 `KubeJSPersistentData.PlayerPersisted.sao_kol_balance`，不应迁移到 ForgeData。旧扩展读错了磁盘路径，且把迷宫区回执也放进了脚本钱包命名空间。

0.41.7 修正所有钱包扩展的读盘路径。钱包所有者仍负责余额和库存内存应用；`PackWalletTransactionPort` 协调器在同一应用回调返回后、任何保存之前，将原生迷宫区状态明确写入 `ForgeData.PlayerPersisted.saodg`。脚本不再把迷宫区状态写进 KubeJSPersistentData。仍使用原钱包保存方法，并由 Java 独立回读同一人物文件确认库存、余额、经验和回执；不以公共保存方法正常返回作为成功证据。

新增 packTest 夹具仅显式 `-Dsaodg.packWalletAcceptance=true` 且目录名精确匹配私有副本、没有真实在线玩家或副本时运行。临时人物通过真实 PlayerList 登录；预留不同值的 Forge 同名字段，避免两个命名空间碰巧相等掩盖错误。夹具直接调用端口，不开放准入、不绕过正式 RewardService 的外部资产门禁；不宣称证明完整世界意图日志或崩溃恢复。

首个命名空间修复包的实际日志 `logs/pack-native-wallet-namespace-fixed-20261028.log` 确认内存/磁盘回调余额均为 500，但应用时又发现 Rhino 无法反射 JDK 17 的非公开 `ImmutableCollections$ListN` 实现。ScriptBridge 在脚本边界传入独立的公开 ArrayList，不改变规则层不可变快照和事务后的资产校验。该失败保留，不作为成功事务证据。

## 验证状态

两个 profile 的源散列、精确补丁及合并后语法检查通过；Node 夹具确认七个冻结入口、缺少材料策略拒绝、材料交易与快照保护和登记元数据。新增 packTest 编译通过。0.41.7 第一次完整回归通过 100 项 JUnit / 43 项 GameTest（`logs/wallet-namespace-default-20261028.log`，应用 ArrayList 修复之前）；最终 Java 修复后的完整 `build runGameTestServer -PgameTestRunDirectory=run/gameTestServer-wallet-public-list-20261028-1821 --offline --console=plain` 退出 0，100 项 JUnit（零失败/错误/跳过）、43 项必需 GameTest 和 112 个房间四旋转实际通行检查全部通过；日志 `logs/wallet-public-list-default-20261028.log`。所有失败 JSON/日志保留；正式开本与奖励保持关闭，市场仍为 UNKNOWN，任务事实桥仍关闭。

## 真实钱包事务通过

源提交 `734f029171088677810be301f63ceba7475a7cc6` 的干净构建产物 `build/verified/0.41.7-dev-734f02917108-20261028-101934-db3c53e9/saodg-0.41.7-dev.jar`，SHA-256 `c9359ab185b9ce0a4058e0e83a7bc53c392381ad11ccbdcc0a99ea6135a871ca`。私有副本安装散列相同，原钱包补丁合并后散列 `0e127d525757465e5a6c1a9fda2155f802148c2c72874e9d24ed93f1c4d0898b`，部署清单 `legacy-wallet-installation-20261028.json` 保留原文件备份路径和夹具散列。

实际启动同一私有目录时增加 `-Dsaodg.packWalletAcceptance=true`（未设置旧 native owner 测试开关），仅测试夹具加载后执行一次。日志 `logs/pack-native-wallet-list-fixed-20261028.log`，结果 `native-wallet-probe-ee0ca2d6-2033-43ea-b3db-02276741d205.json`，临时人物 `15427725-312d-400f-b0a2-86e288cbabd4`，操作 `de3eb533-979a-43fe-b5de-1f268582e202`：

- 原钱包 500→475，获得 2 个钻石、30 迷宫区 XP；准备阶段无变化，应用后的原钱包保存调用经真实文件回读 CONFIRMED。
- 原有 7 个带自定义 NBT 的铁锭保留；原持久标记保留。ForgeData 中刻意设为 123 的同名余额字段未改变，KubeJSPersistentData 未出现第二份迷宫区回执。
- 同一 Plan 再应用被 conflict 拒绝；原余额、钻石数量不再变化；重复保存确认仍 CONFIRMED。
- 余额不足、余额超过上限、满背包均在预检拒绝，没有扣款。归还库存快照后仍能确认原操作。
- 临时人物正常从 PlayerList 移除，没有 cleanup_error，未删除其审计文件。

之后第一次 reload 捕获当前钱包端口，第二次 reload 检查旧引用：代际 3→5，旧端口 id() 返回 adapter_unavailable，新端口仍为 sao:pack_wallet_v1；原脚本 facade 也被撤销。各轮准入始终 pack_disabled，外部资产始终 UNKNOWN。原包 sao_npc.js 的 registerPage 错误仍存在，不隐去。

较新市场补丁中的相同 getUUID 调用也改为 Rhino 的 uuid 属性；市场逻辑夹具和精确合并检查通过，但未在此无市场的旧服中冒充实际市场验收。完整奖励服务的资产租约、世界意图日志、保存失败/崩溃矩阵、任务事实、真实多人经济与客户端仍待独立验收。

实际管理命令确认最终 runs/lobbies/pendingReturns/tickets 为 0，四槽位空闲。独立测试服已正常保存停服、25579 端口释放；临时夹具 JAR 已移入 validation-history，不留在 mods。原钱包原文件散列复查不变。
