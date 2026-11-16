# 纹样来源与制作

用于选择图库、导入或裁取图片、绘制小位图和保存组合资产。得到图源后进入[纹样拟合与质量](pattern-fitting.md)，不要把资产创建成功当作拟合、安装或验收成功。

这里区分两种参数入口：独立纹样的 `pattern_*` 请求使用 `sample` / `shapes`；附属于参数化构件的装饰放在 `ornament` 内，使用 `sample_shape_fit`。它们不是可互换的字段，实际 Schema 从对应工具查询。

## 构件附带的样本装饰

ornament.richness 取 0～3，逐级加入珠饰、斜线花丝和中心环。ornament.highlight 控制这些细节最外层的材质，默认沿用装饰材质。此叠加仍遵守布局范围、中心留白和构件保护规则。

```json
{
  "kind": "wall",
  "size": [27, 25, 4],
  "style": "classic",
  "ornament": {
    "profile": "geometric",
    "material": "chiseled_stone_bricks",
    "highlight": "gold_block",
    "richness": 3,
    "depth": 2,
    "density": 100,
    "seed": 42,
    "sample": {
      "path": "references/rosette.png",
      "sha256": "<从本地图片计算的SHA256>",
      "channel": "luminance",
      "fit": "contain",
      "threshold": 50,
      "noise_strength": 20,
      "noise_scale": 4,
      "mirror": false
    }
  }
}
```

亮度模式默认亮处生成装饰，alpha 模式用透明度生成装饰。invert 可反转阈值输入，完全透明区域仍排除。contain 保持比例并留边，cover 等比裁切以填满装饰面。noise_strength 为 0～100，0 保留纯样本阈值。noise_scale 为 1～16 格，数值越大，变化越连片。同一图片哈希、种子和参数可复现几何。sample.mirror 可沿样本左半边镜像，与结构纹样的 symmetry 分开。density 可继续稀疏采样结果。样本替代内部基础纹样，边框、布局、留白和华丽度叠加仍生效。

工具接收工作区内的单帧 PNG、JPEG 或 WebP，最多 8 MiB、4194304 像素。它将图案按装饰面的格数重采样，再用固定种子的二维值噪声扰动阈值。这是一种二维掩模到方块纹样的转换，颜色材质由 material 和 highlight 指定。建议使用高对比正视线稿、浮雕掩模或透明剪影。倾斜照片与复杂背景需要先裁切或校正。后续可用 parametric_preview 查看结果，再按安装面运行贴面、预算和路线检查。


## 图源、重复与收边

`parametric_list` 的 `architectural_samples` 提供馆藏下载页、公开使用标记、建筑用途及裁切建议。卡尚星十字砖适合制作墙面重复单元，布尔萨卷草用于门口边带，卡尚角砖用于角饰。它们是实际建筑使用的实例。模型流程采用建模师常用的做法，将纹样裁成重复单元，先排布整体，再加收边和浮雕。馆藏照片仍需按用途裁切，尤其不能把单块十字砖等同于可无缝覆盖的星十字组合。

```json
{
  "sample_repeat": [3, 1],
  "edge_trim": {
    "slab": "stone_brick_slab",
    "stairs": "stone_brick_stairs"
  }
}
```

以上字段位于 ornament 内，sample_repeat 分别控制横纵重复次数。它按重复单元重新拟合样本，支持1～8次。指定 sample.reference_id 可携带馆藏来源，图片的实际内容仍由本地 path 和 sha256 校验。可使用目录项的 suggested_layout 和 suggested_repeat 作为起点。

edge_trim 仅用于墙饰和吊顶的新增外层边缘，不替换现有基底格。半砖用于薄收边，直形楼梯用于有方向的转折。depth=2 或3可保留内层厚度。安装后仍按现有贴面与路线流程核验。半砖和直形楼梯状态支持现有旋转、镜像。


## 配色与构件轮廓

`ornament.sample.colors` 可声明 1～8 对 RGB 色值与方块材质。例如 `[{"rgb":"#204784","material":"blue_concrete"},{"rgb":"#E6DFCD","material":"quartz_block"}]`。样本 RGB 按最近颜色映射到指定材质。透明度或亮度阈值仍独立决定轮廓，边框保留 material，华丽细节保留 highlight。建议先裁出单个周期、去背景，再保留 2～4 个主色，避免把釉面反光和拍摄阴影当成新颜色。

`ornament.sample_shape_fit` 可指定 `{"slab":"quartz_slab","stairs":"quartz_stairs"}`。墙饰在 depth=1 时按每格四个半格选择空格、整块、上/下半砖或东西向直形楼梯。整块按配色表选材，半砖和楼梯使用各自指定的材质。此模式与 edge_trim 互斥。报告分别给出各类方块用量和拟合轮廓中遗漏、多出的半格。图片投影仍需要正视裁切，密集细纹可以先勾出主轮廓。

## 小纹样生成、区域采样与组合资产

外部 Agent 可先设计一个小型二维纹样，再交给共用拟合器。`pattern_create` 接收小位图或受限绘图配方，生成实际 PNG、缩略图和配方，并保存为原生纹样资产。它不执行代码，也不写建筑。外部 Agent 已有生图能力时，也可把生成图片保存到创作工作区，再用 `pattern_assets` 导入。

小位图示例：

```json
{"name":"菱花徽记","resolution":[64,64],"layers":[{"kind":"bitmap","rows":["...##...","..####..",".##..##.","##....##","##....##",".##..##.","..####..","...##..."]}]}
```

bitmap 的行数、每行宽度均为1～128，所有行等宽。`#` 或 `f` 为白色，`.` 或 `0` 为黑色，十六进制1～e为灰度。resolution 为最终图片尺寸，每轴8～256，默认16×16。小位图按最近邻放大，绘图与组合则使用四倍采样后归一化。

组合示例：

```json
{
  "name":"八瓣花与菱形格栅",
  "resolution":[128,128],
  "tags":["墙饰","吊顶","组合"],
  "layers":[
    {"kind":"preset","preset":"diamond-lattice","repeat":[2,2],"opacity":0.5},
    {"kind":"ellipse","bounds":[0.4,0.08,0.6,0.5],"radial_count":8},
    {"kind":"ellipse","bounds":[0.44,0.44,0.56,0.56],"blend":"subtract"},
    {"kind":"ellipse","bounds":[0.04,0.04,0.96,0.96],"fill":false,"stroke":0.025}
  ]
}
```

图层从前向后依次计算。支持以下来源：

| kind | 参数与用途 |
| --- | --- |
| bitmap | rows，小位图草图 |
| rect / ellipse | bounds、value、fill、stroke，矩形/椭圆及边框 |
| polygon | points 至少3点，填充或描边 |
| polyline | points 至少2点，连续线条 |
| bezier | points 恰好4个二维控制点，三次贝塞尔曲线；samples=16～1024，默认257个含起终点的采样 |
| preset | preset 图库 ID，可选 crop、channel |
| asset | id 与 image_sha256，复用已保存图像，可选 crop、channel |
| sample | sample 中的 path、sha256、crop、channel，使用工作区图片 |

图层通用参数包括 box（在画布中的归一化目标框）、rotation（逆时针角度，旋转在图层内裁切）、flip_x / flip_y、repeat（每轴1～8）、radial_count（1～16份绕图层中心旋转叠加）、opacity（0～1）。几何 points、bounds、box 都以左上角为原点，坐标范围0～1；stroke 是相对图层短边的笔画宽度，value 是0～255灰度。blend 支持 union（取亮）、subtract（镂空）、intersect（取暗）、xor（绝对差）和 add（饱和相加）。最多32层，配方最多512KiB；空白结果拒绝保存。输出的 analysis 记录前景占比和左右/上下边缘差异，边缘差异不为0时不能宣称无缝平铺。

所有拟合接口的 sample 现在支持 `crop:[x0,y0,x1,y1]`，对原图先裁取，再缩放、重复、减色和半格拟合。坐标同样从左上角起算，范围0～1，原图 SHA256 仍绑定整张原图。图库用 preset_options.crop。组合图层也能各自裁取不同区域后拼合。

```json
{"surface":"wall","size_uv":[32,24],"sample":{"path":"references/ornament.png","sha256":"<原图SHA256>","crop":[0.25,0.1,0.6,0.7],"noise_strength":0},"shapes":{"stairs":"quartz_stairs","slab":"quartz_slab"}}
```

`pattern_create` 返回 fitting_input（sample 路径和图像哈希），可直接合并到 pattern_compile / pattern_preview 请求中。楼梯和半砖的匹配、接触、旋转仍由脚本负责。优先以8～32像素绘制单个主纹，用 pattern_microfit 在2～8格验证后再重复铺排；过细时裁取更简单的区域或加粗主纹。

原生纹样库保存于 `nbt_models/asset_library/patterns/<id>/`。pattern.json 保存名称、标签、来源和组合配方；pattern.png 是拟合图片，thumbnail.png 是缩略图；导入或裁取副本另保留 original.image 原始字节。图像、缩略图、原图和元数据都绑定哈希。创建新纹样使用新ID，重命名和回收只修改元数据，图像内容保持可复用。

通过 `pattern_assets` 管理：

| action | 请求 |
| --- | --- |
| list | 仅 action，查询内置与工作区纹样，内置图库不复制进用户目录 |
| get | id，读取配方、图片、尺寸和 fitting_input |
| import | name、sample，或 name、image_base64；可选 tags |
| copy | id、image_sha256；可选 name、tags、crop，生成独立副本 |
| update | id、content_sha256；可选 name、tags、archived，拒绝过期元数据 |

内置 ID 为 `builtin:<图库ID>`，只读，可 copy 创建工作区副本。asset 图层使用 image_sha256 绑定像素，因此仅重命名不会破坏复用。界面在素材库的“纹样”分类中展示同一批资产，支持导入、裁取、组合、改名、回收、拟合预览和保存为建筑构件。纹样资产与拟合后的构件分别保存；不自动定稿 NBT。

基础几何预设包括棋盘格 `checkerboard`、横条 `horizontal-stripes`、竖条 `vertical-stripes`、错缝砖 `running-bond`、编织格 `basket-weave`、人字折纹 `herringbone`、菱形格 `diamond-lattice`、回折纹 `greek-key`、之字带 `zigzag-band`、十字 `cross-tile`、阶梯菱形 `stepped-diamond` 和四瓣花 `four-petal`。建议从 16×16 格开始；不同预设支持的安装面以 `pattern_list` 为准。`repeat` 按面板宽高重复完整图样，建议在较大面板上使用，尺寸太小时细节可能合并。

新增原生欧式微纹样 `micro-fleur-de-lis`（百合莨苕花冠）和 `micro-rose-window`（重瓣玫瑰窗花）。推荐尺寸由 pattern_list 返回：百合用于8×8墙/柱/吊顶，玫瑰窗花用12×12墙/柱/地板/吊顶；没有推荐的安装面不冒称已验证。纹样可复制进工作区资产后继续组合与命名绑定。

纹样的FFT预处理用 `pattern_filter`，参数、适用规模与边界见[频域滤波](pattern-spectral.md)。滤波生成新资产，再交给微型拟合与原门槛；不能以滤波成功代替拓扑和实际看图。
