# 建筑库保存位置、描述与世界转换

当前默认作者资产目录为工作区 `nbt_models/<形状>/<中文房间名>/<版本>/`，SAODG中即 `SAODG/nbt_models/...`。形状目录固定为 `single`、`long`、`square`、`l_shape`、`t_shape`、`cross`、`irregular`、`standalone`；以完整主模型的实际有效cells判定，不能只凭文件夹名猜。测试夹具放 `_tests`，控制台缓存/任务放 `_workspaces`，不合规或待补证据资产保留在 `bugged`，迁移清单和原始JSON证据放 `_migration`。build不再是作者资产默认目录。

先运行 `python <skill>/scripts/nbt_library.py new --workspace <工作区> --shape l_shape --name-zh 冷铸阶地工场` 获取独立版本目录，任务生成器全部写到该目录。完成主模型落盘后调用 `nbt_library.register_building(master_path, name_zh, cells)`，或CLI `register --master <完整主模型JSON.GZ> --name-zh <中文名>`。每版必须有 `room_description.json`：name_zh为房间中文名，shape为标准目录键，shape_zh为中文形状，display_name与description_zh统一为“中文房间名-形状”，master为实际完整主模型路径，geometry_sha256/size/cells绑定实际几何。中文名沿用设计材料；从旧slug翻译时记录name_source，不把译名当作设计验收。

网页按 `display_name` 显示“中文名-形状”，完整源路径在提示和高级信息中保留；同名版本通过版本选择区分。metadata中的audit只表示实际执行的文件/静态检查，不能把迁移归档当作新的视觉、49布局或游戏通过。所有新建、精修、网页回导都保留中文描述。不要再往build创建真实建筑或把整份历史副本标为新作品。

## 日期命名与版本

- 新建NBT、图片、可下载文档/压缩包、任务生成脚本采用`YYYY-MM-DD_<房间编号>_<用途>.<扩展名>`，例如`2026-10-31_r001_p00.nbt`、`2026-10-31_r001_p00_body.nbt`、`2026-10-31_r001_p00_walls.nbt`、`2026-10-31_r001_overview.png`。批次汇总使用`YYYY-MM-DD_<批次短名>_gallery.png`等名称。
- `coordinates.json`、`reading_record.json`、`design_review.json`、`delivery.json`和工具固定清单可保持稳定basename，放在上述日期/房间/版本目录内；通过清单记录实际带日期的文件路径，不为同一几何额外复制一套无日期NBT。
- 重生成、精修和回导采用新的`versions/YYYY-MM-DD_HHmmss_<阶段>/`或`exports/YYYY-MM-DD_HHmmss/`目录。需要同目录并存时增加时间或明确迭代号，不能覆盖已审阅初稿、图像、墙mask与哈希。并发agent先由主agent分配唯一房间编号，禁止多个agent写同一路径。
- 跨日的新产物用其实际创建日期；保留`created_at`与`source_version`等对应关系，用户确认仍绑定所看的源模型和图像哈希，不因日期变化自动失效或自动取得批准。
- `nbt_delivery.export_delivery`接受`file_prefix='YYYY-MM-DD_r001_'`；`nbt_whole_cut.slice_master`接受相同参数并同步用于完整分片和两层交付。工具默认空前缀仅为兼容旧调用，新任务需显式传入。工具固定的JSON/GZ主模型清单留在日期目录。
- 已有任务保持原路径和引用，不自动迁移；用户另外指定目的地或名称时沿用其要求。

## 文件分区

- `scripts/`：按日期命名的任务专用生成脚本及参数；通用脚本仍在skill/scripts，SAODG仓库共享工具放`tools/`。
- `master/`：完整未切割主模型、全局墙mask和冻结版本。
- `coordinates.json`：整体尺寸、原点、地板/平台Y、适用的door_y/端口及关键目标。

- `runtime/parts/`：完整含空气的运行模板和原始分片偏移。
- `delivery/`：每有效分片恰好body/walls两份稀疏NBT及交付清单，不混入完整模板。
- `previews/`、`validation/`：图像、审阅依据及分项检查结果。
- `layout.json`：世界放置输入；`world/`：新建超平坦制作存档及`structure_map.json`。
- `exports/YYYY-MM-DD_HHmmss/`：从离线编辑存档回导的全新输出，含runtime/parts、适用的delivery、坐标、布局与验证记录。

任务生成物、世界、任务脚本及Python缓存不提交源码。`build/`含制作资产，执行Gradle clean前先备份需要保留的任务。输出根目录可由用户指定；以上分区不改变整体建模、密闭后开洞、看图授权精修和机械切片的顺序。

## 可继续编辑的坐标上下文

coordinates.json 也是应用继续编辑与 Agent 换人接手的正式上下文，不能只写设计说明而把可执行字段分散到旧验证报告。必须包含真实 `start`（玩家脚位XYZ）、非空 `targets`、非空 `interior_probes`、适用的 `protected_paths/protected_boxes/route_legs`。SAODG 使用 `mode: "saodg"`、`cells/door_y/ports`；独立建筑使用 `mode: "standalone"`、显式 `openings`（无开口填[]），不套用SAODG门洞。墙mask在主模型或显式配置中保存，不按材质补造。相机可放独立 cameras.json。

交付前运行 `nbt.py control inspect --source <主模型>` 核对 `editing_ready` 和 `context_readiness`，再做实际整体验证。editing_ready 只表示上下文字段可用，不证明通路或设计合格；缺少配置时应用允许只读看图/3D和评论，不能宣称已经可修改或导出。

SAODG工作区提供可选的独立工具`tools/structures/structure_world.py`（依赖`tools/requirements.txt`）：`create --layout <布局JSON> --output <新世界目录>`创建Java 1.20.1超平坦存档；`export --world <离线存档> --output <新回导目录>`按映射恢复NBT。详细布局与命令见工作区`docs/NBT_AUTHORING.md`。该仓库工具不是本skill分发依赖；迁移skill到其他工作区后先确认是否有此工具，不能虚报命令存在。

世界映射必须记录每片尺寸、世界原点、作者偏移及原墙坐标；同一整体按48连续偏移放置，不自行改为49运行布局。回导只读声明的范围；新增墙归属需明确维护mask，不能按材质猜墙。缺失区块不能当空气；有方块实体的数据不能静默剥离。单完整模板未声明墙归属时不编造两层交付。

生成存档供用户复制到空白制作环境；工具不自动安装到活动saves、资源目录或房间池，不覆盖既有输出。退出游戏后读取实际编辑的存档；编辑后仍需恢复完整主模型，重新完成受影响的建筑验收。转换回读通过不代表密闭、通路、设计、游戏加载或49运行兼容通过。

转换默认不随机改材质。用户明确需要带权替换或连片噪声时，使用[通用方块模式](patterns.md)在完整主模型上显式处理、另存版本并重验；不在分片转换循环中随机换块。原转换输出、坐标映射和墙归属证据继续保留。
