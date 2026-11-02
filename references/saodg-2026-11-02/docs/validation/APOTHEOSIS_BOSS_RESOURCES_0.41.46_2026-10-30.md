# 客户端冷启动与Apotheosis配置目录冲突：0.41.46

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

## 实际客户端检查发现问题

用户手动从既有PCL启动SAO-0.8，确认进入主菜单；随后进入测试存档，`/saodg` 能打开，中文与标题0.41.45均正常。实际客户端日志载入0.41.45 JAR、新内容目录（28房/1迷宫区），97/97份KubeJS server脚本加载，脚本计数0错误/0警告。证据汇总 `logs/client-cold-start-0.41.45-20261030.json`。

此“脚本零错误”不表示整个整合包没有错误。读取同一客户端日志发现Apotheosis Adventure报 `Failed parsing bosses file saodg:ruin_sentinel`，因为其通用`bosses/`动态注册表跨命名空间读取资源，而SAODG恰在该目录保存自己的不同schema。缺失Apotheosis字段的异常不是SAODG未找到首领，也不是用户KubeJS语法错误。选定错误记录保存在 `logs/apotheosis-boss-directory-conflict-20261030.json`。

Windows Computer Use能列出启动器和Minecraft窗口，但截图连续出现FrameArrived/window capture timeout；按技能恢复要求停止盲点。实际启动和界面由用户确认，不冒充自动截图验证。账号、令牌和认证配置未读取或修改。

## 修复

提交 `0da582003a88`，生产版本0.41.46：随包资源移至 `data/saodg/dungeon_bosses/ruin_sentinel.json`，生成工具、读取器和当前制作文档同步。资源ID仍为 `saodg:ruin_sentinel`，数值和阶段定义字节保持，不改变怪物、评分、网络协议或奖励经济。

读取器优先专用目录；仅当新资源不存在时兼容外部旧数据包的`bosses/`路径并记录迁移提示。这种外部旧包仍可能被Apotheosis读取，作者应一并迁移；兼容读取不等于修改或修复第三方旧包。本工程JAR不再包含该通用目录下的首领资源。

## 实际验证与产物

固定提交导出执行 `jar reobfJar runGameTestServer -PgameTestNamespaces=saodg_boss_resources` 成功，日志 `logs/boss-resource-0da5820-20261030.log` 明确1项测试通过、正常停服。测试实际资源管理器中旧路径不存在，新路径可读，现有Boss ID仍在活动内容快照；既有schema、冲锋配置和非法字段拒绝检查保持。加载内容散列仍为 `20970cac7ced7b30c70fd519158197a1bab3fab105620e3622946c1ac7fca74d`，与0.41.45相同。

JAR核对确认专用首领路径存在、`data/saodg/bosses/`下无任何文件、41个既有NBT结构与中文语言副本保持，未包含用户beta结构或测试夹具。产物 `build/verified/0.41.46-dev-0da582003a88-boss-resource-20261030/saodg-0.41.46-dev.jar`，SHA256 `b846ff35bbee5224700cf2ae8c8be3488eaae821ef444c74d83fd383d77f6673`。这是资源隔离和目录读取证据，仍需实际Apotheosis环境重新加载确认报错消失。

## 用户关闭后同步

修复产物和 `build/integration/0.41.46-ready-20261030/` 先准备完成。用户明确回复“已保存并关闭，可以更新”，再由安装器确认无Java/javaw进程后更新两端；没有在运行游戏时替换文件。脚本与disabled配置内容保持，旧0.41.45 JAR已备份移出，两端均只装一个SAODG 0.41.46。

| 目标 | 回执 |
| --- | --- |
| `D:/Documents/Coding/Game/Minecraft/SAO-server-0.7` | `.saodg-backups/c6c86a1fde994f2b9409b394779456a5/receipt.json` |
| `D:/Minecraft/.minecraft/versions/SAO-0.8` | `.saodg-backups/1ffb3132e3d24863a698a29d4285c599/receipt.json` |

每端19项文件操作，安装后全部前后散列/旧文件缺失状态复核通过，汇总 `logs/runtime-role-install-0.41.46-20261030.json`。安装器不启动游戏，不操作世界、玩家文件、EULA或原核心。独立私有整合包测试服本轮保持0.41.45。

用户重新启动后明确确认“已进入测试存档”。同次新日志确认0.41.46 JAR、97/97脚本0错误/0警告、原内容散列和集成服务器启动；Apotheosis成功Registered 24 bosses，不再出现旧的`saodg:ruin_sentinel`解析错误。证据 `logs/client-apotheosis-reload-0.41.46-20261030.json`，开发包verification.json已追加实际重载结果。

这只证明特定目录冲突消除，并不宣称Apotheosis及整个整合包没有其他警告（已有词缀数量警告未在此处理）。客户端其余窗口尺寸/地图、真人远程网络、所有新角色攻击、服务器本体冷启动与正式奖励经济未由本轮证明；当前目标未标为完成。
