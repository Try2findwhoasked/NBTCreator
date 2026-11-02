# 已注册建筑云端新维度增量包（2026-10-31）

用途：将此前已制作的79个注册房间展示世界并入云端服务器的新维度。用户自行增量更新存档；本轮没有连接或修改云端服务器。

最终输出：`build/nbt_models/registered_gallery_dimension_20261031_v2/SAODG_Registered_Gallery_Dimension.zip`，5,326,648字节。维度ID：`saodg_gallery:registered_buildings`。

ZIP根目录只有：

```text
datapacks/saodg_gallery_dimension/
dimensions/saodg_gallery/registered_buildings/
```

包中包含数据包、12份区域文件、更新维度ID的NBT映射和建筑索引/目录/坐标表/展区图。没有 `level.dat`、主世界 `region/`、玩家数据或服务器配置；没有全局gamerule或自动模式切换命令。新维度类型保持 -64～319 的高度范围、固定白天，区块生物群系转换为原版刷怪表为空的 `minecraft:the_void`，目录提示仅筛选展示维度内的玩家。创造/旁观模式使用空中观察点，其他模式使用建筑外侧地面传送点。

来源：此前 `registered_buildings_gallery_20261031/world` 的79个房间、169个分片、3,265个区块。以该已交付展示世界的快照为准，本轮没有重新扩展房间注册池。类型字段和垂直范围已核对本机Mojang 1.20.1 `client.jar` 的 `data/minecraft/dimension_type/overworld.json`，虚空群系核对其 `worldgen/biome/the_void.json`；没有套用26.x或1.21.x数据格式。

## 实际执行及结果

```powershell
python -m unittest tools.structures.test_structure_world tools.structures.test_dimension_bundle -q
python tools/structures/dimension_bundle.py --world build/nbt_models/registered_buildings_gallery_20261031/world --output build/nbt_models/registered_gallery_dimension_20261031_v2
```

- 14项专项测试通过，覆盖旧主世界回导、自定义维度读取、主世界同坐标内容不同的防误读、分层恢复、路径跳转拒绝、维度不匹配拒绝和增量包范围。
- 全部3,265个区块在修改生物群系后重新落盘，逐一比较各section的完整方块状态容器（含palette与packed data），与来源完全一致；区块坐标和原始来源未改变。
- ZIP CRC通过；包内所有文件均属于上述两个目录，导航函数引用有效，映射含79项注册资源ID。
- 在隔离的临时完整存档布局中装入该维度，实际使用 `export --dimension saodg_gallery:registered_buildings --structure r011` 回导；3份完整模板和6份主体/墙层NBT逐块/状态等于原主世界回导基线。结果位于最终输出目录的 `exports/verify_r011_r01/`。
- `git diff --check` 通过（仅有工作区既存CRLF规范化提示）。

包SHA256：`86c60d8ab45d72597d388125a370ce2cd010fbee561999ec513c83a4cdb1ce5b`。文件级报告为输出目录 `validation.json`。

## 安装与回导

停服、备份，将ZIP的两个目录合并到服务器实际存档根目录（`server.properties` 的 `level-name` 指向的目录），完整重启。仅 `/reload` 不足以加载新维度；如数据包被禁用，启用 `file/saodg_gallery_dimension` 后再重启。OP玩家用 `/function saodg_gallery:enter` 进入，`/function saodg_gallery:menu` 打开目录。

同名维度若已有编辑成果，应先回导或备份后再覆盖相应区域文件。编辑后停服并下载完整实际存档，使用：

```powershell
python tools/structures/structure_world.py export --world <完整存档根目录> --dimension saodg_gallery:registered_buildings --structure r011 --output <新的回导目录>
```

未启动Minecraft或云端服务器，未验证实际维度加载、传送、光照、碰撞或多人行为；本轮也没有构建模组或执行全套JUnit/GameTest。
