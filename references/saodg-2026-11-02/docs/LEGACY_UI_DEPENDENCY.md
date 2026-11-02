# 旧服 NPC 基础 UI 依赖

旧 `SAO-server-0.7` 拷贝包含 `sao_npc.js` 与 NPC 实体事件桥，但没有定义 `global.saoUI` 的文件。NPC 脚本加载到 `registerPage` 时失败；更改 priority 不能补上缺失提供器。

`compat/legacy-ui/sao_ui_core.js` 是现有 `Saomodpackdevidkwhy` 在提交 `3c9ac40e1da4279850c20ed1753fc6ce4687d0fa` 的完整原字节副本。源文件当时无工作区修改，未调整实现；散列与旧 NPC 依赖基线见同目录 `SOURCE.json`。它提供真实页面注册、KubeJS 胸箱菜单、按钮、余额只读查询和原有 `/sao` 命令路由。NPC 购买仍委托原钱包，不添加资产写入或奖励。

仅对项目内已准备且已停止的私有验收副本使用：

```powershell
python tools/compat/install_legacy_ui.py --target run/pack-acceptance-实际目录
python tools/compat/install_legacy_ui.py --target run/pack-acceptance-实际目录 --mode apply
python tools/compat/install_legacy_ui.py --target run/pack-acceptance-实际目录 --mode rollback --receipt legacy-ui-实际事务ID/receipt.json
```

默认仅计划。安装核对 NPC 基线、提供器散列、目标不存在和 Node 语法；拒绝覆盖现有 UI，先写 PREPARED 回执，再独占创建这一个文件并 fsync，完成后写 APPLIED。不改既有脚本、配置、JAR、EULA 或玩家文件。非多文件事务，也不声称断电写入天然原子；不完整文件保留等待人工核对。回滚仅删除回执对应的新增文件，散列不一致时保留人工修改并拒绝，回执始终保留。

此基础文件只内置 `about` 页面，旧 NPC 脚本另注册 `npc` 页面。旧副本还缺 `hub/shop/trade/auction` 等功能页面，调用这些页面会明确提示未知界面。此修复不导入新版商城/市场，也不把这些页面替换为空壳或宣称整个主城 UI 已完成。真实客户端显示、交易、命名实体右键与其他缺失页面需要分别验收。

定向检查：`node compat/tests/legacy_ui_dependency_test.cjs <旧 sao_npc.js>` 加载真实提供器和真实旧 NPC 脚本，用 Java GUI 替身验证目录、商人货架、确认、钱包委托、重复确认与实体路由；不等于真实客户端。`python -m unittest discover -s tools -p test_install_legacy_ui.py -v` 检查新增/回滚、重复回滚、人工编辑保护、已有文件及错误基线拒绝。

此脚本修复与模组 JAR 独立，不需要重新编译或替换已发出的 0.41.15。
