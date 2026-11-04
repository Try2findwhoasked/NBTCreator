# 工作区构件资产

资产管理保存可复用的体素构件，不覆盖源建筑。库位于工作区 `.nbtcreator/components/`，随工作区移动，不进入应用安装包。

## 内外 Agent 共用结构协议

`capabilities` 的 `agent_tools` 是结构工具定义与 JSON 参数 Schema 的共同来源，内部 API、资产管理与外部 Agent 都通过同一个 Python 引擎执行。入口无需 Electron：

```powershell
python .agents/skills/nbtcreator-workspace/nbt.py components agent --tool structure_list --request list.json
python .agents/skills/nbtcreator-workspace/nbt.py components agent --tool structure_preview --request preview.json
```

`list.json` 内容为 `{}`。`preview.json` 是下面的独立结构方案，不是已经编码的构件文件：

```json
{
  "spec": {
    "name": "带基座石柱",
    "size": [7, 8, 7],
    "tags": ["支承"],
    "operations": [
      {"kind": "box", "label": "基座", "classification": "body", "lo": [1, 0, 1], "hi": [5, 0, 5], "state": "stone_bricks"},
      {"kind": "box", "label": "柱身", "classification": "body", "lo": [2, 1, 2], "hi": [4, 6, 4], "state": "stone_bricks"}
    ],
    "camera": {"azimuth": 45, "elevation": 25}
  }
}
```

| 工具 | 参数与行为 |
| --- | --- |
| structure_list | `{}`；列出当前工作区资产 |
| structure_read | `{id}`；读取完整体素、材质、墙层、锚点和内容哈希 |
| structure_view | `{id}`；生成已有资产的独立只读快照、缩略图和一个相机，不打开或修改建筑 |
| structure_preview | `{spec}`；使用共用工具序列或已有资产的放置参数，生成空白空间中的候选及实际预览 |
| structure_write | `{preview_id,preview_sha256}`；核对完整候选绑定后，保存为全新资产ID，不覆盖旧资产 |
| structure_place | `{id,content_sha256,position,size,quarter_turns?,mirror?,overwrite?}`；返回放置操作，不修改模型 |

工具响应为 `{ok,result}`，失败为 `{ok:false,error}`。本地 HTTP 对应 `POST /__detail__/components/agent`，请求是 `{tool,arguments}`，它是应用的同源接口，不是外部网络服务。外部 Agent 使用 CLI，不需要 GUI 自动化或发现临时端口。

结构使用局部整数XYZ、包含两端的lo/hi、合法1.20.1方块状态及明确的body/wall归属。每轴1～64格，展开后最多128步、65536条方块记录；总变化预算可由 `max_changed_blocks` 降低，不能超过65536。空白结构和模型编辑调用相同的编译、候选计算、墙层和预算逻辑。不能提交Python、脚本、任意路径或自行构造write_group。锚点默认底部中心，可显式指定界内整数坐标。

已有资产可用 `spec.placements` 组合，每项包括 `id/content_sha256/position` 及可选 `quarter_turns/mirror/overwrite`；不必重新发送体素。position表示目标空间中的资产锚点，不能猜测ID或哈希。需要复制、阵列或曲面时使用工具目录支持的参数，减少逐块输出。`include_air=true` 明确保留空气，整个体积也必须不超过65536格。

预览返回 `preview_id/preview_sha256`、真实缩略图、主模型草稿、快照、相机文件、几何内容哈希与未完成的设计/通行验证状态。查看真实图像后，按当前用户授权显式调用structure_write；不能把保存资产当作看图批准。生成的诊断草稿位于 `nbt_models/_workspaces/structure_agent/`，正式复用资产仍在 `.nbtcreator/components/`。应用新入口“让Agent生成资产”支持内置API生成、外部参数JSON预览及复制外部Agent任务；它不要求先打开建筑。创作偏好使用 `component` 区域，旧五区域配置会保留并补齐新区域。

保存资产后按structure_place返回的operations走现有模型preview/validate/新版本手动导出流程；落地位置仍需真实源哈希、保护、占用和预算检查。观察机位由脚本补齐，不声明玩家站立或无遮挡。独立资产预览与保存不自动写出NBT，也不授予精修批准。

## 检索相关资产与适配

用 [本地参考检索](reference-retrieval.md) 按任务与尺寸推荐资产、挑选工作流已启用的资料片段，并生成带哈希的引用集合。placements 可用 material_map 在旋转前映射至多32个原始状态，保留原资产不变；structure_preview 的可选 reference_bundle 绑定资料与资产出处，显式保存后记录在新资产配方中。

## 保存与读取

```powershell
python .agents/skills/nbtcreator-workspace/nbt.py components list
python .agents/skills/nbtcreator-workspace/nbt.py components save --source nbt_models/形状/建筑/版本/master/master_geometry.json.gz --name 石柱 --lo 8,4,8 --hi 10,10,10 --tags 支承,石构
python .agents/skills/nbtcreator-workspace/nbt.py components get --id <构件编号>
python .agents/skills/nbtcreator-workspace/nbt.py components place --id <构件编号> --position 20,4,20 --size 48,24,48 --quarter-turns 1
```

`--workspace <目录>` 放在 components 后、子命令前；默认当前 Agent 工作目录。`place` 只返回 operations/lo/hi，不执行写入。将返回的操作合入 control 请求，按原 preview/validate/新版本导出流程使用。

构件的 position 是锚点在目标模型内的坐标，默认锚点为底部中心。不静默裁切或收拢越界构件。原主体与墙 mask 拆为不同操作以保留归属。默认不包含空气；显式保存空气时，空气也是实际写入。默认拒绝目标实体冲突，需要用户明确选用 overwrite 才允许覆盖，仍不能修改保护区。

需要一次放置多份或复用材质映射时，使用 `components batch`，详见 [参数化配方、主题与XYZ阵列](reusable-recipes.md)。构件详情可设置数量和锚点间距；配方与主题入口在资产管理左侧，不占用顶部浏览空间。

每轴最多64格，总计最多65536个记录。旋转为绕Y轴90°的整数倍，可选 X/Z 镜像；采用保守状态转换，暂不支持的楼梯、门、轨道等状态明确拒绝，不猜朝向。

## 数据与管理

JSON schema_version=1，包含 name、tags、size、anchor、palette、blocks 和 content_sha256。blocks 是 `[x,y,z,材质编号,是否墙层]`。导入会验证哈希、坐标、状态和尺寸；不接收代码或脚本。缩略图是本地简化材质示意，不代替正式纹理审阅图。

```powershell
python .agents/skills/nbtcreator-workspace/nbt.py components import --file 柱子.component.json
python .agents/skills/nbtcreator-workspace/nbt.py components update --id <编号> --name 新名称 --tags 石构,支承
python .agents/skills/nbtcreator-workspace/nbt.py components update --id <编号> --archived true
python .agents/skills/nbtcreator-workspace/nbt.py components update --id <编号> --archived false
```

回收操作保留几何和缩略图，可以恢复。UI 与 CLI 读取同一库和索引；已缓存列表不重复解析体素。导入/放置后的作品仍需真实预览、相应检查及用户导出，保存资产不代表批准精修。

## 3D 手柄与选区移动

模型编辑的“构件”菜单提供复制选区、移动选区；资产管理也可选择“3D 手柄调整后放置”。拖动箭头移动，绿色圆环按90°旋转，支持X/Z镜像、整数网格及表面贴放。示意仅在视口显示；取消不添加步骤。应用后由同一引擎生成真实候选，满意后手动导出下一版。“应用后继续复制”保留已应用的副本，取消只关闭下一份示意。

无界面接口增加 `components extract` 和 `components transform`，具体参数用 `--help` 查询。extract仅返回构件而不保存库；transform返回移动/复制所需的操作，不直接修改文件。网页接口绑定当前显示模型的源哈希与快照；移动只清除提取的实体格，再放置到目标，保留选框内空气和无关结构。旋转/镜像同步转换方块朝向和墙层归属。

## AI 构件写入与整体移动

AI返回选区内相对坐标的box/beam/frame或少量离散方块，本地引擎负责合法状态、坐标平移、保护、预算与NBT导出。应用保存最近构件的原始坐标基础，整体移动使用相对于该基础的偏移；归零恢复原位，不重复堆叠步骤。草稿恢复后仍可移动。

“允许AI构件覆盖现有方块”仅允许替换实际写到的格子，不清空整个选区，也不放宽保护和改动预算。API不能自行授予覆盖权限。write_group由应用生成，使一份构件的柱帽等步骤可以覆盖本组刚添加的柱身，而不能占用旧建筑的方块。

小型结构建议压缩为不超过48步，同材质连续体积优先使用box。如果API明确因长度上限截断，应用最多额外请求一次24步以内的精简完整方案；不续写或应用半截JSON。任务详情记录API阶段、本地预览阶段、重试次数和接口提供的令牌统计；其中任何一次预览失败都不等于正式建筑被修改。

## 混合资产批次与 JSON 清单

资产管理的“批量资产 / JSON 清单”支持多选构件JSON、Java1.20.1结构NBT及完整主模型JSON.GZ。每批最多100项、原始文件合计32MiB；失败条目保留错误，其他条目继续。原文件保留，工作区专用目录为 `nbt_models/asset_batches/<批次ID>/`，`items/`保存经校验的规范副本，`assets.json`保存路径、类型、名称、SHA256和构件ID，`import-report.json`记录导入结果。构件另登记到共用构件库；建筑副本保存主模型与明确的独立结构分类，在项目库可见，不自动导出NBT或生成批准。

```powershell
node scripts/cli.mjs --workspace D:/MyProject asset-batches import --request import.json
node scripts/cli.mjs --workspace D:/MyProject asset-batches generate --request scope.json
node scripts/cli.mjs --workspace D:/MyProject asset-batches list
node scripts/cli.mjs --workspace D:/MyProject asset-batches read --file nbt_models/asset_batches/批次ID/assets.json --include-data
```

`import.json`示例：`{"name":"本次批量构件","paths":["D:/Generated/pillar.component.json","D:/Generated/room.master.json.gz"]}`。paths只对显式CLI调用开放；应用通过文件选择上传数据。`scope.json`示例：`{"name":"工作区资产列表","scope":"all"}`，scope可为components、models或all。无界面Agent可通过工作区nbt.py的同名asset-batches命令调用。资产库过大时分批导入并使用各自清单；生成整库清单同样限制100项。

清单schema为 `schema_version=1,kind="nbtcreator.asset-list",path_base="workspace",entries=[{type,path,sha256,name}]`，path是工作区相对路径。read验证所有文件真实存在、路径在工作区内及内容哈希一致，再读取类型与几何；默认返回摘要，--include-data返回完整体素、墙层和材质，总输出限制32MiB。界面可选择JSON清单或已保存批次读取。仅迁移清单而未迁移资产无法读取，不根据清单猜测或重建缺失内容；请迁移完整工作区。读取不产生新构件或模型修改。

## 模型生成后直接脚本保存

对外Skill和内置AI共用 `structure_save`。这条入口在用户授权生成并归档资产时，自动执行本地结构/材质/预算校验，生成真实预览与缩略图，保存为 `review_status=pending_visual_review` 的新资产，并在 `nbt_models/asset_batches/<id>/` 保存构件副本、缩略图、来源配方和 `assets.json`。不需要先手工导出JSON再导入；保存不声明已经实际看图或获得设计批准。正式建筑仍需真实看图和显式NBT导出。

```powershell
python .agents/skills/nbtcreator-workspace/nbt.py components agent --tool structure_save --request generated.json
python .agents/skills/nbtcreator-workspace/nbt.py asset-batches save --request generated-batch.json
python .agents/skills/nbtcreator-workspace/nbt.py asset-batches organize
```

`generated.json`用 `{ "spec": {"name":"石柱","size":[4,6,4],"operations":[{"kind":"box","label":"柱身","classification":"body","lo":[1,0,1],"hi":[1,4,1],"state":"stone_bricks"}]} }`。也可提交 `{component:完整构件数据}`，或 `{preview_id,preview_sha256}` 复用已生成的绑定预览；三种方式只能选一种。绑定预览重复保存返回同一资产，不重复入库。返回id、content_sha256、preview_id、preview_sha256、batch_manifest和待审阅状态。可用batch_name指定批次名称。原有structure_preview/write和手动导入继续可用。生成结果若已经是建筑主模型或NBT文件，使用 asset-batches import 的 paths 请求即可通过脚本直接归档，无需在界面手动导入。

`generated-batch.json`为 `{ "name":"批量生成","assets":[{"spec":结构方案},{"component":构件数据}] }`，最多100项，各项复用同一structure_save实现，失败条目记录errors，成功项生成合并清单。

内置独立结构新增“生成并入库”，复用实际显示的预览后直接入库；“AI生成并预览”和手动保存仍保留。资产卡片标记“待审阅”，返回资产工作区会重新读取库，外部脚本保存结果无需手动导入。

“批量资产 / JSON 清单”也可粘贴上述生成参数直接保存，并提供“整理现有资产到规范目录”。organize为已入库资产生成可读取的规范副本和清单，保留原ID、回收状态、缩略图及来源配方；同内容重复整理复用上次结果。它不把预览草稿自动提升为正式资产，不删除原文件。整理索引为 `nbt_models/asset_batches/organization.json`。

## 原生工具效果配置资产

除构件、可调配方和材质主题外，资产管理提供“工具效果”。保存当前面板配置时捕获整体参数、混材、风化、自动地面、精确换块、结构编辑及建模operations；自动道路面板尚未执行的输入也可直接捕获。源文件、全局选区、保护资料、预算、write_group/write_bounds和覆盖权限不进入效果资产。载入效果时保留当前目标的源、选区、预算及已有工具步骤，合并新增步骤，真实预览失败回退原候选。结构填充仍须先指定目标局部选区。

```powershell
python .agents/skills/nbtcreator-workspace/nbt.py effect-assets save --request effect.json
python .agents/skills/nbtcreator-workspace/nbt.py effect-assets list
python .agents/skills/nbtcreator-workspace/nbt.py effect-assets get --request id.json
python .agents/skills/nbtcreator-workspace/nbt.py effect-assets preview --request id.json
python .agents/skills/nbtcreator-workspace/nbt.py effect-assets compile --request id.json
python .agents/skills/nbtcreator-workspace/nbt.py effect-assets organize
```

`effect.json`使用 `{asset:{name:"石砖步道",settings:{operations:[{kind:"auto_road",label:"步道",classification:"body",lo:[0,0,0],hi:[47,15,47],start:[6,3,6],end:[20,3,20],width:3,depth:1,route:"straight",state:"stone_bricks"}]},tags:[]}}`（文件须为合法JSON）。`id.json`为 `{id:资产ID,content_sha256:可选内容哈希}`。调用不需要Electron，应用HTTP对应 `/__detail__/effect-assets/<action>`，能力目录的effect_asset_contract记录开放动作。save总是写新ID，archive可移入回收站或恢复。

面板配置可只提供部分字段，例如 `settings:{pattern:{enabled:true,fraction:0.12}}`；样例预览使用默认值补齐，compile仍返回原始部分配置，应用时保留目标面板未提供的字段。材质名称的命名空间由界面规范化，不应据此判定参数被用户修改。面板配置先于工具序列运行；需要对刚放入的构件继续换材或风化时，使用具名 `operations`，追加在现有步骤之后。候选应用失败时恢复原参数与原画面，不产生正式NBT。

原生效果文件为 `nbt_models/asset_library/tool_effects/<id>/effect.json`，同步生成assets.json批次清单。独立预览在封闭样例中运行真实引擎，生成前/后主模型、快照、缩略图和变化数量；样例包含不同地板材质和墙柱，默认剖切屋顶查看内部。返回sample_only，不声明适用于用户建筑。没有变化时明确显示0，配置不适用样例时保留错误，不伪造图像。预览过程存放在 `nbt_models/_workspaces/effect_previews/`，不会被当成正式建筑。compile只返回settings候选，不直接写建筑或导出NBT。

organize保留构件ID和内容哈希，备份改动前的标签资料到asset_library/_migration；去掉01/02等序号标签及无用途的批次标签，按共享asset-taxonomy.json进行用途分组。前端也会隐藏旧工作区的数字标签，原SAODG无需被本任务改动。整理会导入工作区效果保存目录顶层的有效旧配置，以及现有recipe的默认值（原可调配方保留，并将来源保存在source-recipe.json），重复配置不会反复入库。原文件保留；无法迁移的项记录错误。统一整理索引为 `nbt_models/asset_library/catalog.json`，记录构件、工具效果、可调配方和材质主题；整理报告记录所有实际变化。

来自原配方的效果带source_recipe_id，样例按局部原点展示；compile时需提供position整数XYZ，应用中先选择放置范围。保存为新效果会保留原配方来源。风化floor.levels与配方高度一起平移，不再错用原高度。原配方仍可在“可调配方”中调整参数。
