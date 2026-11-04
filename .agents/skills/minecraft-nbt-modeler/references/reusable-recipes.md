# 操作配方、材质主题与构件阵列

应用和 Agent 共用工作区 `.nbtcreator/reusable/<编号>.json`。这是可移植的 JSON 资料，不包含脚本、安装路径或模型文件。入口在资产管理左侧“操作配方 / 材质主题”；构件详情中的“批量阵列与材质主题”设置 XYZ 数量、间距及主题。上方浏览布局保持与项目管理一致。

## 配方与参数

配方保存有序工具序列及可调参数。可从当前建模工具序列保存，勾选要暴露的字段，再生成参数控件；独立的整体混材、地面等面板不会自动收入序列。保存时按全部步骤的包围盒最小点归零，坐标变成本地坐标；半径、长度、偏移向量和粘贴体素的相对坐标不随原点平移。

数值支持 integer / number，可声明 min、max；方块状态使用 block；开关使用 boolean。引用只能为 `{"param":"名称"}`，数值可附加固定常量 `add`，不执行表达式或代码。多个字段可在高级 JSON 中引用同一个参数，例如高度同时控制顶面和梁端。最多32个参数、128项步骤，数据不超过8MiB。

```json
{
  "schema_version": 1,
  "asset_type": "recipe",
  "name": "可调石柱",
  "tags": ["支承"],
  "parameters": {
    "height": {"type": "integer", "label": "柱高", "default": 4, "min": 1, "max": 32},
    "material": {"type": "block", "label": "柱身", "default": "minecraft:stone_bricks"}
  },
  "operations": [{
    "kind": "box", "label": "柱身", "classification": "body",
    "lo": [0, 0, 0], "hi": [0, {"param": "height", "add": -1}, 0],
    "state": {"param": "material"}
  }]
}
```

在工作区运行：

```powershell
python .agents/skills/nbtcreator-workspace/nbt.py recipes list
python .agents/skills/nbtcreator-workspace/nbt.py recipes save --file 柱子.recipe.json
python .agents/skills/nbtcreator-workspace/nbt.py recipes get --id <编号>
python .agents/skills/nbtcreator-workspace/nbt.py recipes capture --file 工具数组.json --name 双柱 --bindings 参数绑定.json
python .agents/skills/nbtcreator-workspace/nbt.py recipes compile --id <编号> --values 本次参数.json --position 20,4,20 --size 48,24,48
```

`参数绑定.json` 例如 `[{"path":[0,"hi",1],"name":"top","label":"柱顶本地Y"}]`；默认值从归零后的坐标提取，柱高4时顶面Y为3。`本次参数.json` 例如 `{"height":6,"material":"minecraft:oak_log"}`，未提供的参数使用默认值。`--workspace <目录>` 放在 recipes 后、子命令前，默认当前 Agent 工作目录。

compile 返回 operations、lo、hi 和实际参数，**不修改建筑**；复制、移动、线性阵列或旋转步骤的目标也计入包围盒。应用将返回步骤追加到候选并立即预览，可撤销；CLI 调用者把它们合入 control 请求，再走 preview / validate / 新版本输出。编译检查坐标和基本格式，具体几何、冲突、保护及预算由原有引擎的预览、验收和导出继续检查。

UI 编译绑定当前源文件、哈希、尺寸与参数；等待期间换建筑或调参会拒绝旧结果。JSON 中不能保存 write_group；本地编译为创建步骤生成新组，使同配方的新增构件能叠加自己的细节。覆盖开关由本次使用者决定，不沿用配方里的旧权限，也不越过保护和验收。修改类步骤仍有其原工具语义，使用前核对是否包含挖空、替换或移动。

## 材质主题

主题是一组单次方块映射，可应用于配方或构件阵列，包括只放一份的构件；不是自动替换整座建筑的按钮。

```json
{
  "schema_version": 1, "asset_type": "theme", "name": "深色石构",
  "mapping": {"minecraft:stone_bricks": "minecraft:deepslate_bricks"},
  "preserve_shape": true
}
```

同样通过 recipes save / get / list 管理。最多64条映射，不接受空气；完整状态映射优先，其次按方块名映射。保留兼容的朝向、轴向等属性，显式目标属性优先。映射只走一次，例如 A→B、B→C 时 A 不会继续变成 C。

preserve_shape 默认 true，实际使用时比较碰撞形状；完整块换成半砖会拒绝。显式关闭后仍需检查通路与净空。未知碰撞形状不会被当作可靠的“相同形状”。主题改变参数中的 state、palette、from_states、风化材质与地面映射，不改坐标和体素编号。

```powershell
python .agents/skills/nbtcreator-workspace/nbt.py recipes compile --id <配方编号> --position 20,4,20 --size 48,24,48 --theme <主题编号>
python .agents/skills/nbtcreator-workspace/nbt.py recipes archive --id <编号> --archived true
python .agents/skills/nbtcreator-workspace/nbt.py recipes archive --id <编号> --archived false
```

导入总是创建新编号；按编号保存用于更新已有内容。回收站可恢复，资料随工作区移动。

## XYZ 网格阵列

```powershell
python .agents/skills/nbtcreator-workspace/nbt.py components batch --id <构件编号> --position 12,4,12 --size 48,24,48 --counts 3,1,2 --spacing 6,0,8 --quarter-turns 1 --theme <主题编号>
```

数量包含原始放置的第一份，示例生成3×1×2共6份；spacing 是相邻锚点的 XYZ 差值，可为负数，重复轴不能为0。每轴1～64、总数最多64，合计最多65536格体素记录。副本从同一不可变构件生成，支持已有90°旋转、镜像和墙层归属；不逐份复制上一份，以免累积坐标或状态误差。

副本实际体素重叠、超出世界尺寸或主题无法保持形状会明确报错，不静默裁切。默认拒绝与原建筑冲突；`--overwrite` 允许目标写入，仍受保护和最终验收约束。返回候选步骤，不直接写 NBT。资产管理的手柄操作仍调整单份构件，批量设置用于“载入并预览”及“3D选点放置”。
