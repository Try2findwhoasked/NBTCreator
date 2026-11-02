# 连片风化：苔痕、裂纹与地面破损

`scripts/nbt_weathering.py`提供统一的`weathering`操作，可放入`nbt_refine.py`的operations，也可用单命令入口调用。它在完整主模型的全局坐标中处理，再由精修流程重验、切片；不能逐片重置种子。仅制作/测试工具无需建筑精修授权；对已有作品实际应用仍沿用[精修流程](refinement.md)中对应缩略图后的真实用户确认。

## 三类效果

- **苔痕**：在相连的指定原材质表面上从种子点生长，优先填充共享边较多的邻块，形成不规则斑片。`patch_size`控制每次生长的格数，不是半径；相邻斑片可能合并成更大的区域。
- **裂纹**：沿六邻接表面进行带方向惯性的游走，少量分叉、绕过障碍。`length`控制每次裂纹生长的格数；`straightness`越高越倾向延续原方向，`branch_chance`控制从已有裂纹换支点继续生长的概率。坑缘另有连续裂纹轮廓。
- **地面破损**：在明确标出的地板层上选择相连的小片区，按`slab_share`混合下半砖与整块坑洞。下半砖留在原地板方块坐标，顶面降低0.5格；坑洞移除顶部和指定深度内的方块，露出下方真实空间及坑底，周围整砖替换为裂纹材质。地面同样不以独立逐格撒点实现。

三者可独立关闭（fraction=0），也可一次组合；工具不会自动猜测“同类材质”。默认处理石砖，其他材料需要显式提供源、苔痕/风化、裂纹和半砖对应关系。不能把完整方块的规则直接用于楼梯、半砖、方块实体或带状态的装饰。

需要自动识别可达地面、匹配常用材料家族并按房间风格主动规划时，使用新的[auto_floor工具](floors.md)。本weathering操作保留原有显式levels/材质配置及默认行为，不静默改写旧作品效果。

## 一份操作配置

例子适用于地板方块位于Y=3、足部位于Y=4的96×14×48完整模型；按真实尺寸与楼层修改lo/hi/levels。坐标端点均包含在内。保存为本任务目录中的`weathering.json`：

```json
{
  "kind": "weathering",
  "label": "潮湿石砌空间的连片风化与地板破损",
  "classification": "inherit",
  "lo": [1, 1, 1],
  "hi": [94, 11, 46],
  "from_states": ["stone_bricks"],
  "seed": 2718,
  "moss": {
    "fraction": 0.16,
    "patch_size": [16, 45],
    "state": "mossy_stone_bricks"
  },
  "cracks": {
    "fraction": 0.14,
    "length": [8, 22],
    "straightness": 0.86,
    "branch_chance": 0.06,
    "state": "cracked_stone_bricks"
  },
  "floor": {
    "fraction": 0.055,
    "levels": [3],
    "slab_share": 0.6,
    "patch_size": [3, 7],
    "pit_depth": 1,
    "rim_width": 1,
    "slab_state": "stone_brick_slab[type=bottom,waterlogged=false]"
  }
}
```

常用调整：

| 参数 | 含义与范围 |
| --- | --- |
| moss.fraction / cracks.fraction | 各自占原始可处理表面方块的目标比例，0～1 |
| moss.patch_size | 每次连片生长的最小/最大格数，默认[12,40]，2～512 |
| cracks.length | 每条裂纹的最小/最大格数，默认[6,18]，2～512 |
| cracks.straightness / branch_chance | 0～1，默认0.8/0.12 |
| floor.fraction | 占指定楼层可处理地面的目标破损比例；默认0，显式开启 |
| floor.levels | 地板**方块**Y值列表；启用地面破损时必填，不自动选择屋顶或平台 |
| floor.slab_share | 破损方块中半砖凹陷的目标份额；0为全坑洞，1为全半砖，默认0.65 |
| floor.patch_size | 每个地面破损片区的最小/最大格数，默认[2,6] |
| floor.pit_depth | 从原地板顶面向下的整格深度，1～8；默认1，只移除顶部整砖 |
| floor.rim_width | 地面破损周围裂纹轮廓的格数，1～3，默认1；含转角以保持连续 |
| seed | 整数；同主模型、范围、保护配置和参数得到同一结果，不受字典遍历顺序或Python哈希种子影响 |

未写moss或cracks时分别默认12%/6%，只做地面时显式将两者fraction设为0。每项完整参数见上例；未知参数、非有限比例、无效范围或不支持的形状会拒绝，避免拼错参数后静默使用默认值。

## 比例、冲突与结构保护

比例是目标预算，不保证在小区域或障碍密集区域精确满足。分母在本次操作开始时固定：表面是范围内、未受保护、匹配from_states且六面之一接触**模型内空气**的方块；地面还要求处于levels，头顶至少两格空气。埋藏底层、模型外空气及其他材质不算表面。仅从可处理片区扣预算，不修改保护区来凑比例。

顺序为地面破损与坑缘 → 补足目标的连续裂纹 → 苔痕。裂纹和苔痕不覆盖坑洞或半砖；苔痕不覆盖裂纹。地面坑缘是必需的裂纹，计入cracks总数，即使超过cracks.fraction也保留，报告rim_excess。其余裂纹只补目标缺额。目标不足最小片区时保留缺额，不把剩余预算均匀撒成孤立点。大比例、大片区或受保护路径较多时可能明显不足，检查报告中的shortfall，不自动调大范围或取消保护。

地面处理只接受已有完整地板。半砖下方必须有完整支撑；坑底必须在模型内且为已知完整方块，坑深内只移除指定源材质或已有空气。坑侧壁在每层保持完整，原有有底且有侧壁的小空腔可按指定坑深露出，薄地板与通向下层房间/外部的空洞会跳过。开挖坐标必须在lo/hi内，故深坑的lo.y要包含其开挖深度。底部不改写，也不自动补方块伪造封闭。

范围外、其他材质、门槛、保存路线及其支撑、额外保护节点均保持原样。随机选区主动避开这些保护；最终精修流程继续执行全局变更预算、密闭、通路和墙归属检查。不能用这一操作自动认证深坑可通行；关键路线应列入protected_paths，静态通路仍以原碰撞器能力为限。

## 工具调用与结果

对已按精修流程prepare并记录真实用户确认的review，一条命令组合三类效果：

```powershell
python .agents/skills/minecraft-nbt-modeler/scripts/nbt_weathering.py --review <任务目录>/draft_review --operation <任务目录>/weathering.json --output <任务目录>/weathered_01 --style-note "按潮湿区域成片长苔、连续开裂，地面局部破损并保留主路"
```

CLI沿用原确认和原保护配置，不另造确认、不覆盖原稿。输出与nbt_refine一致：完整主模型、逐块diff、同相机对比、重验报告、重新切片的body/walls与独立runtime模板。`refinement.json`的operations[].weathering保存目标/实际数量、实际比例、缺额、片区大小、半砖/坑洞列数、坑深和坑缘裂纹数量。尚未进行游戏运行验收时runtime_verified保持false。

也可把上面的操作直接放入精修plan.operations，与其他节点操作组合。需要在自定义生成器或合成测试中复用算法时：

```python
from nbt_weathering import weathering_plan
edits, report = weathering_plan(whole_master, operation, protected=protected_positions)
```

该函数只返回坐标/状态和报告，不修改输入、不导出文件、不证明真实用户授权。对现有作品落盘仍走精修入口，以保留墙mask、保护验证和统一重切；不要循环调用单片模型。

验证命令：

```powershell
python .agents/skills/minecraft-nbt-modeler/scripts/check_weathering_fixtures.py --output nbt_models/_tests/weathering_validation
```

只创建合成fixture的新运行目录，覆盖连片/裂纹、比例、跨切面、跨进程复现、坑深与支撑、状态保留、保护路线、授权/预算和CLI整体重切。`--skip-workflow`仅跑算法用例，不代表完整精修流程通过。诊断图使用程序配色，不能当作真实游戏材质或光照预览。
