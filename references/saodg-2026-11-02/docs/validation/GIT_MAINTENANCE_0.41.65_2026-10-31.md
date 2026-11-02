# 0.41.65-dev 集成快照与 Git 维护

2026-10-31，Minecraft 1.20.1 / Forge 47.4.10 / Java17 / Gradle8.8 / ForgeGradle6.0.54，网络协议 **23**。本轮在实体奖励箱、继电机追加挑战、符文门效果三个任务均确认停止源码改动后执行；不是生产发布验收。

## 仓库归档

- 基线为 `c243c96b2a9b8465b154d387e84b9e25a443c878`（`v0.41.64-dev`）。集成分支为 `codex/integration-0.41.65-dev`，开发快照使用注解标签 `v0.41.65-dev`，保留开发后缀。
- 制作工具提交：`66c7dff`（`feat(authoring): add NBT world conversion and marker tools`）。包含可复用工具、测试、示例和制作规范，生成世界及作者素材不入库。
- 模组集成提交：`66e045381191a22bbbc610c74a46ac797c33c13d`（`feat(dungeon): integrate special rooms and reward encounters`）。这是下述构建与验证的代码快照；随后文档提交不改变其代码、资源或构建配置。
- 更新 README/开发说明的当前版本、协议和活动房池；CHANGELOG 将未发布的并行工作整合到 `0.41.65-dev`。为 Ogg 声明二进制 Git 属性，保留此前历史验证数据与未验证边界。
- `main` 和 `codex/event-sound-effects` 的原指向保留。远程 `codex/dungeon-message-isolation` 的 `115b587` 仍是独立未合入工作，没有擅自合并、删除或改写；既有 `v0.41.63-dev`、`v0.41.64-dev` 不改写。
- 已检查远程分支/标签、工作树和对象完整性。维护前的引用与历史 bundle 位于忽略的 `build/git-maintenance-20261031/pre-maintenance.bundle`。没有执行 `clean`、`git clean`、强制推送、历史重写或删除制作资产。
- `build/`、`run/`、`logs/`、`references/`、`.agents/`、可选模组 JAR 和生成世界不入库；文档中的截图是明确保留的验证证据。归档远程为仓库现有 `origin`：`https://github.com/Try2findwhoasked/SAODG.git`。

## 当前实现范围

79间活动房间保留精选/精修及功能房，包含8间特殊房替换和3间新增谜题。分散刷怪、高点弓手、大型怪和长路线实体预算保留；按后续决定使用原生怪物数值，取消额外玩家等级伤害/承伤倍率。

结算箱使用中央三倍实体和个人奖励事务；协议23要求两端一起更新。继电机房 Y 形立即清房，可选启动后接 Δ，每房为合格成员通关增加60副本经验，失败不撤销原清房。符文门首次开启只向附近本局成员发送落雷、电弧和原创风声，不生成服务端伤人/点火闪电。既有准入、资产和奖励所有者边界保留。

保存兼容范围：成功结果/原生经验请求及 `circuit_bonuses` 使用受校验的新增字段，旧局不追补；临时奖励箱不增加活动局跨进程续玩能力，不保证降级旧版读写。

## 实际验证

所有测试使用独立编译输出、项目缓存和新测试世界，未连接玩家服务器。主代码/资源在三个任务交付后冻结；维护中另修复了一处测试批次冲突。

### 单测与工具

1. 当前 JUnit **165项，0失败、0错误、2跳过**。两项跳过为未配置外部职业弓参考 JAR 的可选二进制检查，不能作实际组件兼容证明。日志 `logs/git-maintenance-validation-2026-10-31.log`，XML 位于 `build/git_maintenance_validation/test-results/test/`。
2. 本次明确排除3个此前已通过的重型参数用例（试炼/标准/精英各10,000种布局种子）。逐项比较当前与早前隔离输出的布局序列、房池及形状/端口/旋转/门高/优先级输入，并核对 `LayoutTest` 和全部布局实现源码哈希，均未改变。几何输入 SHA256：`2516eb5fa6b23bd7bf98ce01a3e610d60c7102a2b69b7b5f90ab6f9d88a12a33`。原通过证据保留于早前监督记录，不把它们当作本次重新执行的测试。
3. NBT 工具 **12/12通过**；人工房间标记脚本的 `--legend` 入口成功。日志 `logs/git-maintenance-authoring-tests-2026-10-31.log`、`logs/git-maintenance-markers-2026-10-31.log`。

JUnit init 过滤仅为：

```groovy
tasks.withType(Test).configureEach {
    filter {
        excludeTestsMatching 'cn.saodg.domain.layout.LayoutTest.tenThousandActualContentSeedsAreReachableAndKeysPrecedeLocks*'
    }
}
```

本轮是当前165项单测加已核对不变的3项重型证据，**不是一次默认完整 `test` 全绿**。需要全部重跑可直接执行标准 `gradlew.bat test`。

### Forge 组合复验

```powershell
$env:JAVA_HOME = 'D:\Java\jdk-17'
.\gradlew.bat -I logs/git-maintenance-validation.init.gradle --project-cache-dir .gradle/git-maintenance-validation --offline test runGameTestServer -x downloadAssets '-PgameTestNamespaces=saodg_circuit,saodg_rune_portal,saodg_sound,saodg_completion_rewards,saodg_exit,saodg_room_rewards,saodg_population,saodg_miniboss' -PgameTestRunDirectory=run/gameTestGitMaintenance20261031a --console=plain
.\gradlew.bat -I logs/git-maintenance-validation.init.gradle --project-cache-dir .gradle/git-maintenance-validation --offline runGameTestServer -x downloadAssets '-PgameTestNamespaces=saodg_circuit,saodg_rune_portal,saodg_sound,saodg_completion_rewards,saodg_exit,saodg_room_rewards,saodg_population,saodg_miniboss' -PgameTestRunDirectory=run/gameTestGitMaintenance20261031b --console=plain
```

首轮当前 JUnit 通过，18项运行检查中有1项失败：`RunePortalGameTest` 与 `ExitPortalGameTest` 同处默认批次、跨tick占用相同槽位3，符文门清理正确拒绝了另一夹具的 `reward_chest`。将符文门几何检查放入独立批次，未放宽生产资产白名单，未跳过检查。

最终 **18/18 必需 GameTest通过，BUILD SUCCESSFUL（3m23s）**。覆盖 Y→Δ 的成功/追加失败/持久化防重、三套首领房实体箱/归途门、领取和经验恢复、四向符文门效果及发送范围、68个战斗房间布点、小首领/原生数值和装备保护。日志为 `logs/git-maintenance-runtime-final-2026-10-31.log`；首轮失败日志保留，不称作全部通过。

运行目录加载79间房，内容哈希 `16dc3bd860f3e7acc87b02d01ee3abfac2b40b81b03b44e9936ae3d8d955b36f`。这是数据目录哈希，不代表后续 Java、协议或客户端实现未变化；当前不复用早前协议22的67项默认套件结论。

## 从 Git 源码构建的开发包

将代码提交 `66e0453` 用 `git archive` 导出到新的 `build/git-maintenance-20261031/export-code`，执行根 wrapper 的离线 **`build -x test`**，主代码、GameTest/packTest编译及重混淆打包成功（27秒）。测试依据来自上方独立调用，没有把跳过测试的构建写成完整测试通过。日志 `logs/git-maintenance-export-build-2026-10-31.log`。

Git源码ZIP SHA256：`c6dba2818fd21561994bdb89f3dd3371585eb3eaa5c6c9f9fa004a4d8b999aab`。

开发包：`build/verified/git-maintenance-0.41.65-dev-66e0453/saodg-0.41.65-dev.jar`，3,974,796字节；SHA256 **`f0adc84ddee7ff0e891c3961c1e878ecae2c322b67f1e60a1c462c58b8096cd8`**。同目录保留 `verification.json`、`SHA256SUMS.txt`；机器可读摘要位于 `logs/git-maintenance-results-2026-10-31.json`。

已打开JAR核对：版本、实体箱/渲染/符文效果/追加谜题类、refmap和15个声音事件齐全，338份生产模板与Git源码集合相等；中文及派生默认语言相同。不包含GameTest、packTest、本地beta模板或已撤销的额外战斗倍率类。JAR、源码ZIP及世界均不提交到Git。

## 未验证边界

未在真人双客户端、完整SAO/KubeJS/灾变整合包、实际经济支付、延迟丢包、完整硬重启矩阵或长期性能环境中验收。实体箱截图和各任务的定向验证见对应记录；符文门新增效果的真实客户端画面/混音仍待实机确认。没有部署到客户端、服务器或玩家世界，正式副本准入不因这次Git归档开放。
