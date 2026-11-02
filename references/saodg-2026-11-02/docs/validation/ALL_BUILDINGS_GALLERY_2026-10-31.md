# 全建筑超平坦展览验证（2026-10-31）

输出目录：`build/nbt_models/all_buildings_gallery_20261031/`。存档包：`SAODG_All_Buildings_20261031.zip`（11,036,717 字节）；`world/` 是可直接复制的同内容存档。

## 收录与布局

- 199 个去重后的建筑/版本，368 个原始分片，7,311 个区块、33 个 Anvil 区域文件。保留现存初稿和状态不同的精修版本；相同整体几何的副本合并为一处展品，其来源、偏移和文件哈希保留在 `building_index.json`。
- 扫描 `build/nbt_models/`、`build/room_models/` 并补充仅存在于当前房间资源定义中的 5 个建筑。工具夹具、开洞前封闭快照及运行接缝诊断碎片单列排除。全部作者 NBT 均有归属或排除原因，没有未处理文件。
- `build/选择` 和旧审阅目录中的 547 份归档 NBT 均为原作者目录的字节相同副本，已核对。
- 12 列展位，展位原点间距192格，模型基底Y64；最大144格整体之间保留至少48格空间。每座内部保持原始作者偏移48连续拼接，不拆散展示，不增加49格运行接缝，不挖门、拆顶或改变原建筑几何。稀疏形状的缺角不生成占位分片。
- 配套 `建筑目录.html`、`建筑坐标.csv`、`展区地图.png`、`使用说明.txt`。存档内包含相同文件、完整 `structure_map.json` 和 `building_index.json`。
- Java 1.20.1 数据包提供199个传送目标、17页可点击目录，以及首次进入的提示。目录命令为 `/function saodg_gallery:menu`；旁观查看和创造编辑入口包含在提示中。数据包静态引用均已检查，未在真实游戏中执行。

## 实际验证

创建命令：

```powershell
python tool/structure_world.py create --layout build/nbt_models/all_buildings_gallery_20261031/layout.json --output build/nbt_models/all_buildings_gallery_20261031/world --max-chunks 32768
```

全部368个分片落盘后回读，共比较30,083,369个方块位置，包含空气和方块状态，与来源相等。源文件哈希检查覆盖1,168份NBT，未发现变化。`scripts/verify_gallery.py` 检查分片原点、尺寸、偏移、整体分组、导航引用、区块数量、来源覆盖和ZIP CRC，均通过。压缩包内映射与未压缩存档的映射哈希一致。

实际单座回导：

```powershell
python tool/structure_world.py export --world build/nbt_models/all_buildings_gallery_20261031/world --structure b044 --output build/nbt_models/all_buildings_gallery_20261031/exports/verify_b044_r01
```

`b044` 为三分片L形建筑“折街商旅站”。成功输出3份完整运行模板与6份主体/墙层NBT；落盘回读和非空气分层重建相等。地图、目录和未压缩存档中的映射全部保留。

工具新增按区域加载来源、显式区块预算和按建筑ID筛选回导。大批量输入的结构读取改为有长度、深度及重复字段检查的标准库解析器，保留 `nbtlib` 的区块/存档写入。`python -m unittest discover -s tool -p 'test_*.py' -q` 实际12项通过，包含原有往返、缺区块/方块实体拒绝、L形、外置区块、选定建筑回导和新解析器的截断/重复位置拒绝。

实际证据在任务目录的 `inventory.json`、`gallery_validation.json`、`world/validation.json` 和回导 `validation.json` 中。

## 使用与边界

解压ZIP顶层文件夹到 Minecraft Java 1.20.1 的 `saves/`，或复制整个 `world/`。编辑后退出世界，对实际编辑过的那份存档回导；保留 `structure_map.json`。`--structure b044` 可替换为目录中的其他ID，省略则回导全部建筑。新增占据坐标默认归主体，新增墙归属须明确维护mask。

本轮未启动Minecraft客户端/服务端，未验证实际光照、碰撞、通路、数据包游戏内执行或多人行为。该世界用于48连续作者空间查看和编辑，不代表49格SAODG运行布局验收。未安装到活动存档或修改生产模板，未运行Gradle构建、全套JUnit或GameTest。

ZIP SHA256：`a3d378ea1dd08163f03799686beaa3a77030be8413c48f4b88fdf8fce20ee2c2`。
