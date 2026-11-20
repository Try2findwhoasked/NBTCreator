# Java 1.20.1 细件的保守通路证明

`nbt_collision.check_routes` 对经过核实的细件使用碰撞障碍上包络，支撑仍仅来自已支持的完整块、半砖和楼梯。石墙、栅栏使用1×1.5×1，其余接纳细件使用单格包络。玩家包络仍为0.6×1.8格，沿半格采样图检查扫掠和连续支撑。这可证明返回的静态路线能避开实际形状，但可能拒绝真实可穿的窄缝，不认证所有路线或游戏效果。

## 版本与证据

规则版本为 `minecraft-java-1.20.1-bounded-obstacles-v5`。名单是固定的原版方块名，不按运行时名字后缀推断，也不接纳模组同名方块；每个状态继续通过1.20.1注册表校验。

v5 将已放置的原版水方块整格排除在静态步行路线之外。普通道路和梯段仍能通过干地检查，水格既不能进入也不提供站立支撑。报告列出实际水状态。水流、游泳、含水状态和邻接更新按各自的支持范围验证。

v4 增加 lantern 的单格保守包络，已核对 LanternBlock 的两种形状均在单格内。allium 和 lilac 单列为空碰撞花植，依据 Blocks 中的 noCollission 构造设置及 FlowerBlock、TallFlowerBlock 到 BlockBehaviour 的碰撞继承关系。两种花植不提供支撑。核对使用同一下方指纹的 Java 1.20.1 服务端，证据保存在本次藤袴创作项目的 `nbt_models/_workspaces/fujibakama/collision-evidence/`。植物存活条件、邻块更新、灯光和流体行为继续按实际游戏环境验证。

v3 核对 Mojang Java 1.20.1 服务端经 VanillaGradle 官方映射的类字节码：先从 `Blocks` 构造器核对具体方块所属类，再检查继承、碰撞方法、形状常量与偏移。映射后服务端 SHA256 为 `35a85fd83ec0054b602a73079918b46d669027ba5b26ea27818a98c119746aac`。本次证据保存在 `build/goal-collision-evidence/`，包括类检查日志、来源版本及方块到类的表；不作为运行依赖，也不分发 Minecraft 类。

| 类与实际接纳范围 | 保守上包络依据 |
| --- | --- |
| WallBlock，22种原版石墙 | `collisionShapeByIndex` 的柱与所有 low/tall 连接臂均使用 Y0～24像素，X/Z在单格内；不能按可见模型的16像素高度处理。 |
| FenceBlock，12种原版木栅栏/下界砖栅栏 | 传入 CrossCollisionBlock 的碰撞高度为24像素；所有连接状态联合仍在1×1.5×1内。 |
| IronBarsBlock、StainedGlassPaneBlock，18种玻璃板/铁栏杆 | 高度16像素，中央柱及水平连接不越出单格；染色玻璃板继承该形状且未覆盖碰撞。 |
| TrapDoorBlock，12种原版活版门 | 关闭顶/底板与四向打开板均为单格内3像素薄板。 |
| SnowLayerBlock，snow | 各层的形状不越出单格，碰撞使用 layers-1 项；不能把可见高度当成精确支撑高度。 |
| CarpetBlock、WoolCarpetBlock，17种地毯 | 形状为单格内1像素薄层；WoolCarpetBlock未覆盖该碰撞形状。 |
| PressurePlateBlock、WeightedPressurePlateBlock，15种压力板 | 未触发和触发形状的高度为1或0.5像素，均在单格内；不模拟红石或实体触发。 |
| EndRodBlock、ChainBlock | 六向末地烛、三轴链条的静态形状均在单格内；不把发光或纹理效果视为碰撞证明。 |
| pointed_dripstone | 各厚度形状水平2～14像素，最大水平偏移2像素，含偏移后仍在单格内；不模拟掉落、伤害与生长。 |
| lever、stone_button | 无实体碰撞，仍保守占用单格；不允许以它们充当地板。 |

门、砧、容器及其他未接纳类型继续作为未知形状拒绝证明。新增类型需要核对所有状态的碰撞、偏移与方块类；仅有模型预览或合法状态不足以扩展名单。

## 报告边界

- `passed=true` 仅证明返回的静态步行路径，不证明游戏加载、光照、伤害或全部构件可达。
- `collision_mode=bounded_obstacles_exact_support` 表示路线避开了已核实的包围障碍，支撑来自原有精确形状。
- `conservative_obstacles`、`obstacle_envelope_version` 列出实际使用的代理状态、数量和规则版本。
- 只要存在保守代理，`geometry_supported`、`exact_geometry_supported` 均为 false；不能改写成“细件精确碰撞通过”。
- `route_geometry_supported` 表示所有障碍都有受支持形状或已验证包络；任何真正未知/无效状态仍阻止 passed。
- `support_from_proxies_allowed=false`：代理从不提供站立、跨缝或步进支撑。

`conservative_obstacles=False` 保留严格模式，细件继续作为未知形状拒绝通过。低层 `collision_cells` 仍返回 unsupported，避免把上包络当成混材等价、接触接口或可靠地面。

从项目根目录运行 `mise exec -- python -B tests/engine/fine-collision-envelopes.py`，覆盖全部接纳状态、1.5格高度、不可支撑、绕行及严格拒绝。正式工作模型、refine和网页转换沿用同一检查报告，不将代理路线证明写成游戏实测。
