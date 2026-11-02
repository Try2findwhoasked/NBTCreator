# 服务端配置与管理员界面

当前迁移分支 `0.5.2-neoforge-dev`，Minecraft 1.20.1 / NeoForge 47.1.106 / Java17，协议25。沿用 `0.5.1beta` 的36个服务端配置；[迁移验证](validation/NEOFORGE_MIGRATION_2026-10-31.md)。客户端与服务端需要同时更新；历史 Forge 发布标签不变。

## 打开与保存

- OP等级至少2：输入 `/saodg admin config`，或从副本菜单右上角进入「服务器配置」。普通玩家没有管理入口，伪造网络请求仍由服务器拒绝。
- 六类配置支持滚轮浏览。悬停标签或输入框查看含义、范围、默认值和生效时机。编辑暂存，切换分类、滚动和缩放会保留修改。
- 「默认」只重置单项，「本分类默认值」只重置当前分类；仍需点击「保存修改」才提交。无效输入标红并禁用保存。
- 保存整批校验；一项越界、未知或受限就整批拒绝。其他管理员或文件更新导致快照过期时，必须重新加载后核对。关闭或重新加载时有暂存修改，需要再点一次确认放弃。
- 保存位置为当前世界 `<存档>/serverconfig/saodg-server.toml`。不写入客户端本地配置，不自动修改 `defaultconfigs/`。原有键名和默认值保留，缺少的新键由Forge补齐。

控制台省略斜线，使用 `list` / `set`，与GUI共享权限、校验和保存规则：

```text
/saodg admin config list
/saodg admin config set dungeon.blockChangesPerTick 4096
/saodg admin config set rewards.mathBonusXp 45
/saodg admin config set safeReturn.hubDimension minecraft:overworld
```

## 生效规则

- **立即生效**：生成/回收预算、自动同步间隔、部分交互和提示设置。
- **空闲时可保存**：必须没有组队大厅、运行/待回收实例或建筑预览。人数/并发硬上限仍是4人/2局。
- **仅新开局生效**：奖励开关、材料档案和旧击杀任务策略沿用既有开局快照；五项经验参数新增持久化快照，不重算已开的局或已生成奖励。
- **下一次结算场景生效**：已有结算期限不变。
- **新生成实体生效**：星标怪生成时记录发光期限，已有实体不重算。

20游戏刻约1秒。公共回城维度必须已加载且不能为副本维度；返还时仍检查安全地板与空间。不修改既有资产、实例隔离、准入验证或钱包所有权；不自动启用开本/奖励设置。原生SAO经验、物品掉落表、房间池仍由既有适配和数据包管理。

## 配置清单

### 实例运行

| 配置键 | 名称 | 默认值 | 范围 | 生效时机 |
| --- | --- | --- | --- | --- |
| `dungeon.unrestrictedDevelopmentEntry` | 放宽开发准入 | `true` | 开 / 关 | 服务器空闲时可保存 |
| `dungeon.enableDevelopmentRuns` | 独立开发入口 | `false` | 开 / 关 | 服务器空闲时可保存 |
| `dungeon.maxPlayers` | 每局人数上限 | `4` | 1 ～ 4 | 服务器空闲时可保存 |
| `dungeon.maxConcurrentRuns` | 并发实例上限 | `2` | 1 ～ 2 | 服务器空闲时可保存 |
| `dungeon.lobbyTimeoutTicks` | 组队大厅有效期（刻） | `2400` | 20 ～ 72000 | 服务器空闲时可保存 |
| `dungeon.reconnectWindowTicks` | 断线重连窗口（刻） | `2400` | 20 ～ 72000 | 服务器空闲时可保存 |
| `dungeon.settlementStayTicks` | 通关结算停留（刻） | `2400` | 20 ～ 72000 | 下一次结算场景生效 |
| `dungeon.developmentVanillaEnemies` | 开发原版怪物池 | `true` | 开 / 关 | 服务器空闲时可保存 |
| `dungeon.customEncounterSkills` | 自制敌人技能 | `false` | 开 / 关 | 服务器空闲时可保存 |
| `dungeon.nativeEncounterMobs` | SAO / 灾变原生阵容 | `true` | 开 / 关 | 服务器空闲时可保存 |

### 生成性能

| 配置键 | 名称 | 默认值 | 范围 | 生效时机 |
| --- | --- | --- | --- | --- |
| `dungeon.generationTimeoutTicks` | 生成超时基线（刻） | `600` | 20 ～ 72000 | 服务器空闲时可保存 |
| `dungeon.blockChangesPerTick` | 生成方块预算 / 刻 | `2048` | 128 ～ 8192 | 立即生效 |
| `dungeon.cleanupBlockChangesPerTick` | 回收方块预算 / 刻 | `0` | 0 ～ 8192 | 立即生效 |
| `presentation.uiSyncIntervalTicks` | 界面同步间隔（刻） | `10` | 2 ～ 100 | 立即生效 |

### 交互提示

| 配置键 | 名称 | 默认值 | 范围 | 生效时机 |
| --- | --- | --- | --- | --- |
| `presentation.roomDiscoveryMessages` | 发现房间聊天提示 | `true` | 开 / 关 | 立即生效 |
| `presentation.enemyGlowDelayTicks` | 星标怪发光延迟（刻） | `200` | 0 ～ 2400 | 新生成实体生效 |
| `interaction.keyAutoPickupTicks` | 钥匙自动收取延迟（刻） | `100` | 0 ～ 1200 | 立即生效 |
| `interaction.keyPickupRadius` | 钥匙靠近收取距离（格） | `2.0` | .5 ～ 6 | 立即生效 |
| `interaction.mathTalkCooldownTicks` | 答题对话间隔（刻） | `5` | 1 ～ 100 | 立即生效 |
| `interaction.mathInteractionDistance` | 答题交互距离（格） | `6.0` | 2 ～ 8 | 立即生效 |
| `presentation.waypointDurationTicks` | 寻路提示持续时间（刻） | `100` | 20 ～ 1200 | 立即生效 |

### 奖励经验

| 配置键 | 名称 | 默认值 | 范围 | 生效时机 |
| --- | --- | --- | --- | --- |
| `dungeon.enableDevelopmentRewards` | 开发通关奖励 | `false` | 开 / 关 | 仅新开局生效 |
| `dungeon.developmentMaterialRewards` | 开发材料奖励档案 | `false` | 开 / 关 | 仅新开局生效 |
| `rewards.trialMaximumXp` | 试炼基础经验上限 | `120` | 0 ～ 100000 | 仅新开局生效 |
| `rewards.standardMaximumXp` | 标准基础经验上限 | `240` | 0 ～ 100000 | 仅新开局生效 |
| `rewards.eliteMaximumXp` | 精英基础经验上限 | `420` | 0 ～ 100000 | 仅新开局生效 |
| `rewards.circuitBonusXp` | 继电机追加通关经验 | `60` | 0 ～ 100000 | 仅新开局生效 |
| `rewards.mathBonusXp` | 数学额外题经验 / 题 | `30` | 0 ～ 100000 | 仅新开局生效 |

### 安全回城

| 配置键 | 名称 | 默认值 | 范围 | 生效时机 |
| --- | --- | --- | --- | --- |
| `safeReturn.hubEnabled` | 公共回城点后备 | `false` | 开 / 关 | 服务器空闲时可保存 |
| `safeReturn.hubDimension` | 公共回城维度 | `minecraft:overworld` | 已加载的非副本维度 ID | 服务器空闲时可保存 |
| `safeReturn.hubX` | 公共回城 X | `0.5` | -29999900 ～ 29999900 | 服务器空闲时可保存 |
| `safeReturn.hubY` | 公共回城 Y | `64.0` | -2048 ～ 2048 | 服务器空闲时可保存 |
| `safeReturn.hubZ` | 公共回城 Z | `0.5` | -29999900 ～ 29999900 | 服务器空闲时可保存 |

### 兼容接入

| 配置键 | 名称 | 默认值 | 范围 | 生效时机 |
| --- | --- | --- | --- | --- |
| `dungeon.preset` | 运行预设 | `STANDALONE` | 独立运行 / SAO 整合服 | 服务器空闲时可保存 |
| `dungeon.allowLegacyKillObjectives` | 旧版击杀任务计数 | `false` | 开 / 关 | 仅新开局生效 |
| `integration.requireExternalAssetFenceWithKubeJs` | 外部资产归属检查 | `true` | 开 / 关 | 服务器空闲时可保存 |

## 存档与验证

新增可选运行记录 `reward_tuning`，格式版本1，保存三档基础副本经验上限和两种追加经验。旧记录缺省时使用历史120/240/420与60/30。默认奖励指纹保持兼容，自定义参数进入结算指纹，改变参数重放会被拒绝。进程重启继续中止未完成副本，不新增战斗恢复，不保证降级读写。

实际验证和界面截图入口见[本轮记录](validation/ADMIN_CONFIGURATION_2026-10-31.md)。独立运行测试和预览不代表真人联机、完整整合包或生产经济验收。
