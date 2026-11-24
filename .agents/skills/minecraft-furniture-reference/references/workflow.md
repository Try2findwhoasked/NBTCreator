# 单件家具的使用说明

从 NBTCreator 软件仓库根目录运行下列 PowerShell 命令。先完成仓库 README 中的本地环境安装。源码出图可分别通过 `mise run build:web` 和 `mise run ci:renderer` 准备前端及锁定 Chromium。创作工作区可沿用已绑定的渲染依赖与 `paths` 返回的解释器。

```powershell
$skill = '.agents/skills/minecraft-furniture-reference'
$tool = "$skill/scripts/furniture.py"
mise exec -- python -B $tool build --spec "$skill/examples/chair.json" --output build/furniture-chair-a --render
mise exec -- python -B $tool build --spec build/furniture-chair-a/spec.json --output build/furniture-chair-b --render
mise exec -- python -B $tool compare build/furniture-chair-a build/furniture-chair-b --output build/furniture-chair-replay.json
mise run test -- furniture-reference
```

把 `chair.json` 换成 `table.json` 或 `cabinet.json` 即可试跑另外两类。实际创作时使用创作工作区的 `nbt_models` 内的新输出目录。省略 `--render` 可先校验并保存配方。已存在的输出不会被覆盖。若在已创建输出后失败，检查候选的 `render.log`，重试时用新的目录。

## 从照片冻结输入

**观察提示词**　“仅描述这张图中可看见的家具。按正面、侧面和下方识别部件实例，记录各部件的定位特征、材料角色和重复组。分别列出遮挡部件及其补全理由，写明依据是对称、可见端点或类别先验。给出不超过两格高的目标 XYZ 格数和指定视角。标出最重要的可观察特征与无法保证的形状或行为。先说明在室内距离下容易通过什么轮廓认出类别。”

**配方提示词**　“按冻结部件选择原版方块状态。为每份候选添加标明部件 ID 的局部闭区间盒。不重复占用格。优先用半砖、楼梯和活板门保留厚薄及透空。只有相邻件应当发生接触时才声明接合。候选共用尺寸和相机。用一句话写清各自取舍和需要实测的游戏行为。”

输出一份 UTF-8 JSON，其字段和结构可从 [合成椅](../examples/chair.json) 和 [轮背椅](../examples/met-wheel-back.json) 复制。脚本验证结构、占用及部件关系，视觉判断由出图审阅完成。

| 字段 | 契约 |
| --- | --- |
| `schema_version/name/category` | `1`，非空名称，`chair`、`table` 或 `cabinet` |
| `source` | `kind` 和 `title`。照片另有来源 `url`、`license`、`credit`、原图小写 `sha256`，可附 `image_url`。可通过 `Get-FileHash -Algorithm SHA256` 计算。 |
| `size/front` | 正整数 `[X,Y,Z]`，X/Z 各 1–64，Y 为 1–2 且向上，正面固定为 `north`（−Z）。局部原点及放置锚点均为 `[0,0,0]`。两候选共用此盒。 |
| `parts` | 唯一 `id`、`role`、`material`、`feature` 和 `evidence`。证据取 `visible`、`inferred` 或独立夹具的 `synthetic`。重复件用可选 `repeat_group` 关联。若一个部件既有可见主体又有遮挡接头，应拆开记录。 |
| `joins` | 接触部件 ID 对。入口检查占用格的面邻接，已知形状再检查至少一处精确半格面接触。缺少精确形状时记录证据等级。 |
| `candidates` | 一至两个具名方案，每项含 `design` 和 `regions`。每个 region 包含 `part`、局部闭区间 `lo/hi` 和 `state`。所有部件都须落地成形，每格只能有一个状态及部件归属。占用须六邻接连通，至少一格位于 Y=0。 |
| `cameras` | 两候选共享 renderer 视图数组，镜头相对地面的 Y 须大于 0 且不超过 2。示例用 Y=1.62、约 5 格观察距离，保留正面和两侧约 45° 斜视。见 [视图契约](../../minecraft-nbt-modeler/assets/viewer/src/view-contract.mjs)。出图时由 renderer 验证。 |
| `gameplay` | 写拟表达的游戏行为及验证范围。静态造型可与可交互的原版块并存。 |

照片阶段由观察者或视觉模型执行。后续 `build` 读取已经冻结的 JSON；交付时可加 `--photo <原图>` 复制输入并校验原始字节，或者使用规格内允许保留的来源引用。图片版权由来源页记录，脚本本身只核对文件哈希。

大都会博物馆示例可由[原图](https://collectionapi.metmuseum.org/api/collection/v1/iiif/1657/16163/main-image)下载到 `reference.jpg`，然后运行：

```powershell
mise exec -- python -B $tool build --spec "$skill/examples/met-wheel-back.json" --photo reference.jpg --output build/met-chair-a --render
mise exec -- python -B $tool build --spec build/met-chair-a/spec.json --photo build/met-chair-a/reference.jpg --output build/met-chair-b --render
mise exec -- python -B $tool compare build/met-chair-a build/met-chair-b --output build/met-chair-replay.json
```

每个候选保留 `component.json`、回读后的 `model.snbt`、列出 XYZ/状态/墙层/几何指纹的 `ledger.json`，以及纹理 PNG 和渲染清单。家具全部写入主体层。`receipt.json` 记录工具、引擎、运行时和实际文件摘要。`compare` 比对已保存的结构与两次图片，并记录同机位下候选之间的像素差。设计相似度仍需逐项对照原照片。

## 预检已有建筑的安装位

保留宿主当前制作源及其约束文件。填写 `host.json`，其中坐标采用宿主 WorkingModel 的 XYZ 空间：

```json
{
  "source": "nbt_models/standalone/样例/v001/master/model.snbt",
  "source_sha256": "<宿主当前制作源的 SHA256>",
  "position": [6, 1, 5],
  "quarter_turns": 1,
  "writable_box": {"lo": [5, 1, 5], "hi": [6, 3, 7]},
  "route_start": [1.5, 1, 1.5],
  "route_targets": {"passage": [1.5, 1, 8.5], "front-standing": [4.5, 1, 5.5]}
}
```

```powershell
mise exec -- python -B $tool host-check --spec "$skill/examples/chair.json" --candidate main --workspace D:/CreativeProject --host host.json --output host-proposal.json
```

检查非覆盖放置、宿主保护与留白、每个家具底格的精确半格落脚接触，以及放置前后的命名静态路线和站位。相邻通路及站位以宿主声明为准，漏填的路线无法据此验收。待采用时，复跑同一预检，以提案的 `placement.operations` 构造源哈希绑定的 `apply_operations` WorkingModel 请求。按项目要求复验并保存新制作版。参见 [模型操作入口](../../minecraft-nbt-modeler/references/exposed-tools.md)。

碰撞引擎对部分状态只能使用保守包络。包络只用于有限静态通路，无法提供可靠支点。将活板门开合、坐卧、柜门联动、状态更新以及游戏内实装结果另行记录。
