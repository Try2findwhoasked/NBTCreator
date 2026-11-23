# 完整主模型的统一组合入口

新建建筑、编辑已有制作源及独立构件使用共享 `nbt_working_model.WorkingModel`。它管理当前完整候选、实例安装基线和制作版；`ModellingSession` 继续只负责缓存。原有几何与参数化工具可继续使用，无需把整栋建筑强制改成对象图。

新增构件编译器或工作模型操作时，使用[处理器与配方注册器](extensions.md)。工作模型与对象图通过同一编译注册器接入，公共参数仍以工具目录为准。

在创作项目根目录运行 `mise run nbt -- capabilities --model` 查询请求契约；执行 `mise run nbt -- model --request request.json`。软件源码维护时使用 `mise exec -- node scripts/cli.mjs --workspace <隔离工作区> model --request <JSON>`。引擎位置仍由工作区 `paths` 返回，不写死安装路径，不在软件源码生成创作入口。

复杂建筑可由[可执行建筑方案](architecture-workflow.md)编排同一个工作模型。方案绑定随制作版保存，普通 `validate` 也复检实际空间、梯段、承托和风格规则；不改变用户看图与定稿边界。

## 梁架节奏候选

在 `model` 请求的 `actions` 中使用 `beam_rhythm` 搜索。用 `capabilities --model` 查字段。将既有制作源和 `source_sha256` 放在请求顶层。目标示例在生成的 `search.json` 中。

- `goal.region` 是包含两端的世界 XYZ 修改区域，`origin_xy` 是左柱脚坐标，`span_x` 含两端柱。每榀厚一格，由两根单格截面立柱与一根沿 X 的矩形梁组成。`materials.post` 和 `materials.beam` 分别指定完整方块状态。未注明轴向的原木按构件方向取木纹。
- `count` 指定榀数，`target_pitch` 指定理想间距，`pitches` 与 `starts` 指定允许尝试的间距和世界 Z 起点，最多 64 种组合。`anchor_z` 可填写既有轴线或入口的实际世界 Z 坐标，用于同分排序。
- 每组候选作为一次完整写入检查范围、占用、保护区、留空、改动预算、适用的必需路线和装配接口。两根柱脚均须有已知碰撞形状的顶面接触。回执报告方块、墙层和受影响坐标的实际改动量，支承证据限于静态接触。
- 基线在构件掩模内按固定 XY 对候选实测占用做 Z 向 FFT。比较目标基频及其谐波附近各一格频率 bin 的幅度，并加上相对间距误差、缺块比例和材质状态偏差比例。总误差保留 12 位小数后依次比较离锚点的距离、变动格数、间距和起点。相同幅度的平移候选由约束和位置证据区分。回执包含每榀坐标、实际间隔、误差和拒绝原因。无解返回 `no_legal_candidates` 和 `rejection_counts`。
- 搜索时可提供 `preview: {"output":"新的预览目录"}` 预览首选。也可同时给出 `pitch`、`start_z` 预览指定候选。检查落盘的 SNBT、快照和真实图像后，用独立的 `adopt_beam_rhythm` 动作传入同一个 `goal`、所选间距及起点和 `candidate_sha256`。采用时重算候选与检查，哈希绑定搜索时的宿主、目标、预算及引擎。制作版保存仍由请求的 `save_draft` 控制。

在软件仓库根目录运行下面的合成示例。每次选一个新的输出目录。

```powershell
mise exec -- python -B scripts/examples/beam-rhythm.py --workspace build/beam-rhythm-example
mise run nbt -- render --source build/beam-rhythm-example/beam-rhythm-preview/candidate.snbt --cameras build/beam-rhythm-example/beam-rhythm-preview/cameras.json --output build/beam-rhythm-example/render
mise run nbt -- --workspace build/beam-rhythm-example model --request adopt.json
```

示例在 18 个组合中选中 Z=10 起步、间距 6 格的 9 榀梁架。候选报告与预览哈希分别见 `beam-rhythm-report.json` 和 `beam-rhythm-preview/beam-rhythm.json`。在仓库根运行 `mise run test -- beam-rhythm` 复验同谱异位、保护拒绝、无解反馈、完整预算及 CLI 采用。

## 单开间檐底小波移植

在 `model` 的 `actions` 中使用 `wavelet_eave`，用 `capabilities --model` 查请求字段。顶层 `source` 和 `source_sha256` 绑定现有制作源。

- `goal.target` 和 `goal.reference` 以世界 XYZ 的 `start`、水平 `along`、垂直于沿线的水平 `inward`、相同的 `length`（8～64 格）逐格对齐。两段可采用不同朝向。参考可位于同一模型的另一段檐口，也可在 `reference` 内通过 `source` 与 `source_sha256` 绑定外部 SNBT/NBT。
- 采样限于同高、单格宽的直檐，檐边上半层须连续。曲线以格为单位，读出下半层从内侧连续占据的进深 0、0.5 或 1。三种输出分别由干燥上半砖、朝内的干燥直上楼梯、干燥双半砖表达。变动位置使用 `materials.slab` 和 `materials.stair` 指定的方块 ID。原有实例拥有的方块位置会使候选被拒绝。
- NumPy 使用 B3 样条不降采样分解。各层滤波间隔为 1、2、4、8 格，采用镜像延拓。工具从参考减去目标的选定细节带（`levels`），将差值按 `taper` 做余弦渐变后叠加到原目标，两端保持原状态。`strengths` 限定本次尝试的强度，工具比较编译后实测曲线与未量化目标的均方根误差。
- `ridge` 圈定必须保留的实际屋脊。候选必须保持所有整格占据坐标和三轴正投影的半格占据轮廓。工具复查两端内外接缝、相邻站点、向内背衬的已知形状面接触和楼梯朝向，并沿用保护、留白、预算和适用的通路及装配检查。检查范围为静态几何。回执列出实际变更、接缝、背衬和测试过的投影射线。受控强度下无合法结果时返回 `no_legal_candidates` 与逐项原因。
- `preview: {"output":"全新目录"}` 写首选候选的制作源、快照、机位和回读报告。可增加 `strength` 选择其他合法候选。使用 `render` 查看候选和原稿的同机位纹理图，再用独立的 `adopt_wavelet_eave` 动作传入同一 `goal`、`strength` 和 `candidate_sha256`。采用会重新检查源、实际方块与全部约束。显式保存制作版仍使用 `save_draft`，用户批准和定稿仍各走原入口。

在软件仓库根目录运行三开间廊屋样例。每次使用全新的示例和渲染目录。

```powershell
mise exec -- python -B scripts/examples/wavelet-eave.py --workspace build/wavelet-eave-example
$root = (Resolve-Path 'build/wavelet-eave-example').Path
$before = (Get-Content -Raw (Join-Path $root 'search.json') | ConvertFrom-Json).source
$cameras = Join-Path $root 'preview/cameras.json'
mise run nbt -- --workspace $root render --source $before --cameras $cameras --output (Join-Path $root 'render-before')
mise run nbt -- --workspace $root render --source (Join-Path $root 'preview/candidate.snbt') --cameras $cameras --output (Join-Path $root 'render-after')
mise run nbt -- --workspace $root model --request adopt.json
```

样例的 `wavelet-eave-report.json` 记录目标、量化和实测曲线，`readback-evidence.json` 从落盘方块独立重建三个完整投影并记录屋脊、包络和逐格差异。使用 `mise run test -- wavelet-eave` 复验成功、无合法轮廓、保护与预算、接缝、支承、楼梯、源绑定和采用流程。运行只依赖当前 Python/NumPy 引擎。

## Python 制作脚本

```python
from nbt_working_model import WorkingModel

model = WorkingModel(workspace, [96, 24, 48], context={
    "mode": "standalone", "openings": [],
    "max_changed_blocks": 120000,
}, limits={"max_changed_positions": 120000})
model.install("west_pillar", {
    "tool": "parametric_compile",
    "arguments": {"kind": "pillar", "size": [3, 7, 3]},
}, position=[47, 1, 12])
print(model.inspect("west_pillar"))
# 继续构造本次设计的地面、围护、顶构和路线，再按实际阶段检查。
receipt = model.save_draft(name_zh="本次建筑", shape="standalone")
```

`install`、`update`、`remove`、`detach`、`patch` 和 `apply_operations` 先在副本上检查，成功后才替换内存候选；不自动保存或定稿。`install` 接受纯编译配方与世界锚点，内部完成 build、状态变换和放置。构件每轴与方块上限保持原接口约束；完整主模型允许跨48格存储边界。实例 ID 在该建筑中稳定且唯一。

`inspect` 返回实例配方、安装参数、占用数，以及对象图子对象的宿主世界坐标和真实接触接口；`inspect(positions=[[x,y,z]])` 或CLI顶层 `positions` 可查询实际方块、墙层和实例归属，用于构造带旧值的宿主补丁。`update` 返回实际差异和受影响子对象。宿主切削后重新核对实际接口与声明连接，失效接口不会复用旧的通过回执。`preview(output, cameras)` 在全新目录写候选SNBT、审阅快照和机位；用既有 `render --source <候选SNBT>` 生成纹理图并实际查看。快照和图片不代表技术检查或用户批准。

## 宿主修改与预算

新增几何与宿主增删改保持不同含义。构件未写的位置保持原状；显式空气才表示删除。`patch` 的每项是 `{"pos":[x,y,z],"before":["minecraft:stone",true],"after":["minecraft:air",false]}`，绑定预期旧状态及墙层，任何不一致都拒绝整批操作。`apply_operations` 调用现有工具序列，通过同一完整宿主检查，不使用逐分片编辑。

`limits` 分别限制 `max_component_blocks`、`max_written_positions` 和 `max_changed_positions`。最后一项按本次工作副本初始主模型到最终候选的方块状态/墙层变化坐标并集计算，不能把多个各自未超预算的组合拼成超预算结果。保存制作版后，以新保存版本作为下一次编辑基线。上下文 `max_changed_blocks` 与工作模型上限取较小值。

保护按完整模型执行；`reserved_boxes` 拒绝新增占用，`require_routes:true` 使用 start、targets 及 route_legs 在完整候选上复查。未配置路线时不宣称已验通路。源文件、二进制源的墙层附属文件、外部上下文或已发布制作版的核心资料变化，会使工作副本失效。续版绑定规范化后的有效约束与保存预算，替换上下文或修改内存上下文均不能放宽保护、留白和路线；机位可另行调整。自由体素脚本在保存时也复核保留空间与 require_routes。对象图的保护、留白、路线和预算在受管安装后继续执行。

## 实例更新与手工编辑

安装记录配方、局部到全局变换、实际安装结果和被替换的原方块/墙层。与宿主完全同值的重复写入不会取得已有方块的所有权。不同受管实例不能争用同一归属；同格镶嵌须作为宿主配方的一部分或一次显式替换。

`update(id, recipe=..., transform=...)` 对照上次安装结果、当前宿主和拟生成结果。当前等于基线时可更新；当前已等于新结果时可合并。其余受管位置的分歧返回 `INSTANCE_EDIT_CONFLICT`，包含实例、世界坐标、基线、当前和拟生成值。墙层单独变化、手工挖空及新位置占用均参与比较。第一版对这些分歧整体拒绝，使用 `detach(id)` 可显式保留当前方块并解除管理，之后按自由几何编辑；不把局部手改伪装成可随对象移动的参数化覆盖层。

### 预检构件尺寸与安装位置

在受管实例改尺寸、抬高或重新安装前，可在 `model` 请求的 `actions` 中使用 `{"method":"preflight_update","identifier":"palace","transform":{"position":[40,28,40]}}`。如需改尺寸，可同时提供 `recipe`。查询返回实例和整栋的前后实际占据范围、构件拟放置范围、受影响的具名接口和实际通路。主路线、往返分段及对象图路线分别比较起点、目标、可达状态和静态路线哈希。没有声明时显示 `not_declared`。越界、保护或写入冲突导致无法构建候选时，仍会返回可以计算的范围与冲突坐标。

根据预检结果选定方案后，在同一源版本上提交相同的参数和位置，将 `method` 改为 `update` 并带上 `preflight_sha256`。工具重算候选和检查，变更宿主、配方或位置后会要求重新预检。采用该方式更新时，受管实例保存选择绑定。如果输出的预览仍对应这份候选，预览目录会附上绑定制作源和快照哈希的 `assembly-preflight.json`。视觉确认与定稿沿用各自入口。

缩小、移动或 `remove` 时，只有该实例实际取得归属且未被冲突修改的位置才恢复原底材。底材逐格记录，不能统一补成某种石材。无安装记录的旧作品以自由体素打开，不猜测归属和历史底材。

## 检查、保存与恢复

建筑按实际阶段检查。`design` 可以保存进行中的制作稿，报告明确整体验证尚未执行；`seal()` 在真实未开洞模型上检查全部 interior_probes，并保留开洞前主模型；`open_declared()` 按上下文策略处理独立 `openings`。要求密闭时必须先取得有效封闭记录；未要求密闭时可直接按声明开洞。无声明洞口时不写几何，进入沿用名称的 `opened` 验证阶段。`opened` 保存前执行完整建筑验证。独立 `component` 不强制通过整栋建筑的密闭/开门流程，每轴≤64，按实际尺寸、状态及方块预算检查。设计阶段、静态通过、看图完成和用户批准分别记录。

`save_draft` 只发布 SNBT 制作版。先在工作区 `.nbtcreator/model-staging/` 写齐并回读，再在建筑锁内核对父版本并发布完整目录：

- `master/model.snbt`：实际方块与显式墙层；有真实开洞前证据时另存 `master/preopening.snbt`。
- `model-instances.json`：配方、实例安装基线与底材，以及可选建筑方案绑定。
- `coordinates.json`：有效上下文。
- `validation/working-model.json`：本次实际检查及未验范围。
- `changes.json`：相对父制作版的方块状态与墙层实际变化。
- `model-version.json`：绑定上述核心文件、引擎和父版本的不可变清单。
- `room_description.json`：建筑库登记信息，预览与定稿输出继续是派生资料。

版本放在原建筑的新 `v_model_<清单摘要>/` 目录。配方不同但方块相同也形成不同版本。保存不移动、覆盖原稿，不生成 NBT、批准或游戏部署。当前工作版在 `.nbtcreator/model-heads/` 以相对路径绑定；桌面/CLI从同一父版保存时，只允许仍基于当前父版的一方推进。

同一候选重复保存核对并复用已有成果；发布后历史登记失败返回 `history_pending:true`，重试同一保存可幂等补录。版本已完整发布、但更新工作版指针中断时，只在父版仍未改变的条件下修复，不倒退较新的工作版。旧历史格式继续兼容。历史切换、派生、桌面转换和 CLI 共用建筑锁与工作版指针；旧请求重放只复用已发布结果。补录按已验证清单先登记祖先再登记子版，历史索引中由旧故障留下的空父关系可据清单补全，并通过新的历史提交记录。

历史索引只保留文件哈希与大小，文本预览从已校验的归档对象读取；旧索引在下一次写入时校验对象后迁移，失败不会替换原历史。版本详情的文本预览合计限 16 MiB，标记 `text_omitted: "preview_limit"` 的文件可通过历史 `get` 请求附带 `id`、文件 `name`，以及需要时的 `context: true` 单独读取；单个文本预览不超过 2 MiB。历史列表中的 `index_capacity` 报告索引占用和磁盘剩余空间，接近上限时界面显示预警。登记失败时制作版仍保留，可在解决空间或归档问题后重试。

CLI已有源请求须给 `source_sha256`，相对路径以创作项目为基准。请求中的 `save_draft:{}` 表示显式保存已有建筑下一制作版；新建时提供 `save_draft:{"name_zh":"中文名","shape":"standalone"}`。定稿继续使用单独的 `finalize`，精修继续遵守对应图像后的真实用户确认。

验证：在软件项目根目录运行 `mise run model:test`；测试使用独立临时创作工作区，包含真实 CLI、冻结Skill入口、跨48安装、底材恢复、手改冲突、整模预算及版本恢复。`mise exec -- npm run test:model-preview` 先构建前端，再对合成柱梁顶组合生成同机位前后纹理图，输出在 build/model-render-*，不会发布用户资产或定稿NBT。
