# 0.41.10 定向战斗流程回归

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

为减少无关检查，将既有 CombatGameTest 独立为 saodg_combat 命名空间，使用本项目原 empty.nbt 的同内容模板；默认命名空间列表仍包含它，不移除全量回归覆盖。未增加新的战斗测试实例，仅给原夹具加入最近两项修复的断言。

```powershell
.\gradlew.bat '-Dnet.minecraftforge.gradle.check.certs=false' runGameTestServer -PgameTestNamespaces=saodg_combat -PgameTestRunDirectory=run/gameTestServer-combat-0410-retry-20261029 --offline --console=plain
```

日志 logs/combat-0410-targeted-retry-20261029.log：只注册/运行 1 项 required，全部通过，BUILD SUCCESSFUL in 1m 23s，正常保存全维度并退出 0。该项内部执行三局成功挑战，以及必要敌人异常消失和真实死亡/重生两个非成功对照，不是五个独立 GameTest。

本次实际通过的新增断言：

- 服务端人物到达已完成的非入口房间，建立受信位置后调用 loggedOut/loggedIn，回到该房声明的 arrival，钥匙和修订不变。仍是同一人物对象的同进程回调，不是网络断线或新登录身体。
- 封印大厅准备阶段调用旧 readyBoss 取得精确 portal_only；钥匙保持 1、bossGateOpened=false、阶段和修订不变。随后真实封印大厅方块碰撞仍开启独立首领区，并将两个在线服务端人物一起传送。

原夹具的固定普通敌人/星标清房、精英/封印大厅波次、主路门/自由支路、安全房出口门、谜题/秘密、首领阈值/冲锋、结算停留、个人箱入口、外界领取去重、回程和独立首领区清理/票据断言也实际执行通过。它是开发环境中的受控人物和操作，不能代替用户客户端视觉、真实多人操作或带 SAO/KubeJS/TACZ 的整合包验收。

## 首次失败与夹具修正

保留 logs/combat-0410-targeted-20261029.log：首轮只运行同一项，在新增旧入口断言失败，BUILD FAILED in 51s。该位置由夹具直接 teleportToRoom 到达封印大厅，但没有像授权移动入口那样更新 lastRoom，因而未建立此检查所需的合法位置前置条件。

修正为在测试旧准备请求之前调用已有 authorizedSkillLocation，并明确断言 legalPosition=true，再验证精确 portal_only；失败诊断也输出实际拒绝原因。本次重试在新目录执行，没有放宽生产位置校验、跳过断言或复用失败世界。重试中 required_enemy_missing 是原异常对照的预期中止，最终 required 全部通过。

本轮未执行 JUnit、其余 GameTest、全量 build、私有整合包或客户端；没有打包/部署。私有 JAR 仍为 0.41.9，当前源码 0.41.10 的实机客户端检查仍待进行。
