# FTB 接收器代际约束

0.41.8-dev：ScriptBridge.connectFtb 原先返回 FtbQuestReceiver 本体，其公开方法只检查服务器线程。BridgeRegistry 会撤销自己的注册，但脚本若保留 receiver 引用，可直接调用 acceptFact/checkAdmission/personalSummary/team，绕过注册代理的代际检查。实际旧引用复用尚未在服务器复现，源代码边界已经明确存在。

接收器现在创建时必须传入 binding 校验器；ScriptBridge 传入自身 current 检查。创建在解析配置/发现 FTB 类/写日志前检查一次，之后所有公开查询与投递入口在原线程检查前再次校验，包括 route。旧 ScriptBridge 被重载或停服撤销后，保存的接收器也不能继续读取或投射任务进度。保留当前注册代际的正常行为；没有修改 FTB 内容、已有事实日志格式或队伍归属。

仅运行 `gradlew.bat test --tests cn.saodg.integration.ftb.FtbReceiverBindingTest --offline --console=plain`，两项通过：失效创建者在配置解析前拒绝，关闭的配置仍要求有效绑定且不加载可选 FTB/写文件。日志 `logs/ftb-receiver-binding-targeted-20261028.log`，编译成功。这些单测没有构造运行中的 FTB 接收器，不代表实际 reload 后旧引用拒绝已完成原生复测；该场景纳入后续联合整合包验收，避免此轮反复启动。

未部署，正式开本与奖励保持关闭。没有运行全量回归或服务器。

后续已在实际 0.41.8 私有包验证重载后旧接收器五个入口均拒绝，新接收器可用。见[合并记录](JOINT_0.41.8_2026-10-28.md)。
