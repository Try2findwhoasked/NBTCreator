# 0.41.8 私有整合包合并验收

仅在已授权私有目录 `run/pack-acceptance-20261028-081137-fd148a65` 更新运行时，原服未改。旧运行时 `0.41.7-dev` 保存至 `validation-history/saodg-0.41.7-dev-before-joint-0418.jar`。使用固定提交 `9f848296aaf43de7c26ff0d5e3b2819832b40ecb` 的 0.41.8 JAR，SHA-256 `9c8576fb8546ab5ef46df8b1d530481d8f181cfd08cd4bf84f00227875709465`，没有混入未提交 beta 素材。

本轮只编译 packTestJar/reobf，并启动一次实际整合包；显式 `-Dsaodg.packBindingAssetAcceptance=true` 开启 BindingAssetProbe，其余夹具关闭。没有重跑全量 JUnit/GameTest。私有入场/奖励仍关闭，外部资产 owner=market 仍 UNKNOWN，不给正式资产操作授权。

日志 `logs/pack-binding-asset-0418-20261028.log`；结果 `binding-asset-probe-5af96036-5f7f-410a-9322-d22d73518db6.json`：passed=true。安装散列和旧版路径在私有副本 `binding-asset-installation-20261028.json`。

## 已实际证明

- 临时人物 `036e20f7-1ba7-4c9a-ac64-11c2305dad91` 通过真实 PlayerList 登录。原始无市场回执时 ExternalAssetHistory 返回 false，避免一个总是返回 true 的损坏读取器冒充正例。
- 分别向该临时人物当前 Forge/Kube 根加入测试回执，实际读取均 true；通过真实人物保存后移除内存中的 Kube 回执，磁盘中保留的回执仍令检查返回 true。没有移除 KubeJS 模组，这不代替“卸载引擎后的完整启动”验收。
- 测试 finally 恢复原持久数据并保存，正常移出人物。没有产生真实市场订单或更改旧钱包。当前模板只读市场回执内容，未知类型也不会被当作 CLEAR。
- 管理员真实执行 `/saodg admin member dg_asset_probe` 成功，输出等级 1、职业未选、正常濒死状态、单人社交名单、无副本绑定。普通 permission=0 来源不能访问 admin 节点。
- 直接保存当前 FtbQuestReceiver Java 对象，受控 `/reload` 将代际 1→3 后，旧对象 route/team/personalSummary/checkAdmission/acceptFact 五个入口全部在执行前返回精确 stale_binding。新接收器 route 正常读取。用于旧投递测试的事实在绑定检查前被拒绝，不产生新任务事实。
- 原脚本探针也确认旧 facade 拒绝；各轮真实准入一直 pack_disabled，外部资产一直 UNKNOWN。

原包 NPC 的 registerPage 错误等既有第三方问题未在本轮修复或隐藏。该轮不证明实际市场事务、移除引擎启动、钱包完整故障矩阵、真实多人/客户端、原生经验新检查或整局通关已验收；正式门禁不变。

最终管理状态无活动副本/大厅/回程/票据，四槽位空闲；正常保存全维度、退出 0、端口释放，临时夹具移入 validation-history。私有副本保留 0.41.8 运行时与原始默认关闭开关。
