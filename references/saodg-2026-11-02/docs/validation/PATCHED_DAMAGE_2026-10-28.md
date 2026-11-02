# 与原平衡补丁共存的剑技/职业伤害权限

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

0.41.3 实际整合包类加载暴露两个伤害 Redirect 冲突：SaoCombatMixin 与 SwordLevelDamageMixin，SaoProfessionsMixin 与 ProfessionProgressionMixin。
原补丁根据实际 DamageSource 的玩家来源计算攻略等级倍率或职业成长，并可能转换 SoulDamage；不能用提高优先级抢占它们。
0.41.4 把没有这些补丁时的原生伤害钩子分离为两个独立 Mixin，完整捕获原 strike/hit 参数。仅在相应原补丁 class 散列精确匹配时跳过它们，在原补丁合并后的处理方法前添加布尔权限检查。
SwordLevelDamageMixin class SHA-256：`405d1a603800a0d1388111652a5cca329ebd51f931867c8a4c1cf8b3e40857f9`；ProfessionProgressionMixin：`f8deb932d12cbdd67b102eb5879fe9c74dc8a823a77d9ed9191a713303657763`。
处理方法同时验证 MixinMerged 所有者、完整签名、静态属性与唯一性；未知或重复方法不做部分写入。

权限从 DamageSource 的实际来源读取，不按附近玩家补造施法者；若直接来源是投射物，则经过已登记租约和原路径检查。受管目标遇到未知来源拒绝，外部未受管场景继续原行为。
拒绝返回 false，不进入原伤害计算；合法来源进入原方法体，不改倍率、SoulDamage 或原 hurt 返回值。健康状态仍为 GUARDS_APPLIED_UNVERIFIED，不能当作实际技能效果认证。

## 实际验证

执行 `gradlew.bat build runGameTestServer -PgameTestRunDirectory=run/gameTestServer-balanced-damage-2026-10-28 --offline --console=plain`，`logs/balanced-damage-build-2026-10-28.log`：完整构建、97 项 JUnit、42 项 required GameTest 通过，5 分 10 秒。新增三个 ASM 边界测试通过；双实例实际人物夹具已执行同局来源放行、跨实例与未知来源拒绝，112 个房间旋转通行场景也继续通过。
从提交 `54c979f99579e3b7200e89543dfe1acd187d31ad` 导出干净源码，完整 build 再通过，97 项 JUnit、41 个结构无 beta，1 分 23 秒。产物 `build/verified/0.41.4-dev-54c979f99579-20261028-085339-f4614e0e/saodg-0.41.4-dev.jar`，SHA-256 `8d4c3ec010369e520279a8725ea9e3e5bd5955308abf8cb32a47a696e678638a`。
仅替换同一授权副本的 SAODG，保留旧包和原世界、原包 121 个模组；仍为 127.0.0.1:25579，开本/奖励关闭。探针只加载 Combat、Professions、ProfessionExpansion 并读取状态，不创建人物或施放技能。
实际加载日志 `logs/pack-balanced-damage-20261028-081137-fd148a65.log`：16:56:31 Done（准备 4.152 秒），三个探针均返回 GUARDS_APPLIED_UNVERIFIED；当前加载未再出现 SAODG 治疗/剑技/职业伤害 Redirect 冲突或注入失败。
读取实际 `.mixin.out` 导出，用独立 ASM 程序对原补丁与合并后的两个伤害方法做标准化指令逐项对比；忽略标签/行号并扣除新增六条权限指令后，20 条 sao_scale、29 条 sao_damage 原指令完全相等。倍率、SoulDamage 与原 hurt 调用没有被本次检查重写。证据 `logs/damage-owner-body-audit-2026-10-28.log`，辅助源码保留于 `.gradle/pack-control-20261028`，未打入模组。
执行 admin status、validate、stop 后保存全部维度并退出 0，端口释放；副本记录 runtime-run-0.41.4.json。原服务端和玩家数据不改动。
仍未验证真实 SAO 施法命中/伤害数值/冷却、同队及跨实例实际技能、未知补丁与无平衡补丁的原生回退、真实多客户端、钱包/任务完整故障矩阵；原包 sao_npc.js 错误与 KubeJS 迷宫区桥缺失仍保留。当前类加载无冲突不能外推为所有未来加载的类均无冲突，正式开本继续阻断。
