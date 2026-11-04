# 状态、邻接、操作来源与工具维护

核心工具按本skill目录定位引用，不依赖外部仓库。状态索引、渲染资源、碰撞几何与SAODG策略分别维护；不把其中一项支持扩展解释成其他项目已通过。

## 版本注册表

`block-registry-1.20.1.json`由本机原版Java 1.20.1服务端的 `net.minecraft.data.Main --reports` 输出压缩整理而来，包含1003种方块的属性枚举和默认值，并记录服务端、原报告和整理后内容的SHA-256。它不包含游戏JAR或纹理。

`nbt_registry.normalize`校验ID、属性名、枚举和重复属性，`nbt_model.state/put/load`使用同一入口；无效状态抛ValueError。省略属性仍保持原文件写法，避免悄悄改动旧模型指纹。碰撞和预览读取时用 `effective`叠加原版默认值；未知碰撞仍拒绝认证。部分已核实细件可用[保守障碍上包络](collision-envelopes.md)证明特定步行路线，但不认证精确形状，且代理不提供支撑。仅有合法ID的方块也可能被SAODG拒绝或在邻块更新时变化。

```powershell
python .agents/skills/minecraft-nbt-modeler/scripts/nbt_registry.py query "oak_stairs[facing=east]"
```

不手写修改注册表。确需重建时，在新的临时工作目录用JDK17运行自己的1.20.1服务端：

```powershell
java -DbundlerMainClass=net.minecraft.data.Main -jar <1.20.1_server.jar> --reports --output <新报告目录>
python <skill>/scripts/nbt_registry.py compile --report <新报告目录>/reports/blocks.json --server-jar <同一服务端JAR> --output <新索引JSON>
```

比较版本、数量和差异，确认输入报告确实由同一JAR生成，再替换随包索引并跑状态回归。编译器核对JAR版本并记录哈希，不自行证明报告与JAR的运行关系。模组方块、其他游戏版本及方块实体策略不由该索引授权。

## 全局邻接状态

`nbt_connections.resolve_connections(model, wall_positions=...)`只填补缺少的水平连接字段：玻璃板/染色玻璃板/铁栏杆、同类木栅栏或下界砖栅栏，以及一组明确的普通实心墙面。不同木种可连接；木栅栏与下界砖栅栏不连接。显式字段保持作者原值，工具幂等。

相邻墙、楼梯、半砖、栅栏门及其他未证明形态不会猜测连接：需要补充对应显式字段，或另扩展有版本依据的规则。工具不推导墙的low/tall/up、楼梯转角、门/活板门、红石、轨道、流体、支承或旋转。

完整几何完成后，先结束活动的WallMask写入追踪并保存mask，再解析连接；这只是原构件的状态更新，沿用返回的wall_positions。若仍有OperationTrace，它可以记录更新，但此后应重新保存来源记录。工具先计划所有写入，遇到不支持的邻接整体拒绝，不留下半更新模型。之后重新检查密闭、碰撞并冻结；不在切片内各自计算邻接。已冻结/已开门模型必须回到正规改稿流程，不能为了更新状态伪造阶段或丢弃原门洞证据。

## 操作ID与修改定位

`nbt_provenance.OperationTrace`为任务生成器提供可选的稳定操作ID和末次写入记录，不限制几何工具或空间骨架：

```python
from nbt_provenance import OperationTrace
trace = OperationTrace(master)
with trace.operation('north_arch', '北侧拱脚与承托连接'):
    # 调用本次设计自己的几何生成代码，最终经master.put写入。
    build_north_arch(master)
trace.save(task_dir / 'operations.json')
trace.close()
```

每个操作ID只注册一次；不同作品不能仅靠同一骨架的参数变化冒充独立设计。记录保留被挖空气的位置，后写覆盖更新归属，未标记写入归属为null。直接改blocks不会被追踪；不能将记录当作全部生成逻辑的证明。与WallMask叠用时按后安装先结束的顺序恢复put，避免丢失包装。来源记录绑定几何指纹；改模后必须重存。

接到修改反馈时，先关联源版本、具体坐标/截图和已有操作ID，再在完整主模型中修改。操作归属帮助定位，不要求只能编辑这一操作，也不自动证明改动已满足用户意见。反馈文件、预览按钮和操作ID均不等于用户在对话中批准精修。

## 统一入口与可选纹理预览

`nbt_task.py inspect`只读完整NBT或完整master JSON.GZ，校验状态并列出未执行项目；不重新认证密闭、路线或设计。稀疏单层不能冒充完整来源。`snapshot`生成新的只读审阅JSON，可附 `--provenance operations.json` 和 `--cameras cameras.json`（role/eye/target数组）。几何指纹不符的来源记录拒绝加载。

纹理质检的agent默认使用 `nbt_task.py render` 批量落盘PNG与元数据，再直接读取本地图片；网页 `preview` 保留给用户交互。相机JSON、可选依赖安装、整数剖切范围、性能设置、失败记录与浏览器专项回归统一见 [渲染与交互](rendering.md)。不为常规出图使用computer use逐次下载，也不把截图生成当作实际看图或用户精修确认。

## 维护与回归

```powershell
python .agents/skills/minecraft-nbt-modeler/scripts/check_skill.py
python .agents/skills/minecraft-nbt-modeler/scripts/nbt_task.py regress --output <全新的测试输出目录>
```

第一条检查本地引用、Python语法、注册表完整性及可选前端锁文件；第二条汇总现有check_*_fixtures.py和新增状态/来源回归，保存每套真实退出状态。合成fixture中模拟的确认只属于测试数据，不授权用户资产。维护skill无需重建SAODG或运行历史建筑示例；涉及模组接入或引擎行为另按工作区要求测试。

建模工具的定向回归为 `python .agents/skills/minecraft-nbt-modeler/scripts/check_modelling_fixtures.py --output <全新目录>`，覆盖几何/CSG、复制状态、旋转轴、形态学、扩散障碍、爆炸确定性、散落间距与保护/预算拒绝。check_refine_fixtures同时覆盖新geometry操作经真实精修入口（仅合成确认）重验及重切。新增kind同步维护nbt_tools.KINDS、精修路由、参数文档与可观察行为测试；不要只登记名称或假造passed。

复制分发前排除node_modules、__pycache__、任务生成物。`upstream-sources.json`记录参考仓库、固定提交、复用文件及修改说明；Apache预览源的原许可证保留在assets/viewer/LICENSE.upstream。minecraft-schematic-lab仅参考版本校验、操作ID和按版本反馈的思路，没有复制其AGPL代码、资源或指南。
