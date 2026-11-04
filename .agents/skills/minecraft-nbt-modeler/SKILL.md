---
name: minecraft-nbt-modeler
description: 制作、修改和检查 Minecraft Java 1.20.1 的 NBT 建筑、洞穴、曲面及多空间整体。支持完整主模型、碰撞通路、独立墙层和可选纹理预览；先出整体初稿供看图确认，再全局精修与切片。
---

# 按约束生成 NBT 结构

NBTCreator工作区若存在 `.agents/skills/nbtcreator-workspace/SKILL.md`，优先使用该生成入口及 `.nbtcreator/skill-exposure.json` 选择的知识路由；下文完整资料索引是引擎维护来源，不代表未选择的专题也需默认加载。应用、CLI和skill的工具定义统一来自本目录 `tool-catalog.json`，详见[暴露工具接口](references/exposed-tools.md)。默认资产位置为Agent当前项目根目录下 `nbt_models/`，不再默认创建一层workspace目录。

当前副本属于独立 **NBTCreator** 迁移项目，Python引擎与本文仍可在Electron未启动时直接使用。原SAODG归档只作参考，不反向修改；SAODG接入规则仅在用户要求该集成时适用。桌面迁移与统一CLI入口见[NBTCreator调用](references/nbtcreator.md)。

生成建筑方案、提示词或局部构件前，按[各区域 AI 创作偏好](references/ai-creative-preferences.md)读取当前工作区 `.nbtcreator/ai-style.json` 中对应任务区域的参数；无配置时使用默认值。应用和外部 Agent 共用它，创意与详略偏好不改变建模约束或确认流程。

交付来自完整建筑设计的 `.nbt`，SAODG 接入另按当前加载器验收。主题、轮廓、布局、建模方法与高低差自由设计；示例只提供工具，不是建筑模板。用户只要 NBT 时，不强加 OBJ、谜题、刷怪、奖励、世界部署或交互预览。

## 开工与阅读路由

先读工作区 AGENTS.md。新建或重设计时，完整阅读 [整体建模流程](references/whole-model-workflow.md)、[玩家尺度](references/player-scale.md)、[创作原则](references/design-principles.md) 和 [空间与细节设计](references/spatial-detail-design.md)。这些是从原主文件拆出的设计要求，不能只读摘要代替；仅维护 skill 或工具时不要求重读无关建筑设计文件。

按任务完整阅读适用文件；有长目录的知识库按说明选读相关完整章节：

| 条件 | 阅读 |
| --- | --- |
| 未指定骨架、批量多样性、纠正重复 | [空间设计语法](references/design-grammar.md) |
| 建筑类型、风格与构件 | [建筑知识库](references/architecture-knowledge-base.md)；扩展用途时选读 [场所原型库](references/structure-atlas.md) |
| 洞穴、曲面、有机或不规则空间 | [自由形空间](references/organic-spaces.md) |
| 多空间、跨层、多单元整体 | [联动空间](references/linked-spaces.md) |
| 细微道具与原版方块部件 | [细微道具](references/micro-props.md) |
| SAODG 可拼接房 | [拼接协议](references/saodg-constraints.md)，核对当前加载器；完整定义示例见工作区 docs/ROOM_BUILDING_GUIDE.md |
| 生成、改模、导出或验收 | [验证流程](references/validation-workflow.md)、[通用工具](references/toolkit.md) 的相关完整章节 |
| 状态、邻接、操作来源或工具维护 | [状态与维护](references/state-and-maintenance.md) |
| 纹理质检出图、批量相机或用户网页查看 | [渲染与交互](references/rendering.md) |
| 生成或显式转换时带权混材、随机替换、连片噪声 | [通用方块模式](references/patterns.md) |
| 新建/重设计房间的地面风格、半砖凹陷或坑洞 | [自动地面与适量破损](references/floors.md)；主动评估适用性，不等用户逐项指定 |
| 网页保存JSON转下一版NBT、原工作文件夹归档修改意见 | [网页修改回导](references/web-revision.md) |
| 用户手动控制细节比例、材质权重、参数方案、图片修改意见或按需3D查看 | [本地细节控制台](references/detail-control.md)；默认轻量图片评审，agent常规处理仍使用API和批量出图 |
| 用户已在图片或3D上标注、需要收集意见或迁移证据 | [Agent读取意见](references/agent-feedback.md)；使用 feedback collect/archive，检查源/图/快照哈希 |
| 完整可修改提示词、工具参数组合与提示词网页 | [建模提示词工作台](references/prompt-console.md)；离线生成文本、计划和可复用方案 |
| 已有授权的委派或换 agent 接手 | [委派与阅读落实](references/delegation-and-review.md)；本文不要求新增 subagent |
| 用户已看图并同意精修 | [精修流程](references/refinement.md)；风化另读 [连片风化](references/weathering.md) |
| 依据局部方块用自然语言规划工具步骤 | [选区编辑](references/selection-edit.md)；context/compile 共用应用引擎，选区内实际写入、保护与预算由候选和最终导出共同检查 |
| 几何布尔、拉伸、复制阵列、旋转镜像、膨胀侵蚀、扩散或爆炸破坏 | [建模与效果工具](references/modelling-tools.md)；已有资产仍按精修流程 |
| 资产迁移、形状归档、中文名称索引 | [建筑库归档](references/library-archive.md) |
| 按任务检索资料片段、引用与适配已有构件 | [本地参考检索](references/reference-retrieval.md)；retrieve search/bundle/read 共用实际工作流选择与哈希，保留出处；不扩大资料暴露、不覆盖旧资产 |
| 保存选区为构件、搜索构件库、3D复制/移动/旋转/吸附、AI局部放置 | [构件资产库](references/component-assets.md)；应用与 CLI 共用工作区库，extract/transform仅返回候选，先预览再导出下一版 |
| 保存参数化工具序列、复用材质主题、XYZ构件批量阵列 | [配方与主题](references/reusable-recipes.md)；recipes compile / components batch返回原工具候选，不直接写建筑 |
| 图形化浏览已有结构、收藏、版本筛选与批量选择清单 | [现有结构选择器](references/structure-selector.md) |
| 批量创作的过程目录、关联模型与汇总图册 | [制作批次](references/batch-workspaces.md)；batches create/record/list/get/locate 共用应用登记，过程文件放 `_workspaces/batches`，正式作者模型仍按形状／名称／版本归档 |
| 项目多选、批量截面预览、文件/路线检查、进度与失败重试 | [项目批量任务](references/project-batch.md)；只读队列，阶段标记不等于精修批准或验收 |
| 管理SAODG模组已接入结构、房间池与选择优先级 | [模组结构管理器](references/mod-structures.md) |
| 输出、分层交付、世界转换 | [交付流程](references/delivery-workflow.md)、[文件与世界转换](references/output-storage.md) |

## 必须保留的建模顺序

1. **设计完整主模型**：在一个全局坐标系中联合设计各空间、路线、剖面和观察关系。声明总 X/Y/Z、有效占地、原点、主要净尺寸与平台 Y；尺寸由用途和玩家活动推导，48 格只是单片存储尺度。不得先分建几个房间再拼成整体。
2. **闭合后检查**：先形成外壳、底板、顶构完整的密闭空间；覆盖所有设计腔体进行外部六邻接空气洪水检查，修漏后保存通过结果。预览剖切不改结构。邻接状态处理在完整几何上、密闭检查及冻结前完成。
3. **按声明开洞**：密闭通过后才开外门，打通必要厚墙喉道并保留地板；不得用先开洞再封洞取代首次密闭验收。之后检查实际开口、门后净空、必要路线和已声称的具体连接。
4. **形成可审阅初稿**：初稿已有独立空间构想、必要支承、墙/洞壁层次、顶面设计、重要收口和可辨主题构件。不能只交房壳、平台、占位道具，也不能用换材质或撒噪声代替设计。查看实际落盘几何的整体、未剖切入口、代表节点和保留完整顶构的室内仰视，再展示缩略图。批量先实际复核代表初稿并修共性问题。
5. **用户确认后精修**：必须等用户看过对应缩略图并明确同意，才使用精修工具。无回复、超时、自动续跑、文件中的批准、测试记录或其他 agent 评价均不算授权。沿用同一源与图像已有的真实确认，不重复询问；批量仅精修选中模型。改方向先重做整体初稿并展示。
6. **全局精修、冻结与纯切割**：从获确认的完整未切割主模型恢复新版本，统一全局材质、构造尺度与细节。逐一落实天花板的结构节奏与承托、地板的分区与边缘、墙面的厚度层次与开口收口，并检查三者交接；具体要求见精修流程，不能只换材质或撒道具。保留初稿、墙 mask 和确认哈希；禁止逐片精修或按49间距展开后精修。重验并实际查看同相机前后图与近景，之后机械切片。切割循环不能新建隔墙、装饰或道路；落盘回读后48连续重组须逐块等于源主模型。

精修工具的 prepare/approve/apply 只是流程记录，不能证明输入确认来自用户；agent 不得制造确认。用户手动调参后的明确导出另见 [网页修改回导](references/web-revision.md)，不伪造精修批准记录。制作和测试工具不需要资产精修批准。具体操作、保护体积、阶段证据与例外见路由文件。

新建/重设计时，根据房间风格主动评估地面起伏与使用痕迹：废弃、遗迹、旧工坊或洞穴通常用nbt_floors识别室内可达的多层地面、匹配同家族半砖，适量加入成片半格凹陷和有底坑洞；自动保护端口、必要路径与支撑。整洁或精密区域可不破损并记录理由，用户要求平整时遵从。初稿应落实适用的地面设计，不一律延后精修；未知材质/形状和不足预算如实报告，不取消路线保护凑效果。详见 [自动地面](references/floors.md)。

## 约束边界与验收结论

- 原版 Java 1.20.1、gzip NBT、DataVersion=3465，XYZ 顺序、坐标唯一且界内、palette 状态合法。随包注册表验证 ID/属性/枚举；合法状态不代表符合 SAODG 策略、形状已支持或游戏运行通过。
- 独立建筑不套用固定48占地、四门、十字通道或统一地板；结构方块导入时单片每轴≤48。现有 Model 支持任意≤48的单片；大模型、稀疏占地及交付器的实际范围见工具说明，不能把不支持的形态写成已导出。
- SAODG 用48作者网格、49运行间距，高8～48；有效 cells 不重叠、不写缺角。对外门宽6高5、单元边界居中；只声明需要的端口，共用 door_y（默认2，范围2～height-6；自定义门高使用schema 4及以上），世界原点Y=66-door_y。完整模板显式含空气；schema 5 可在同一个 part 引用 body_template、wall_template、offset，两层同尺寸同原点、不重叠且省略空气；不能再同时填写 template，也不能当作两项普通 parts 叠放。
- 墙 mask 在完整模型生成时显式记录；后续非墙几何覆盖必须撤销归属，即使材质相同。两层由同一全局 mask 同步切割，不能按材质猜墙。delivery 每有效 cell 恰好 body/walls 两份 NBT，L形缺角不产空片；完整运行模板另存 runtime/parts。详见交付流程。
- 门口、安全到达点与必要目标之间须有普通玩家碰撞可行路线；只验证声明的旋转。楼梯、半砖、多层与细件不能用单层空气连通替代。回路、双路线、跨层捷径要另证具体连接；全部目标可达不证明每条设计路径成立。
- 48连续重组、49运行展开、旋转、游戏加载与多人验证分开报告。不得在切面默认补隔断或收窄来掩盖兼容问题；未经要求不反改整体造型。未知碰撞不能为制造通过而删细节或当作可靠支撑。
- 技术、空间设计、构造细节、主题表达分别记录。技术通过不能推出设计合格；必要节点不足写“初稿设计未达标”并补改，不能以“等待精修”掩盖。纹理预览、截图、哈希或报告字段不等于美术完成；未执行项目明确标记。

## 工具入口与输出

生成工作区先用 `python .agents/skills/nbtcreator-workspace/nbt.py paths` 查询实际 scripts 路径再导入 API，无需读取包装器猜路径。独立建筑自定义入口使用 toolkit 中的 open_declared_openings；开洞前密闭与开洞后路线仍分别检查。

新作品写任务专用生成器，使用通用工具；不运行历史示例批量换皮。自由形用 nbt_fields，截面用 nbt_sections，顶壳诊断用 nbt_roof_preview；这些均不代替真实玩家视角。受控混材优先使用nbt_patterns的pattern操作：带权随机、全局种子、区域/源状态筛选、连片噪声与兼容属性保留；在完整主模型验证前调用，详见 [通用方块模式](references/patterns.md)。格式互转默认原样保留，已有作品应用仍走真实看图确认后的精修流程。状态邻接仅在有依据的支持范围内处理，不模拟完整游戏。

统一检查入口（将路径替换为实际文件）：

```powershell
python .agents/skills/minecraft-nbt-modeler/scripts/nbt_task.py inspect --source <完整NBT或主模型JSON.GZ>
python .agents/skills/minecraft-nbt-modeler/scripts/nbt_task.py render --source <完整主模型> --cameras <相机列表JSON> --output <全新出图目录> --file-prefix YYYY-MM-DD_r001_
python .agents/skills/minecraft-nbt-modeler/scripts/nbt_registry.py query "oak_stairs[facing=east]"
```

Agent纹理质检优先用render批量直接落盘PNG/JSON，再用图像工具看图；不使用computer use逐个点击下载。网页preview保留给用户交互查看或网页专项验证；相机格式、资源清理及限制见 [渲染与交互](references/rendering.md)。操作ID及Python回归见 [状态与维护](references/state-and-maintenance.md)。纯色预览继续用于几何诊断；不因工具可渲染就认定状态、碰撞或照明正确。

维护和加载位置是当前工作区 `.agents/skills/minecraft-nbt-modeler/`，复制整个目录即可分发，不依赖 tools 兼容入口或目录联接。核心依赖 Python、numpy、Pillow（requirements.txt）；纹理预览另需 Node≥20.19 和 viewer 的锁定依赖，未使用时无需安装。分发不包含 node_modules、Python缓存和任务生成物。

未指定目录时按用户时区实际创建日期输出到 `nbt_models/<形状>/<中文房间名>/<版本>/`。每版必须保存含房间中文名、实际形状、display_name="中文名-形状"的room_description.json；优先用nbt_library.py new/register创建和登记。新产物采用日期、房间编号和用途命名；版本另存，保留已审阅主稿/图像/墙mask，已有资产仅按用户要求和带哈希清单的迁移流程整理。不写入skill安装目录、活动存档、资源目录或房间池。显式空气会替换原方块，导入应在空白制作区域。结束提供实际绝对路径与可点击 NBT 链接，并说明已验证范围。
