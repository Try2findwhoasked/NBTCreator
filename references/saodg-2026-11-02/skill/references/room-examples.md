# 房间模型初稿

执行 `python tools/legacy/generate_room_models.py`，输出到忽略的 `build/room_models/`。需要 Pillow；生成器为原创，不读取参考仓库或 beta 素材。

这批是方块对齐的程序化建模初稿，同一几何数据导出 OBJ 和 NBT，不经过有损网格拟合。OBJ 为 Y 向上、1 单位=1 方块；在 Blender 导入时选择 Y 为上轴并保留单位比例。材质来自同目录 materials.mtl，为纯色预览，没有 Minecraft 纹理。

| 模型 | 建筑意图 | 尺寸 X×Y×Z | 局部 Y 范围 | 顶板 Y |
| --- | --- | --- | --- | --- |
| arcade | 八柱拱廊、分区战斗空间 | 48×24×48 | 0～23 | 21 |
| sanctum | 铜环圣所、八座灯柱 | 48×28×48 | 0～27 | 25 |
| archive | 木质书架造型、侧翼通道 | 48×24×48 | 0～23 | 21 |
| crystal | 紫水晶簇、青苔地面 | 48×32×48 | 0～31 | 29 |

全部模型地板 Y=1，落点和四个刷怪点脚部 Y=2；门洞 Y=2～6，宽度为21～26，分别位于四面外墙。保留六格宽十字通路。顶板以上两层为空气，完整写入 NBT。Y 坐标均相对于模板原点；door_y=2 时引擎基底世界 Y=64，玩家脚部世界 Y=66。

每间包含 OBJ、`data/saodg/structures/models/<name>.nbt` 和 `data/saodg/rooms/models/<name>.json`。房间沿用现有 combat_light 遭遇，未配置秘密、容器或实体。书架用木板与铜条表达造型，避免方块实体。

preview.png 为剖视示意，隐藏顶板、前墙及部分高墙；完整 OBJ/NBT 保留这些部分。validation.json 记录各房间 Y 值、显式体积和地面连通检查结果。

生成时已检查完整体积数量、门洞空气、落点及刷怪点三格净空、四门至落点的地面四邻接连通。尚未在 Forge 中加载、验证四方向旋转或多人运行；这些是设计素材初稿，不是完成运行验收的正式房间。

没有修改活动房间池。接入时按 ROOM_BUILDING_GUIDE.md 将对应 data 文件复制到资源目录，并在当前完整地牢定义的 layout.room_pool 中添加 `saodg:models/<name>`，随后在隔离世界完成目录加载和四方向预览验收。输出不含 pack.mcmeta，不能直接当作可启用的数据包。
