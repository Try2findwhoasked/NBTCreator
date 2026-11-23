# 选区自然语言工具编辑

用途：依据已有完整主模型或当前候选的真实局部方块，生成可审阅的建模工具步骤。模型编辑的“AI建模 → 选区自然语言工具编辑”使用同一 Python 引擎；外部 Agent 可直接调用 `selection-edit context/compile`，Electron 无需启动。

## 使用方式与边界

先用“修改范围”填写局部 XYZ，或在 3D 中依次点击两个已有方块确定包围盒；Esc 取消，选点不会创建评论。填写例如“将这段地面改为安山岩，保留边缘和立柱”。应用更新当前参数预览，再读取选区的真实方块和墙层，发送局部坐标、完整选区摘要及本次要求；不自动发送本地路径、源哈希、其他评论或选区外方块。视口截图只在本工作流单独开启时发送。

最多选择 65536 格、512 种材质和 4096 个连续段，摘要最多 128 KiB。超限会要求缩小选区，不悄悄截断数据。未列出的格为空气，连续段格式为 `[x,y,z,沿X长度,palette索引,wall]`；坐标相对选区最小角，wall=1 表示墙层归属。

AI 只返回 JSON 数据：`{"coordinate_space":"local","summary":"修改与保留说明","operations":[...]}`。使用 capabilities.tools 中适用的操作，最多 32 步，每步提供有意义的 label、合法参数和 classification。无法合理完成时返回空 operations，并说明缺失条件。AI 不生成 NBT、执行代码或批准信息，不能指定覆盖、写入边界和变化预算。

先阅读说明并勾选需要的步骤，再“载入参数并预览”。本地将点坐标平移一次，向量、偏移和半径不平移；所有步骤实际写入均限制在原选区，移动／复制的目标也在此限制内。失败会保留原参数与原预览；成功后在操作历史撤销／重做。覆盖已有方块由用户控制，不能绕过保护、模型边界和总变化预算。满意后再显式导出下一版，保留源文件。

## 无界面调用

从创作工作区根目录调用。下例使用 `mise run nbt --`；同名任务时用生成 Skill 的文件任务前缀。若手里只有制作源路径，先用 `control inspect --source <制作源>` 核对 `result.source`、`source_sha256`、`geometry_sha256`、`size` 和 `context`。用 `editing_ready` 判断上下文是否可用于修改。

1. `mise run nbt -- selection-edit context --request <请求JSON> [--snapshot <候选after.json>]`。
2. 按返回的完整局部摘要规划工具步骤。UI 使用当前参数的已绑定候选；CLI 不提供 snapshot 时读取源模型。不用图片猜坐标，不把其他对象的同尺寸快照当作当前模型。
3. `mise run nbt -- selection-edit compile --request <含operations的请求JSON> [--snapshot <同一候选after.json>]`。
4. 将编译返回的全局 `operations` 原样追加到同一编辑请求的 `settings.operations`。以该请求运行 `control plan` 和 `control preview`，各用新输出目录。用同一编辑请求和 `control preview` 返回的 `result.snapshot` 运行 `validate`，为检查另选新目录。编译负责参数和坐标转换；预览和候选验证检查实际写入。使用 `render --snapshot` 生成候选的实际图片并打开查看。

context 请求：

```json
{
  "source":"nbt_models/single/中文名/v_日期时间/master/master_geometry.json.gz",
  "source_sha256":"<实际源文件SHA256>",
  "geometry_sha256":"<实际当前几何哈希>",
  "lo":[10,3,10],
  "hi":[12,6,12]
}
```

| 值从哪里来 | 接续时怎么用 |
| --- | --- |
| 从当前制作版或候选查得 | `source` 与 `source_sha256` 从当前制作版的保存回执或 inspect 取。候选必须是同源的 `after.json`；用同一 `--snapshot` 执行 context 和 compile。 |
| 从实际选区查得 | 填全模型 XYZ 整数 `lo`、`hi`，两端均包含。点位应能在真实模型定位；缺坐标就先找点或请用户明确范围。 |
| 从上一步传递 | 把 context 返回的 `geometry_sha256` 写回 compile 请求。无候选时也可从 inspect 取得当前几何哈希来绑定初次读取。 |
| 本次修改决定 | 按 `palette` 和局部 `runs` 选要换的材料与需保留的格子。填局部 `operations` 与布尔 `allow_overwrite`，参数查 `capabilities --operation replace`。 |

`--request`、`--snapshot` 和请求内的 `source` 优先使用创作根目录相对路径。以示例的 `lo:[10,3,10]` 为原点，将这条局部工具步骤放进 compile 请求的 `operations`：

```json
{"kind":"replace","label":"地面换安山岩","classification":"inherit","lo":[0,0,0],"hi":[2,0,2],"from_states":["stone_bricks"],"state":"andesite"}
```

先用实际摘要确认这片局部范围内只有应换材的地面石砖，避开声明开口及其相邻门槛保护。令 `allow_overwrite:true` 进行本次替换；编译后的操作边界为 `[10,3,10]` 至 `[12,3,12]`，`asset_written:false` 表示本步只返回步骤。保留原请求的 `source`、`source_sha256`、`context` 和其他设置，可从 `control inspect` 取制作源的绑定与上下文。若从候选读取选区，继续沿用构造该候选的编辑请求，再追加本次步骤。

编译器添加 `write_bounds:{lo,hi,allow_overwrite}` 元数据；不要从 AI 输出接受此字段，不能通过删去它把选区编辑改成全局编辑。候选与最终 writer 都会剥离元数据后调用原工具，再核对实际写入位置；原有不含 write_bounds 的工具计划保持原规则。

局部操作的写入上限由编译器设置。为本次候选指定更小的总变化预算时，在 `control preview` 的请求中填写 `settings.max_changed_blocks`。

退出 1 且提示 `lo`、`hi` 时，复查全模型边界与两端坐标。源、快照或几何变化时重跑 context。候选验证以 `result.passed` 为准，失败时把 `result.validation` 指向的完整报告交给 `diagnostics --kind candidate --report <报告>`。

## 配置与恢复

`selection_edit` 是独立内部工作流和创作偏好区域，规则、资料与截图开关位于 AI 助手。旧版五／六区域配置会补齐新区域，保留既有自定义规则、资料选择和截图开关；创作偏好初始继承 structure，之后可独立调整。

候选草稿绑定源文件、原参数和基准几何。源、参数或画面变化时须重新生成，历史文本只供参考。任务记录显示 API 及预览阶段，完成表示该阶段结束，不表示已导出、精修获批或游戏内验收通过。
