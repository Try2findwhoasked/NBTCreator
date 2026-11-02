# 原生经验回调与人物保存边界

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

仅在已授权的私有整合包副本运行 0.41.9-dev，使用提交 9ebf0cc 的独立 packTest 夹具和 JVM 开关 saodg.packNativeXpAcceptance=true。原服、原账号与开发客户端未改；正式入场和奖励始终关闭，市场所有者仍为原来的 UNKNOWN，未伪造 CLEAR。

日志 logs/pack-native-xp-20261029.log，结果 native-xp-probe-6ed5d876-c843-4098-a0ef-4272b26810a0.json：passed=true，无清理错误。临时人物 UUID 74b84a2c-1b34-452b-82c9-64c290379540，实际经验所有者 saodg:sao_xp_curve_v2_1731657。运行 JAR 与散列见 [0.41.9 产物](DEVELOPMENT_PACKAGE_0.41.9.md)。

## 实际回调

使用世界中已发布的真实原版 Zombie 与真实 PlayerList 成员（生存模式），同步临时注册 RuntimeRun/ManagedEntity。仅在调用期间替换 InstanceService 的经验服务为独立目录日志，finally 恢复原服务与登记索引；不分配槽位、不生成结构、不传送人物，也不让临时局进入正式 tick。

反射调用实际已变换 ExternalKillXp.onDeath，而非直接调用 SAODG hook。原函数 amount 得到 13；取消事件无捕获，未取消的同一事件调用两次只产生一个 WAITING_DEATH 请求、数额仍为 13。人物 XP 保持 0，externalXpNoted 没有被旧 note 写入，证明本次原生数额调用和两个 Redirect 路径实际生效。没有投递整个 Forge 事件链，也没有将此通知冒充真实伤害致死。

独立日志没有确认死亡链接，重新构造读取器后将该请求标为 CANCELLED，待处理数为 0，仍不发经验。这是同进程日志重读，不能替代强制中断/重启恢复验收。

## 原生经验端口

另建仅用于端口验证的独立请求，以同一原生数额运行 SaoExperiencePort；没有伪造完成死亡链接或调用绕过市场门禁的服务领奖。

- 使用实际 PlayerData.get 初始化并校验当前曲线，保存原生人物基线文件。
- 在事务租约内打开真实 ChestMenu，apply 返回 close_container，经验/回执均不变；恢复库存菜单后实际 PlayerData.xp 将 0 增到 13。
- 回执为 MATCH，saveAndConfirm 从真实人物文件核对 UUID、SaoProgress.xp、回执和库存，返回 CONFIRMED；再次确认仍通过。
- 重复 apply 返回 native_xp.conflict，仍为 13，没有重复加经验；原 7 个带自定义 NBT 的铁锭保留，迷宫区成长及其他奖励数据不变。

该下层端口请求与回执只属于私有临时人物，保留作审计，不作为真实副本通关/经验归属凭证。没有覆盖跨级治疗/体力、经验上限、原生未打补丁曲线、完整服务发放链、晚取消/复活、真实客户端多人及全部崩溃边界。

## 清理和运行时观测

同次启动执行实际 /saodg admin metrics 成功；仅启动阶段短样本，不认证性能。测试后 status 为 runs/lobbies/pendingReturns/tickets=0、四槽位 FREE、journal=true，测试区块 [3,3] 未强加载。正常 stop，全维度保存完成、进程退出 0、25579 释放。临时夹具 JAR 移入 validation-history/native-xp-0419-20261029，审计人物/日志保留。私有运行 JAR 为 0.41.9，开发客户端仍未更新。

本轮仅编译/reobf 夹具与干净提交的 runtime JAR（14 秒 packaging_only），未重复 JUnit、默认 GameTest 或全量 build。正式开放条件未完成。
