# 0.33 恢复构建与基础运行时验证

日期：2026-10-28（Asia/Shanghai）。源码以 `5a82474` 为基础，包含本次构建仓库/测试夹具修正。
用户已明确恢复构建测试；此前章节中的“暂停/未运行”是当时状态，本记录覆盖下述实际执行范围。
正式 `SAO_SERVER` 仍阻断，不把基础环境通过外推到整合包或发布验收。

## 环境与命令

Windows，JDK `D:\Java\jdk-17`（17.0.12），Gradle Wrapper 8.8，ForgeGradle 6.0.54，Minecraft 1.20.1 / Forge 47.4.10。
测试服实际加载仅 Minecraft、Forge、SAODG；SAO/KubeJS/FTB/TACZ 不在此进程内。
原 `C:\Users\xiaju\.gradle` 首次运行因空间不足退出；没有清除/搬走原缓存。
只将所需缓存复制到工程忽略目录 `.gradle/user-home`，本次进程 TEMP/TMP 指向 `.gradle/tmp`。
补充 Architectury 官方 Maven 仓库，供编译期 KubeJS 的传递依赖解析，未升级任何固定依赖。

```powershell
$env:JAVA_HOME = 'D:\Java\jdk-17'
$env:GRADLE_USER_HOME = Join-Path (Get-Location) '.gradle\user-home'
$env:TEMP = Join-Path (Get-Location) '.gradle\tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
.\gradlew.bat build --console=plain
.\gradlew.bat runGameTestServer -PgameTestRunDirectory=run/gameTestServer-validation-2026-10-28 --console=plain
node compat/tests/material_policy_test.cjs
node compat/tests/asset_fence_test.cjs
python tools/verify_compat_patches.py 'D:/Documents/Coding/Game/Minecraft/Saomodpackdevidkwhy'
```

`gameTestRunDirectory` 是新增并实际使用的运行目录参数，默认仍为 `run/gameTestServer`。
本次指定目录开始时没有世界，创建了独立测试世界；原有测试世界保留，未操作任何客户端/真实服务器世界。

## 最终结果

| 项目 | 实际结果 | 直接证据 |
| --- | --- | --- |
| 完整构建 | 通过，当前主源码、GameTest 编译、重混淆打包完成 | `logs/build-resume-compile-2026-10-28.log`、`logs/build-resume-final-2026-10-28.log` |
| JUnit | 13 个测试套件、78 项，0 失败/错误/跳过 | `build/test-results/test/TEST-*.xml`、`build/reports/tests/test/index.html` |
| Forge GameTest | 34 个 required tests 全部通过，进程退出 0 | `logs/gametest-resume-clean-2026-10-28.log` 及该测试目录 `logs/latest.log` |
| 脚本策略逻辑 | 材料保全、市场状态两份 Node 夹具通过 | 上述两条 Node 命令正常退出 |
| 待安装脚本语法 | 6 份 `compat/kubejs/server_scripts/*.js` 通过 `node --check` | 实际逐文件执行 |
| 合并补丁 | 对 5 个源文件验证精确散列、完整补丁上下文/长度，写入 `build/compat-validation` 后 Node 语法通过 | `tools/verify_compat_patches.py`，不写源整合包 |
| 产物 | `build/libs/saodg-0.33.0-dev.jar`，1,324,884 字节 | SHA-256 见下 |

```text
8e6af2bcff5c86bfe851cc65ba8d7a607c63bf6eb5d246ee8a0d9a8a1e39463a
```

日志/产物/测试世界属于忽略的本地输出，未提交或安装到整合包。JAR 包含四份 Mixin 配置及 refmap。

## 失败定位与修正

首次 GameTest 完成 34 项，5 失败：两个夹具仍要求 23 房，清理清单仍假设一房一格；战斗夹具未把箭加入世界取得来源租约；奖励夹具在同一 tick 重试并错误期待越过 outbox 退避期限。
修正为明确检查 28 房/41 分片、逐个实际占用单元的清理覆盖；箭进入世界并确认可命中后注入伤害；奖励 ACK 故障在实际等待 220 tick 后检查去重与重投递。
这些修正没有放宽生产来源过滤、奖励退避、资产保存或正式入场门槛。

第二轮在既有开发测试世界中 33/34 通过，唯一失败是外来箱子预检夹具的 100 tick 截止。
该夹具等待异步区块实体加载；改为 600 tick，并增加“若放置竟然完成则立即失败”的断言，保留必须先拒绝并保全箱子的要求。
最终在上述新隔离世界执行全部 34 项通过。没有把先前失败轮记成通过，亦没有删除旧世界来修复生产数据。

## 覆盖与限制

- JUnit 覆盖生成图/钥匙顺序（每难度 10,000 种子）、稀疏房旋转、评分、大厅、谜题、等级/前置、固定奖励散列、秘密和冲锋纯规则。
- GameTest 覆盖真实目录加载/失败重载保留、维度/命令/协议、占用清理、50 次双位置放置票据循环、入场/回程/模式恢复、三类谜题实局通关/首领阈值、死亡取消/敌人丢失/人物真实死亡，以及原生免费奖励的真实人物文件与故障回执。
- 新材料/配方/村民、来源边界、外部资产注册代际、成长/秘密/首领定义等夹具按各自断言通过；部分只使用私有状态或未列入 PlayerList 的人物对象，不能宣称真实整合包交易/经验/联机已通过。
- 战斗夹具直接注入已授权伤害并快速推进，不验证真实箭飞行、普通敌人/首领实际预警命中、冲锋躲避、四旋转可达性或实战平衡。
- Node 采用假 Tag/Stack 或只解析语法，不验证 Rhino 重映射、KubeJS 加载/重载、原生钱包/市场保存、经济故障、FTB 或目标 gunpack。
- 未启动普通客户端；模型、HUD/GUI、网络插值与真实多客户端/双队、进程中断、性能/经济采样、安装/升级/回滚仍待验证。50 次双位置放置不是完整双队副本 50 轮。
- 日志含故意注入的坏重载、保存失败、消费方 ACK 失败/未知 schema 及所需中止，最终成功以 GameTest 总结与进程退出码为准，不能仅以无 ERROR 判断。
- Forge 开发运行报告 refmap 读取警告，重混淆 JAR 中已确认有 refmap，但尚未在正式整合包验证其应用；可选依赖未加载的钩子仍属未验收。依赖弃用提示没有升级固定基线。

完整目标未完成。下一步仍需完成内容缺口与上述实机/兼容验收，不把本记录作为开放正式开本的许可。
