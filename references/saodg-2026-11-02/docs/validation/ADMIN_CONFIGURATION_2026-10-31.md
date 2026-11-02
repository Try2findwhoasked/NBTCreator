# 管理员配置与可调参数验证

2026-10-31；分支 `codex/admin-configuration`，开发版 `0.5.1-dev`，协议25，Minecraft1.20.1 / Forge47.4.10 / JDK17。操作、36项配置的默认值/范围/生效时机见[服务器配置说明](../SERVER_CONFIGURATION.md)。本轮没有改写 `v0.5beta`。

## 实现范围

新增15项可调参数，统一展示36项原有和新增服务端配置。管理员等级至少2，可从 `/saodg admin config` 和副本菜单进入；控制台支持 `list` / `set`。中文界面分为实例运行、生成性能、交互提示、奖励经验、安全回城、兼容接入，支持暂存、滚动、单项/分类默认值、无效输入标红、保存及未保存关闭/刷新确认。

专用请求/回包限制条数、字段长度和NBT大小。服务端核对实际在线对象、当前OP权限、白名单、全部输入、配置快照指纹及空闲条件，再统一保存当前世界的Forge服务端TOML；同局客户端不直接写服务端设置。配置指纹包含服务端会话与实际配置值，重启或其他管理员/文件修改后，旧编辑快照不能覆盖当前设置。

五项副本经验参数在开局时保存到 `reward_tuning` 格式1；旧记录缺省时使用历史默认值。自定义参数参与奖励结算指纹，旧默认指纹保持，不重抽物品、不修改SAO原生经验和钱包所有权；不追补旧局，进程重启继续中止未完成副本。

## 实际验证

| 检查 | 本轮结果 |
| --- | --- |
| 编译/打包 | `build -x test`通过；编译Java、全部GameTest/packTest夹具并生成JAR，明确跳过整套JUnit |
| 定向JUnit | 13项通过、失败/错误/跳过均为0；`domain.config.*` 和 `domain.reward.*` |
| Forge定向运行 | 17项必需测试通过；`saodg_config,saodg_math,saodg_completion_rewards,saodg_sync,saodg_circuit` |
| 管理员增强复验 | 新增控制台维度ID解析和撤销OP后旧编辑上下文拒绝断言，`saodg_config`全部3项再次通过；不是另外3个唯一用例 |
| 客户端视觉 | 实际开发客户端生成4张截图：运行分类、暂存的奖励分类、无效输入、640×480小窗口；小窗口滚动和跨分类暂存未丢失，无效输入为红色且保存禁用 |
| 内容审计 | 80间活动房，保留五个非活动功能定义；340/340份生产模板有引用，无错误 |
| JAR检查 | 340份生产NBT集合及逐字节对照一致；中文/默认语言一致、版号正确、管理员运行类齐全；不包含GameTest/packTest/预览类 |
| Git检查 | `git diff --check`通过；仅现有CRLF规范化提示，无项目级clean或制作资产清理 |

管理员测试使用两名真实PlayerList内的2级OP、一个普通玩家和一个复制UUID的非登记对象。覆盖普通玩家与假对象拒绝、两管理员旧快照冲突、无效混合批次不发生部分更新、NaN/越界/未知键/副本回城维度拒绝、实际世界TOML落盘、组队期间空闲项整批拒绝但立即/新局项可保存、OP撤销后旧权限上下文拒绝，以及带冒号的控制台维度ID。测试结束恢复所有配置并清理测试玩家/大厅。

首轮12项运行测试中权限夹具没有取得所需2级权限，被生产校验拒绝；调整隔离服务器的测试OP条目后，五个命名空间17项完整通过。没有降低生产权限要求。奖励测试检查自定义600基础经验+17继电机+两道9经验数学题，恰好635经验；运行记录回读、旧记录默认回退、未知格式拒绝、真实玩家保存与奖励日志重放不重复支付均通过。

视觉预览使用默认值投影与暂存编辑，没有连接服务器或调用保存。它证明实际渲染、缩放、滚动和草稿表现，不替代真人客户端与专服的端到端GUI操作验收。截图在 `build/previews/admin-config/admin-config-{runtime,rewards,performance,small}.png`。

## 可复现命令与证据

根目录、JDK17下执行，不运行项目级clean：

```powershell
.\gradlew.bat test --tests 'cn.saodg.domain.config.*' --tests 'cn.saodg.domain.reward.*' compileGameTestJava --console=plain
.\gradlew.bat --console=plain -I tools/ci/runtime.init.gradle runGameTestServer -x downloadAssets '-PgameTestNamespaces=saodg_config,saodg_math,saodg_completion_rewards,saodg_sync,saodg_circuit' '-PgameTestRunDirectory=run/admin-config-validation-final'
.\gradlew.bat --console=plain -I tools/ci/runtime.init.gradle runGameTestServer -x downloadAssets '-PgameTestNamespaces=saodg_config' '-PgameTestRunDirectory=run/admin-config-auth-final'
.\gradlew.bat --console=plain -I tools/ci/runtime.init.gradle runClient '-PadminConfigPreview'
.\gradlew.bat build -x test --console=plain
python tools/verification/content_audit.py --check
```

两组服务器测试使用各自新世界，只跳过客户端下载任务；`runtime.init.gradle`仅限制JVM资源。日志为 `build/admin-config-{tests,runtime,runtime-final,auth-final,preview-final,package}.log`，产物检查为 `build/admin-config-artifact.json`。定向JUnit结果不外推为默认完整套件通过，本轮未重跑30,000种子布局矩阵或全部默认GameTest。

## 产物与未验收边界

本机开发产物 `build/libs/saodg-0.5.1-dev.jar`，4,060,920字节：

```text
SHA256 8c29ef11b2cf7333c37e8a6cd2e666b091f7a9e43a11ec52ca3865e2d3af6463
```

产物来自当前未提交工作区，基线为 `ae0f2ec`，不宣称为已提交源码发布包。协议25要求客户端/服务端一起更新；GUI修改的是当前世界的服务端配置，不自动更新其他世界或`defaultconfigs`。本轮没有安装到活动存档、部署生产服或发布新标签。

真人双客户端同时编辑、完整SAO整合包、实际进程重启后的配置恢复及生产经济仍未验收。文件写入失败会尝试恢复原值并记录日志；无法写入磁盘的异常路径未通过破坏文件权限来模拟。已有准入、资产和实例隔离门禁保持。
