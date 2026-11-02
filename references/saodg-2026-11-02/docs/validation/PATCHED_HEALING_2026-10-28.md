# 与 gameplay-fixes 2.3.3 共存的职业治疗检查

完整整合包实际加载证明，原治疗 Redirect 与 ExpansionBalanceMixin 的三个 Redirect 争抢同一调用；不能用提高优先级覆盖现有补丁，因为那会丢失其治疗比例、预算与职业平衡计算。
0.41.3 把无补丁时的原生治疗钩子独立为 SaoProfessionHealingMixin，分别捕获 tick/shaman/heal 的完整原方法参数。
只有精确匹配 ExpansionBalanceMixin 原始 class SHA-256 `a2e95a6721488dd0574f4a776fd59f5cb9964a1a1e28c1b7eabf058827e7ceb3` 时跳过这个原生 Redirect，并在原平衡补丁已经合并的自疗、萨满被动与队伍治疗方法前增加权限条件。
匹配同时要求三个处理方法的完整签名、静态属性及 MixinMerged 所有者均与已检查版本一致；先全部验证再写入，不接受只保护一部分。未知或不完整布局不记录应用成功。
补丁原方法体不替换、不改数值，合法目标继续执行原方法；拒绝的目标在调用治疗/预算逻辑前返回。队伍治疗从第三个参数读取实际施法者，自疗和被动以自身为来源。
新增 profession-balanced-healing 健康状态，成功安装仍标为 GUARDS_APPLIED_UNVERIFIED；没有人物与实际疗效证据时不升级为兼容认证。

## 构建与实际加载

最终从 `b0d2234e46a3fe043d27dda43b85662edda4abf1` 导出干净源码构建，94 项 JUnit 全部通过、GameTest 编译通过，1 分 16 秒；JAR 位于 `build/verified/0.41.3-dev-b0d2234e46a3-20261028-083839-0f366f37/saodg-0.41.3-dev.jar`，SHA-256 `80723e92542496c8c99984ec088e39e7325f7fc41cff49aadb4c4ab82158aa35`。该构建没有重新执行默认 GameTest，不把既有 42 项证据当成本次新增实际疗效验证。
同一授权副本只替换 SAODG，保留旧包和世界。启用 Mixin debug export 导出变换后的实际类，增加只加载 ProfessionExpansion 和读取健康状态的私有脚本，不调用治疗/技能、不创建玩家、不开放入场或奖励。
最终日志 `logs/pack-healing-final-20261028-081137-fd148a65.log`：16:41:04 Done（世界准备 3.447 秒）；16:42:11 admin status 显示 `profession-balanced-healing=GUARDS_APPLIED_UNVERIFIED`。旧 SaoProfessionExpansionMixin 的三个治疗 Redirect 冲突不再出现。
读取 `.mixin.out` 中实际变换后的 ProfessionExpansion.class，经 javap 确认三处前置检查使用了正确来源参数。另用独立 ASM 审计比较原 gameplay-fixes JAR 与最终类，忽略行号/标签编号差异并去掉新增的五条前置指令后，原三种治疗方法的全部 28/9/10 条指令分别完全相等；原补丁的治疗比例、预算/职业计算没有被替换。证据 `logs/healing-owner-body-audit-2026-10-28.log` 与 `logs/patched-expansion-export-2026-10-28.txt`，本地审计辅助源码保留于忽略的 `.gradle/pack-control-20261028`。
服务端执行 status、validate 和 stop 后正常保存全部维度、退出 0，端口释放。原服务端与玩家数据未修改。

## 保留的失败与限制

首次原生启动命令的 `-D` 参数没有引号，被 PowerShell 拆成主类名，尚未进入 Forge 即失败；之后改为带引号参数，保留日志。初版辅助类位于保留的 mixin 包内，真实加载触发 IllegalClassLoadError；已移至 integration.sao 外层，重新导出构建和原生加载通过。
私有探针首次用了与其他脚本冲突的局部变量名，出现 redeclaration；去掉变量赋值并 reload，最终健康状态与导出字节码提供独立确认，未把探针脚本错误当作成功。原包 sao_npc.js registerPage 未定义等错误仍在。
本次更多类加载还暴露了 SaoCombatMixin 与 SwordLevelDamageMixin、SaoProfessionsMixin 与 ProfessionProgressionMixin 的伤害 Redirect 冲突，尚未处理；没有以消除三条治疗警告来宣称全整合包冲突已解决。
本次仅证明最终类中权限前置检查安装成功且原所有者方法体保留；同队/跨队实际治疗量、职业冷却、濒死救援、未知补丁与未安装 gameplay-fixes 的原生运行路径、真实多人仍需继续验收。
此前已验证的其它技能、击杀 XP、钱包和任务所有权不因此自动通过；正式开本与奖励保持关闭。
