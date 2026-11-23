# 大型组装制作源

组装制作源将多份 Java 1.20.1 SNBT 保存为一个带全局画布和整数偏移的制作源。每份分区仍遵守单轴 294 格和 256 MiB 限制，并须声明显式墙层。组装最多 2048 份分区、400 万实体方块，画布每轴最多 4096 格。当前支持导入、检查、历史登记、`model` 修改与制作版保存、`render` 和有范围的协作回装；密闭封装、开洞发布及 NBT 定稿尚未接入。不要把制作分区当作运行时导出。

建筑库将组装清单作为一个来源列出，不把它的存储分区当作独立建筑。桌面支持只读 3D 查看；桌面交互式编辑和标注证据尚未接入，修改请使用下面的 `model` 命令。快速列表只索引清单，未复核分区；打开、修改和出图时会检查所有分区。

从**创作工作区根目录**准备请求。下例的文件名和偏移只是示意；根据实际分区位置修改，画布尺寸不应从示例推断：

```powershell
$parts = @(
  @{ source = 'parts/lower.snbt'; offset = @(0, 0, 0) },
  @{ source = 'parts/upper.snbt'; offset = @(0, 294, 0) }
)
foreach ($part in $parts) {
  $part.sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $part.source).Hash.ToLowerInvariant()
}
$request = @{
  size = @(300, 384, 300)
  output = 'nbt_models/standalone/example/v01/master'
  partitions = $parts
}
$request | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 assembly-request.json
mise run nbt -- assembly import --request assembly-request.json
```

`source` 必须位于当前工作区；`output` 须是 `nbt_models` 中尚不存在的建筑版本 `master` 目录。输入 SNBT 不会被覆盖。每个分区的局部原点按 `offset` 转为全局坐标；超出画布的实体、重复方块、缺失墙层或源哈希变化会被拒绝。允许分区包围盒部分伸出画布，但实际实体必须在画布内。写入前逐份回读，清单公开后再次回读；中断可能留下没有 `assembly.json` 的未登记目录。

导入会尝试登记版本历史；检查回执的 `history_pending`。为 `true` 时制作源仍保留，排除历史或空间故障后可用 `history record --source <assembly.json>` 重试。只有显式传入请求字段 `set_current: true` 才会选择当前工作版。历史登记会保存清单与全部分区，任一分区发生变化后原版本不再被标记为匹配，可从历史另存恢复。

```powershell
mise run nbt -- assembly inspect --source nbt_models/standalone/example/v01/master/assembly.json
mise run nbt -- render --source nbt_models/standalone/example/v01/master/assembly.json --cameras cameras.json --output nbt_models/standalone/example/render-review
```

渲染前后校验清单和每个分区的 SHA256；变化时输出标记为失败。渲染清单保存分区绑定和图片哈希，仍须实际查看图片。真实看图、用户确认、可通行性和游戏内放置是独立步骤。

## 修改和保存

`model --request <JSON>` 使用导入回执的 `source` 和 `source_sha256`。`patch` 的 `pos` 是全局方块坐标，每条 `before` 和 `after` 都是 `[方块状态, 是否墙层]`；保存时用 `save_draft` 指定含中文的 `name_zh`。也可在同一请求中使用已有构件安装、更新和局部操作，先按具体工具契约检查坐标及保护。`--output <新目录>` 保存独立候选快照；`save_draft` 保存不可变制作版，均不生成定稿 NBT 或用户批准。

保存时沿用原分区尺寸与偏移。原有方块保留原分区归属；新方块落在多个相交包围盒中时写入清单中首个覆盖它的分区。每个实体必须由至少一个分区覆盖，否则保存失败。原分区调色板和额外 SNBT 数据随制作版保留。引用的任一源分区在打开后改变，后续补丁、预览和保存均拒绝继续，需重新打开；不可把相同清单哈希误当成分区仍未改变。

`control walk-inspect --request <JSON> --output <新目录>` 可在组装源上检查声明的起点与终点，跨分区路线使用全局坐标。请求绑定清单 `source_sha256`；报告同时记录所有分区哈希。`model` 的上下文可声明 `require_routes`、`start` 和 `targets`，修改后会重新检查路线。静态碰撞检查不模拟游戏中的光照、流体或动态方块。

## 签发切片与回装

协调方从同一版组装主稿签发每片。下面的哈希是占位示例，必须替换成导入或保存回执中的真实值；范围使用**全局、包含上下界的整数坐标**。`region` 是包含只读邻区的切片范围，`write_bounds` 必须位于切片和主稿内；切片可在画布外保留只读邻区。输出须位于 `nbt_models/_workspaces/assembly-handoffs/` 下，使用新目录，或对同一请求安全重试已登记的目录。

```json
{
  "source": "nbt_models/standalone/example/v01/master/assembly.json",
  "source_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "context": {"mode":"standalone","openings":[],"start":[1.5,1,1.5],"targets":{"end":[7.5,1,1.5]}},
  "region": {"lo":[-1,0,0],"hi":[9,8,4]},
  "write_bounds": {"lo":[0,0,0],"hi":[8,8,4]},
  "output": "nbt_models/_workspaces/assembly-handoffs/section-a"
}
```

在创作工作区运行 `mise run nbt -- assembly slice --request slice-request.json`。回执包含 `manifest`、`manifest_sha256`、`baseline` 和 `context`。保留**签发时**的清单哈希，由协调方自行提交回装请求；不能把片作者修改后重新计算的清单哈希当成原授权。局部 SNBT 的坐标以回执 `origin` 为原点；随附 `coordinates.json` 保护只读邻区，以及已声明的保护、保留、开口和全局路线扫掠净空及支撑。若声明起终点或路线段，签发前会实际走测；未声明路线时 `routes_checked` 为 `false`，不代表通行通过。单片每轴不超过 294 格，投影保护范围合计最多 200 万格。签发中断后可用相同请求重试；已有文件与发布记录不匹配时会拒绝覆盖，需检查或选择新目录。

同一宿主可一次签发多个切片。用 `slices` 数组取代顶层的 `region`、`write_bounds` 和 `output`，每个元素各填这三个字段。宿主及全局路线检查在批内共享，回执的 `slices` 按请求顺序给出单片回执。每批最多 16 片，切片内的方块总数最多 400 万，输出目录须互相独立。每片各自校验并发布，中断后可重试同一批，已签发的切片按原哈希复用。

片作者使用该 `baseline` 和 `context` 通过 `model` 生成局部 SNBT 候选，并向协调方提供候选路径及 SHA256。回装请求中的 `context` 须与签发时同一组宿主约束一致：

```json
{
  "source": "nbt_models/standalone/example/v01/master/assembly.json",
  "source_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "context": {"mode":"standalone","openings":[],"start":[1.5,1,1.5],"targets":{"end":[7.5,1,1.5]}},
  "name_zh": "协作修改",
  "slices": [{
    "manifest": "nbt_models/_workspaces/assembly-handoffs/section-a/slice.json",
    "manifest_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
    "candidate": "nbt_models/_workspaces/assembly-handoffs/section-a-result.snbt",
    "candidate_sha256": "0000000000000000000000000000000000000000000000000000000000000000"
  }]
}
```

运行 `mise run nbt -- assembly merge --request merge-request.json`。工具先核对每片签发清单、局部基线、上下文、候选与宿主分区，再合并到临时完整候选并复核全局路线；任何过期、越界、保护或重叠写入均拒绝发布并报告冲突范围或坐标。成功后返回新制作版与回装摘要，`editing/handoff.json` 记录输入哈希及走测；相同请求重复提交复用同一结果。切片和原主稿均保留，回装不等于用户确认或 NBT 导出。
