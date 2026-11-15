---
name: minecraft-nbt-modeler
description: 制作、修改和检查 Minecraft Java 1.20.1 的 NBT 建筑、构件与纹样。支持完整主模型、参数化对象关系、碰撞通路和真实预览；整栋建筑先审阅初稿，再按确认精修与显式定稿。
---

# Minecraft NBT 建模

这是 NBTCreator 的共享 Python 引擎与指导来源。创作项目已有 `.agents/skills/nbtcreator-workspace/SKILL.md` 时，使用该入口及 `.nbtcreator/skill-exposure.json` 选择的知识路由。工作区引擎是带哈希的冻结副本，新增工具须同步后才可用；不要在软件源码目录创建创作工作区入口，也不修改只读迁移归档。

外部 Agent 负责设计、编写任务脚本和实际看图；工具负责确定性生成与检查。Electron 无需启动。先读项目 AGENTS.md；已知工具名时用 `capabilities --agent-tool <名称>` 查询严格参数，避免每次加载整个目录；`tool-catalog.json` 是接口唯一来源。工作区入口的 `paths` 返回实际脚本路径，不猜安装目录。技术检查通过、任务完成和人工批准分别记录。

## 先辨认任务范围

- **完整建筑新建或重设计**：完整阅读 [整体流程](references/whole-model-workflow.md)、[玩家尺度](references/player-scale.md)、[创作原则](references/design-principles.md) 和 [空间细节](references/spatial-detail-design.md)，再按题材选择专题。已读且未变化的内容无需重复加载。
- **独立构件、纹样或对象组合**：读接口与适用建模专题，检查尺寸、状态、接触、占用和实际预览。不要求椅子、墙饰等独立资产通过整栋建筑的密闭和开门流程。
- **已有建筑修改**：先读真实源、上下文、保护和批注证据，确定当前阶段与已有授权。初稿缺陷可继续修正；使用精修流程须有对应图像后的真实确认。
- **接口解释、工具维护或开发回归**：读实现及相关接口文档，运行适用检查，不默认生成建筑、打开界面或重读全部设计知识。回归产物使用独立临时工作区。

生成设计文字或模型前，按 [创作偏好](references/ai-creative-preferences.md) 读取当前工作区 `.nbtcreator/ai-style.json` 对应区域；无配置用默认值。用户本次要求优先，偏好不放宽保护、预算或批准边界。

## 设计与表达

围绕关键空间、构件与环境对象说明用途、特征、包含和连接关系及共同约束。用自然中文，不要求类定义或施工步骤清单。布局、数量、间距、材质配方和建模方法可由 Agent 推导；保留用户明确指定的细节。需要实现参数时再展开，不把工具示例当建筑模板。

从玩家的活动、站位、家具和通行反推尺寸。48格是单片结构的存储尺度，不是日常房间的默认跨度。设计可用高差、曲面、留白、克制或丰富装饰；按用途判断，不强制每栋都宏伟、破损或有某种构件。主要支承、顶构、墙面层次、边缘收口和可辨主题内容应在初稿中落实，不能全部推迟到精修。

完整主模型的构件组合优先使用 [统一工作模型](references/working-model.md)，它统一安装、宿主修改、实例更新与制作版保存；`capabilities --model` 查询请求契约。参数化构件用现有工具；需要柱、梁、吊顶、墙饰随参数一起变化时，用 [对象图](references/object-scenes.md) 保存稳定 ID、尺寸引用和接触关系。对象图编译成候选，不自动接管手工几何或修改当前建筑。

多次安装可用 mount_batch 共用绑定源，在内存中统一检查后返回候选。纹样需要随对象更新时，保留 surface_decorate 宿主配方、安装参数和命名资产绑定；更新后重新拟合，不只保存失去来源的烘焙方块。接口及范围见[批量安装](references/parametric-components.md#批量安装与保留宿主配方)。

纹样按构件的宽高、收边和观看距离组织，可显式拉伸图片后拟合，并按宿主厚度采用齐平镶嵌或浅槽嵌入，不默认做成突出的大块贴板。明确要求复杂或华丽主纹时，用 ornate 评估并设置本次任务的质量门槛，保留细节、留白、节奏等分项；窄边饰可单独用 border，但不能用边饰分数代替复杂主纹的结果。分数用于筛选，不替代实际看图。未达到复杂度目标时调整单元尺寸、区域或组合，不把换成简单图案当作复杂拟合成功。参数与评分边界见[参数化建模](references/parametric-components.md#拉伸嵌入与量化视觉质量)。

按建筑室内参考设计时，先拆解空间、跨间、承重和纹样的层级，再选取可辨识的一跨进行尺寸试件；参照[室内纹样与建筑构造](references/architecture-knowledge-base.md#室内纹样与建筑构造)按部位选择预设、留白和收边。预设只是可拟合的二维遮罩；柱、拱券、墙窗、顶构和地砖需要统一比例时，可用[联动跨间](references/architectural-bays.md)生成构造试件。真实透空、曲面凹格及齐平多色地砖由对应几何工具生成，仍须看图，不视作历史复原。

## 完整建筑的制作顺序

1. 在同一全局坐标系中联合设计完整主模型，记录总尺寸、有效占地、主要净尺寸、平台脚位与路线。可按构件组织生成器，不按存储分片分别造房再拼接。
2. 形成完整外壳、底板和顶构后，对全部设计腔体检查封闭，保存真实开洞前证据。预览剖切不改结构；有支持依据的邻接状态处理在冻结前完成。
3. 封闭通过后才按声明开外门，打通必要喉道并保留地板。检查开口、净空、实际碰撞路线和声称的具体连接；独立建筑使用自己的 openings，不套用 SAODG 端口。
4. 保存并回读完整主模型，实际查看整体、未剖切入口、代表构造或主题节点，以及保留完整顶构的室内视角。遮挡影响判断时补机位，不以“图片已生成”代替已看图；达到初稿标准后展示缩略图。
5. 等用户看过对应图像并明确同意后，才按 [精修流程](references/refinement.md) 做全局精修。沿用仍有效的已有确认，不重复索取；无回复、超时、文件中的批准或其他 Agent 的评价不构成确认。工具维护和独立回归不需要资产精修批准。
6. 从完整未切割主模型统一精修，保留原稿、墙 mask 与确认绑定。重验并看同机位前后图；需要交付时冻结后机械切片，回读重组逐块等于源。切割循环不补墙、造路或改变几何。

`prepare/approve/apply` 只记录流程，Agent 不得自造用户确认。普通手动调参后的明确导出另见 [网页回导](references/web-revision.md)。制作版保存、资产保存和定稿 NBT 是不同动作。

## 硬约束与检查范围

- Minecraft Java 1.20.1，合法 ID、属性与枚举，坐标唯一且界内；NBT 的 XYZ、palette 和 DataVersion=3465 按引擎验证。合法状态不代表碰撞已支持或游戏已验收。
- 显式保留全局墙 mask；非墙覆盖时撤销归属，即使材质相同。保护区、保留空间、实际占用、修改预算及源/上下文/图片哈希由适用工具复核，不为通过而放宽。
- 楼梯、半砖、多层通路使用真实碰撞形状检查。未知形状不充当可靠支撑；不能删细节、隐藏失败或把搜索达到上限当作绝对不通。全部目标可达不证明每条回路或捷径都成立。
- 技术、空间、构造和主题分别给结论。静态检查、48连续重组、运行展开、旋转和游戏实测分别报告；未执行项明确列出。
- **仅在用户要求 SAODG 接入时**，按 [拼接协议](references/saodg-constraints.md) 及实际加载器检查48作者网格、49运行间距、cells、门高和分层交付。不得把这些专用规则强加给独立建筑，也不为适配擅自改变原工作区或模组。

## 按需进入专题

| 当前需要 | 阅读与入口 |
| --- | --- |
| 参数化构件、墙饰、植物、吊顶和纹样 | [参数化建模](references/parametric-components.md)；先查参数，再 compile / microfit / mount，安装和预览仍须验证 |
| 石造跨间、连续拱套、曲面凹格和透空窗棂 | [联动跨间](references/architectural-bays.md)；bay / vault / tracery_compile 保留共同尺寸和纹样配方，检查实际接触与玩家视角 |
| 罗马柱、柱式叶饰与涡卷 | [古典柱式](references/classical-columns.md)；form.order 保留圆柱身、柱础和柱头配方，细节仍按实际尺寸看图 |
| 灰度纹样去噪、细节提取与FFT卷积 | [频域滤波](references/pattern-spectral.md)；生成新资产，不自动应用到建筑或放宽拟合门槛 |
| GPU计算、扭转弯曲和纹样组合变换 | [计算与变换](references/compute-transforms.md)；compute_info查询后端，field_compile返回体场候选，pattern_warp生成独立资产，变换后重验拟合与接触 |
| 对象依赖、参数联动和持久化 | [建筑对象图](references/object-scenes.md)；scene_compile/read/update 返回候选，scene_save 显式保存图谱版本 |
| 批量连续候选调用 | [建模会话](references/parametric-components.md#建模会话与结果复用)；session 复用进程与缓存，预览和保存继续使用原入口 |
| 领取任务、续期、批注与版本回传 | [机器接口](references/agent-protocol.md)、[任务回传](references/agent-task-return.md)；领取与提交保留租约、版本和幂等边界 |
| 建筑骨架、风格或场所 | [空间语法](references/design-grammar.md)、[建筑知识库](references/architecture-knowledge-base.md)、[场所原型](references/structure-atlas.md)；选读相关完整章节，例子不是白名单 |
| 曲面、洞穴和多空间联动 | [自由形空间](references/organic-spaces.md)、[联动空间](references/linked-spaces.md) |
| 近观道具及薄构件 | [细微道具](references/micro-props.md)；区分已支持碰撞、保守障碍与未验证形状 |
| 选区编辑及通用建模效果 | [选区编辑](references/selection-edit.md)、[建模工具](references/modelling-tools.md)；原范围、保护和预算保持执行 |
| 混材、地板或风化 | [方块模式](references/patterns.md)、[自动地面](references/floors.md)、[连片风化](references/weathering.md)；评估适用性，不强制破损 |
| 构件资产、主题配方和本地参考 | [构件资产](references/component-assets.md)、[配方主题](references/reusable-recipes.md)、[参考检索](references/reference-retrieval.md)；引用真实 ID 与内容哈希 |
| 批量创作和项目任务 | [制作批次](references/batch-workspaces.md)、[项目批量任务](references/project-batch.md)；过程目录与正式作者资产分开 |
| 看图、批注或网页候选 | [渲染](references/rendering.md)、[读取意见](references/agent-feedback.md)、[意见任务](references/comment-tasks.md)、[细节控制台](references/detail-control.md) |
| 提示词交接和归档 | [提示词工作台](references/prompt-console.md)、[提示词归档](references/prompt-archive.md)；设计要求交给下一个 Agent，任务状态不代表批准 |
| 验证解释和写出 | [验证流程](references/validation-workflow.md)、[检查解释](references/diagnostic-guidance.md)、[通用工具](references/toolkit.md) |
| 制作源、定稿和版本历史 | [SNBT 与定稿](references/snbt-authoring.md)、[版本历史](references/version-history.md)、[交付](references/delivery-workflow.md)、[存放](references/output-storage.md) |
| 已获授权的委派与接手 | [委派与阅读](references/delegation-and-review.md)；此 Skill 不要求为普通任务新增 subagent |

## 工作区、产物与结束说明

默认作者工作区是调用 Agent 的创作项目根目录，正式资产保存在 `nbt_models/`。新作品写任务专用生成器，复用通用工具，不运行历史示例批量换皮。按建筑库入口创建实际形状／中文名称／版本目录，保留 `room_description.json`、坐标配置和可接手的验证记录；不覆盖已审阅源、图像和历史，也不写入安装资源或游戏活动存档。

制作阶段默认用共享 save_master / save_snbt 写出并回读 `master/model.snbt`；旧 JSON.GZ 和 NBT 继续可读。仅在用户明确要求定稿时，用 finalize 在 `nbt_models/_exports/` 创建交付副本。未经要求，不强加 OBJ、游戏部署、交互网页或其他格式。

Agent 质检优先用 `render` 批量落盘，再实际查看图片，不用 GUI 逐个点图。渲染依赖、相机与资源清理按渲染专题；缺少依赖就如实说明，不把纯色诊断当作纹理或游戏验收。

结束按本次范围交付真实产物的绝对路径和可点击链接：制作任务给 SNBT、预览及验证；定稿任务才给实际生成的 NBT。工具维护说明改动、实际测试与限制，不为凑交付生成建筑或伪造批准。接口与工具维护检查见 [状态与维护](references/state-and-maintenance.md)。
