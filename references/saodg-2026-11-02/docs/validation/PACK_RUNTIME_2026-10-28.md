# 完整整合包首次独立加载与实际冲突

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

用户明确同意 Minecraft EULA 并授权仅启动 `run/pack-acceptance-20261028-081137-fd148a65` 的本机测试服。仅在该副本写入 eula=true，授权记录保留在 `user-consent.json`；未更改原服务端或原玩家数据。
Java 17、Forge 47.4.10、原包 121 个模组 JAR 加已验证 SAODG 0.41.1，仅绑定 127.0.0.1:25579，SAO_SERVER 预设，开本/奖励继续关闭。

## 首次实际结果

输出 `logs/pack-acceptance-start-20261028-081137-fd148a65.log`：16:18:24 出现 Done（世界准备 118.221 秒）；原生 SAO、gameplay-fixes 2.3.3、KubeJS、FTB、TACZ 与 SAODG 内容目录实际载入。
这不是兼容通过。实际发现 SAODG 的 TaczBulletMixin 注入 tacAttackEntity 时只接收目标一个参数，实际方法还有 float 与 Pair 参数，Mixin 拒绝整个钩子；另有 SaoProfessionExpansionMixin 三个治疗 Redirect 被 gameplay-fixes 的 ExpansionBalanceMixin 抢占。
正式门禁拒绝开本，资料/濒死/队伍为 DETECTED_UNVERIFIED，KubeJS 桥为 REQUIRED_UNBOUND/UNAVAILABLE，不能因出现 Done 就标记原生技能与资产已验收。
还存在原包配方、进度、Curios 槽位与 LDLib 客户端类读取警告；没有无 SAODG 的对照试验，不将其全部归因于本模组，也未删除其他模组来掩盖冲突。

## 诊断与停服

首次启动的标准输入管道关闭，不能向原 exec 发送控制台命令。没有重复启动或强制杀进程。
本地一次性 Java Attach 辅助源码保留 `.gradle/pack-control-20261028`，先校验目标 JVM user.dir 精确匹配授权的私有目录、服务端对象必须为 DedicatedServer，再向服务器 Executor 排队执行 `saodg admin status`、`saodg admin validate` 和经本机 SRG 字节码核对的正常 halt(false)。辅助代码不包含任意命令接口或客户端控制。
16:19:51 诊断完成后出现 Stopping server，16:19:53 All dimensions are saved，原启动进程退出 0，本机端口释放。后续启动改用保留 stdin 的 tty 会话。

## 修复进度

0.41.2 将 TACZ 钩子签名补全为实际三个参数，保持原目标权限检查，不关闭钩子、不放宽伤害规则。职业治疗冲突仍待处理，不通过提高优先级强行替换原补丁的治疗数值。
修复从提交 `f6fd973a76b2822598232913da897cc3b44f8580` 导出干净源码构建，91 项 JUnit 通过；产物 `build/verified/0.41.2-dev-f6fd973a76b2-20261028-082122-17ab904b/saodg-0.41.2-dev.jar`，SHA-256 `4c042edfdfa99aa1ab4e0e73e9e5d7511404fab0982939ce4559058b33310c7f`，41 个结构无 beta，耗时 1 分 22 秒。
仅在已停服的授权副本中把旧 SAODG JAR 移入 validation-history 留存，复制上述新包，其余 121 个模组未删改。原玩家世界和原服务端仍未写入。
第二轮 `logs/pack-acceptance-tacz-signature-20261028-081137-fd148a65.log`：16:24:29 Done（准备 3.534 秒），无 TaczBulletMixin 签名异常；实际诊断 EntityKineticBullet=HOOKS_APPLIED_UNVERIFIED，证明该钩子已装配而不是仅有二进制匹配。
TTY 会话可正常输入，执行 `saodg admin status`、`saodg admin validate`、`stop`。16:24:47 Stopping server 与 All dimensions are saved，进程退出 0、端口释放；私有目录另保存 runtime-run-0.41.2.json。
第二轮仍出现三条治疗 Redirect 冲突，以及 sao_npc.js:177 的 registerPage 未定义等原脚本错误，没有将它们当成已解决。KubeJS 迷宫区桥尚未安装，状态仍阻断。
实际射击命中/取消、治疗效果、多人和完整资产矩阵均未验收；“HOOKS_APPLIED”不等于“技能已验证兼容”。
