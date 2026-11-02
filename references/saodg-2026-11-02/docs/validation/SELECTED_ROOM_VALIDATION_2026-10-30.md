# 已选房间接入验证（2026-10-30）

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

## 结果与来源

`build/选择/选择清单.json` 的63个图册条目，对应62座独立建筑；49/50是同一转角走廊。53座通过本次检查，其中17座沿用 `saodg:latest/...` 原ID、模板、刷怪点及遭遇配置，只增加识别信息；36座新增为 `saodg:selected/<形状>/<原目录>`。未通过的9座不进入生成池，原始交付文件保持原样。完整逐房目录、失败原因和235个生产NBT文件的来源/SHA256见[导入记录](SELECTED_ROOM_IMPORT_2026-10-30.md)及其JSON。

形状分类为27间单格、1间两格长条、6间三格长条、6间2×2大厅、6间L形、3间T形、4间十字形。另按建筑主题与出口种类分类。全部仅启用原朝向0度。

## 最终运行时检查

使用 `D:\Java\jdk-17`、Minecraft 1.20.1、Forge 47.4.10，执行：

```powershell
.\gradlew.bat runGameTestServer '-PgameTestNamespaces=saodg_selected,saodg_spacing' -PgameTestRunDirectory=run/selected-room-final-20261030 --console=plain
```

5项必需GameTest全部通过。实际ContentCatalog加载91个唯一房间ID、1个迷宫区；其中53个房间带本次精选识别信息。最终目录SHA256为 `86e8549a318ed036c48a4f5e449f931bf8cec3d0715d446559de3fcd0cf95430`。

- 53间全部通过当前StructurePlacer最终49格写入计划检查：注册表/方块属性、封闭外门后的六邻接空气洪水、实际Minecraft碰撞形状下的玩家落点/出口/刷怪点通路。
- 53间的逐房通过结果见[最终运行时记录](SELECTED_ROOM_RUNTIME_2026-10-30.json)。运行日志为 `logs/selected-rooms-runtime-final.log`。
- 最终房池在试炼、标准、精英三个难度各检查32个种子，共96个种子，并确认新精选模板实际参加生成。
- 同时通过现有 `saodg_spacing` 的原始拼缝、凹角方向和放置计划回归检查。

第一轮确实发现了3间的自动刷怪点选择问题，已调整接入坐标候选及采用原交付刷怪定义，未修改NBT。第二轮57个候选中4间因与外界空气连通被拒绝；最终只复测通过的53间。仅看Gradle退出状态不足以证明GameTest运行：中间一次启动曾因开发类加载失败而未执行测试，本文使用的是实际有5项通过汇总和53项逐房结果的最终运行。

## 构建与包内容

```powershell
.\gradlew.bat build -x test --console=plain
```

构建成功，完成主代码、GameTest和整合包测试夹具编译及重混淆打包。由于完整JUnit初跑发现未涉及的钱包隔离测试失败，打包命令明确跳过JUnit；不能将此记为默认 `build` 全绿。

产物：`build/libs/saodg-0.41.62-dev.jar`，SHA256：`1963d54321b4d6987b1ed988e44f4348fac1cd7df853ae1d74041cba886d938e`。直接打开JAR核对了91个唯一房池引用、53间精选定义、全部235个引用NBT与源文件哈希、识别类、中文/回退语言一致性，并确认被拒绝的SAO合集NBT未装入精选资源。未复制到客户端或正式服务器。

## JUnit与兼容范围

初次完整JUnit执行140项，发现6项失败：3项布局测试仍按固定门高Y2读文件；3项为未修改的 `LegacyWalletAssetScopeTest`。布局测试已按生产加载器的 `door_y` 归一化和 `selection_priority` 修正。后续布局种子与识别测试的结果另见下方最终补记。

最终补记：`test --tests 'cn.saodg.domain.layout.*' --tests 'cn.saodg.infrastructure.content.*'` 成功，试炼、标准、精英各10,000种子全部通过，耗时15分11秒；日志为 `logs/selected-rooms-layout-tests.log`。该长测试与候选收敛交错执行：试炼使用去重前候选池、标准使用去重后的候选池、精英使用最终91房池，因此不把它表述为最终房池的三难度30,000种子证明；最终房池另由上述96种子的GameTest复测。

随后单独复核新增识别测试的最终版本，3项全部通过，覆盖旧定义兼容、补零编号查询、重复编号与非法来源拒绝、形状/出口标签匹配，以及稀疏T形和非T形的区分。同一命令复现了钱包隔离3项失败，日志为 `logs/selected-rooms-identity-and-wallet-tests.log`；钱包生产代码与测试文件均未修改。

保留原功能房、旧ID和历史模板资源。迷宫区 `content_version` 更新为 `ruins-selected-20261030`；分类信息为可选 `identity`，旧房间可省略。现有房间的玩法规则不因建筑主题自动改变。新增管理员命令 `/saodg admin rooms [筛选条件]`，支持原图册编号（含补零）、形状、主题、出口类型及玩法类型；点击条目填写详情命令，`roominfo` 增加ID补全。识别信息只供管理员查询，没有增加未探索内容的客户端投影。

未逐房进行真人通行、全部旋转、动态液体、怪物寻路、双客户端、断线重连或存档重启验收；没有因此打开正式副本准入。

## 重现导入

```powershell
python tools/import_selected_rooms.py
python tools/import_selected_rooms.py --stage --write
.\gradlew.bat runGameTestServer -PgameTestNamespaces=saodg_selected -PgameTestRunDirectory=run/selected-room-candidate-check --console=plain
python tools/import_selected_rooms.py --write --runtime-report run/selected-room-candidate-check/selected-room-runtime.json
```

暂存阶段可能包含待拒绝的候选，必须消费实际GameTest生成的逐房报告再打包。运行时门槛将结果绑定到完整房间定义SHA256；最终写入再次核对原始副本与目标NBT字节。完整源文件审计会检查分层互斥、覆盖、48格规范和完整模板逐块一致性；暂存完成后消费报告时重用源审计并重新计算文件哈希。只删除本导入器目录内、仍与已审计原件哈希一致的过期模板，遇到未知修改会停止。
