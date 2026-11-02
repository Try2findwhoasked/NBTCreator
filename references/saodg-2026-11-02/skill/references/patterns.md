# 通用方块模式：带权随机、连片噪声与状态保留

`scripts/nbt_patterns.py`提供统一的 `pattern` 操作，供新作品生成器使用，也接入已有整体精修流程。它不是WorldEdit命令解析器，不要求安装WorldEdit；不改变格式转换默认原样保留方块的行为。只有明确指定规则时才处理。

## 生成阶段调用

在完整主模型中完成几何后、密闭与通路检查前处理材质；完成后继续正常密闭→开洞→验证→冻结→机械切片。初稿里的材质设计可以使用工具，不要把必要的设计表达全部拖到精修。

```python
from nbt_patterns import apply_pattern

# 先结束活动的WallMask追踪，取出准确的全局墙mask。
walls = wall_tracker.finish()
walls, report = apply_pattern(master, {
    'kind': 'pattern', 'label': '砌体的受控材质混合',
    'action': 'replace', 'lo': [1, 2, 1], 'hi': [46, 15, 46],
    'from_states': ['stone_bricks'], 'scope': 'surface',
    'palette': [
        {'state': 'stone_bricks', 'weight': 70},
        {'state': 'cracked_stone_bricks', 'weight': 20},
        {'state': 'mossy_stone_bricks', 'weight': 10}
    ],
    'mode': 'independent', 'fraction': 1, 'seed': 2718,
    'classification': 'inherit'
}, wall_positions=walls, protected=protected_positions)
```

这是48格单元中的API语法示例，不是推荐建筑骨架或固定尺寸。保存本次规则和report，随后重新验证并出图。`pattern_plan(model, operation, protected=())`只返回 `(edits, report)`，不改源；`apply_pattern`只用于design阶段，返回 `(新墙mask, report)`，不会自动验收、冻结或导出。它通过model.put写入，OperationTrace可正常记录；不可绕过墙mask结束/回收步骤。

## 字段与筛选

| 字段 | 行为 |
| --- | --- |
| action | replace为默认：只选已有非空气；fill按区域或mask填充，包括原来的空气，不接受from_states |
| lo/hi | 全局整数XYZ包围盒，两端包含，必须在主模型包围范围内；不是49展开坐标 |
| from_states | replace可选源选择器。只有方块名时匹配该ID所有状态；带属性时匹配这些属性的子集，以1.20.1默认值补齐后判断。省略时选非空气 |
| scope | volume默认选区域内候选；surface只选六邻接至少一面接空气的非空气方块，不区分室内/室外，需用区域或mask限定 |
| mask_positions | 可选的精确全局XYZ列表，须唯一且在lo/hi内；可由作者的墙mask、几何字段或功能分区生成 |
| palette | 字符串列表默认等权，或 `{state, weight}` 列表；权重须有限且非负，至少一项大于零，零权重不选。比例为相对权重，不必和为100 |
| fraction | 候选的抽样概率，默认1；与选择哪种材质使用独立随机通道。0为不修改 |
| seed | 整数种子；不使用Python随机hash或遍历顺序决定结果 |
| mode | independent为逐格独立随机；clustered为平滑相关噪声，形成较大材质斑片 |
| scale | clustered相关尺度，默认6格；也可按XYZ给三个>=1的值，用于拉长或压扁材质斑片，不等于精确斑片半径 |
| coordinate_origin | 默认[0,0,0]，在哈希/噪声采样前加到局部坐标上；用于明确的世界/作者坐标映射，可为负。不把运行时49间距混入作者材质坐标 |
| preserve_properties | 默认true：将源的兼容属性值继承到目标，目标明确填写的属性优先 |
| shape_policy | replace默认preserve，拒绝无法证明碰撞形状相同的替换；fill默认any，不认证原几何保持。显式any必须另验所有受影响项目 |
| classification | inherit默认沿用原墙归属；body移出墙mask；wall明确归墙。不能按最终材质推断归属 |

`protected`由API参数或精修配置提供；命中位置跳过并统计，不为了凑比例破坏门洞、路线、机关或重要节点。LogicalAssembly的缺角单元自动跳过并记录；普通Volume没有cells信息时，作者必须用mask或分区限制fill，不能让包围盒把缺角填满。精修另外按config.cells拒绝缺角写入。

## 可复现性与比例的含义

随机按完整作者坐标采样。一个整体的不同区域或48切面两侧不会因为遍历顺序、分片或重跑而重置相位；始终在完整主模型上执行，再切割。即使使用coordinate_origin保持采样相位，也不能用逐片处理代替整体的表面识别、墙归属及验证。

70/20/10表示**预期概率**，不承诺小区域恰好70%、20%、10%。同材质抽样不会计入changed，因此不能用“改变后的方块数”反推整体材质比例。报告分别记录eligible、sampled、changed、sampled_states、resulting_states、protected_skipped和footprint_skipped，判断时明确各自分母。

显式classification=body/wall时，同材质的抽样写入也会更新归属，不能因为几何没变就忽略墙mask变化。candidate_writes可包含这些写入，changed只统计方块状态实际变化，wall_membership_changed另记归属变化；plan_only区分只读计划与已应用报告。

clustered使用全局高斯值场、平滑插值、方差归一化和CDF映射；避免直接插值均匀噪声导致权重偏向中间值。它提供空间相关性，不保证每个色斑六邻接连通、固定面积或精确占比。需要确定的连片苔痕、沿面裂纹或坑缘破损时继续用 [weathering](weathering.md)。材质随机只表达配色/工艺/风化，不代替独立空间、构造和主题设计。

## 楼梯、半砖与未知形状

例如将 `oak_stairs[facing=east,half=top,shape=inner_left]` 换为未显式指定属性的spruce_stairs，会保留兼容的facing、half、shape和waterlogged。更换石砖半砖到安山岩半砖会保留type。目标明确指定facing=north则优先使用north；若这改变碰撞形状，默认preserve会拒绝。

保留属性不等于邻接或碰撞已经通过。preserve只使用现有保守碰撞工具证明局部几何不变，遇到未知形状不假定相同。目标方块及属性先经原版1.20.1索引校验，目标空气不允许；需要凿坑用已有几何/风化操作。填充或显式any后，要验密闭、真实通路、门洞、顶构和邻接；材质/状态变化仍不证明游戏中的摩擦、燃烧、流体和邻块更新行为正确。

## 已有作品与显式转换处理

只查看会修改哪些方块，可用无写入主模型的计划入口：

```powershell
python .agents/skills/minecraft-nbt-modeler/scripts/nbt_patterns.py plan --source <完整主模型> --operation <规则JSON> --output <新的计划目录>
```

它只导出候选编辑清单及统计，不产生修改后的NBT，不代替审阅、保护配置或任何技术验收。

对已有作品实际应用，先出对应缩略图并取得真实对话确认，再将 `kind=pattern` 加入nbt_refine的全局operations；或使用便利入口：

```powershell
python .agents/skills/minecraft-nbt-modeler/scripts/nbt_patterns.py apply --review <已真实批准的review目录> --operation <规则JSON> --style-note <本次整体材质意图> --output <新版本目录>
```

apply委托既有refine，沿用确认哈希、保护范围、变化预算、密闭/通路重验和主体/墙层重切，不提供独立审批或逐片写入通道。报告的operations内保留pattern统计。独立非48尺寸模型若不适用当前精修导出器，明确记录工具限制，不伪造review或阶段来绕过。

NBT/世界互转继续原样保留。用户明确要随机处理时，在恢复的完整主模型中显式应用规则，另存新版本，再走适用验收；不改写既有存档、原始转换输出或房间池。

回归：`python <skill>/scripts/check_pattern_fixtures.py --output <新的合成验证目录>`；该套也纳入nbt_task.py regress。只生成合成数据，不为用户资产制造确认。
