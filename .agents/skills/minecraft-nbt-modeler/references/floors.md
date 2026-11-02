# 自动地面候选识别、半砖匹配与适量破损

`scripts/nbt_floors.py`提供 `auto_floor`，不必逐层手写floor.levels或为每种常用材料拆配置。它从明确的玩家起点、必要目标和室内空气探针出发，识别可达的多层完整承托面，按实际方块匹配半砖，再规划局部半格凹陷和有底坑洞。它不是地形或家具的语义识别器，也不替代游戏验收。

## 按风格主动采用

新建/重设计房间时主动考虑地面的使用痕迹和起伏，不因用户没单独写“挖坑”就默认整片平铺。废弃工坊、遗迹、旧通道、自然岩洞一般以worn/ruined/cavern为起点，控制在少量成片区域；维护良好、礼仪、精密操作或整洁风格可保持完整并说明理由。用户要求平整时遵从用户。

| profile | 默认目标破损率 | 半砖在破损中的份额 | 默认每片格数 |
| --- | --- | --- | --- |
| maintained | 0 | 1 | 2～3 |
| worn | 4% | 85% | 2～4 |
| ruined | 8% | 70% | 2～6 |
| cavern | 6% | 85% | 2～5 |

这些是工具的起始预算，不是每间房的固定配额。agent根据用途、材质、空间比例和路线调整，给出style_note；不让洁净大厅一律长坑，也不让遗迹只有换色。保留安静的完整地面、主要站位和通行节奏；局部破损不能替代大尺度地形、空间或构造设计。

在初稿阶段落实适用的地面设计，不把全部处理延后到精修。推荐主空间、基础地面、必要路线和门口定义完成后，在添加碰撞工具尚不支持的细微道具之前运行；随后新增设备仍须复核通路。对于已完成的模型，不得临时删除装饰制造验证通过。

## 上下文来自已有设计记录

context至少包含：

- `start`：真实玩家脚位XYZ。
- `targets`：必要站位/目标的name→脚位映射，或脚位列表。与可用端口一起验证；不能用空目标假装通路通过。
- `interior_probes`：覆盖设计腔体的整数空气坐标；区分室内与外界/屋顶，不接受未声明漏口。
- `ports`：实际声明的min/max/facing端口列表；门槛、喉道及其支撑自动保护。无外门独立模型可为空。
- 可选 `protected_paths`、`protected_boxes`：特定桥/坡/回路的真实路径、设备或功能区保护。除自动到达路径外，声称的具体连接仍需显式检查，不能靠另一条绕行路径代替。

沿用coordinates/config里的坐标，不另造一套地板高度。SAODG的端口与尺寸协议仍先按当前加载器核对；此工具不取代schema、门洞尺寸或49运行拼接验收。

## 初稿API

```python
from nbt_floors import apply_floor_damage

# 主模型仍处于design阶段；先结束WallMask追踪并取回全局mask。
walls = wall_tracker.finish()
walls, floor_report = apply_floor_damage(master, {
    'kind': 'auto_floor', 'profile': 'ruined', 'seed': 2718,
    'label': '废弃石铺与木台的轻度凹陷',
    'style_note': '旧作业间保留顺畅主路，在非操作带呈现局部磨损',
    'exclude_boxes': [
        {'lo': [8, 3, 10], 'hi': [13, 8, 15]}
    ]
}, context, wall_positions=walls)
```

示例坐标必须改为本次真实设备范围，不能照抄。调用返回更新墙mask和报告；地面修改归主体，不按材质把地面拆进墙层。支持 `protected=` 额外整数坐标集合。工具只接受design阶段的直接写入；后面仍在原主模型完成首次密闭检查、开门、最终验证、批量看图和机械切片。

只想检查候选时：`detect_floors(master, context)` 返回 `(floor_positions, report)`；只读规划时：`auto_floor_plan(master, operation, context)` 返回 `(edits, report)`。这两个函数不修改输入，规划后会在副本验证密闭和必要通路，但不自动批准/导出建筑。

## 检测边界与材质匹配

检测先在验证副本中封回已声明端口，排除外部空气，再按现有碰撞器的0.6×1.8玩家和半格步进查找室内可达站位。六邻接候选空气不等于步行证明。屋顶的外表面、封闭空腔和无法步行抵达的桌面不会因为“上面有空气”就被识别为地面；各高度分别保留，不只取每列最高点。

同一Y的候选按水平连通分区，默认小于9格的零碎承托面跳过，以减少小型器件误判。大而可走的工作台、台座或屋内装饰平台仍可能成为候选，须用exclude_boxes排除；真正的小平台可显式调小min_area。检测报告不是语义识别保证，必须实际查看候选和最终地面。

内置匹配覆盖常用木板/竹镶嵌、石砖及苔石砖、圆石、花岗岩/安山岩/闪长岩、深板岩砌体、砂岩、石英、下界砖、黑石、末地石砖、紫珀、海晶石及对应切制铜等存在的半砖。每个目标都经随包1.20.1注册表验证，且必须是干燥下半砖。

裂纹石砖没有原版“裂纹石砖半砖”，因此用同家族石砖半砖，并在material_matches标为family_fallback；其他近似家族匹配同样明确记录。泥土、混凝土等没有合适原版半砖的材料保留原样，列入unmapped_states，不编造ID或擅自换成石砖。原有楼梯/半砖用于通路计算，但不反复下沉；干燥double半砖可作为完整地面匹配到同种bottom半砖。

确实需要覆盖匹配时，用 `slab_overrides: {"blue_concrete":"stone_slab"}` 等显式映射；这是作者允许的材质变化，目标仍校验形状和状态。含水地面不自动破坏。

## 门口与路线保护

工具为每个可用端口生成内侧站位，连同必要目标从start验证；自动保存这些实际路径，保护路径扫掠体积、横向余量、地板与下方支撑。默认route_margin=0.5格，门口额外保护约4格深的喉道及周边。protected_boxes向下补足支撑保护，已有protected_paths继续保留。

只在映射成功、未保护且四周有完整地面的区域成片处理。半砖凹陷保留下方完整块；坑深默认1格，底部和各层侧壁必须完整，不能挖穿薄楼板、外壳或通向下层房间。坑底不自动填补，无法处理就跳过。分片接缝不是造型边界，整体处理后才切片。

规划副本重新验合法门封回后的密闭、必要目标的通路，以及原先保存的具体路径是否仍可走。范围不足不会取消保护、撒孤立点或反复重跑凑数。房间定义声称的其他路线、旋转、49展开和实际游戏行为仍单列验证。

## 可选参数与报告

- `fraction`、`slab_share`：0～1，可覆盖profile；分母是检测、映射且未保护的候选地面，不是整个房间面积。
- `patch_size`：2～512的[min,max]，控制连片格数；`pit_depth`为1～8。
- `rim_width`：1～3，坑/半砖周围保留的完整地面环。默认保留原材质，不统一染成裂纹石砖；`rim_cracks=true`时仅对存在真实裂纹变体的材质更新坑缘。
- `include_boxes`、`exclude_boxes`：限定或排除全局范围；`min_area`默认9；`max_poses`默认250000，超出则拒绝不完整的检测结论。
- `route_margin`：0～4，默认0.5；`seed`为整数；`classification`固定body。

报告包含多层地面坐标/分区、映射与未映射材质、保护量、目标/实际数量、shortfall、半砖/坑洞数量、成片大小和前后路径/密闭证据。比例是目标预算，缺额必须保留并解释。maintained或预算为0时可以没有修改；不因此宣称地面设计已经过视觉验收。

未知碰撞形状会拒绝自动认证，不能把未知件当完整方块支撑或删除细节让报告变绿。先在支持的基础几何阶段规划，或补充有依据的形状/游戏检查。报告不证明流体、伤害、摩擦、动态方块更新、照明或多人行为正确。

## 命令与已有作品

```powershell
python .agents/skills/minecraft-nbt-modeler/scripts/nbt_floors.py detect --source <完整主模型> --context <上下文JSON> --output <新检测目录>
python .agents/skills/minecraft-nbt-modeler/scripts/nbt_floors.py plan --source <完整主模型> --context <上下文JSON> --operation <风格规则JSON> --output <新规划目录>
```

两个命令只写floor_report.json，不修改源模型。对已有作品实际应用，仍需对应缩略图后的真实确认；使用nbt_refine的kind=auto_floor或便利入口：

```powershell
python .agents/skills/minecraft-nbt-modeler/scripts/nbt_floors.py apply --review <已真实批准的review> --operation <风格规则JSON> --style-note <整体意图> --output <新版本目录>
```

精修从原config读取上述context，保留预算、保护、整体重验和主体/墙层重切。maintained/no-op无需发起只有零变化的精修。自动识别不授权approve，也不改写格式转换、世界或生产房间池。

合成回归：`python <skill>/scripts/check_floor_fixtures.py --output <新目录>`；已纳入nbt_task.py regress。材质/地面效果优先用render批量出图，实际查看完整入口、脚下、坑缘与多层关系，不用仅俯视或纯颜色图代替。
