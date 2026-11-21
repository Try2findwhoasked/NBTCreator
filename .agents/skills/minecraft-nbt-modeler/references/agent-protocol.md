# 外部建造助手的机器接口

由人手动触发工作区 Skill。应用不自动启动外部 Agent，不自动验收、不自动定稿导出。

统一入口：`mise run nbt -- machine --request request.json`。
用 `machine --schema` 获取当前契约，定义来自 `tool-catalog.json` 的 `machine_protocol`，与 capabilities 共用源。
源码维护时可用 `node scripts/cli.mjs --workspace <创作项目> machine --request <绝对请求路径>`，无需启动 Electron。

请求：

```json
{"protocol_version":1,"request_id":"agent-job-20261106-0001","method":"prompts.claim","params":{"id":"任务ID","owner":"我的建造助手","ttl_seconds":900}}
```

响应始终包含 `protocol_version`、`request_id`、`ok`、`data`、`error`。成功时 error 为 null；失败时 data 为 null，error 包含稳定的 `code`、可读的 `message`、`retryable` 和 `details`。进程成功退出码为 0，失败为 1。未知参数和类型错误直接拒绝。不要通过匹配中文消息决定重试。

## 发现与领取

- `prompts.list` / `prompts.get`：读取人工审查后发布的提示词任务。creation cursor 只发现新增任务；另定期查询 `status: pending`，以接手超时任务。读取完整任务后核对 `source_matches`。
- `tasks.list` / `tasks.get` / `tasks.discover`：读取建筑修改任务、原版本与待登记的新版本。
- `annotations.scan` / `annotations.collect`：独立读取正式批注及证据，不改变任务状态。结构批注仍保存在建筑版本目录。
- `annotation-tasks.list` / `evidence`：读取人工整理的意见分组。create/update/merge 只整理跟进状态，不改写原批注或验收结论。

`prompts.get` 的 `view` 省略时仍返回 `full`。用 `compact` 读取冻结表单摘录、阶段、有效约束、保护区摘要、源匹配状态和同一方案的上一条已发布修订差异。`clipped` 列出超过 240 字的字段。`design_supplement_present` 表示冻结正文包含补充设计说明。需要正文、完整表单、操作计划或坐标时分别使用 `text`、`document`、`plan` 或 `context`。`source_matches` 为 `null` 表示新建任务无既有源。

提示词和建筑修改任务各自支持 claim、heartbeat、release。默认领取 15 分钟，可设置 60～3600 秒；执行期间按租期约三分之一间隔 heartbeat。领取回执给出 `lease_token` 和 `lease.fence`；之后续期、释放和提交都带上这两项。公开 get/list 隐藏令牌。

超时后读取会将执行中任务显示为 pending，下一次领取原子地替换租约并增加 fence。超时执行者无法续期或提交，即使它后来恢复运行。`prompts.task-status` 登记 completed 后结束租约；`tasks.record` 登记新版本后标记 completed 并结束租约；后续修改应由人根据审查意见建立新任务。任务完成/版本登记均不等于人工验收。

建筑修改任务的租约释放或到期后，同一建筑可普通另存制作版。已领取过的任务仍要求有效租约才能登记回传。修改计划、保护配置或其他绑定来源变化时停止制作和回传，原持有者可用 `task-client --session <会话名> release` 释放租约，之后核对来源并建立新任务。原持有者不可用时，等租约到期后再继续。另存仍检查父版本，可能需要从最新版本重新打开模型。

`tasks.record` 还需携带 get/claim/heartbeat 回执的最新 `revision`；`prompts.task-status` 可携带 `expected_revision`（使用 `state_revision`，不是内容摘要 revision）。意见分组写操作使用其最新 revision。冲突时重新读取并由调用者核对新状态，不盲目重试旧意图。

## 幂等与恢复

建筑修改任务清单损坏时，`task-client list` 的 `issues` 会指出登记文件、索引保存的 SHA256 和恢复命令。执行 `task-client recover-registration <任务ID> --expected <SHA256> --request-id <固定编号>`。恢复先核对当前修订，尝试从原 JSON 的规范编码、登记时的本地副本或 `--backup <nbt_models 内的备份>` 取回匹配哈希的完整原文。成功后索引指向新文件，旧文件留存，原令牌、租期和 fence 继续生效。已释放或已过期的租约允许普通另存。缺少可信原文时保留阻断，可找回当前修订的备份再试。

机器写操作必须提供 16～128 位字母、数字、横线或下划线组成的 request_id。一次逻辑操作固定一个编号；网络中断、进程退出或响应丢失后，使用**原编号及完全相同的参数**重试。业务索引与回执索引同一次原子替换，成功重试返回原结果，不新增版本登记或重复任务。相同编号但不同操作/内容返回 IDEMPOTENCY_CONFLICT。

编号作用域是对应任务索引（提示词任务、建筑修改任务或某建筑版本的意见分组），建议全局使用 UUID 避免误用。新意图、修改参数、重新领取、每次续期均使用新编号。重复原领取请求返回原令牌和原到期时间，不会延长租约；到期后必须以新编号领取。

业务失败未提交时不会保存成功回执。回执文件按内容哈希保存，缺失或改动时拒绝重放；索引上限 20000 项，不自动删除仍可能重试的记录。迁移工作区后，相对路径保持有效，重放返回的 absolute_source 按新根目录计算。读取/审查时仍需重新核对源文件；回执只证明曾经提交成功，不证明当前文件未变化。

LEASE_EXPIRED、TASK_CLAIMED 和 REVISION_CONFLICT 的 retryable 表示可以重新读取状态后继续协调；不是允许自动覆盖。LEASE_NOT_OWNER、LEASE_FENCE_CONFLICT 不应继续写入。人工核对仍使用应用独立入口，机器接口不提供自动批准方法。旧命令保留兼容，已纳入租约的任务必须通过机器入口携带有效凭据提交。

## 本地任务客户端

从已同步 Skill 的创作项目根目录执行。`inspect` 是只读命令，`start` 领取明确指定的任务。用 `--session` 区分并行任务，各命令使用同一会话名。省略时使用 `default`。

```powershell
mise run nbt -- task-client inspect prompts <任务ID>
mise run nbt -- task-client inspect prompts <任务ID> --view text
mise run nbt -- task-client --session room-a start prompts <任务ID> --owner <执行者>
mise run nbt -- task-client --session room-a status
```

- 用 `task-client list --pending` 查找两类待领取任务，或用 `task --id <任务ID> --view compact` 自动识别类型。只读视图标记损坏的绑定附件，仍可显示其他已核验内容。看到 `next.action: stop` 时停止执行，已领取的原会话可释放。即使原模型已丢失，`task-client inspect tasks <旧任务ID> --view candidates` 仍会列出该建筑下的未登记文件。找到文件后须能核对原模型、候选父链和当前目标任务的来源。亲缘缺失时，找回原修订，或从目标任务源重新派生。

- 长任务可在另一终端运行 `task-client --session room-a keepalive`。它约每三分之一租期续租，正常完成或释放后退出。短任务可按需调用 `renew`。重启终端后还可用同一会话名继续续租，未到期的租约继续有效。
- 初稿或精修提示词任务用 `task-client --session room-a complete --review <新制作版审阅目录>`，绑定完整制作源、验证记录和审阅图，仍待人工核对。只读计划用 `complete --summary <检查结果与未验证事项>`，不写制作版。发布同一方案的新修订会使未完成的旧任务及其租约失效。
- 建筑方案已通过 `architect review-record` 登记三尺度实图和观察时，把含 `review-pack.json` 和 `review-notes.json` 的目录传给同一个 `complete --review` 命令。机器接口用 `review_kind: "architecture"`，并把 `review_sha256` 设为观察记录回执的哈希。回传会重核制作源、观察修订和图片；原有精修批准和游戏实测入口仍按各自流程执行。
- 建筑修改任务用 `start tasks <任务ID> --owner <执行者>`；保存受管制作版时在 `save_draft` 中传入 `task_session`（Python 同名参数；精修命令用 `--task-session`）。在同一会话以 `complete --new-source <新版本SNBT> --summary <真实改动说明>` 回传。有逐条评论处理时加 `--comments <JSON文件>`。放弃时执行 `release`；如果回传后显示 `history_pending`，执行 `retry` 只补写历史，不重新回传模型。
- 中断或响应不明时先 `status`。看到 `pending` 时用 `retry` 重放原编号及原参数。租约失效、源变化、修订冲突时重新读取当前任务，由执行者核对后决定下一步。客户端状态保存在本工作区 `nbt_models/_workspaces/agent_protocol/clients/`，活跃会话的状态文件含租约令牌，仅在本机保留。

### 将未登记候选回传到新的修改任务

目标任务应有当前的计划附件（`origins` 中的 `role=plan`）。有建筑方案的制作版用自己的三尺度审阅目录，目标任务的计划须与该制作版执行的方案一致。其他受管制作版可使用全景和入口缩略图，其计划哈希须与旧任务匹配，并通过 `--observations <工作区文件>` 提供 JSON 数组，每张缩略图对应一条含 `image_sha256` 和 `note` 的实际观察。

1. 运行 `task-client check-candidate <目标任务ID> --from-task <旧ID> --new-source <制作源> --review <审阅目录>`，检查返回的两项任务、父版本、计划、制作源、图片和观察指纹。此步骤只读。
2. 领取目标任务后，运行 `task-client --session <会话名> reuse-candidate --from-task <旧ID> --new-source <制作源> --review <审阅目录> --expected <上步 binding_sha256> --summary <实际改动>`。普通缩略图两次均带同一份观察。登记会重新核验全部证据，检查目标租约、fence 和修订，再返回待人工核对状态。机器接口使用 `tasks.revalidate` 和 `tasks.reuse`。

通过任务会话保存的新版本会在本地留下任务编号、fence 和原稿哈希。普通回传只接收当前领取制作的受管版本。历史受管版本可凭父链、同一计划及候选自身的新鲜审阅核验后登记。早期工具产生的裸文件在有多个交接任务或多轮领取时缺少归属凭据，请从合法任务的原稿重新派生。

## 内置 AI 的并发

AI 设置可选同时运行 1～4 个生成请求，默认 2。超过数量的请求等待空位，最多接收 64 个未完成请求。每个请求固定输入、所选资料与工作区上下文，有自己的取消信号和超时计时；点击终止会立即结束界面等待，中断本地请求/预检并丢弃迟到结果；记录清理在后台完成。取消其中一条不影响其他条。远端服务是否同步停止计算取决于其对断连的处理。切换工作区会取消旧区所有请求并等待它们退出。

批量编写按建筑分配独立草稿，完成后分别自动保存，失败项可单独重试；生成完成仍须人逐条审查再交接。并发只覆盖生成阶段，同一建筑的采用、预览、保存继续依次执行。
