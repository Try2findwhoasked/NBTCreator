# Agent 任务回传与评论核对

外部 Agent 新集成请先读 [机器接口](agent-protocol.md)，使用 machine 统一契约领取、续期与幂等提交。下面的旧命令保留兼容；已领取的任务必须通过机器接口携带 lease_token 与 fence 提交。

用于应用导出修改方案后，由外部 Agent 读取 Skill、生成同一建筑下一版，再回到应用核对。任务登记、Agent 处理声明、人工评论核对及建模批准是不同记录。

## 工作流程

1. 应用生成 Agent 修改方案时，自动建立任务，保存原模型文件哈希、几何哈希、原评论快照以及计划／校验包路径和哈希。任务编号写入“交给Agent.md”。也可在模型编辑的“Agent 回传”中为当前建筑建立任务，此时保存当前相机。
2. Agent 读取工作区 Skill，用 `task-client inspect tasks <任务ID>` 核对源、原评论和保护，再按[机器接口](agent-protocol.md#本地任务客户端)领取指定任务。精修沿用对应缩略图后的真实用户确认。
3. 在同一建筑下另存从原任务源派生的完整制作版。`save_draft` 传入领取会话的 `task_session`；精修命令使用 `--task-session`。用同一会话的 `task-client complete --new-source <完整主模型SNBT> --summary <实际改动>` 回传，可通过 `--comments` 附逐条评论处理说明。回传后若显示 `history_pending`，用 `retry` 补录，不再次回传。
4. 应用“Agent 回传 → 刷新任务与版本”读取登记。“发现同一建筑的新版本文件”只扫描同一对象的文件名和元信息，显示为未核验候选；它不会读取全库模型、自动推断完成或自动登记。
5. 选择已登记回传版，可以在同一镜头查看基准／回传及真实差异。建立任务时有相机则恢复该相机；否则使用开始对比时的相机。切换前后不重新拟合镜头，允许渲染器正常浮点精度误差。结束对比恢复原编辑视角和参数，不把回传版偷偷设成当前编辑模型。
6. 逐项审阅 Agent 声明与原评论，记录“待核对／符合这条要求／仍需修改”和观察备注。没有声明的评论明确显示“未提供说明”。原评论正文、证据与 resolved 状态不变；人工核对不表示整座模型已通过技术、设计或游戏验收。

## 无界面共用接口

入口 `python .agents/skills/nbtcreator-workspace/nbt.py agent-tasks --workspace <项目根目录> <动作> --request <JSON>`。Electron 无需启动，路径优先使用工作区相对路径。

- `list`：`{}` 返回已登记任务；可传 `source`，匹配任务原建筑或已登记回传源。
- `get`：`{"id":"<任务id>"}` 返回当前 revision、原模型与评论快照、Agent 回传及人工核对；读取会核对原模型、登记的原计划／校验包及已登记回传文件哈希。
- `discover`：`{"id":"<任务id>"}` 在同一建筑对象内发现未登记的可能版本，结果 `verified:false`。完整回传登记时才读取真实主模型。
- `create`：`{"source":"<主模型>","source_sha256":"<实际SHA256>","name":"建筑修改任务"}`。可选 camera 为 eye/target/up/fov，可选 origins 最多8个 `{role,path}`，保存实际文件哈希；不从文件名猜批准。
- `record`：下例是历史无租约任务的兼容请求。已领取的任务使用本地任务客户端或 `machine --request`，将 method 设为 `tasks.record`。revision 使用最近一次读取或租约回执的值。
- `review`：仅在用户实际核对并明确要求记录时使用。`{"id":"<任务id>","revision":2,"return_id":"<回传id>","comment_key":"<原评论key>","state":"accepted","note":"真实观察结论"}`。state 为 pending/accepted/rejected；Agent 不可自行制造人工核对。应用点击保存使用相同接口。

```json
{
  "id":"<任务id>",
  "revision":1,
  "new_source":"nbt_models/single/中文名/v02/master/master_geometry.json.gz",
  "new_source_sha256":"<真实新版本文件SHA256>",
  "summary":"说明本版实际修改、验证范围和仍未完成的事项",
  "comments":[{
    "key":"<get返回的原评论key>",
    "content_sha256":"<原评论内容哈希>",
    "status":"addressed",
    "note":"说明修改了哪些实际构件；未处理则说明原因"
  }]
}
```

Agent 声明状态为 addressed/deferred/not_applicable。comments 可以为空，但应用会将未声明的原评论显示为待说明，不能据此宣称全部处理。评论证据未核验、属于不同源几何或已变化时不能沿用旧声明；先读取原始 snapshot／图像并重新建立适当任务，不把截图上的位置直接当作另一几何的坐标。

task 及不可变修订位于原结构版本的 `Agent交接/task-<id>/`；发现索引位于 `nbt_models/_workspaces/agent_tasks/index.json`。内容用相对路径关联，工作区迁移后仍可读取。任务原稿或已登记回传被覆盖时拒绝继续核对，要求保留原版本并重新登记。建立任务后新增评论不自动加入旧快照，应新建任务，以免悄悄改变原修改范围。

目前支持由版本目录组织的完整主模型。若新文件没有符合当前目录规范的对象／版本归属，先按 library new/register 和 output-storage 完成归档，再登记；不自动移动旧文件来制造关联。
