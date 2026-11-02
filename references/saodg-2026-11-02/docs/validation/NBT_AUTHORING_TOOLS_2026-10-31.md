# NBT 制作世界工具验证（2026-10-31）

范围：`tool/structure_world.py`、`tool/nbt_world.py`、存放规范及本地 `minecraft-nbt-modeler` 的相关说明。未修改生产房间模板或安装到活动存档。

## 实际执行

- `python -m unittest discover -s tool -p 'test_*.py' -v`：10 项通过。覆盖五位 padded long 编码、负坐标/跨区域、方块 Properties、完整含空气模板与两层互斥重建、模拟编辑后的墙归属、新增主体块、缺失区块拒绝、映射范围内方块实体拒绝、覆盖/路径/重叠拒绝、输入实体拒绝、L 形三片六份交付、48 格偏移和外置 `.mcc`。
- `python tool/structure_world.py create --layout tool/examples/structure_layout.json --output build/nbt_models/flat_world_validation_20261031/world`：成功，1 片、25 个区块；落盘 MCA 全映射体积回读相等。
- `python tool/structure_world.py export --world build/nbt_models/flat_world_validation_20261031/world --output build/nbt_models/flat_world_validation_20261031/exports/r01`：成功，输出完整运行模板和两份制作层。
- 使用已有 `tools/nbt_read.py` 的另一套解析器读 gzip NBT，对比原始 `latest/01_oath_hall/p00_body.nbt`、`p00_walls.nbt` 与回导文件：尺寸均为 `48×32×48`；主体 29,129 块、墙 10,810 块，合计 39,939 个非空气块。原始两层及完整重建逐坐标/状态相等。
- `skill-creator/scripts/quick_validate.py .agents/skills/minecraft-nbt-modeler`：通过。
- CLI 总帮助及 create/export 子命令帮助正常；新增文本文件检查无尾随空白。

生成物保留于被忽略的 `build/nbt_models/flat_world_validation_20261031/`；`world/structure_map.json` 与各输出 `validation.json` 为实际文件证据。输出目录已经存在，复跑命令时应使用新的任务/版本路径。

## 验证边界

这是文件级格式、坐标、状态与分层转换验证，未运行 Minecraft 客户端/服务端加载、光照、密闭/端口/玩家碰撞、49 格运行接缝或多人验收。模拟游戏编辑测试通过写入已修改的区块文件进行，不代表真实游戏编辑。未构建模组或运行全套 JUnit/GameTest，不改变既有版本的验证结论。
