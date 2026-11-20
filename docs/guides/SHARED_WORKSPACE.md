# 桌面与 Agent 共用工作区

新建制作版使用 SNBT，定稿 NBT 位于 `nbt_models/_exports/` 下与建筑／版本一致的镜像目录。专用 Git 历史位于 `.nbtcreator/history/`，与用户项目自己的 Git 独立。完整迁移需同时携带模型目录和历史归档。CLI 与界面通过 `history` 共用版本链、当前工作版及任务与批注的关联，真实批准和人工核对仍单独完成。

NBTCreator 沿用原 minecraft-nbt-modeler 的模型与导出协议。主模型 JSON.GZ、显式墙 mask、room_description.json、coordinates/cameras、runtime 分片、body/walls 分层和 delivery/validation 清单的格式不因接入 Electron 或 AI 而改变。提示词方案的 AI 稿是额外的文本元数据，不改变模型格式。

## 对齐目录和工具版本

建议 Codex 在当前项目目录工作，使用生成的 `.agents/skills/nbtcreator-workspace/SKILL.md` 和统一CLI；工具实现与清单位于 NBTCreator 的 minecraft-nbt-modeler 目录。原 SAODG 旧副本不会自动双向同步，新应用也不再使用它作为调用接口。

同步后从创作项目根目录运行 `mise run nbt -- capabilities --routes`。知识库、建模、验证和渲染都沿用 `mise run nbt --`。任务单独登记在 `.mise/conf.d/nbtcreator.toml`，沿用项目选择的 Python。已有同名任务或自定义任务来源的项目按生成的 `SKILL.md` 显示的 mise 文件入口调用。旧脚本仍可直接运行生成的 `nbt.py`。便携版如果通过自己的 `mise.cmd` 启动，同样使用 `run nbt -- …`。有关任务发现和配置优先级，见 [mise 任务发现规则](https://mise.jdx.dev/tasks/task-discovery.html)。

默认使用调用 Agent 的创作项目根目录，资产保存在该目录的 `nbt_models/` 中。支持显式 `--workspace`、`NBTCREATOR_WORKSPACE` 及手动选择；应用不会默认把安装资源或系统目录当作资产根目录。软件源码根目录也不作为创作项目，不在此生成 `nbtcreator-workspace`。旧用户资产通过迁移命令转入新的创作根目录。

当前创作项目根目录的 `.nbtcreator/skill-exposure.json` 保存知识组选择，可在 AI 助手配置页修改，修改后会同步生成入口。这项配置控制知识路由与阅读范围，不控制文件访问权限，也不删除资料库。所有知识组共享同一份工具能力；`tool-catalog.json` 是定义源，`sync:tools` 生成网页目录与工具接口文档，`check:tools` 会在版本不一致时阻止打包。

生成的 `SKILL.md` 只保留任务路线、入口和必要约束；同目录 `knowledge.md` 列出本次已启用专题。纹样来源、拟合、宿主安装和会话复用分别阅读对应资料，不再从一篇参数化长文中查找所有步骤。重新同步会先备份用户修改过的生成入口及索引；现有创作项目不会因为软件源码里的文档整理而自动改写。

可在 AI 设置中导入自己的 Markdown/TXT，文件复制到 `.nbtcreator/knowledge/`，选中的文档通过相对链接加入 Agent 入口。切换到尚无配置的工作区时，会携带自定义文档和开关；目标已有配置时，保留目标的列表。知识仅供参考，不授予执行或批准权限，也不自动上传到 API。

已有建筑书库可在“检索本地参考 → 本地书库”按工作流连接。原书目录保留，索引与连接配置在当前工作区。桌面与 Agent 可以查到同一片段，选入参考集合后按原文、片段和清单哈希复核。[本地参考检索与书库入口](../../.agents/skills/minecraft-nbt-modeler/references/reference-retrieval.md#外部建筑书库)

需要查公开网页时，打开参考选择器里的「联网补查」，填写公开搜索词或原页链接。可把网页摘录与本地书库片段一起选入同一份参考集合。[联网补查与引用](../../.agents/skills/minecraft-nbt-modeler/references/reference-retrieval.md#联网补查)

常用摘录可以收藏到当前工作流。之后在「已收藏网页」浏览，或直接用本地参考检索查找。收藏保留原页及访问时间，取消收藏后已有引用仍可回查。[收藏网页证据](../../.agents/skills/minecraft-nbt-modeler/references/reference-retrieval.md#收藏网页证据)

保存的 request/settings 文件尽量使用相对于工作区的 source/context/cameras/review 路径，room_description.master 则相对于描述文件定位；旧绝对路径仍可读取。外部文件或跨盘引擎无法使用相对路径时，保留绝对路径，因此并非任意单文件都能独立搬迁。Agent 应在项目根目录执行命令，或为统一 CLI 指定前置参数 `--workspace <根目录>`。

共用工作区时，选择一个包含 nbt_models 的磁盘根目录，在桌面通过“选择工作区…”指定；误选 nbt_models、缓存或房间子目录时会自动识别项目根目录。Agent 在同一根目录调用，保存参数使用工作区相对引用；旧绝对路径保持兼容。

切换工作区时，会先取消旧工作区的 AI 请求并等待结束，拒绝迟到结果，再将经哈希校验的 Skill 脚本、资源、数据与知识库同步到目标 `.nbtcreator/runtimes/<内容哈希>/`。新工作区会携带当前知识组，已有目标配置则保留。旧工作区及旧运行时不删除；手动改过的生成入口先备份到 `.nbtcreator/skill-backups`。核心入口随工作区搬迁，渲染共享依赖需保持相对安装位置或重新同步/独立锁定安装。

运行时副本不包含 node_modules、Python 缓存和任务产物。核心调用需要可用的 Python/NumPy/Pillow；完整便携包已内置，源码环境则按 requirements 安装。同步的 `.nbtcreator/render-runtime.json` 可关联应用锁定版本的 Playwright、Node/Electron 与浏览器，不必给每个工作区复制依赖。单独复制工作区不等于携带第三方环境。

规范资产目录为 `nbt_models/<形状>/<中文建筑名>/<版本>/`；既有建筑从源目录按原版本规则另存下一版。临时预览与任务在 `_workspaces`，不把它们当正式交付。

顶部的“提示词方案 / 模型编辑 / AI助手 / 任务记录”是同一磁盘项目上的功能页，不会自动建立或切换磁盘项目。

## Agent 交接流程

首次创作在提示词方案页编写和审阅设计要求，再“确认并交接”，任务保存在对应建筑的 `提示词方案/任务/`。Agent 通过 `prompts tasks --after <cursor>` 发现新增任务，`prompts task --id <id>` 读取正文及经哈希检查的方案；进度通过 `prompts task-status` 登记。默认方案不要求具体工具步骤，详见[首次创作](PROMPT_CREATION.md)。

已有建筑可在模型编辑页调好参数后点击“生成 Agent 修改方案”→“复制给 Agent”；Agent 读取当前源、参数、意见和保护配置，完成实际修改后在原建筑工作文件夹内另建下一版本目录。应用刷新列表后选择新版本，不需要再次执行同一修改。保存任务和登记完成均不自动启动 Agent，也不表示用户已验收建筑。

文字交接文档、参数副本、操作计划、校验包与审阅图存入当前结构版本的 `Agent交接/plan-<任务编号>` 或 `review-<任务编号>`，不覆盖原记录。旧建筑根的审阅记录仍可发现。运行日志继续留在任务目录；项目内引用优先相对工作区根目录。

“Agent 精修审阅与执行”和“方案与运行详情”默认收起，用户主动展开或发生相关错误时显示详情。打开建筑自动查找与当前源路径/哈希匹配的审阅记录；执行仍检查保护配置与真实确认。手动指定旧审阅目录保留在可选执行入口。

审阅与确认资料由应用和 Agent 共用，无需两边各执行一次。Agent 已交付下一版时，在应用中刷新即可。若希望由应用执行同一计划，才使用可选执行入口；该入口会另建源建筑工作目录下的精修版本，保留原稿。手动调参后直接“导出建筑下一版”仍可用。所有交接文档和界面操作均不自动产生批准，也不替代真实看图确认。

## 协作边界

应用和 Agent 可以读取同一版本。通过受管制作版入口发布时，桌面与 CLI 共用建筑级发布锁，提交前核对当前父版本和源文件。同一父版本并发发布最多一个成功。收到 `STALE_PARENT` 后刷新并打开新版本，再决定如何处理当前候选。其他写入入口及直接编辑文件仍应轮流操作。参见[架构与并发边界](../development/ARCHITECTURE.md#桌面服务与版本发布)。

Agent 自主精修仍需真实看图确认；用户手动调整后明确导出时，沿用原网页转换流程。AI 建议、参数 JSON、意见文件和界面标签都不能代替批准或实际验证。

## 评论和候选校验

工作台在输入停顿后自动将文字和选点更新为正式标注，JSON、`修改意见/评论索引.json` 与哈希绑定的证据直接保存在被标注的结构版本目录内。继续输入更新同一条；“下一条标注”或 Ctrl+Enter 开始另一条。旧目录意见继续可读，首次修改时迁入版本目录并保留原文件。Agent 由人工手动触发 `mise run nbt -- feedback scan/collect` 发现并验证意见；任务和批注接口保持分离。`mise run nbt -- paths` 可查询当前工具API位置。

预览后使用应用“检查当前效果”或 `mise run nbt -- validate --request <参数JSON> --snapshot <after.json> --output <新目录>` 检查同一候选。计划 planned、预览出图和候选通过是三个不同阶段；校验失败会生成独立报告，参数改变后需重新检查。独立建筑使用显式 mode/openings 和 XYZ 真实边块，SAODG 仍保留原 cells/端口规则。

返回[文档导航](../README.md)。
