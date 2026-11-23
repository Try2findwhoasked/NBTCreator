# 已交接建筑初稿的创作流程

在实际创作项目根目录使用冻结入口。下文以 `nbt` 代指 `python .agents/skills/nbtcreator-workspace/nbt.py` 或工作区已经配置的同一入口。先用 `task-client inspect prompts <任务编号>` 核对阶段、源和附件，再用 `task-client --session <会话名> start prompts <任务编号> --owner <执行者>` 领取。需要长时间工作时，在另一个终端对同一会话运行 `task-client --session <会话名> keepalive`。

## 从外部对话直接建立初稿任务

用户明确要求开始新建建筑时，可以在工作区用 `prompts save --request <方案.json>` 保存，再用 `prompts publish` 交接。将用户硬性要求原文放入 `document.user_requirements`，并在 `text` 中保留原文。把已确定的设计条件及仍可调整的内容写清楚。尺寸由用户固定时使用 `size_policy: "fixed"`。

为方案 JSON 提供 `session_id`（新建时使用 32 位小写十六进制编号）、`text`（完整提示词）、`document`、`plan` 和 `context`。例如独立建筑用 `document.schema_version: 1`，在 `document.project` 中提供 `name`、`stage: "draft"`、`buildingShape: "standalone"`、`size` 和 `size_policy`。没有已确认的操作或坐标时，`plan` 可用 `{"operations":[]}`，`context` 可用 `{"mode":"standalone"}`，建模时再根据实物补齐。

从保存回执取 `index`、`id` 和 `revision`，原样传给 `prompts publish --index <索引> --id <稿件编号> --revision <修订>`。选择极限效果时加 `--creation <档位.json>`，文件内容示例为 `{"mode":"maximum"}`，可另填 `economy_model`、`quality_model`。性价比用 `"economy"`。用户已设置工作区档位时，可将 `.nbtcreator/preferences.json` 中的 `creationMode`、`economyModel`、`qualityModel` 分别带入 `mode`、`economy_model`、`quality_model`。留空档位由宿主按已配置模型选择。发布回执的 `id` 是任务编号，用它领取并运行。

## 读方案和选择模型

- **性价比**沿用常规模型或设置中的性价比模型，从单候选开始。普通设计失败最多局部修两次。楼梯、跨层路线或装配失败可发出一次强模型请求。遇到不明确的跨层关系、共享构造或关键约束，可用 `creation --session <会话名> escalate --request <请求.json>`，传 `kind`（`cross_floor`、`shared_structure`、`ambiguous_constraint` 之一）和具体 `reason`。
- **极限效果**先在请求 JSON 的 `axes` 登记要探索的设计轴，例如 `{"axes":["入口到阅览厅的空间序列","木框与灰瓦的材料分工"]}`。对两个候选使用强模型，保留真实的几何或方块状态差异。每个候选最多局部修一次。
- 用 `creation --session <会话名> start [--request <请求.json>]` 冻结约束，续作看 `brief`。简报给用户硬要求原文、有效约束、设计摘录和本轮请求。用 `brief --expand` 读完整提示词和坐标上下文，也可用任务客户端分别读取 `text`、`document`、`plan` 或 `context`。
- `requests` 中的模型 ID 沿用交接时的工作区设置。档位留空时由宿主使用其已配置的常规或强模型。外部宿主按用户已允许的服务与用量派发；本地 CLI 只生成请求说明和执行确定性步骤。宿主有真实用量时，可在候选写 `"model_usage":{"calls":1,"input_tokens":123,"output_tokens":45}`，未知字段省略。

### 使用参考图或旧版本

在 `start` 请求中加 `reference`，包含 `manifest: {path, sha256}`、`fixed` 和 `explore` 两组文字。用已登记的[三视参考](orthographic-reference.md)清单。把量读得到的轴、轮廓、尺寸或已批准部位写入 `fixed`，把图外的背面、进深、连接方式或室内写入 `explore`。已确定的 XYZ 画布可写成 `canvas_size`，编译、回读和发布都会校验。其他可验证条件应落实到方案的尺寸、路线、构造规则或取样点。

可以用 `comparison: {cameras: {path, sha256}, width, height}` 冻结同机位审阅条件。若使用三视登记相机，再加 `bundle: {path, sha256}`。应使用相机包中对应视图的 JSON 和原始宽高。省略时使用第一个通过候选的相机为第二个候选补拍同机位，两份候选仍各自通过应有的审阅覆盖。

有需复查的留存版本时，在 `start` 加 `retained_review: {path, sha256}`，指向该版已登记的 `review-notes.json`。为当前候选登记图像观察后运行 `retest`，查看稳定问题 ID、质量条目可比性和旧机位重拍。查看重拍后再登记相应视觉结论。同一任务已登记旧版和盲评时，可用 `{"slot":"1","against":"blind"}` 专门复验本轮盲评问题。

## 提交、诊断、看图

1. 将 `{"slot":"1","plan":{…}}` 交给 `creation --session <会话名> candidate --request <候选.json>`。`plan` 用 `capabilities --architecture` 的建筑方案契约。极限效果两个候选用 `"slot":"1"` 与 `"slot":"2"`，分别提供 `variation: {axis, decision}`。轴来自已登记范围，设计决定须真正落实到几何或材质。参考 [归卷阁](../assets/examples/reading-loft/README.md) 的计划和负例。
2. 需要细粒度构造时，在本地 Python 作者脚本中先创建完整 `WorkingModel`，声明实际路线和必要目标，按约束完成开口检查，再调用 `from nbt_creation import submit_working_model` 和 `submit_working_model(session, {"slot":"1","working_id":"draft-r1","view_overrides":cameras}, model)`。每项相机含 `id`、`role`、`eye`、`target`。至少提供全景 `whole`、无剖切且从真实站位看入口的 `entry`，以及覆盖代表构造的 `structure`、`detail` 或 `interior`。用新的 `working_id` 标识设计更新。一个未完成的本地重试保留同一编号和输入。
3. `design` 失败按 `diagnostics` 中的目标、坐标和证据位置处理。下一次候选沿用本次模型角色及改动预算。遇到 `local_execution`，按回执修复本地故障后用 `retry --request <原候选.json>`，已完成阶段从回执恢复。`stale` 表示源、租约、父版本或证据发生变化，停止写入并重新核对。用 `status` 读阶段回执、耗时及已报告的模型用量。
4. 极限效果用 `prepare-blind` 生成公共 A/B 图片和匿名几何检查，交给审阅者的材料只取返回的 `public` 和 `geometry`。实际逐张比较后用 `record-blind` 提交 `decision`（A、B、tie 或 inconclusive）、`actor` 和 `observations`。观察填 `view`、`note`、`remaining`，也可用 `part`、`recheck` 和参考图登记区域。调用 `select` 选择获选候选，平局用 `{tie_choice, reason}` 作出有依据的选择。用 `retest --request <复验.json>`（如 `{"slot":"1"}`）按已登记待复验的机位重拍并重验入选候选。性价比可在查看单候选实图后直接 `select`。
5. `publish` 将入选几何存成新制作版，再从实际制作源回读并出图。看最终图片后使用 `observe --request <观察.json>`，分别为 `review.awaiting_views` 中每个机位提供一条观察，正式制作版用 `"slot":"published"`。建筑方案用现有 `review-record` 的 `{image,note,locations?}` 可纳入问题、评估条目和细部覆盖。脚本式模型用 `{image,text}`。观察结束后用 `finish` 回传。制作任务进入等待用户审阅。

候选、失败回执和比较图保存在 `nbt_models/_workspaces/creation/` 和 `nbt_models/_workspaces/reference-reviews/`。待回传正式制作版位于对应建筑目录。已有建筑的只读计划和精修按[机器协议](agent-protocol.md)走原任务入口。把制作版的真实缩略图展示给用户，获得明确同意后才精修。最终交付 NBT 继续由用户明确要求后独立手动导出，见[精修](refinement.md)和[交付](delivery-workflow.md)。
