# SAODG 迷宫区实现参考

记录日期：2026-10-27。目标为 Minecraft 1.20.1 / Forge / Java 17 的独立迷宫区模组，接入现有 SAO 核心与服务器 KubeJS；不依赖已归档的 SAO 重写版。

完整设计已整理到[迷宫区方案](DUNGEON_DESIGN.md)、[集成契约](INTEGRATION_SPEC.md)和[验收计划](ACCEPTANCE_PLAN.md)。下文的实现边界是初始参考记录，具体范围与阶段出口以完整设计为准。

## 上游源码快照

三个仓库均使用 `git clone --branch 1.20 --single-branch` 克隆，保留该分支完整历史，无本地修改。`references/` 已从未来的 SAODG Git 跟踪中排除；上游仓库各自保留 `.git`，并非 Git 子模块。以下提交是本次参考基线，不会随远程更新自动变化。

| 项目 | 本地目录 | 分支 | 克隆时提交 | 构建目标 |
| --- | --- | --- | --- | --- |
| [DungeonZ](https://github.com/Globox1997/DungeonZ/tree/1.20) | `references/DungeonZ` | `1.20` | `501d3d338acbe9b1f9abf7277b3c81d909af3b21` | Fabric / Minecraft 1.20.1 |
| [Dimensional Dungeons](https://github.com/AllenSeitz/DimDungeons/tree/1.20) | `references/DimDungeons` | `1.20` | `bc9545c1cb1cdd9c0e3e6f3be2a53ea60cb7d9b9` | Forge 46.0.14 / Minecraft 1.20；声明游戏版本范围 `[1.20,1.20.2)` |
| [Gateways to Eternity](https://github.com/Shadows-of-Fire/GatewaysToEternity/tree/1.20) | `references/GatewaysToEternity` | `1.20` | `b39c95dfcb0b25f939de6ce594030c79805aa9ec` | Minecraft 1.20.1 / Java 17；`forgeVersion=47.1.28`，使用 NeoForged Gradle 插件 |

本次仅克隆与核对源码、分支、提交、构建元数据和许可标注，没有构建、安装、启动上游模组或修改服务器。

## 源码阅读索引

### DungeonZ：副本内容定义与进入/离开

- `references/DungeonZ/src/main/java/net/dungeonz/data/DungeonLoader.java`：数据包 JSON、人数、难度、结构池、怪物、Boss、出口和行为限制。
- `references/DungeonZ/src/main/java/net/dungeonz/dungeon/Dungeon.java`：副本定义及规则的数据模型。
- `references/DungeonZ/src/main/java/net/dungeonz/dungeon/DungeonPlacementHandler.java`：进入、离开、结构生成、刷新和怪物强化。
- `references/DungeonZ/src/main/java/net/dungeonz/block/entity/DungeonPortalEntity.java`：入口关联的状态。
- `references/DungeonZ/src/main/java/net/dungeonz/block/logic/DungeonSpawnerLogic.java`：刷怪逻辑。

参考其内容配置、生命周期和返回位置处理。Fabric 的事件、注册、网络、Yarn 名称与 Mixin 接线不能直接套入 Forge 1.20.1。

### Dimensional Dungeons：房间布局与结构放置

- `references/DimDungeons/src/main/java/com/catastrophe573/dimdungeons/structure/DungeonDesigner.java`：先规划房间网格，按门口方向、房型和主题选择模板。
- `references/DimDungeons/src/main/java/com/catastrophe573/dimdungeons/structure/DungeonRoom.java`：房间布局数据。
- `references/DimDungeons/src/main/java/com/catastrophe573/dimdungeons/structure/DungeonPlacement.java`：把布局与模板放置到世界。
- `references/DimDungeons/src/main/java/com/catastrophe573/dimdungeons/dimension/DungeonData.java`：维度相关持久状态。
- `references/DimDungeons/src/main/java/com/catastrophe573/dimdungeons/PlayerDungeonEvents.java`：玩家与迷宫区交互规则。

参考“房间图生成”和“世界放置”分离的设计，自行实现 SAODG 的主路、支路、钥匙门、秘密点及可达性验证。此仓库的许可标注有冲突，当前仅作为设计阅读参考。

### Gateways to Eternity：战斗房、波次与事件

- `references/GatewaysToEternity/src/main/java/dev/shadowsoffire/gateways/gate/Wave.java`：怪物列表、修改器、奖励、战斗时限、准备时间及生成失败。
- `references/GatewaysToEternity/src/main/java/dev/shadowsoffire/gateways/gate/WaveEntity.java`、`WaveModifier.java`、`Reward.java`：可组合的战斗定义。
- `references/GatewaysToEternity/src/main/java/dev/shadowsoffire/gateways/entity/GatewayEntity.java`：战斗运行状态。
- `references/GatewaysToEternity/src/main/java/dev/shadowsoffire/gateways/event/GateEvent.java`：供外部扩展订阅的玩法事件。
- `references/GatewaysToEternity/schema/`：配置结构与文档。

参考其数据驱动的战斗定义与事件边界，为 SAODG 的清怪房、守点房和精英房设计自己的机制。无需为此给服务器新增 Gateways、Placebo 或 Apothic Attributes 运行时依赖。

## 许可与来源记录

- DungeonZ：根目录 `LICENSE` 及 `fabric.mod.json` 均标注 MIT。若实际复用代码，应保留版权与许可声明，并记录源仓库、提交、文件和改动。
- Gateways：根目录 `LICENSE` 与模组元数据标注 MIT。实际复用时同样保留声明和来源。
- DimDungeons：该分支的 `LICENSE.txt` 为 GPLv3 文本，而 `gradle.properties` 的 `mod_license` 是 `All Rights Reserved`，分发页也标注后者。本次不据此认定其原创代码获得明确可复用授权；先阅读设计，不复制代码或房间素材。
- 新代码、贴图、结构与音效分别记录来源；不因源码可见而默认素材可以复制。

如未来采纳上游实现，在 SAODG 中新增第三方来源清单，固定实际使用的提交，不把整个参考仓库打包发布。

## SAODG 的实现边界与开发顺序

以下为计划，尚未实现。以 Hypixel SkyBlock 迷宫区的玩法循环为参考，自行制作地图、素材和代码，不把这三个上游模组作为强制运行依赖。

1. 独立 Forge 工程与副本生命周期：准备、生成、探索、Boss、结算、失败、回收。首个版本使用一个固定维度内的多个隔离区域，保存实例 UUID、成员、返回位置及占用状态；区域间的传送、伤害、实体和交互权限由实例规则约束。
2. 固定地图闭环：清怪开门、Boss、个人领奖、离开与重置。先验证两个队伍并发、断线重连、服务器重启恢复与回程。
3. 随机房间图：按种子先生成可达布局，再放置 NBT 模板；检查门口旋转、模板占地、钥匙可取得且不会锁在对应门后。
4. 探索玩法：普通房、精英房、解谜房、秘密点、主路钥匙及 Boss 入口。房间绑定实例、怪物 UUID 和完成目标，实体卸载不算击杀。
5. 评分与个人奖励：探索、目标、耗时和死亡记录进入可配置评分；奖励按稳定领取编号保存与恢复，背包满时待领。具体分值和数值以服务器测试为准。
6. 客户端地图、目标、计时和结算展示，随后扩充职业协作与 Boss 阶段。

现有 SAO 仅通过隔离的兼容层接入队伍、等级、职业和濒死状态；迷宫区核心不散布 SAO 内部类引用。KubeJS 接入入口 NPC、开放条件、珂尔钱包与 FTB 任务。开本时冻结参战 UUID 名单，结算不依赖后来变化的社交队伍。

需要明确调整现有 KubeJS 的 Boss 调血、击杀收入和护甲掉落规则，使其能识别 SAODG 管理实体。第一版优先保留已有 SAO 击杀经验，独立结算攻略经验和通关奖励；原生 Boss 奖励若发生重复，再通过限定范围的兼容入口处理，避免两套系统同时发放同一收益。
