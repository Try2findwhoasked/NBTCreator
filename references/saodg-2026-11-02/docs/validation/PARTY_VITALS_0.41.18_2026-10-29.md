# 队友生命与状态显示：0.41.18

源码提交 `354ba7fa02231c1f500010de6b353fff3234de85`，对应设计 M5 的队友状态可读性。原 HUD 仅显示姓名和状态颜色，现增加当前生命条、生命值和在线／离线／待救援／淘汰／待确认文字；完整地图页使用同一状态解释并显示生命值。仍不推测治疗、护盾或贡献数值。

服务端沿用每 10 tick 的本人实例投影，仅在队员实际在线、存活、未淘汰且仍属于同一实例维度时附带有限的 `health` / `max_health`。不向其他实例投递队伍资料，也不从离线记录读旧生命。客户端对缺失、错误类型、负值、NaN、无穷值和无效上限显示未知生命，不绘制满血条；超出上限的生命显示限制在条内。低生命改为醒目颜色，濒死状态优先提示救援。

这些字段为可选展示数据，协议保持 20，旧服务端未提供时新客户端继续显示原状态；没有新增客户端提交生命的请求。世界格式、经济、战斗和正式入场条件均不变。HUD 队员列表继续随小地图设置显示。四名队员的行末位于现有 208 高度内。

## 实际验证

在本提交全新 Git 导出 `.gradle/source-release-354ba7fa0223-20261029-043456-921a1ec8` 中执行：

- `test --tests cn.saodg.client.PartyMemberViewTest`：3 项通过，覆盖低生命、濒死优先级、离线／淘汰、未知状态、缺失／异常生命和超上限值。
- `runGameTestServer --offline --console=plain -x downloadAssets -x downloadMCMeta -PgameTestNamespaces=saodg_concurrent -PgameTestRunDirectory=run/gameTestServer-party-vitals-04118-20261029`：1 项通过，59 秒、正常停服。现有四人双实例／槽位复用场景新增实际快照检查：每名观察者收到的名单仅为自己的固定队伍，每条生命与实际在线人物对象一致；原隔离、门、清理和槽位复用断言继续通过。

首次合并执行时，3 项 JUnit 已通过，但 `downloadMCMeta` 连接超时，未启动 GameTest。保留 `logs/party-vitals-04118-initial-20261029.log`；随后校验上一轮同为 Minecraft 1.20.1 的 `version.json`，复制至此独立导出并跳过仅下载该元数据的任务。复用元数据 SHA256 为 `5a60bf164ed8c8af0d7547ec2e619b91a37bca2b566bdaa06acf796e85e95f1e`，未修改测试世界或断言以绕过失败。

成功运行日志：`logs/party-vitals-04118-20261029.log`。没有重跑全量 JUnit、原生整合包或其他未变命名空间。本轮未启动真实客户端、未取得画面截图或远程联机反馈；不把数据测试当作视觉验收。

## 开发包

`build/verified/0.41.18-dev-354ba7fa0223-20261029-043456-921a1ec8/saodg-0.41.18-dev.jar`

SHA256：`2e20fa5f72e3da3b55b8f8e2273193f3eac425beffb5a6ca6baee333d9008023`。

独立导出打包验证通过：41 个结构、481 个语言键、映射与 refmap、未跟踪 beta 目录排除。打包工具使用 `--package-only`，其 verification.json 如实标记没有执行测试；上述定向测试随后在同一导出另行执行。没有替换用户客户端、整合包或原服，也没有启动私有原生测试服。正式发布、真实多人、兼容与完整故障矩阵仍未完成。
