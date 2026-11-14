# 外部建造助手的机器接口

由人手动触发工作区 Skill。应用不自动启动外部 Agent，不自动验收、不自动定稿导出。

统一入口：`python .agents/skills/nbtcreator-workspace/nbt.py machine --request request.json`。
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

提示词和建筑修改任务各自支持 claim、heartbeat、release。默认领取 15 分钟，可设置 60～3600 秒；执行期间按租期约三分之一间隔 heartbeat。领取回执给出 `lease_token` 和 `lease.fence`；之后续期、释放和提交都带上这两项。公开 get/list 隐藏令牌。

超时后读取会将执行中任务显示为 pending，下一次领取原子地替换租约并增加 fence。超时执行者无法续期或提交，即使它后来恢复运行。`prompts.task-status` 登记 completed 后结束租约；`tasks.record` 登记新版本后标记 completed 并结束租约；后续修改应由人根据审查意见建立新任务。任务完成/版本登记均不等于人工验收。

`tasks.record` 还需携带 get/claim/heartbeat 回执的最新 `revision`；`prompts.task-status` 可携带 `expected_revision`（使用 `state_revision`，不是内容摘要 revision）。意见分组写操作使用其最新 revision。冲突时重新读取并由调用者核对新状态，不盲目重试旧意图。

## 幂等与恢复

机器写操作必须提供 16～128 位字母、数字、横线或下划线组成的 request_id。一次逻辑操作固定一个编号；网络中断、进程退出或响应丢失后，使用**原编号及完全相同的参数**重试。业务索引与回执索引同一次原子替换，成功重试返回原结果，不新增版本登记或重复任务。相同编号但不同操作/内容返回 IDEMPOTENCY_CONFLICT。

编号作用域是对应任务索引（提示词任务、建筑修改任务或某建筑版本的意见分组），建议全局使用 UUID 避免误用。新意图、修改参数、重新领取、每次续期均使用新编号。重复原领取请求返回原令牌和原到期时间，不会延长租约；到期后必须以新编号领取。

业务失败未提交时不会保存成功回执。回执文件按内容哈希保存，缺失或改动时拒绝重放；索引上限 20000 项，不自动删除仍可能重试的记录。迁移工作区后，相对路径保持有效，重放返回的 absolute_source 按新根目录计算。读取/审查时仍需重新核对源文件；回执只证明曾经提交成功，不证明当前文件未变化。

LEASE_EXPIRED、TASK_CLAIMED 和 REVISION_CONFLICT 的 retryable 表示可以重新读取状态后继续协调；不是允许自动覆盖。LEASE_NOT_OWNER、LEASE_FENCE_CONFLICT 不应继续写入。人工核对仍使用应用独立入口，机器接口不提供自动批准方法。旧命令保留兼容，已纳入租约的任务必须通过机器入口携带有效凭据提交。

## 内置 AI 的并发

AI 设置可选同时运行 1～4 个生成请求，默认 2。超过数量的请求等待空位，最多接收 64 个未完成请求。每个请求固定输入、所选资料与工作区上下文，有自己的取消信号和超时计时；点击终止会立即结束界面等待，中断本地请求/预检并丢弃迟到结果；记录清理在后台完成。取消其中一条不影响其他条。远端服务是否同步停止计算取决于其对断连的处理。切换工作区会取消旧区所有请求并等待它们退出。

批量编写按建筑分配独立草稿，完成后分别自动保存，失败项可单独重试；生成完成仍须人逐条审查再交接。并发只覆盖生成阶段，同一建筑的采用、预览、保存继续依次执行。
