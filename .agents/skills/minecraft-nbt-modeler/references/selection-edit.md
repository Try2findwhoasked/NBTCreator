# 选区自然语言工具编辑

用途：依据已有完整主模型或当前候选的真实局部方块，生成可审阅的建模工具步骤。模型编辑的“AI建模 → 选区自然语言工具编辑”使用同一 Python 引擎；外部 Agent 可直接调用 `selection-edit context/compile`，Electron 无需启动。

## 使用方式与边界

先用“修改范围”填写局部 XYZ，或在 3D 中依次点击两个已有方块确定包围盒；Esc 取消，选点不会创建评论。填写例如“将这段地面改为安山岩，保留边缘和立柱”。应用更新当前参数预览，再读取选区的真实方块和墙层，发送局部坐标、完整选区摘要及本次要求；不自动发送本地路径、源哈希、其他评论或选区外方块。视口截图只在本工作流单独开启时发送。

最多选择 65536 格、512 种材质和 4096 个连续段，摘要最多 128 KiB。超限会要求缩小选区，不悄悄截断数据。未列出的格为空气，连续段格式为 `[x,y,z,沿X长度,palette索引,wall]`；坐标相对选区最小角，wall=1 表示墙层归属。

AI 只返回 JSON 数据：`{"coordinate_space":"local","summary":"修改与保留说明","operations":[...]}`。使用 capabilities.tools 中适用的操作，最多 32 步，每步提供有意义的 label、合法参数和 classification。无法合理完成时返回空 operations，并说明缺失条件。AI 不生成 NBT、执行代码或批准信息，不能指定覆盖、写入边界和变化预算。

先阅读说明并勾选需要的步骤，再“载入参数并预览”。本地将点坐标平移一次，向量、偏移和半径不平移；所有步骤实际写入均限制在原选区，移动／复制的目标也在此限制内。失败会保留原参数与原预览；成功后在操作历史撤销／重做。覆盖已有方块由用户控制，不能绕过保护、模型边界和总变化预算。满意后再显式导出下一版，保留源文件。

## 无界面调用

先从工作区根目录调用 `python .agents/skills/nbtcreator-workspace/nbt.py paths` 查询实际引擎；下文的 nbt.py 指该工作区入口。

1. `nbt.py selection-edit context --request <请求JSON> [--snapshot <候选after.json>]`。
2. 按返回的完整局部摘要规划工具步骤。UI 使用当前参数的已绑定候选；CLI 不提供 snapshot 时读取源模型。不用图片猜坐标，不把其他对象的同尺寸快照当作当前模型。
3. `nbt.py selection-edit compile --request <含operations的请求JSON> [--snapshot <同一候选after.json>]`。
4. 将编译返回的全局 operations 追加到原计划，使用原 control plan/preview/validate 流程执行并实际看图。compile 只验证参数并转换坐标，不证明步骤成功写入、通路或设计已通过；实际写入边界在候选和最终导出中都会再次检查。

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

路径优先采用工作区相对路径；候选快照须为该源的有效 after.json，源哈希、完整几何和墙层证据按原快照规则核验。compile 在相同请求中增加 `operations` 与布尔 `allow_overwrite`。工具参数为局部坐标；例如 `replace` 的 lo/hi 为 `[0,0,0]` 至 `[2,0,2]`，编译后成为 `[10,3,10]` 至 `[12,3,12]`。返回 `asset_written:false`，不写正式建筑。

编译器添加 `write_bounds:{lo,hi,allow_overwrite}` 元数据；不要从 AI 输出接受此字段，不能通过删去它把选区编辑改成全局编辑。候选与最终 writer 都会剥离元数据后调用原工具，再核对实际写入位置；原有不含 write_bounds 的工具计划保持原规则。

## 配置与恢复

`selection_edit` 是独立内部工作流和创作偏好区域，规则、资料与截图开关位于 AI 助手。旧版五／六区域配置会补齐新区域，保留既有自定义规则、资料选择和截图开关；创作偏好初始继承 structure，之后可独立调整。

候选草稿绑定源文件、原参数和基准几何。源、参数或画面变化时须重新生成，历史文本只供参考。任务记录显示 API 及预览阶段，完成表示该阶段结束，不表示已导出、精修获批或游戏内验收通过。
