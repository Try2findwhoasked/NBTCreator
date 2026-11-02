# 当前静态仓库兼容补丁后的契约验证

按 INTEGRATION_SPEC §10 与静态仓库 AGENTS.md，在当前工作文件的独立副本中执行四项原有 Node 验证。源 D:/Documents/Coding/Game/Minecraft/Saomodpackdevidkwhy 存在用户尚未提交的 NPC/任务线/商店及验证器修改，因此没有用旧 Git 提交替代当前文件，也未改动、提交或恢复那些文件。

verify_compat_patches.py --profile current 核对五份原始散列、精确合并上下文和 Node 语法后，将结果写入本工程 build/compat-validation。另把源库 kubejs/config/tools 当前文件复制到 .gradle/compat-contract-04113-2d06b228（实际为 kubejs、config、tools 三棵目录），再覆盖且仅覆盖五份已生成补丁：sao_assets、sao_ui_data、sao_commerce、sao_wallet、sao_quest_kill_history。副本 saodg-contract-snapshot.json 记录原始复制散列、来源、目标及覆盖文件；不是对源仓库安装补丁。

四项在该副本根目录独立运行，全部退出 0：

| 命令 | 实际 PASS 摘要 | 日志 |
| --- | --- | --- |
| node tools/incremental/verify_npc_ui.cjs | 52 NPC、配置隔离/匹配、目录/返回、确认取消、服务路由、手/侧检查 | logs/compat-contract-verify_npc_ui-20261029.log |
| node tools/incremental/verify_hub_ui.cjs | 玩家菜单、实时统计、只读装备/钱包、任务书/公告及局部导航 | logs/compat-contract-verify_hub_ui-20261029.log |
| node tools/incremental/verify_quest_history.cjs | 解锁后历史补记、队友累计、召唤/统计去重、失效对象排除、团队锁、重载/重复奖励保护 | logs/compat-contract-verify_quest_history-20261029.log |
| node tools/incremental/verify_npc_questline.cjs | 领域/配置、端口与奖励渠道、UI、交付和 NPC 集成 | logs/compat-contract-verify_npc_questline-20261029.log |

补丁预检日志 logs/compat-current-patch-20261029.log。这里只运行集成契约明确要求的四项原有检查，没有重跑 Gradle、地图/战斗或旧安装器测试。工具以 VM/stub 模拟脚本，不证明 Forge/Rhino、真实资产保存/市场反向互斥或真实联机行为。current profile 属于当前静态仓库，不能把这些结果当作原生旧服 sao-server-0.7 六脚本版本已升级或所有兼容已通过。原服、静态源库、旧原生验收环境均未写入，正式门禁仍关闭。
