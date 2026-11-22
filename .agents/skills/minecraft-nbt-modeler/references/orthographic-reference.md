# 三视参考与回投影

`reference` 在创作工作区中登记三视图、锚点及其依据，输出可重复的 `geometry.loft` 截面，并以用户提供的轮廓掩模检查实际方块投影。图源、掩模、模型和输出均保留 SHA256；登记、拟合、回投影与用户实际看图确认是不同步骤。

## 登记视图和锚点

从创作项目根目录执行 `mise run nbt -- reference register --request reference-request.json`。请求包含：

- `output`：`nbt_models/_workspaces/reference-views/` 下尚不存在的目录。
- `views`：恰好包含 `front`、`side`、`top`；每项有工作区内图片 `image`、小写 `sha256`、来源类别 `origin_type`（`original`、`generated` 或 `derived`）、文字依据 `basis`、像素原点 `origin: [u,v]`、`pixels_per_block`、`u_axis` 和 `v_axis`。轴使用 `x`、`-x`、`y`、`-y`、`z`、`-z`；正视使用 X/Y，侧视使用 Z/Y，俯视使用 X/Z。轴的符号描述屏幕正方向，俯视 Z 方向须明确。三图使用相同方块尺度。
- `anchors`：每项有稳定 `id`、`part`、世界 `world: [x,y,z]`、文字 `basis`、`confidence`（`measured`、`estimated` 或 `generated`）、以方块为单位的 `uncertainty`，以及 `views` 中实际量读到的像素坐标。锚点在各图的像素与同一世界坐标必须在声明的不确定范围内对齐。
- `assumptions`：文字数组，记录遮挡、不可见深度、生成图和其他推定；空数组表示未登记推定，不证明没有推定。

图片应为 PNG、JPEG 或 WebP，单张不超过 64 MiB。输出保存图像副本和 `reference.json`；原图不覆盖。回执的 `manifest` 和 `manifest_sha256` 用于后续步骤。输出公开前会校验原图与副本，读取时重新校验登记图像。

## 从锚点拟合截面

`mise run nbt -- reference fit --request fit-request.json --output nbt_models/_workspaces/reference-fits/tower.json`。请求包含 `reference`、`reference_sha256`、`part`、`sample_step`（1～128 格）、`vertices`（8～128 且为 4 的倍数）及 `rows`。每行的 `x_min`、`x_max`、`z_min`、`z_max` 是已登记锚点 ID；四个锚点必须属于指定构件、处于同一高度，各行高度严格递增。真实尖角或台阶接点可在该行设置 `corner: true`，保留两侧独立坡度。

输出包含每段贝塞尔侧向控制值、采样高度和 `geometry: {"shape":"loft","sections":[...]}`。各截面为相同顶点顺序的椭圆多边形，四条边界的手柄约束在相邻锚点范围内；不会自动表达孔洞、壳厚、平台或支承，需单独建模和检查。把 `geometry` 放进现有 `model` 局部几何操作，并提供操作范围、材质和墙层；拟合本身不写模型，也不自动批准粗模。

拟合回执包含结果文件的 `sha256`。运行 `mise run nbt -- reference verify-fit --fit <拟合JSON> --sha256 <回执哈希>` 会重新读取登记图像和锚点并重算截面，核对结果与同一输入一致；任何输入或结果变化均拒绝通过。

## 登记材质正交相机

`mise run nbt -- reference cameras --request camera-request.json` 接收 `source`、`source_sha256`、`reference`、`reference_sha256` 和 `output`，其中输出为 `nbt_models/_workspaces/reference-cameras/` 下的新目录。工具从登记图的屏幕轴、原点、尺度和实际模型深度生成三个正交相机，每个视图回执含相机 JSON 文件、SHA256 及匹配原图的宽高。`reference verify-cameras --bundle <cameras.json> --sha256 <清单哈希>` 重新核对模型、组装分区、登记图和相机参数。

实际出图时使用回执中某一视图的相机文件，并同时提供 `render --camera-bundle <cameras.json> --camera-bundle-sha256 <清单哈希>`；`--width` 和 `--height` 须等于该视图回执的尺寸。渲染前后都会复核登记相机绑定，报告保存清单、参考图和相机哈希。可用同一相机文件渲染不同模型候选，但相机清单所绑定的原模型与参考图必须仍然有效。

相机请求可选 `lighting_options`，须同时给出非零 `direction: [x,y,z]`、`temperature_kelvin`（1000～40000）、`background: [r,g,b]`（每项 0～1）和 `exposure`（0.1～4）。这些参数写入各相机文件和图片元数据；背景使用统一天空色，色温采用以 6500 K 为白点的可重复近似，不是校准的光谱色彩。省略时使用现有 `day` 或 `night` 预设。比较候选时保持相同参数，不用更换光照掩盖形体差异。

## 轮廓回投影

`mise run nbt -- reference compare --request compare-request.json`。请求字段为：

- `source`、`source_sha256`：当前 SNBT、NBT、压缩主稿或组装清单及其哈希。
- `reference`、`reference_sha256`：登记清单及其哈希。
- `masks`：恰好包含三个视图；每项提供工作区内掩模 `file`、`sha256` 和 1～255 的灰度 `threshold`。大于等于阈值是参考轮廓内部。可另提供 `ignore_file` 和 `ignore_sha256`，用同一阈值标记遮挡或不参与评分的像素。
- `regions`：可为空；局部项含 `id`、`view`、`lo` 和 `hi`，范围为图像内包含上下界的像素坐标。
- `output`：`nbt_models/_workspaces/reference-reviews/` 下尚不存在的新目录。

报告分别列出制作画布、实际占据包围盒、每视图和局部区域的轮廓交并比，以及参考轮廓到模型、模型到参考轮廓的双向一格容差覆盖率。容差以配准尺度换算像素，使用方形邻域；没有参考轮廓时相应覆盖率为 `null`。叠图中绿色为重合、蓝色为参考独有、红色为模型独有、黄色为排除区域。原图、掩模和制作源均不修改。

投影使用静态碰撞半格形状；完整块、半砖和支持的楼梯按碰撞形状处理，不支持或无碰撞的可见形状采用近似并列入 `approximate_states`。这不是材质正交渲染，也不证明遮挡背面或视觉风格。用 `mise run nbt -- reference verify --report <comparison.json> --sha256 <回执哈希>` 可重查绑定文件和叠图；该检查不重新计算分数，也不授予视觉批准。实际图片、斜视、必要通路及游戏内状态仍需分别审阅。

## 同机位匿名 A/B 审阅

先用两个模型分别运行 `render`，确保相机文件、光照、输出宽高、质量和图层一致。使用登记相机时，两次均提供同一个相机清单及哈希。渲染清单必须包含相机路径和图片元数据哈希；较早的不完整清单需重新出图。

审阅清单和单张图片的元数据上限为 4 MiB，含体素的渲染快照上限为 64 MiB。快照与清单分别校验哈希，适用于同一机位下的大型原稿及候选。

`mise run nbt -- reference review-prepare --request review-request.json` 接收 `renders`（两个 `{manifest, sha256}`）、`scope`（此次实际比较范围）、`crop`（`[左,上,右,下]` 像素边界，右和下不包含；`null` 表示全图）和 `output`（`nbt_models/_workspaces/reference-reviews/` 下的新目录）。工具检查两个渲染的源、分区、机位、光照、画幅、快照、图片和元数据，并随机分配 A/B。输出 `public/` 只含去除 PNG 元数据的匿名图片、差异图和 `review.json`；差异图将 RGB 绝对差放大 4 倍并截到 255，透明度差异用洋红标出，变化像素数按原始 RGBA 非零差计算。`private/binding.json` 保存来源映射，应留给协调方。需要盲评时只向审阅者提供 `public/`，不要同时提供私有绑定，也不要在 `scope` 中写入会暴露来源的名称。

实际看图后，`reference review-record --request <JSON>` 使用 `public`、`public_sha256`、`decision`（`A`、`B`、`tie` 或 `inconclusive`）、`actor`（`human` 或 `agent`）、`observations` 和 `output` 保存新记录。每条观察含匿名 `view`（如 `view-01`）、`note` 和未解决项 `remaining`；可选的 `part`、`reference_region`、`expected` 和 `recheck` 分别用文字记录部位、参考区域、预期关系及复核条件。参考区域文字本身不是图源坐标或哈希绑定。`actor` 是记录标签，不证明身份；这一步不核验来源是否仍有效，也不构成用户批准。

需要绑定具体参考区域时，可在观察中另加 `reference`：`{"manifest":"<登记清单>","sha256":"<清单哈希>","view":"front","lo":[x0,y0],"hi":[x1,y1]}`。`view` 为 `front`、`side` 或 `top`，`lo` 和 `hi` 是包含上下界的整数像素坐标。保存时核对区域范围、登记清单和三张登记图，并将清单路径改为工作区相对路径；后续审阅核验会重新检查它们。自由文字 `reference_region` 仍可描述区域意图，两者作用不同。盲评期间避免在文字或参考区域信息中泄露匿名候选身份。

协调方使用 `reference review-verify --request <JSON>`，提供 `binding`、`binding_sha256`，以及可选的 `record`、`record_sha256`。核对会重新检查来源、分区、相机、光照、图片和裁切，确认匿名图像像素及差异图与原渲染一致；任一输入变化即失败。核对通过仍只证明证据绑定，不能代替实际观察、用户明确确认、通路检查或游戏实测。
