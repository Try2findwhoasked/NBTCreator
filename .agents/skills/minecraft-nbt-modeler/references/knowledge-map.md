# 知识库的任务路线与内容归属

这份资料用于选路和维护，不要求建模时通读全部专题。创作工作区以生成的 `nbtcreator-workspace/SKILL.md` 和其 `knowledge.md` 为入口；已启用表示本次允许按需引用，不表示每次都要加载。软件源码维护直接读共享引擎及相关专题，不在这里生成创作入口。

## 按阶段阅读

| 当前要解决的问题 | 先读 | 需要时再展开 |
| --- | --- | --- |
| 从用途形成整栋初稿 | [整体流程](whole-model-workflow.md)、[玩家尺度](player-scale.md)、[创作原则](design-principles.md)、[空间细节](spatial-detail-design.md) | [需求与活动落实](architecture-workflow.md#需求落实与活动动线)、[空间语法](design-grammar.md)、[建筑知识](architecture-knowledge-base.md)中的人工作品、飞檐及适用构造、[场所原型](structure-atlas.md) |
| 整栋初稿有地面嵌纹、屏风边饰或墙面徽记 | [纹样来源](pattern-authoring.md)、[纹样拟合](pattern-fitting.md)中的适用章节 | 选定代表单元、承载面和观看距离，回主模型出近景并复核通路 |
| 把设计落实为完整主模型 | [建筑方案闭环](architecture-workflow.md)、[工作模型](working-model.md) | [参数化构件](parametric-components.md)、[对象图](object-scenes.md)、[通用几何](modelling-tools.md) |
| 制作或准备图案来源 | [纹样来源与制作](pattern-authoring.md) | [频域预处理](pattern-spectral.md)；已有合适图源时直接拟合 |
| 将图案拟合成方块 | [纹样拟合与质量](pattern-fitting.md)的适用模式 | 扩展形状、圆柱及复杂主纹验收章节 |
| 把构件装到现有建筑 | [贴面安装](surface-mounting.md) | [对象图](object-scenes.md)中的依赖联动；持续修改仍回到工作模型 |
| 检查和判断实际结果 | [渲染](rendering.md)、[验证流程](validation-workflow.md) | [诊断说明](diagnostic-guidance.md)、[碰撞包络边界](collision-envelopes.md) |
| 用户看图后批准精修 | [精修流程](refinement.md) | 实际修改的专题；批准继续绑定对应源和图像 |
| 保存制作源、续版或交付 | [SNBT与定稿](snbt-authoring.md)、[版本历史](version-history.md) | [交付](delivery-workflow.md)、[存放](output-storage.md) |
| 协作、批注或维护接口 | 对应任务的[机器接口](agent-protocol.md)、[批注](agent-feedback.md)或[维护](state-and-maintenance.md) | [扩展注册器](extensions.md)、[会话](modeling-sessions.md)；不因此加载全部创作知识 |

新建整栋建筑需完整阅读第一行的基础文件；其余按当前任务读取适用的完整章节。原型库是可选的设计资料，不是必须照抄的建筑菜单。独立纹样、构件和工具维护不继承整栋的所有制作步骤。

## 事实与规则由谁负责

| 信息 | 唯一详细来源 | 其他文档的写法 |
| --- | --- | --- |
| 工具字段、类型、枚举和 CLI 映射 | `tool-catalog.json`，由 `capabilities --agent-tool <名称>` 等入口查询 | 说明用途与决策，示例只展示本场景所需字段 |
| 制作阶段、用户看图和精修边界 | 整体流程；精修文档负责对应工具步骤 | 入口保留简短提醒，避免复制整套流程 |
| 玩家尺度、脚位和净尺寸 | 玩家尺度 | 设计和工具专题引用，不各自维护另一张尺寸表 |
| 工作模型、对象关系与实例归属 | 工作模型与对象图，各管自己的层次 | 纹样与构件文档不重述整栋状态管理 |
| 图源、拟合、宿主安装 | 纹样来源、纹样拟合、贴面安装，分别负责一个阶段 | 链接下一阶段，不混用 `ornament`、`shapes` 和安装请求字段 |
| 图像检查与实际碰撞范围 | 渲染、验证、碰撞包络，各自说明证据边界 | 合法状态、生成图片、静态路线和游戏实测分别报告 |
| 历史、旧兼容和本机回归记录 | 对应历史或兼容专题；临时证据放项目约定输出目录 | 不把一次修复经过追加成所有任务的强制步骤 |

用户当前要求和项目约定决定本次范围；示例、预设、知识组开关、检查回执和其他 Agent 的评价都不扩大执行权限，也不构成真实看图批准。遇到文档与接口不一致，先核对对应 Schema 和当前实现，修正资料，不通过改写用户约束来迁就例子。

## 后续增补

先找现有专题的责任边界。只有出现不同任务阶段或独立阅读需求时再拆文档；不按每个工具或每个字段各建一篇。长篇保留用途、章节索引、输入、操作、检查和下一步，让读者能找到完整的适用章节。

内容迁出后，更新共享入口、生成的工作区路由、内部可选资料与引用；旧文件和旧锚点保留简短跳转。新的源文档应进入知识组导航，兼容示例标明边界。验证本地链接、冻结副本、选择过滤和入口备份，不能只确认 Markdown 能打开。
