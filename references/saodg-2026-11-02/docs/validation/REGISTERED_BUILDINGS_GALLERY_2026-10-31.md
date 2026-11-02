# 已注册建筑超平坦展览（2026-10-31）

范围：只展示当前源码中被副本 `layout.room_pool` 引用的房间，遵照 `ContentCatalog.prepare` 的加载范围，而非扫描所有 `rooms/*.json`。当前 `saodg:ruins_01` 引用79个唯一房间；未启动游戏核对活动服务器的数据包覆盖。

输出位于 `build/nbt_models/registered_buildings_gallery_20261031/`，存档包为 `SAODG_Registered_Buildings_20261031.zip`（5,360,875字节）。原199展品存档保留，新版独立存放。

- 79个注册项、169个分片、3,265个区块。按当前房间JSON解析实际模板路径和偏移，每个注册ID一处展位，保留48格连续拼接及各自高度。展位间距192，基底Y64。
- 注册类型：入口1、精英4、谜题6、普通战斗63、安全房1、Boss3、封印大厅1。
- 5份未被房间池引用的历史定义不展示：`ruins/boss_01`、`ruins/outpost_01`、`ruins/safe_01`、`ruins/safe_02`、`ruins/safe_gallery`。其他未注册初稿、精修版本和独立道具也未纳入。
- 映射增加注册资源ID与展品ID对应关系；`building_index.json` 保存注册来源、房间定义哈希和模板引用。CSV、HTML、平面图及7页游戏内可点击目录包含在存档中。

实际执行：

```powershell
python build/nbt_models/registered_buildings_gallery_20261031/scripts/prepare_registered.py
python tool/structure_world.py create --layout build/nbt_models/registered_buildings_gallery_20261031/layout.json --output build/nbt_models/registered_buildings_gallery_20261031/world --max-chunks 16384
python build/nbt_models/registered_buildings_gallery_20261031/scripts/finish_registered.py
python build/nbt_models/registered_buildings_gallery_20261031/scripts/verify_registered.py
python tool/structure_world.py export --world build/nbt_models/registered_buildings_gallery_20261031/world --structure r011 --output build/nbt_models/registered_buildings_gallery_20261031/exports/verify_r011_r01
```

验证通过：映射房间集合与当前注册池严格相等，逐项核对当前房间JSON、模板引用和作者偏移，331份输入NBT哈希相符；169片共14,148,864个方块位置（含空气和状态）落盘回读相等。ZIP CRC及压缩包内映射一致性检查通过。注册项 `r011`（`saodg:refined/folded_sword_viaduct`）单独回导成功，输出3份完整模板与6份主体/墙层NBT。

存档包SHA256：`f43f47e20996775628ee47000ebb829b23fb23ee264bb29e855527529fb95639`。

未修改生产模板、安装活动存档、运行Gradle或启动Minecraft。本轮未实测游戏加载、光照、碰撞、49格运行接缝、数据包游戏内执行或多人；文件验证不代替上述项目。
