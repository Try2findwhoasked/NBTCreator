# Java 1.20.1 细件的保守通路证明

`nbt_collision.check_routes` 的细件处理不是精确形状模拟。默认对下表的有限方块名单，按经核实的范围建立碰撞障碍上包络（通常单格，spruce_fence 为1.5格高），但不将代理格加入可用支撑面。所有姿态、扫掠和连续支撑检查仍使用原来的 0.6×1.8 玩家包络、半格采样及最多半格步进。若在更大的障碍之间找到始终由已支持几何承托的路线，则该路线也不会撞到包含在障碍内的实际静态形状。它可能拒绝真实可穿过的窄缝，不能证明所有实际可走路线，也不认证游戏效果。

## 版本与边界依据

规则标识为 `minecraft-java-1.20.1-bounded-obstacles-v2`。名单只接纳随包 1.20.1 注册表校验过的合法状态，不按名字后缀推测其他方块，不接纳模组同名方块。v2 新增经同一官方类核对的 spruce_fence：包络为1×1.5×1，不能用单格高度代替。

本次依据本机 Mojang Java 1.20.1 服务端经 VanillaGradle 官方映射后的类字节码，核对 `getShape`、构造器、方块属性和静态形状常量。映射后服务端 SHA256 与检查日志记录在本次维护的 `build/skill-unblock-20261103/collision/source-evidence.json`；这些本机维护证据不是分发依赖，不复制 Minecraft 类或资源到 skill。

| 接纳的方块 | 核对的类与上包络依据 |
| --- | --- |
| chain | ChainBlock 三轴 shape：轴向 0–16 像素，横向 6.5–9.5，均在单格内。 |
| iron_bars | IronBarsBlock 的 CrossCollisionBlock 构造参数为高度 16 像素；中央柱及水平连接联合仍在单格内，不沿用栅栏的 1.5 格碰撞高度。 |
| iron_trapdoor、spruce_trapdoor | TrapDoorBlock 的关闭顶/底板、四向打开板都是单格内 3 像素厚薄板；这里只用单格上包络，不提供薄板支撑。 |
| pointed_dripstone | PointedDripstoneBlock 各 thickness 形状最大水平范围 2–14 像素，Y 在 0–16；getMaxHorizontalOffset 为 0.125（2 像素），因此含偏移后仍不越出单格。只证明静态阻碍，不认证掉落/伤害/生长。 |
| lever、stone_button | 对应方块注册为无实体碰撞，仍保守地占用单格障碍；不会因无碰撞就被当作可站立地面。其朝向/触发状态和动态更新不由本检查认证。 |
| spruce_fence | FenceBlock 向 CrossCollisionBlock 传入 collision height=24 像素；中央柱和所有连接臂均为 X/Z 单格内、Y0–24像素。因此采用1×1.5×1障碍上包络，拒绝代理地面支撑，邻接状态仍须正确保存。 |

除上述 spruce_fence 之外的 fence、wall、door、chest、流体等仍保留未知或不支持结论。不能把高于一格的栅栏/墙加入单格名单。添加新方块之前需要核对所有接纳状态的碰撞上包络与偏移；仅看到一张预览图不足以扩展名单。

## 报告如何解读

- `passed=true`：仅证明返回的静态步行路径在本次碰撞模型内成立，不证明游戏加载、光照、伤害或所有构件可达。
- `collision_mode=bounded_obstacles_exact_support`：路径避开了已验证单格包围障碍；支撑来自原有支持的完整块、楼梯或半砖。
- `conservative_obstacles` 和 `obstacle_envelope_version`：列出实际采用上包络的状态、数量与规则版本；它们不属于精确形状已支持。
- `geometry_supported`、`exact_geometry_supported`：存在任何保守障碍或未知形状时均为 false；不能因 routes passed 就改成 true。
- `route_geometry_supported`：所有碰撞障碍都有已支持几何或已验证上包络。任何真正未知/无效状态仍为 false，并阻止 passed。
- `support_from_proxies_allowed=false`：代理从不成为地板，也不参与步进期间的连续支撑区间；即使它恰好在脚下也不可借它“搭桥”。

调用 `check_routes(model, start, targets, conservative_obstacles=False)` 可保留严格精确形状检查：名单内细件也作为未知形状拒绝通过。低层 `collision_cells` 仍对这些细件返回 unsupported 原因，避免混材/完整块检测把包围盒误作精确几何或可靠地面。

正式 refine/网页转换沿用同一验证报告，保留上述模式、状态与未验证项。不能把该路径证明写成“薄构件碰撞完全支持”或“已在 Minecraft 实走”。
