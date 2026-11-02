# Boss 击败后归途门（0.41.65-dev，2026-10-31）

## 行为与接入

- 既有 `completePrototype -> SETTLING -> SettlementService.begin` 流程在准备个人奖励后生成结算箱与一个归途门；战斗中没有离场门。
- 门为独立的 13×13×7 内部摆件，黑石厚尖拱、石英内套、铜质侧脊、金色冠部与海晶灯嵌件，双面半砖台阶从脚位 0 经 0.5 到 1。34 格青色门面使用新注册的无碰撞 `saodg:exit_portal`，附解析生成的 24 帧动画、末地烛粒子和一次信标开启音效。
- 不修改三个已精修 Boss 房的 NBT。摆件按现有 49 格运行坐标放置，逐个候选检查房间归属、全体积空气、地面支撑、直线入口净空、方块实体和实体占位，再写入非空气构件；支持转向备用位置。无安全位置时保留原方块、奖励与命令回程，使用专门的回退提示。
- 只有结算期本局在线、存活、可行动且拥有本局返回日志的玩家，实际接触登记门面及相符方块时才能返回。调用既有 `leave`，沿用伙伴归还、原返回点/模式恢复、人物保存回读和日志清除；不发奖、不替队友退出。重复碰撞不能重复返回或发奖。
- 两分钟停留上限保持；最后一名队员离场后进入原有回程/清理流程。门完全位于已记录 Boss 区域，随正常清理移除。

## 资产与审阅

- 运行模板：`src/main/resources/data/saodg/structures/props/victory_exit.nbt`。
- 制作目录：`build/nbt_models/boss_victory_exit_20261031/`，含生成器、完整 NBT、坐标、回读与碰撞报告、阅读记录、三张已实际查看的离线预览及设计验收。
- 模板 SHA256：`9c9579be78ef6e2b9f0f69ab44a43b0f9c47511834905689efbe44d045f00f8f`。DataVersion 3465，单 palette，空 entities，无方块实体，1183 个显式体积坐标，317 个非空气方块。
- 独立门是现有密闭房间内的摆件；不新建房壳、不挖房间边界，所以新增房间密闭、6×5 边界端口及 48 格分片检查不适用。没有将静态玻璃当作可穿行传送门；作者模板中的青色玻璃只标记门面，运行时替换为自定义无碰撞方块。
- 主稿整体、未剖切玩家入口及侧墩近景已审阅；尖拱承接、侧墩嵌件、门套进退和台阶边缘达到初稿标准。没有调用 `nbt_refine`，没有制造用户缩略图批准记录；后续精修依技能要求另行等用户看图确认。
- 离线预览表示几何与程序颜色，不是游戏实拍；游戏光照、动画和纹理尚未进行客户端视觉验收。

## 本次验证

已通过：

- JDK 17 / Forge 47.4.10 编译和 GameTest 源集编译。
- NBT 独立解析回读逐块相等、半格图的 0.6×1.8 玩家碰撞路线。
- 首轮 `saodg_exit`（独立目录 `run/gameTestServer-victory-exit-20261031-c`）：1/1 通过，实际放置三个 Boss 房、生成完整门面、原有实心建筑不变、入口半砖碰撞、两名 PlayerList 受控玩家依次返回、同队结算继续、原位置/模式/背包与人物保存确认、非成员/战斗期/无本局日志/假门/远程/重复调用拒绝，以及清理和票据释放。

最终定向运行：

```powershell
$env:JAVA_HOME = 'D:\Java\jdk-17'
.\gradlew.bat runGameTestServer -x downloadAssets '-PgameTestNamespaces=saodg_exit,saodg_return,saodg_room_rewards' -PgameTestRunDirectory=run/gameTestServer-victory-exit-20261031-e --offline --console=plain
```

结果：**3/3 通过**，`BUILD SUCCESSFUL in 1m 45s`。除上述覆盖，还验证 16 个候选位置全部被占时不覆盖外来方块，阻挡正反候选后自动选择旋转 90 度门面、旋转半砖/楼梯和实际碰撞路线；原有 `saodg_return` 安全回程及 `saodg_room_rewards` 钥匙/箱体检查一同通过。日志：`build/nbt_models/boss_victory_exit_20261031/gametest-e.log`。本次内容快照 hash 为 `7c508e10b9ff8e66738f7fdbae87d035f1dd1da73745da56c7bc0856f7925caf`，不把该结果借用于后续改变的房间池。

早期运行保留：a 轮因夹具的 `Write` accessor 和比较器泛型未编译；b 轮的台阶采样在玩家前缘已进入半砖时仍使用较低脚位；d 轮在旋转门中沿旧方向移出的“假门”实际上仍属于合法门面。上述均修正夹具坐标/断言，最终按 e 轮实跑结果计数，不隐藏失败或将其归因于生产碰撞/权限代码。

构建：`.\gradlew.bat build -x test --offline --console=plain`，**BUILD SUCCESSFUL in 19s**。这会编译并打包当前工作区，也编译 GameTest/packTest 源集；没有运行默认完整 JUnit 套件。成品为 `build/libs/saodg-0.41.65-dev.jar`，不是附加的 `pack-acceptance` 测试包。

已打开成品 JAR，核对两个新增运行类、NBT、blockstate、模型、动画 PNG 与 mcmeta 均存在，所有新增资源字节与源码一致，派生 `en_us` 含中文门名；NBT 与已审阅主稿相同。完整成品 SHA256 和条目清单保存于制作目录 `package_verification.json`，本次技术结果汇总于 `validation.json`。

## 兼容与未验收

- 没有改变世界日志 schema、房间 schema、奖励账本或网络包；新门的运行登记只存在本局内存。服务器重启沿用既有未结束实例回程/清理和已准备奖励账本恢复，不尝试续建门。没有运行这次改动专门的崩溃/重登恢复实验。
- 客户端和服务端均须更新包含新方块与动画资源的模组。没有替换活动整合包 JAR，没有修改生产存档或运行中的实例。
- PlayerList 受控角色和独立 Forge 测试不等于真实双客户端、多队同时攻略或目标 SAO/KubeJS 整合包生产验收；这些尚未执行。
- 本次不声明默认完整 JUnit 套件为绿色；已有钱包隔离测试背景及其他并行未提交修改保持各自验证边界。
