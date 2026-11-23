# 建筑方案到主模型、审阅与回查

适用完整建筑或需要稳定构件身份的重设计。先按[整体流程](whole-model-workflow.md)完成用途、玩家站位、通路、空间与顶构的设计，再把能执行和检查的内容写入建筑方案。文本风格仍由 Agent 和用户判断；尺寸、材质、承托及路线交给实际几何检查。

需在编译前比较分层、面积和通路时，先按[整栋建筑量化规划](whole-building-planning.md)生成或检查布局。准备好的方案含可选的 `planning` 绑定，编译和制作源回读都复验对应条件。

## 入口与设计责任

在创作项目根目录使用冻结入口。小型建筑可以从[可直接运行的入口亭示例](../assets/examples/entry-pavilion.json)开始，按需查询：

```powershell
mise run nbt -- capabilities --recipe structure
mise run nbt -- capabilities --architect-action plan-save --field plan.parts.interfaces
mise run nbt -- architect plan-save --request plan-save.json
mise run nbt -- architect plan-build --request build.json
```

从源码根目录使用 `mise run nbt -- --workspace <创作项目根目录> architect <action> --request <JSON>`。全部参数以 `tool-catalog.json` 的 `architecture` 为准，不把 schema 复制进脚本或提示词。无需启动 Electron。

`plan-build`、`plan-check`、`part-preflight` 和 `review-prepare` 支持 `--compact-report <nbt_models 内全新JSON路径>`，父目录须已存在。完整回执写入指定文件，终端给出 `report.path`、`report.sha256` 及重点问题。默认输出仍为完整 JSON。相对 `--request` 文件路径从命令工作目录读取；请求内的 `source`、`output`、`pack` 和 `render_manifest` 相对于创作工作区。使用源码全局 `--workspace` 或从创作根目录走生成入口时，这两处基准指向同一目录。

| 回执中的证据 | 如何接续 |
| --- | --- |
| 退出 1，`ok:false` | 核对 `error` 和 `code`。有 `report.path` 时把完整失败回执交给 `diagnostics --kind model`。请求缺失、JSON 行列或输出路径错误按提示检查对应输入；报告路径无法写入时终端直接返回错误。 |
| `STALE_SOURCE` 或 `STALE_PARENT` | 读 `conflicts` 和可用的 `recovery`。重开当前版本，核对任务、保护和原审阅绑定，再用当前回执重建请求。 |
| `saved` 与 `next.request` | 保存成功后将 `next.request` 原样传给 `review-prepare`。成功的 `plan-check` 也给出同一接法。续版用保存回执的 `revision_request` 合并改好的 `plan` 和 `save_draft`。 |
| `render_command` 与 `review_record_bindings` | 按命令出图，再核对清单和源、相机、图像绑定。实际打开图片后，将绑定字段和观察提交给 `review-record`。可用 `diagnostics --kind review` 解释审阅包、覆盖回执或观察记录。 |
| `status: observations_recorded` | 查 `observations_complete`、`coverage_complete` 和 `missing_locations`。覆盖不足时补拍或补看，随后向用户展示实际图像。精修仍须该批图像的用户明确确认。 |

退出码 0 表示本步执行成功。预检的问题在 `parts[].interface_issues`；审阅准备的 `coverage_passed` 仅报告机位覆盖，`visual_status` 给出看图阶段。两者在完整回执的 `coverage` 下，在简报中位于顶层。入口亭的字段来源和最短接续见[入口亭示例](simple-building.md#入口亭的请求与回执)。

Agent 把自然语言设计转为以下数据，而不是直接猜一串工具调用：

| 设计内容 | 方案中的表达 | 实际落实 |
| --- | --- | --- |
| 用途、层级与可用空间 | `spaces`、`levels`、站位样本与净高，以及 context 的 start/targets | 在最终方块上验站立、支撑、采样净空和起点到各样本的通路；空间包围盒是声明范围，不冒充完整净面积测量 |
| 清晰风格 | `style.materials`、`parameters`、`principles` | 用材质角色和共享尺寸生成构件；`palette` 检查实际材质，`argument`/`ratio` 检查配方，`extent`/`proportion` 检查实际包围尺寸与比例 |
| 整体围护和顶构 | `envelope.volumes` | 对设计空气体积求并集，再生成一次全局边界；闭合屋面台阶与相交体积，不按存储分片重复补墙 |
| 稳定的构件和对象 | `parts` 的 ID、配方、位置和接口 | 调用现有纯配方编译器，保留对象图和世界坐标，安装进同一个 WorkingModel |
| 跨层通行与承托 | `stairs`、`connections` | 生成踏步、可选支承/护栏、跨高梁或托座；逐段走路和实际接口接触复检 |
| 能看见的设计目标 | `views` 的层级、脚位/眼位和目标构件 | 生成真实相机；检查站位、取景范围和采样遮挡，再使用原渲染器出图 |

`standards_snapshot` 可绑定项目规范的完整修订；它保留设计依据，不把自然语言自动转换成“已通过”。需要硬约束的条目应由 Agent 明确译为 style 参数、设计规则和上下文约束。

需测屋顶底部时，在 `part-preflight` 中指定屋顶的 `part` 和 `underside_xz`，例如 `[[10, 12], [14, 12]]`。查询和结果都使用世界坐标。 `bottom_y` 是该列最低实体方块的 Y。空列返回 `null`。几何支承仍需验证。 `auto_roof` 的 `ridge_axis` 只控制 `gable` 和 `gambrel`。

## 需求落实与活动动线

**纯文字初稿**先选一个会改变布局的动作。例如“窗边收卷，再登梯归架”决定了台面的使用侧、上楼时的转向、柜面朝向与梯顶留空。把这些决定做成能接触、能看清的构件，例如用两端柜脚托住薄台面，在书架顶端压一道木条。检查动作能否连贯完成，再从玩家眼位判断哪些细节可读。

**有参考图的初稿**先保留原图方位，定位入口、主要体量和开间。选看得清的交接点，例如窗台伸出墙面多少、玻璃在哪一层、横枋如何搭在门柱上。把这些相对关系转成进深、材质角色和具体方块状态；看不见的厚度、背面和室内另记推导理由。初稿用接近原图的视角比轮廓，再用玩家近景比厚度、接缝和收边。

两条路线都把需要回看的细部写入 `review_locations`，在相邻站位或通路上安排 `activities`。完整的请求、成功初稿、堵梯口变体与看图位置见[可运行的归卷阁样例](../assets/examples/reading-loft/README.md)。

建模前在已有设计笔记中逐项写清需求来源、使用者、动作、物件或操作面、空间及其连接。需求来源标明用户要求或 Agent 的设计推导，推导附理由。用户要求的重点和本次实际采用的设计承诺都进入回查范围，保留未落实项的具体原因。无需先写长篇故事，也不按物件覆盖百分比评定完成。

例如守塔人从码头搬运燃料、入库、登塔并维护灯具，可以推导出卸货站位、储藏空间、连续梯段与顶部维护面。检查入口能否抵达这些位置，以及门宽、转弯、操作面是否适合本次活动。卧室、餐厨或服务门只在用途需要时增加。公共来访、日常居住、搬运与维护可共享路线，也可按公私、噪声、危险或清洁要求分开。

可执行方案提供以下可选字段，旧方案继续可读。字段契约通过 `capabilities --architecture` 查询。

| 字段 | 记录与复检 |
| --- | --- |
| `requirements` | 需求文字、来源与理由，关联 `spaces`、`parts` 和 `review_locations` 的稳定 ID。检查引用及实际构件存在，文字含义仍由 Agent 对照模型与图片复核。 |
| `activities` | 使用者、活动目的，以及按顺序排列的空间与实际脚位。逐段检查真实玩家碰撞通路，核对每个停靠点位于相应空间。搬运尺寸、服务关系及隐私要求另作设计判断。 |
| `review_locations` | 本次需要看清的门口、梯口、路口、操作面、顶构或檐角，记录全局观察目标与可覆盖它的机位。审阅包检查取景与采样遮挡，观察记录关联实际图片和位置 ID。 |

自由脚本沿用同一对应关系，在已有 `design_review.json` 中保存即可。可执行方案中的活动停靠点补充空间采样，按实际设计选取必要中间节点。局部修补之后重验受影响的完整活动顺序，包括门后、平台与梯段出口。

### 操作面与使用侧

为需要伸手取放的停靠点选择具体构件和竖向工作面。归卷阁的收卷台在配方局部坐标中把台沿命名为 `intake`，归档柜把书格正面命名为 `shelves`。接待人站在台沿外侧，柜员站在书格正前方；旅客绕到柜台背面时仍可能走通。

```json
{"space":"hall","feet":[13.5,2,8.5],"use_face":{"part":"return_desk","interface":"intake","height":1.25,"max_distance":1}}
```

在 `activities[].stops[]` 中按需填写 `use_face`。选已有普通构件的命名接口，复合场景可用 `object` 选择子对象。接口随构件平移、镜像和旋转。引擎从脚位向上取 `height` 格，在该高度正对接口，检查实际半格面、站在哪一侧、到面距离是否在 `max_distance` 内，以及中间半格通道是否有碰撞障碍。通路仍逐段实测。查看 `activity_routes.segments` 和 `use_faces` 可区分断路、站错侧、过远、错开工作面和中间被挡；未声明接口的旧方案沿用原有通路检查。

取放的舒适度、动画、游戏交互及大件搬运各有自己的尺度。将柜子的开口、工作空间和脚位放进同一张近景，再结合用途判断。需要验证访客可避开后厨或值房时，在 `context.route_legs` 中用 `validation_only_barriers` 遮住该区域，在验证副本复走指定起点与终点，保留真实模型的门和地面。

### 建筑群与多层选图

建筑群先用全景比较地形、主体与附属建筑的高度、朝向和留白。再从玩家脚位沿主街转入支路，观察铺装怎样接续；到门前看石槛两侧的高差和门柱是否挤占净宽，最后在室内核对操作侧。把接点写进 `activities`，把需要看清的位置写进 `review_locations`。开放街道属于可行走的室外空间，密闭探针只放在实际需要围护的室内。

多层布局从同一制作源补逐层俯视，看门、柜与走廊的相对位置；沿真实梯段切纵剖，看末级、平台和头顶余量。单独渲染这些诊断图并保存清单，完整屋顶、入口和玩家近景继续用于三层审阅。[归卷阁与归卷院的可运行示例](../assets/examples/reading-loft/README.md)给出了剖切文件、街口机位和单独的到案通路。

## 审阅位置的选择与覆盖

从本次建筑实际存在的关系选位置。入口查看门内外及主要去向，跨层路线查看梯段上下出口和平台，有道路分支时查看接头，功能节点查看操作面和使用站位，室内顶构保留完整屋面并查看支点。飞檐同时查看侧面曲线、角部平面轮廓和檐下连接。一个机位可覆盖多个位置，位置数量随设计变化。

最重要的活动选一个接近玩家来路的机位，同框核对主件、配套、操作侧与下一站。用 `activities` 定脚位和去向，用 `review_locations` 记录实际需要看清的位置；接缝和支点用近景补查。观察写明从画面能认出的用途和方向，以及仍需补拍的位置。摆位示例见[沿实际使用路线审细部](spatial-detail-design.md#沿实际使用路线审细部)。

参考图驱动的方案把轮廓、体量比例、屋面、立面节奏与材料部位写成具体目标，再用方向接近的模型视图对照。尺寸及构件比例可使用已有规则。参考未展示的背面与室内记录设计补全的依据。

审阅位置的 `position` 选在可见表面或门洞、梯口等可观察空气点上。观察记录中的 `locations` 只填写该图实际看清的位置 ID。`coverage_complete` 同时核对三层审阅和已声明位置的观察覆盖。采样可见度、图片存在和观察文字各自保留结果，最终由 Agent 实际看图判断构造、用途与风格。位置被遮挡或在画外时调整机位并新出图。细件因 `uncertain_collision` 无法自动确认时，实际看清后在对应图片的 `manual_locations` 填写位置 ID，并在 `note` 记录看到的细节。`observations_complete` 说明所有机位和声明位置均已记录实际观察，`coverage_complete` 仍核对自动取景与所需审阅层次。

## 共享参数与构造边界

共享引用只接受 `{"design_ref":"style.parameters.beam_width"}`，可选数值 `add`。引用根限于 `style`、`levels`、`spaces.<空间ID>`，无表达式求值、Python 模块路径或脚本执行。引用循环、未知字段、不适用的规则参数、无效目标、越界和倒置范围均拒绝。解析后再次验证类型和数值。

围护支持矩形或简单多边形平面，以及平顶、双坡、四坡和穹面剖面。它生成一格厚的封闭边界，不自动设计瓦檐、排水、复杂相贯曲线或现实结构荷载。玻璃补丁必须命中实际围护。命名接口选取当前真实表面。

完整梯段复用 `auto_stairs`。可声明支承基底、间距与材质；基底必须有实际支撑。自动护栏当前支持直梯，包含整块侧缘与栅栏/石墙/铁栏杆；半格高差不伪造斜向邻接。转弯梯需要显式设计平台和护栏构件。每次检查都重验各相邻脚位，避免一条捷径替代整个梯段。

`beam_link` 在两个真实向上承托面之间生成有厚度的阶梯形跨高梁；`bearing_block` 在朝上与朝下接口的共同截面内生成托座。接口需满足整格高度、对齐、居中、净跨及最大间隙条件；不舍入半格接口，不把保守碰撞包络当成接触证明。当前没有受力求解。

## 编译、修改与制作版

`plan-save` 使用父 `revision` 保存不可变方案修订，`plan-get` 可取指定版本。它们位于 `nbt_models/_workspaces/project_design/plans/`。`plan-build` 使用内联 `plan` 或 `plan_id`，两者选一；包含 `save_draft:{}` 时才发布 SNBT 制作版。

### 先比较粗布局

用 `architect layout-search --request layout.json` 在精做梁架、窗列和饰件前比较同一外壳内的摆法。请求填 `plan` 或已保存的 `plan_id`，其余字段可用 `capabilities --architect-action layout-search` 查询。粗方案至少需要能支撑行走的围护、楼板、梯段、关键工位及活动站位。

`variables` 中每个变量有 `id`、一起移动的 `targets` 和备选 `offsets`，每项位移写成 `[dx, dz]`。例如归卷阁可将 `{"kind":"part","id":"archive_cabinet"}` 配上 `[[0,0],[0,5],[1,5]]`，再为 `{"kind":"stop","id":"file_books","index":0}` 提供独立站位偏移。组合上限为 24。候选按总位移从小到大排序。

| 目标 kind | 位移作用 |
| --- | --- |
| `part` | 构件的放置位置 |
| `stair` | 梯段起点、终点和操作包围盒 |
| `space` | 空间边界、空间采样点及其活动站位 |
| `space-extent` | 空间 X/Z 上界，可改变平面面积 |
| `stop` | 指定活动内的站位，`index` 从 0 开始 |
| `route-target` | `context.targets` 中的命名终点 |
| `review-location` | 对应的审阅位置 |

若移动楼梯会改变活动站位、必要路线目标或审阅位置，可在同一个变量中登记这些目标。用 `areas` 指定空间的最小和最大平面格数，用 `adjacency` 指定两空间 XZ 包围盒之间允许的空格数。楼层之间实际能否连通由原有梯段及活动检查验证。

回执的 `attempts` 列出各方案的空间条件和技术失败证据，`candidates` 给出最多三份可继续编辑的 `plan`；空数组表示这一批组合均未通过。选定后用实际方案调整视角、完善构造，再交给 `architect plan-build` 保存并出图。

生成顺序是围护、普通构件、梯段、连接件、按项目要求验密闭、处理已声明洞口、全模型与设计检查、可选保存。候选在临时工作模型中组合，提交仍由原 WorkingModel 执行总预算、保护、留白、原对象图政策和路线检查。任何失败都不发布新制作版。生成几何超过构件存储尺度时，只机械分组，不重新设计接缝。

已有源必须同时提供 `source`、`source_sha256`、`expected_plan_sha256`。续版不能暗改画布、保护、开口或路线。构件保留 ID；受管位置若被手改则报冲突，由 Agent 先判断保留或调整方案。无关自由几何保留，旧源不覆盖。重建也保留原对象图声明的保护、留白和路线。

`architect plan-check` 或普通工作模型的检查/保存会重新执行空间样本、当前构件、梯段、附属构造、承托和风格规则。制作版的 `model-instances.json` 记录方案绑定，核心清单继续校验文件哈希。`inspect` 返回 `architecture_sha256`。没有规则时明确报告风格未作机器验证。

## 三层真实看图与问题回写

需要五维分数、证据覆盖率及续版复验时，在编译前登记[整栋建筑质量清单](building-quality.md)，在完成真实出图后将量表观察随 `review-record` 提交。

1. `review-prepare` 绑定制作源和方案，按 `massing`、`structure`、`detail` 生成审阅包和 cameras.json。脚位须能站立；眼位不能埋在实体内。可见度是有限采样，未知细件和透光/光照限制单独报告。
2. 执行回执中的 `render_command`，生成保留顶构的实际纹理图片。相机通过只说明可取景，不说明建筑美观。
3. Agent 实际查看整体、构造和细节图片后，用 `review-record` 提交 `observations` 与 `issues`。每条问题绑定已看图像、层级及可选构件 ID/世界坐标。接口校验制作源、相机、快照、PNG、图片元数据与哈希；观察修订另存不可变历史。文字声明本身不能证明“已看图”。
4. 修改后保存新制作版，`review-compare` 使用原审阅包、原问题记录的 `notes_sha256` 和新源，按稳定构件 ID 返回当前范围。旧坐标只作对照，不自动成为新版标注；问题保持待新图核对。
5. 新版重新准备同一组相机并出图，再记录实际观察。`review-compare` 不自动关闭问题，也不创建精修批准。用户看到对应缩略图并明确同意后，才进入[精修](refinement.md)。

审阅包与图片放在 `nbt_models/_workspaces/` 的新目录，不能写入已发布版本的核心目录。图像缺失、元数据不一致、记录被更改或父修订过时会拒绝回写。

机位失败或需要补拍时，可用同一 `source` 和 `source_sha256` 再执行 `review-prepare`，指定新的 `output`。在 `view_overrides` 中放入要替换的完整机位，沿用原机位的 `id` 和 `layer`，按需调整 `feet` 或 `eye`、`target` 与 `sample_box`。字段用 `capabilities --architect-action plan-save --field plan.views` 查询。新包沿用原方案的位置绑定，重新检查取景和位置可见性。按新包的 `render_command` 出图并实际看图，再用新包的回执登记观察。原制作版和原审阅记录仍可回查。

`review-prepare` 的 `coverage.delivery_summary` 列出落盘模型上已查的目标与操作面，观察数从零开始。实际看图并调用 `review-record` 后，取其 `delivery_summary` 回报用户。每条摘要区分可达目标、专项路线、已记观察的机位与位置、取景失败和待回查问题。补充一条从图片读到的具体结论，并附当前源、图片与记录路径。未登记活动、未看位置和未实测的游戏项目按其实际范围说明。

## 目标游戏验收

`game-checklist` 给出放置、邻接更新、旋转、行走、光照五项，初始均为 `not_checked`。`game-record` 记录目标运行版本、报告状态、说明和实际证据文件哈希；没有证据不能报告通过或失败。记录是外部观察台账，不证明引擎见证了游戏执行，也不授权导出。

本流程默认交付 SNBT 制作源。真实游戏测试仍需隔离的 Minecraft Java 1.20.1 环境及明确授权的测试 NBT；最终导出使用独立的显式定稿入口。静态路线、纹理图和游戏内表现分别报告。

维护回归从软件根目录运行 `mise run architecture:test`；真实出图、公共 CLI 与冻结入口回归运行 `mise run architecture:preview`。测试输出放在隔离的 `build/architecture-*` 项目，不写入用户作品。
## 构件查询与预检

下例从创作项目根目录运行。已有冻结入口的项目可在同步后运行。

```powershell
$nbt = '.agents/skills/nbtcreator-workspace/nbt.py'
python $nbt capabilities --recipe structure
python $nbt capabilities --operation box
python $nbt capabilities --architect-action part-preflight
python $nbt capabilities --architect-action part-preflight --field plan.parts.interfaces
python $nbt capabilities --block-state 'spruce_button[face=floor,facing=north,powered=false]'
python $nbt architect part-preflight --request preflight.json
```

将 `--recipe structure` 返回的 `example` 放进 `parts[].recipe` 可编译一格石座。建筑配方直接接收 `arguments`。调用 `--agent-tool structure_preview` 查询独立候选工具时，同一份结构规格放在 `spec`；`structure_write` 使用候选回执保存资产。

`--field plan.parts.interfaces` 在 `plan-save`、`plan-build` 和 `part-preflight` 下返回相同的局部契约和例子。北侧台沿用 `{"id":"serving_edge","face":"north","lo":[0,0,0],"hi":[2,0,0]}` 指定构件局部范围。若 `tea_table` 放在 `[8,2,9]`，活动脚位可以从 `[9.5,2,7.5]` 用 `"use_face":{"part":"tea_table","interface":"serving_edge","height":0.5,"max_distance":2}` 引用台沿。实际站立和操作净空由整栋验证。

把下面的请求保存为 `platform.json`，执行 `python $nbt architect plan-build --request platform.json`。这个小型开放平台只编译和检查，不保存制作版。要生成制作源供审阅，在请求顶层加入 `"save_draft":{}`。

```json
{
  "plan": {
    "schema_version": 1, "name": "开放平台", "size": [8,5,8],
    "context": {"mode":"standalone","openings_policy":"none","require_enclosure":false,"openings":[],
      "start":[2.5,1,2.5],"targets":{"far_edge":[5.5,1,5.5]}},
    "style": {"name":"石平台","materials":{"floor":"stone_bricks"}},
    "spaces": [{"id":"deck","purpose":"通过与停留","lo":[1,1,1],"hi":[6,4,6],"feet_y":1,"samples":[[5.5,1,5.5]]}],
    "parts": [{"id":"platform","role":"floor","position":[1,0,1],"recipe":{"tool":"structure","arguments":{
      "name":"平台地面","size":[6,1,6],"operations":[
        {"kind":"box","label":"平台地面","classification":"body","lo":[0,0,0],"hi":[5,0,5],"state":"stone_bricks"}
      ]}}}],
    "views": [
      {"id":"overview","layer":"massing","eye":[10,9,-7],"target":[4,0.5,4]},
      {"id":"edge","layer":"structure","eye":[-3,3,4],"target_part":"platform"},
      {"id":"surface","layer":"detail","feet":[4.5,1,4.5],"target_part":"platform"}
    ]
  }
}
```

`preflight.json` 最小例为 `{"plan_id":"my_building","part":"tea_table"}`。也可用内联 `plan`，或省略 `part` 遍历构件。预检编译单件并应用放置变换，列出状态、世界坐标样本和接口错误。接口错误的 `scene` 坐标属于变换前场景，`bounds` 属于接口定义的局部坐标。跨件支承、实际重叠、全局路线与预算由 `plan-build` 验证。正常的 `INSTALL_OCCUPIED` 回执给出位置、现有归属与双方状态。

省略 `parts[].interfaces` 时沿用原自动接口规则。普通结构使用 `"interfaces":[]` 可明示禁止自动生成接口，适合无碰撞的纯花饰。引用该构件时仍须存在真实接口。地毯等具有已核实保守包络的细件只有与接口区域及其外侧相邻格无交集时才可从精确检查中排除。保守包络只用于静态避障；精确支撑仍须核对对应位置及当前几何。合法但形状未知的按钮仍会阻止通路认证，即使各目标报告 `reachable=true`，可从 `unknown_shapes[].positions` 定位。

整栋保存和回读会复验具名接口的方块与外露面。被接触关系或操作面引用的接口还检查邻近构件的保守包络是否可能盖住接口。声明整件接触时，双方仍需提供完整的精确接触几何。

## 近景和回执接力

在 `views[]` 的近景中，`target_part` 指定取样对象，并在省略 `target` 时以实际构件范围中心为朝向。仅提供 `target` 时，坐标控制朝向，取样仍覆盖整栋。存在多个可能构件时填写稳定 ID，例如 `{"id":"tea","layer":"detail","feet":[8.5,2,7.5],"target_part":"tea_table","fov":60}`。具体脚位按实际模型选择。

大型梁架只需看一处榫接时，可在构造或细节视角同时填写 `"target_part":"timber_frame"` 和 `"sample_box":{"lo":[13,2,5],"hi":[14,5,5]}`。盒坐标使用整栋模型的整数 XYZ，包含两端。取样只包括盒内属于该构件的实际方块，范围越界、倒置、缺少目标构件或交集为空会被拒绝。相机朝向、最低可见比例和审阅位置仍由原字段控制，盒外方块仍参与遮挡判断。用 `capabilities --architect-action plan-save --field plan.views.sample_box` 查看契约及完整机位例子。

回执 `coverage.views[]` 给出取样范围、眼位、视锥覆盖与遮挡格。`coverage.review_locations[].candidates[].visibility` 给出目标方块、是否在已知实体内部及沿路遮挡。优先从可站脚位调整机位，将审阅位置放到实际可见表面前。静态通过后仍须查看真实出图并记录观察。

```powershell
$inspection = python $nbt control inspect --source $source | ConvertFrom-Json
$inspection.result.editing_ready
$inspection.result.context_readiness
$record = python $nbt architect review-record --request record.json | ConvertFrom-Json
$compare = $record.review_compare
$compare | Add-Member -NotePropertyName source -NotePropertyValue $newSource
$compare | Add-Member -NotePropertyName source_sha256 -NotePropertyValue $newSourceHash
$compare | ConvertTo-Json | Set-Content -Encoding utf8 compare.json
python $nbt architect review-compare --request compare.json
```

`review-record.path` 是 `review-notes.json` 的路径。比较时检查原 `pack` 同目录下的该文件，`review-record.sha256` 对应请求的 `notes_sha256`。使用回执的 `review_compare` 可同时沿用原审阅包和哈希。
