# 三倍奖励箱实体（2026-10-31）

按用户后续要求，将结算奖励箱改为实体放置并等比放大。此前的经验与个人奖励事务不变；本次仅调整展示、点击入口和临时实体生命周期。

## 行为

- 新类型 `saodg:reward_chest`，原模型 XYZ 同时乘以 `3.0`，三档材质和开合模型继续复用。闭合箱体点击范围按三倍扩大，光环扩大为原来的 1.8 倍；点击不会生成共享库存。
- 固定位置、无重力、不可推动/骑乘/跨维度、免疫攻击，不掉物品。不开启普通召唤与实体存档；重启沿用原有实例中止、玩家回程和区域清理，不恢复战斗或生成新的奖励。
- 仍优先首领房中央。放置检查扩大为最大开盖范围：4.6 格宽、4.65 格高，约 5×5 地面支持与五格空气检查，包含方块实体、流体、房间边界和已有实体的拒绝；保留原地板，不放置奖励箱方块。中央受阻则在既有半径六格内寻找安全位置。
- 本局运行时登记唯一实体 UUID 和 run UUID。服务端实体交互同时检查真实在线玩家、本局成员、存活/非旁观/可行动、结算阶段、维度、实体身份/锚点、距离和方块视线。复制类型或 run UUID 无法取得权限，遗留奖励箱方块不再是结算入口。
- 主手普通/具体实体点击事件仅为这种箱子放行，其他实体仍维持原有迷宫区交互禁令。成功点击打开原个人面板，40 游戏 tick 后合盖；重复点击仅重开显示，不增奖、不重抽、不延长副本停留。
- 清理只额外允许本局登记的准确实体类型、UUID、run UUID，不按整个实体类型或伪造 NBT 放宽未知资产保护。

## 修改文件

新增 `platform/forge/entity/DungeonRewardChest.java` 和 `client/DungeonRewardChestRenderer.java`；更新注册表、客户端注册、中央放置、结算、实体交互拦截、实例清理白名单、客户端光环与中文名称。原方块和物品模型保留给已有资源/菜单使用。

新增 `RewardChestEntityGameTest`，更新 `CompletionRewardsGameTest`、`ExitPortalGameTest` 和隔离场景摄影夹具。只有显式 `rewardChestScenePreview` 属性会加载摄影夹具；可以指定 `rewardChestSceneWorld` 和 `rewardChestSceneOutput`，不打开玩家存档。

本次实际文件清单（均相对于仓库；同一文件中其他并行任务的改动不计入本任务）：

- `src/main/java/cn/saodg/platform/forge/entity/DungeonRewardChest.java`
- `src/main/java/cn/saodg/client/DungeonRewardChestRenderer.java`
- `src/main/java/cn/saodg/client/RewardChestEffects.java`
- `src/main/java/cn/saodg/client/ClientRegistration.java`
- `src/main/java/cn/saodg/platform/forge/SaodgRegistries.java`
- `src/main/java/cn/saodg/platform/forge/SaodgNetwork.java`
- `src/main/java/cn/saodg/platform/forge/InstanceEvents.java`
- `src/main/java/cn/saodg/platform/forge/RewardChestScene.java`
- `src/main/java/cn/saodg/application/SettlementService.java`
- `src/main/java/cn/saodg/application/InstanceService.java`
- `src/main/resources/assets/saodg/lang/zh_cn.json`
- `src/gameTest/java/cn/saodg/RewardChestEntityGameTest.java`
- `src/gameTest/java/cn/saodg/CompletionRewardsGameTest.java`
- `src/gameTest/java/cn/saodg/ExitPortalGameTest.java`
- `src/gameTest/java/cn/saodg/client/RewardChestScenePreview.java`
- `build.gradle`、`CHANGELOG.md`、`docs/DEVELOPMENT.md`
- 本记录、`docs/validation/COMPLETION_REWARDS_2026-10-31.md` 的历史快照提示，以及 `docs/validation/images/reward-chest-entity/` 下三张实拍 PNG。

网络协议从 22 升为 **23**，服务端与客户端必须一起更新，防止旧客户端缺少新实体类型/渲染器。不修改已有物品奖励、经验账本或世界 schema；临时箱子 UUID 不写入正式奖励记录。

## 验证记录

d 轮定向运行：

```powershell
.\gradlew.bat runGameTestServer -x downloadAssets '-PgameTestNamespaces=saodg_completion_rewards,saodg_exit,saodg_room_rewards' -PgameTestRunDirectory=run/gameTestServer-reward-entity-20261031-d --offline --console=plain
```

**6/6 必需夹具通过**，日志 `build/reward-entity-gametest-d.log`。覆盖三套实际 Boss 房的中心实体、原建筑保持与登记实体清理、四向人工阻挡/拒绝、普通和具体实体点击事件、两名真实 PlayerList 成员、外队/旁观/战斗期/远程/墙后拒绝、伪造 UUID 拒绝、不可推动/受伤、三倍箱体尺寸、无存档/召唤、重复打开不变更资产、实际实体 ticking 后自动合盖，以及原经验/个人奖励保存恢复回归。隔离夹具在生成实体前强制加载并等待测试区就绪，与生产放置任务持有的实体 ticking 区域票据对应；测试结束释放票据。

未运行默认完整 JUnit，不把独立运行测试当作真人双客户端、整合包支付或生产验收。本轮没有提交、切换分支、推送或打标签。

早期检查保留：`build/reward-entity-compile.log` 初次编译暴露出场粒子半径变量引用错误，已修正；a 轮运行暴露测试夹具未强制实体 ticking、清理空引用掩盖断言，以及原归途门障碍测试在中央开盖区放置了障碍块。改为明确强制加载隔离测试区、检查真实实体 tick、保留空引用诊断，并将人工门障碍上移至门体顶部，以继续测试旋转候选且不占用中央箱体空间。b 轮因并行任务的 `CircuitMotorGameTest` 调用了不存在的无参奖励端口构造器而未编译；该文件随后已由并行工作修正，本次未修改它。早期日志不得称为通过。

## 开发客户端视觉检查

```powershell
.\gradlew.bat runClient -x downloadAssets -PrewardChestScenePreview -PrewardChestSceneWorld=reward-chest-entity-3x-current -PrewardChestSceneOutput=build/previews/reward-chest-entity-current --offline --console=plain
```

**成功退出**，日志 `build/reward-entity-client-current.log`。使用本轮已结束的独立 GameTest 存档副本、鎏金王庭、珍藏档和旁观相机；调用生产实体放置，再通过服务端开盖数据同步拍摄。实际打开检查闭合和开盖截图，三倍模型、原比例、朝向、光环和同步后的开盖显示正常。其他两档复用同一实体渲染和比例，本轮未逐档截图；没有把合成经济数据或旁观摄影当作真实奖励领取。

- [中央远景](images/reward-chest-entity/reward-chest-center.png)
- [三倍箱体近景](images/reward-chest-entity/reward-chest-closeup.png)
- [开盖近景](images/reward-chest-entity/reward-chest-open.png)

首次沿用旧预览存档的运行停在注册表迁移阶段，日志 `build/reward-entity-client.log` 保留；已停止该专用预览进程，改用当前测试存档拍摄，不修改生产世界。摄影夹具增加启动诊断与有界退出，避免未来卡在非世界画面时无限等待。

## 最终构建和回归

```powershell
.\gradlew.bat build -x test runGameTestServer -x downloadAssets '-PgameTestNamespaces=saodg_completion_rewards,saodg_exit,saodg_room_rewards' -PgameTestRunDirectory=run/gameTestServer-reward-entity-20261031-final --offline --console=plain
```

**BUILD SUCCESSFUL，6/6 必需运行夹具通过**，日志 `build/reward-entity-final.log`。这会编译并打包 main / GameTest / packTest，显式跳过默认完整 JUnit。没有更改经验公式，因此没有为实体缩放重复计入早前七项单测；本轮以真实 Forge 实体、交互事件、专用服务器与客户端摄影验证为依据。

产物：`build/libs/saodg-0.41.65-dev.jar`，SHA256：`a0455efc4d88f798d884fede162604b5be84e5b8f72d19fa7c147b1aa03db492`。已打开 JAR 确认实体/渲染/光环类存在，闭合/开盖模型与中文资源和源码一致，派生 `en_us` 含实体中文名，摄影和运行夹具未入包。核对明细在 `build/reward-entity-package-verification.json`。

未部署整合包、未修改玩家世界；真人双客户端、延迟/丢包、正式副本完整自然流程和实际经济支付仍待验证。源码修改已停止，仓库提交、分支、标签与推送留给维护聊天统一收尾。
