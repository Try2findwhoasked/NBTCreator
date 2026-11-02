# NBT 生成文件存放与超平坦世界转换

适用于 Minecraft Java 1.20.1（DataVersion 3465）。格式转换不代替建筑设计、密闭/端口/路线检查，也不代表通过 SAODG 方块导入策略或运行接缝验收。

## 文件存放

新任务使用工作区根目录下的 `build/nbt_models/<任务名>/`。任务名建议采用主题及日期；重新生成和回导使用新版本子目录，保留初稿、审阅图及校验依据。已有资产不自动搬迁。

```text
build/nbt_models/<任务名>/
  scripts/                 本次任务的生成脚本、参数；共享工具放 tools/structures/ 或 skill/scripts/
  master/                  完整未切割主模型、全局墙 mask、冻结快照
  coordinates.json         总尺寸、局部原点、关键地板/平台 Y、door_y 与端口（适用时）
  runtime/parts/            完整含空气的运行模板及分片偏移清单
  delivery/                每有效分片 pXX_body.nbt、pXX_walls.nbt，及分层清单
  previews/                整体、入口、顶部与代表节点的预览和审阅证据
  validation/              技术与设计检查记录；未执行项目明确列出
  layout.json              超平坦世界放置输入（路径相对此文件）
  world/                   新建制作存档；包含 structure_map.json 和 validation.json
  exports/r01/             从编辑存档回导的新版本
    runtime/parts/<结构ID>/ 完整含空气 NBT
    delivery/<结构ID>/      仅原先有分层的分片输出主体/墙层两份 NBT
    layout.json            可直接再次创建世界的布局输入
    coordinates.json       本次采用的原始世界映射
    validation.json        文件哈希、回读与未验证项目
```

`delivery/` 的 NBT 数量为有效分片数的两倍，完整合成文件另存 `runtime/parts/`；L 形缺角不生成占位分片。单模板输入未声明墙归属时只回导完整模板，不能按材质猜墙或自动认证为最终分层交付。转换工具输出的分层仍需按建筑流程检查后交付；不能把转换报告当作 `nbt_delivery.verify_delivery` 的验收清单。

源码、通用工具和规范可提交；世界、NBT 生成物、任务专用脚本、渲染和 Python 缓存保留在已忽略的 `build/`，不写进 skill 安装目录或活动资源目录。`build/` 同时存放制作资产，执行 Gradle `clean` 前应将要保留的任务目录另行备份。

## 创建制作世界

可复用工具位于 `tools/structures/`，独立于 `.agents/` 中的 skill；不依赖原机器盘符。先安装依赖：

```powershell
python -m pip install -r tools/requirements.txt
```

单个完整结构直接创建：

```powershell
python tools/structures/structure_world.py create --template build/nbt_models/my_room/runtime/parts/p00.nbt --output build/nbt_models/my_room/world
```

不指定 `--output` 时，默认写 `build/nbt_models/<输入文件名>/world`。单模板默认原点为 `0,64,0`，可用 `--origin=-32,64,-32` 修改。每轴支持 1～48 格，大模型先按原有整体建模流程机械切片。

主体/墙层、多格整体或多个模型使用布局 JSON；[可直接运行的仓库示例](../tools/structures/examples/structure_layout.json) 引用现有房间：

```powershell
python tools/structures/structure_world.py create --layout tools/structures/examples/structure_layout.json --output build/nbt_models/flat_example/world
```

布局格式：

```json
{
  "format_version": 1,
  "name": "制作场",
  "structures": [
    {
      "id": "my_room",
      "origin": [0, 64, 0],
      "parts": [
        {
          "id": "p00",
          "offset": [0, 0, 0],
          "body_template": "delivery/p00_body.nbt",
          "wall_template": "delivery/p00_walls.nbt"
        },
        {
          "id": "p10",
          "offset": [48, 0, 0],
          "template": "runtime/parts/p10.nbt"
        }
      ]
    }
  ]
}
```

`template` 与 `body_template`/`wall_template` 二选一；分层文件同尺寸、同原点、实体坐标互斥。相对路径以布局文件所在目录为基准，支持绝对路径。结构及分片 ID 使用小写字母、数字、下划线或连字符；ID 不可重复。

世界坐标 = `origin + offset + NBT局部坐标`。SAODG 作者布局使用 48 格偏移；这里按输入偏移原样摆放，不生成运行时 49 格接缝。多个独立模型通过不同 `origin` 排列；同一整体的分片保留原始偏移，缺角不填写。所有映射包围盒不得重叠。

世界地表顶层在 Y=63，默认模型原点 Y=64；世界范围 -64～319。制作世界采用创造模式、允许命令、和平难度，关闭生物生成、随机刻和昼夜/天气循环。出生点放在模型左前方地表；每片周围预生成一圈区块，新探索区域继续使用相同超平坦设置。默认预算为 4096 个区块；大型展览可显式指定 `--max-chunks 32768`。生成时按区域加载来源，避免同时保留全部建筑的方块字典。

`structure_map.json` 记录各片世界原点、尺寸、偏移、来源哈希和明确的墙坐标；回导无需原 NBT 仍存在。创建后按全部映射体积逐块回读 MCA，包含空气，结果写入 `world/validation.json`。

## 编辑后回导 NBT

把生成的 `world/` 整目录复制到 Minecraft 1.20.1 的 `saves/`，保留 `structure_map.json`。游戏中编辑后退出世界，再对实际编辑过的存档执行：

```powershell
python tools/structures/structure_world.py export --world 'D:/Minecraft/.minecraft/saves/my_room' --output build/nbt_models/my_room/exports/r01
```

也可对未安装的制作世界直接往返转换：

```powershell
python tools/structures/structure_world.py export --world build/nbt_models/flat_example/world --output build/nbt_models/flat_example/exports/r01
```

未指定输出时，回导到世界同级的 `exports/<时间戳>/`；规范任务中建议显式指定上述 `build/` 路径。映射另存时用 `--map <文件>`。所有创建、回导目录必须尚不存在；不提供覆盖已有存档的参数。回导结果不得写入源世界内部。

大型展示世界可加 `--structure b001` 只回导该建筑 ID，也可重复指定多个 ID；未指定时回导映射中的全部建筑。ID 以实际 `structure_map.json` 和展示目录为准，未知 ID 会报错。该筛选保留所选建筑的全部原始分片，不按单片拆散建筑。

每片从映射尺寸内读取方块，保留方块 Properties 和空气；映射之外的建筑不会被自动纳入。若要改变尺寸/分片边界，应先重新规划完整主模型及布局。分层输入的原墙坐标继续归墙；删掉的墙不复活，原墙位置换材质仍归墙，新增位置默认归主体。要新增墙归属，按全局设计明确更新 `structure_map.json` 的相应局部 `wall_positions`，不能按材质推断。

完整运行模板逐块写满体积；制作层仅写非空气块。`cave_air`/`void_air` 保留在完整运行模板中，分层仅重建非空气几何。每份导出 NBT 均回读验证，两个制作层检查互斥并与世界非空气几何比较；哈希记录在回导 `validation.json`。

脚本拒绝多 palette、实体、方块实体的输入模板，以及缺失映射区块、未完成生成的区块、不同版本存档和映射区域内的方块实体。世界中的普通实体不导出。支持 1.20.1 Anvil 的 gzip/zlib/无压缩区块及外置 `.mcc`；不自动转换版本，也不认证模组方块注册/状态是否合法。编辑带模组方块的世界时需使用相应环境。

## 合并到服务器的新维度

将已生成的超平坦展示世界打成存档增量包：

```powershell
python tools/structures/dimension_bundle.py --world build/nbt_models/registered_buildings_gallery_20261031/world --output build/nbt_models/registered_gallery_dimension_20261031
```

默认维度为 `saodg_gallery:registered_buildings`；可以用 `--dimension namespace:path` 指定另一个新建自定义维度。输出目录必须尚不存在。包内仅包含 `datapacks/saodg_gallery_dimension/` 和 `dimensions/<namespace>/<path>/`，不含 `level.dat`、主世界 `region/` 或玩家数据。它不会自动连接或安装到服务器。

停服、备份后，将ZIP内两个目录合并上传到服务器**存档根目录**（`server.properties` 的 `level-name` 所指目录），然后完整重启。新增维度不能只依靠 `/reload`；如果数据包被禁用，启用后再重启。OP玩家执行 `/function saodg_gallery:enter` 进入，执行 `/function saodg_gallery:menu` 打开建筑目录。

维度保持原作者坐标和 -64～319 的垂直范围，固定白天。区块只将生物群系换为原版 `minecraft:the_void`（原版刷怪表为空），全部方块状态容器落盘回读相等；目录提示只对进入展示维度的玩家显示。包不修改全局 gamerule、默认出生点或自动切换玩家模式。

如果目标同名维度已被编辑，更新前先备份或回导；增量包里的同名区域文件仍会替换旧区域。修改后停服并下载**实际服务器存档**，按维度回导：

```powershell
python tools/structures/structure_world.py export --world <下载的完整存档根目录> --dimension saodg_gallery:registered_buildings --structure r011 --output <新的输出目录>
```

映射默认从 `dimensions/saodg_gallery/registered_buildings/structure_map.json` 读取。也可通过 `--map` 提供映射，工具按映射的 `dimension` 读取区块；同时传 `--dimension` 时两者必须一致。原主世界回导命令继续有效。自定义维度的坐标范围须与映射和实际维度类型一致，路径不能含 `..` 等跳转片段。

文件级验证不代替云端服务器的实际启动、维度加载、传送和多人验证。

回导完成后，仍应按 skill 重新审阅完整主模型，检查密闭、端口、通路、分片连续性和墙层归属；需要精修时继续遵守真实用户看图确认的流程。游戏内加载、光照、实际碰撞、多人与49格运行接缝未由本工具测试。

## 工具检查

```powershell
python tools/structures/structure_world.py --help
python tools/structures/structure_world.py create --help
python tools/structures/structure_world.py export --help
python -m unittest discover -s tools -t . -p 'test_*.py' -v
```

这是独立 Python 文件转换工具；修改它无需构建模组或运行历史建筑生成器。
