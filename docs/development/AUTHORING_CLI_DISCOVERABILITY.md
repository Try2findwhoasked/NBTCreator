# 创作 CLI 的 Agent 可理解性评估

本评估面向 NBTCreator 维护者，范围是外部 Agent 在 `mise run nbt --` 内完成创作时的查找、填写请求、判断结果和接续操作。本文记录 4.3.2 的实测结果、当时可用的路径和改进优先级。

NBTCreator 5.0.0 已补充按任务组织的创作速查、请求与回执接续说明，并改进缺失文件、JSON 解析、版本绑定过期和输出冲突的诊断。当前用法见[创作速查](../../.agents/skills/minecraft-nbt-modeler/references/exposed-tools.md#创作速查)和[5.0.0 发布说明](../archive/releases/RELEASE_5.0.0.md)。

## 结论

模型需要做设计判断，也需要操作工具。用途、尺度、空间关系、材料表达以及实际看图时的判断应由 Agent 和用户作出。当前还需要 Agent 自行推断一些本可由接口说明的事项，包括从哪个命令起步、已有的文件属于哪个阶段、下一个请求从哪份回执取字段，以及报错时先检查什么。把这些事项显式写在入口、示例和回执中，可以减少模型读文档和猜测的成本。

已有两处可复用的设计。工作区生成的 `SKILL.md` 已按「接手任务」「新建初稿」「看参考」「找资产」等场景给出起步说明。建筑方案的 `next.request` 和 `render_command` 已能把上一阶段的绑定传给下一阶段。优先补齐这两种设计的覆盖范围。[工作区入口生成逻辑](../../.agents/skills/minecraft-nbt-modeler/scripts/nbt_exposure.py) · [建筑方案与审阅](../../.agents/skills/minecraft-nbt-modeler/references/architecture-workflow.md)

## 模型实际从哪里查起

在已同步的创作项目根目录，读取生成的 `.agents/skills/nbtcreator-workspace/SKILL.md`，使用其中显示的启动命令。同名 mise 任务冲突时，生成入口会显示文件任务的调用方式。冻结运行时决定当前项目实际支持的参数和能力。维护者在源码根目录核对接口时可查询活动引擎。需要读取创作资产时，从源码用 `mise run nbt -- --workspace "<创作项目根目录>" <子命令>` 指定真实项目，`--workspace` 放在子命令之前。[共享工作区](../guides/SHARED_WORKSPACE.md) · [源码 CLI 工作区选择](../../scripts/cli.mjs)

| 模型知道什么 | 先读或先查 | 查到什么 |
| --- | --- | --- |
| 有交接任务 ID | `task --id <ID> --view compact`，已知类型也可用 `task-client inspect prompts <ID>` 或 `task-client inspect tasks <ID>` | 任务来源、阶段、源是否匹配和下一步。按需读取 `expand` 中的正文、坐标或候选视图。 |
| 只有创作意图 | 工作区 `SKILL.md` 与 `capabilities --routes` | 按任务选择起步命令。需要设计背景时只展开 `knowledge.md` 中适用的专题。 |
| 已知子命令 | `<子命令> --help` | 命令行参数和动作名。使用 `--request` 的工作流还要查 JSON 契约或起步示例。 |
| 已知工具或请求类型 | `capabilities --model`、`--architect-action <动作>`、`--agent-tool <工具>`、`--operation <kind>` 或 `--recipe <工具>` | 对应请求的字段。已知建筑字段时可加 `--field`，例如 `plan.parts.interfaces`。 |
| 已有失败报告 | `diagnostics --kind model --report <完整回执>` 或按报告类型选 `review`、`candidate` 等 | 问题、目标及证据位置。建筑命令的简报给出了 `report.path`，应把它指向的完整报告交给诊断。 |

本次从源码入口测得总帮助列出 45 个顶层命令或别名，速查表有 9 组、25 条，`capabilities --routes` 输出约 7 千字符，完整 `capabilities` 约 104 万字符。字符数按 PowerShell 接收的 stdout 估算，只反映阅读规模。`capabilities --operations` 返回 26 个操作名称与简短说明，高层 `agent_tools` 另有 39 项。让模型先从用途选路，再读取单项契约，可以把它需要处理的上下文限制在本次任务相关的内容。[能力查询实现](../../.agents/skills/minecraft-nbt-modeler/scripts/nbt_capabilities.py) · [工具目录](../../.agents/skills/minecraft-nbt-modeler/tool-catalog.json) · [机器接口与紧凑任务视图](../../.agents/skills/minecraft-nbt-modeler/references/agent-protocol.md) · [增量诊断](../../.agents/skills/minecraft-nbt-modeler/references/diagnostic-guidance.md)

## 按创作意图走查

下表中的命令省略工作区 Skill 所示的启动前缀。实际建模命令从创作项目根目录执行，并按该项目的保护、预算和审阅约定填写请求。

| 用户意图 | 当前可用路径 | 模型目前需要额外推断的内容 |
| --- | --- | --- |
| 从零做一座亭子，并交付可审阅初稿 | `architect plan-build --request <JSON>`。可从已有入口亭示例开始，用 `capabilities --architect-action plan-build` 核对契约。 | 速查表列出复验用的 `plan-check`，`plan-build` 只出现在保存说明里。模型要从「起整栋」跳到 Skill 的建筑专题才看到首个可执行调用。 |
| 已经有尺寸和构件，直接组装或续版 | `model --request <JSON>`，用 `capabilities --model` 查字段。通过 `size` 新建模型，或通过已有 `source` 与 `source_sha256` 打开模型。 | `model` 在速查表出现在检查和保存处。需要文档直接说明「按明确几何组装」也走这个入口，`architect` 用于需要把空间、构件、接口及审阅绑定写成建筑方案的任务。 |
| 把一段地面换材，保留边缘和立柱 | `selection-edit context` → `selection-edit compile` → 把返回的全局 `operations` 追加到原计划，走 `control plan/preview/validate`。 | 速查表缺这条路。CLI 帮助只给 `context` 和 `compile` 两个动作。输入操作用选区局部坐标，编译产物才是带写入边界的全局操作。 |
| 找可用的尖拱构件或重新编译旧配方 | 查现有素材用 `asset-libraries browse --request <JSON>`，例如 `{"query":"尖拱","limit":4}`。已有配方用 `recipes compile`。参数化单件可查 `capabilities --agent-tool parametric_compile`。 | 「找现有」「调整已存配方」「从参数生成」分别有入口。素材浏览结果要保留来源、版本和哈希绑定，查尺寸或样式时沿同一次命中的绑定预览。 |
| 想知道屋顶能用哪些形态和参数 | `capabilities --operations` → `capabilities --operation auto_roof`。独立结构配方可用 `capabilities --recipe structure` 查询。 | `auto_roof` 是请求里的 `operations[].kind`，`parametric_compile` 可用于高层工具调用，也可出现在配方里。速查表的 `call` 字段把命令、字段示例和多步调用放在一起，需要模型自行判别。 |
| 对比换材前后的效果，或给已保存初稿出真图 | 有候选快照时用 `render --snapshot <快照>`。有制作源时用 `render --source <制作源>`。两条均要相机和新输出目录。 | 速查表只列了 `--source`，CLI 帮助才显示两个互斥入口。应在入口处标明 `control preview` 的 `after.json` 是哪类输入。 |
| 检查失败，需要决定下一步 | 对照资产类型选择候选 `validate`、制作源 `model` 中的 `validate:true`，或方案绑定的 `architect plan-check`。再对完整回执用诊断。 | 「检查一下」不能靠命令名决定。输入是什么、检查哪类绑定、通过意味着什么，应在同一行可见。 |
| 用户明确要求交付 NBT | 先在审阅时用 `finalize --source <制作源> --inspect-inputs` 记录源和输入哈希，明确要求定稿时用当时记录的哈希调用 `finalize`。 | 速查表有导出命令，省略了哈希取得的步骤。帮助也把两个哈希列为可选参数，需要分清只读核对分支和写交付文件分支。 |

[简单建筑与入口亭示例](../../.agents/skills/minecraft-nbt-modeler/references/simple-building.md) · [工作模型](../../.agents/skills/minecraft-nbt-modeler/references/working-model.md) · [选区编辑](../../.agents/skills/minecraft-nbt-modeler/references/selection-edit.md) · [资产库](../../.agents/skills/minecraft-nbt-modeler/references/asset-libraries.md) · [配方](../../.agents/skills/minecraft-nbt-modeler/references/reusable-recipes.md) · [出图和输入类型](../../.agents/skills/minecraft-nbt-modeler/references/rendering.md) · [制作源与定稿](../../.agents/skills/minecraft-nbt-modeler/references/snbt-authoring.md)

## 把接口要求写在模型第一次需要它的地方

### 给路线一个明确的起点和产物

优先在现有 `capabilities --routes` 增加「新建整栋」「装配或续版」「局部修改」「找素材与复用」「解释检查失败」几条路线。出图行同时列出制作源和候选快照的分支。每条路线都给首个命令、单项契约或现有示例、需要的输入来源、该步产物和下一步。命令、JSON 字段、多步流程应有明确标签。现有 `call` 是文本字段，如需结构化扩展，可先新增字段供新客户端读取，再验证已有消费者。可复用 `tool-catalog.json` 与现有生成链维护入口，工作区 `SKILL.md` 只提供少量常用起点和索引。[工具目录](../../.agents/skills/minecraft-nbt-modeler/tool-catalog.json) · [现有速查表](../../.agents/skills/minecraft-nbt-modeler/references/exposed-tools.md)

以「有旧建筑，局部换材」为例，这条路线应让模型直接读到四件事。先用已绑定的源和世界坐标边界读真实选区，工具步骤在局部坐标中编写，`compile` 返回可追加到原计划的全局操作，最后在同一个源或候选上下文中预览和验证。这样模型无需自己判断是否再平移一次，也知道到哪一步才出现修改候选。[选区编辑](../../.agents/skills/minecraft-nbt-modeler/references/selection-edit.md)

### 让最小请求说明字段从哪里来

当前已有可复制的[入口亭 JSON](../../.agents/skills/minecraft-nbt-modeler/assets/examples/entry-pavilion.json)和[开放平台请求](../../.agents/skills/minecraft-nbt-modeler/references/simple-building.md)。入口亭示例包含 `save_draft`，用例说明应紧挨着命令标出它会发布制作版。只需编译和检查时省略该字段。一般路线应区分三类字段。

- **由创作者决策**的字段，例如用途、空间关系、尺寸、材料和视角目标。示例写清它表达的设计意图与单位。
- **从当前上下文查得**的字段，例如制作源路径、选区世界坐标和打开的模型版本。已有源请求要说明以哪个工作区为路径基准，局部坐标用哪个原点。
- **从上一步原样传递**的字段，例如 `source_sha256`、`next.request`、完整资产引用和预览内容哈希。示例注明来源字段及哪些值应该随输入变化而重查。

单项 Schema 已能说明类型和枚举。对降低长链路错误更有用的是在最小示例旁写清字段的取得方式、预期结果和一个典型错误。优先复用现有样例和回执，避免在多个入口复制整份 Schema。[建筑方案字段查询](../../.agents/skills/minecraft-nbt-modeler/references/architecture-workflow.md) · [请求路径解析](../../.agents/skills/minecraft-nbt-modeler/scripts/nbt_request_paths.py) · [资产引用与放置](../../.agents/skills/minecraft-nbt-modeler/references/asset-libraries.md)

路径还存在一个易误读之处。源码 CLI 的总帮助将全局 `--workspace` 放在子命令前，若干 Python 子命令又有各自的 `--workspace` 参数。`capabilities` 的 `path_policy` 字面值是 `request_relative_with_absolute_legacy_compatibility`，而共享请求助手按显式工作区或当前目录解析 `source`、`context` 等资源路径字段。帮助和机器元数据宜明确区分「请求文件路径」和「请求内资源路径」，写明各自的基准。修改现有元数据前应先核对调用方。[源码 CLI](../../scripts/cli.mjs) · [能力元数据](../../.agents/skills/minecraft-nbt-modeler/scripts/nbt_capabilities.py) · [共享请求路径解析](../../.agents/skills/minecraft-nbt-modeler/scripts/nbt_request_paths.py)

### 用回执告诉模型当前到了哪一步

保留建筑方案现有的接力方式。当 `plan-build` 保存成功时，用它给出的 `next.request` 运行 `review-prepare`。按审阅准备回执的 `render_command` 出图，实际查看后以 `review_record_bindings` 为基础填写观察。用 `--compact-report` 时，父目录须已存在，报告路径须为 `nbt_models/` 下的全新文件。简报适合判断接下来的动作，完整报告适合诊断。续版则沿用保存回执中的 `revision_request`，避免模型重新猜测父版本和绑定。[建筑入口与回执](../../.agents/skills/minecraft-nbt-modeler/references/architecture-workflow.md) · [简明回执实现](../../.agents/skills/minecraft-nbt-modeler/scripts/nbt_architect.py)

适合推广的部分是明确产物、是否写入、核对状态和下一步。先统一说明已有字段的含义，再对高频入口补短回执或可选视图。

| 此时手中有什么 | 可以据此做什么 |
| --- | --- |
| 编译后的操作、构件候选或 `before.json` / `after.json` | 核对参数和绑定，预览或验证该候选。 |
| 已保存的 SNBT 与源哈希 | 读取、续版、复验或准备审阅，使用实际制作源。 |
| PNG、渲染清单与审阅记录 | 核对图像和源版本，记录真实观察。需要精修时等用户对该批图像明确确认。 |
| 审阅时的源哈希和完整输入哈希 | 用户明确要求定稿后，按同一绑定交付 NBT。输入变化时重新核对审阅。 |
| 交付目录中的 NBT | 交付和后续游戏验收。继续修改时回到对应制作源。 |

[建模流程边界](../../.agents/skills/minecraft-nbt-modeler/SKILL.md) · [精修流程](../../.agents/skills/minecraft-nbt-modeler/references/refinement.md) · [SNBT 制作源与 NBT 定稿](../../.agents/skills/minecraft-nbt-modeler/references/snbt-authoring.md)

### 把失败定位到模型能马上检查的输入

本次用同一个确认不存在的路径做只读查询，四个命令都以退出码 1 结束。`model --request` 报 `MODEL_INVALID` 并指出路径问题，`selection-edit context` 和 `diagnostics` 返回带路径的错误文本。`architect plan-build --request` 却返回 `ARCHITECT_INVALID`，提示「内联plan与plan_id必须选择一种」。显式请求路径不存在时，当前读取逻辑回退为空请求。这会诱导模型重写本来正确的 JSON 设计，而实际检查点是文件路径或工作目录。[建筑请求读取与分派](../../.agents/skills/minecraft-nbt-modeler/scripts/nbt_architect.py) · [工作模型错误返回](../../.agents/skills/minecraft-nbt-modeler/scripts/nbt_working_model.py) · [选区编辑错误返回](../../.agents/skills/minecraft-nbt-modeler/scripts/nbt_selection_edit.py)

另一个容易误读的是候选检查。`validate` 的顶层 `ok:true` 表示生成了结果，候选是否通过要查 `result.passed`，退出码也跟随后者。自动化应同时检查进程退出码、业务结果和产物的源绑定，再决定能否继续。已有 `machine` 接口的 `error.code`、`retryable` 和 `details` 可作为结构化错误的参考。设计新回执时宜分别标明请求是否处理、检查是否通过及结果写到了哪里，兼容现有调用方。[候选检查返回](../../.agents/skills/minecraft-nbt-modeler/scripts/nbt_candidate.py) · [机器接口错误约定](../../.agents/skills/minecraft-nbt-modeler/references/agent-protocol.md)

第一批应覆盖请求文件缺失、JSON 解析失败、必填字段缺失、源或父版本过期、输出路径已存在。让每类错误指出出问题的输入、可重试条件和下一项检查。`STALE_SOURCE`、`STALE_PARENT` 等情况下，模型应重新读当前版本并核对任务，再决定怎么继续。诊断层沿用已有证据指针与原始报告，避免把提示语解释成修复成功。

## 建议实施顺序与验收

| 优先级 | 改进 | 验收方式 |
| --- | --- | --- |
| P0 | 补速查表的创作起步路线，同步生成 Skill 的短导航。 | 给模型「起一座带入口的亭子」「给旧建筑局部换材」「查已有尖拱」三个中文意图。只给生成 Skill 和速查表，逐项观察是否能选中首个命令、找到单项契约，并说出该步会产生什么。 |
| P0 | 修正显式缺失请求文件时的误导信息，给高频验证命令说明退出码和业务状态。 | 在隔离环境下传不存在的路径，期望提示正确输入和路径，检查不会按空请求继续。用已有候选失败夹具核对不会因 `ok:true` 误判通过。 |
| P1 | 把已有整栋示例扩展为「请求字段来源与回执接力」的样板，再补一条选区路线。 | 模型能从上一步找到下一步的绑定，不自行填哈希，也能正确区分局部和全局坐标。核对示例发布制作版、生成预览和写正式 NBT 的边界。 |
| P1 | 复用建筑简报、任务紧凑视图和增量诊断，让结果直接说明已完成和待完成的动作。 | 分别提供失败简报、制作版回执、渲染清单与真实审阅记录，检查模型是否能选择读完整报告、准备看图、登记观察或等待用户确认。 |
| P2 | 若速查表扩充后仍难找，加入按中文意图或工具名称筛选的短索引。 | 同一批用例做前后对照，记录命令与阶段选对率、首次正确调用前的查询次数、误读字段数和输出长度。保留单项 Schema 查询。 |

验收可复用上面的意图及现有入口亭、选区和候选夹具。建议分别记录首次接手与拿到上一阶段回执的结果，二者的信息起点不同。成功标准还包括识别过期绑定、缺失坐标和缺少真实确认，能在需要时请求输入或停在对应阶段。选择建筑用途、空间取舍和真实画面的质量仍需要创作判断。

本次验证只运行了源码入口的帮助、能力查询和不存在文件的错误探查。候选检查的返回约定与工作区 Skill 的生成内容来自源码阅读。本次未生成建筑、同步真实工作区、执行渲染或定稿，也未运行模型对照实验。表中的改进和验收目标供后续实施使用。
