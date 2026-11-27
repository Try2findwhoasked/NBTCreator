# 自由曲面拟合与方块壳体

`surface_fit` 返回可编辑的 Bézier 控制网格。`surface_compile` 将控制网格编译为完整方块组成的曲面候选。两个工具都可在创作工作区的 CLI 或共用结构 Agent API 里调用。用 `capabilities --agent-tool surface_fit` 和 `capabilities --agent-tool surface_compile` 查询参数契约。

## 从四条边界或样点拟合

以下 `fit.json` 定义一张鞍形屋面。`v0`、`v1` 的控制点按 U 增长排列，`u0`、`u1` 按 V 增长排列。每条边使用构件本地 XYZ 和 2～6 个 Bézier 控制点。四个角的对应端点必须相接。只传边界时，曲面内部通过 Coons 插值生成。

```json
{
  "boundaries": {
    "v0": [[2.5, 6.5, 2.5], [17.5, 13.5, 2.5]],
    "v1": [[2.5, 13.5, 17.5], [17.5, 6.5, 17.5]],
    "u0": [[2.5, 6.5, 2.5], [2.5, 13.5, 17.5]],
    "u1": [[17.5, 13.5, 2.5], [17.5, 6.5, 17.5]]
  }
}
```

在含 `nbt` mise 任务的创作项目根目录运行以下命令。使用生成的工作区入口时，沿用其中的命令前缀。

```powershell
mise run nbt -- components agent --tool surface_fit --request fit.json
```

按观测拟合时，传入 `samples`，每项为 `{"uv":[0.25,0.75],"position":[6.25,10.875,13.75]}`。UV 由调用者指定，两个值均在 `[0,1]`。仅样点输入默认双三次，可显式给 `degree:[U次数,V次数]`，每个方向为 1～5。次数为 `[3,3]` 时，至少需要 16 个独立样点。按两个方向覆盖边界和内部，同线或集中在很小范围的样点可能无法约束控制网格。

同时传 `boundaries` 和 `samples` 时，锁定四边，仅拟合内部控制点。边界全为直线时，可显式设 `degree:[2,2]` 为内部拟合留出一个控制点。未传 `degree` 时，每个方向取对应两条边的最高次数。如果样点提供了足够约束，结果的 `fit` 会给出三维距离的 RMSE、最大误差、最差样点的从零开始索引、UV 覆盖和线性系统条件数。可用 `max_error` 指定最大允许样点误差，单位为格。该误差仅衡量给定位置，评估外推区可另取独立样点。

## 编译、预览与装配

把拟合回执的 `result.patch` 原样放到 `compile.json` 的 `patch`，或自填控制网格。`control_points[u][v]` 是 XYZ。所有 U 行须等长。上例的完整编译请求如下。

```json
{
  "name": "鞍形屋面",
  "patch": {
    "control_points": [
      [[2.5, 6.5, 2.5], [2.5, 13.5, 17.5]],
      [[17.5, 13.5, 2.5], [17.5, 6.5, 17.5]]
    ]
  },
  "size": [20, 16, 20],
  "material": "minecraft:stone_bricks",
  "thickness": 1.5,
  "tolerance": 0.1,
  "max_changed_blocks": 2000
}
```

```powershell
mise run nbt -- components agent --tool surface_compile --request compile.json
```

- `tolerance` 控制曲面三角化的偏差上界。回执给出实际细分数和上界。最终方块轮廓还受一格量化影响。
- `thickness` 是以曲面为中心的目标总厚度。编译始终保留闭合方块盒与三角面相交的格子。厚度大于零时，再加入中心到三角面距离不超过半厚度的格子。曲面刚好经过整格边界时，两侧相交格都会保留。曲面和厚度必须完整落在 `size` 内，每轴最多 64 格。
- `face_connected` 和 `connected_cells` 统计生成方块的六邻接连通。检查薄壳边缘、与支承接触、自交及实际外观时，使用预览和装配后的真实剖面。

把编译回执的 `result.spec` 包在 `{"spec": ...}` 中交给 `components agent --tool structure_preview --request preview.json`，可得到含真实缩略图的候选。`result.recipe` 可直接用作 `scene_compile` 的对象配方或 `model` 的 `install` 动作配方。保存制作版和定稿继续走各自的显式流程。
