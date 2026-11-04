# 项目多选与批量任务

项目管理上方“多选”启用卡片勾选，点击卡片改为选择，不会打开编辑器。可选当前页或全部筛选结果，最多100个版本；切换筛选、翻页后保留选择，清空或退出多选时清除。刷新发现文件变化会取消该版本的旧选择，避免给新版误标状态。

“批量”浮层提供截面预览、文件与路线检查，以及创作阶段标记。阶段标记调用同一 project-stages 保存接口，只影响选中的当前文件；失败项保留选择以便重试。标记已精修/已定稿只是进度管理，不产生看图确认、批准或验收记录。

## 预览与检查

队列逐版本处理，浏览时不预读全部模型。截面预览复用 `.nbtcreator/cache/section-covers`；缺图时生成简化材质的截面，不改 NBT。检查先实际读取主模型、合法状态和墙层资料，再在有有效坐标资料时调用既有几何/密闭与声明路线验证。缺坐标资料或不支持的结构会列出原因，不把“文件能读”当作路线通过，也不检查审美或认证游戏运行。

每项可下载独立报告，看到已完成、未通过、等待、运行和停止状态。一个版本失败不会停止其他版本。重试只重跑未完成项，并按当前文件重新记录尺寸/时间戳；原来的报告保留在任务目录。成功项不重复执行。

队列保存在工作区 `.nbtcreator/project-queues/<编号>/`，源路径和报告引用使用相对路径。关闭任务弹窗仍会继续；应用停止可终止工作进程并保留已完成项。重启不会自动执行旧队列，打开“批量任务”后可选择重试。真实操作系统文件锁限制同工作区同时只有一个批量执行器，进程退出后可恢复，不凭残留 PID 或锁文件猜测运行状态。

## Agent 无界面接口

```powershell
python .agents/skills/nbtcreator-workspace/nbt.py project-batch create --request 批量任务.json
python .agents/skills/nbtcreator-workspace/nbt.py project-batch run --id <编号>
python .agents/skills/nbtcreator-workspace/nbt.py project-batch get --id <编号>
python .agents/skills/nbtcreator-workspace/nbt.py project-batch list
python .agents/skills/nbtcreator-workspace/nbt.py project-batch retry --id <编号>
python .agents/skills/nbtcreator-workspace/nbt.py project-batch run --id <同一编号>
python .agents/skills/nbtcreator-workspace/nbt.py project-batch cancel --id <编号>
```

`批量任务.json` 示例：

```json
{
  "sources": [
    {"source": "nbt_models/single/石构厅/v1/master/master_geometry.json.gz", "label": "石构厅"}
  ],
  "actions": ["preview", "check"]
}
```

actions 可为 `['preview']`、`['check']` 或 `['preview','check']`。默认工作区是 Agent 当前目录，也可在子命令前传 `--workspace`。仅接受工作区 `nbt_models/` 内的本地文件，不接受脚本、任意命令或输出路径。run 是同步执行，另一个 CLI 进程可 get 查看进度；CLI cancel 请求在当前项结束后生效，应用停止按钮可终止当前工作进程。

进程正常结束表示队列已处理，仍须检查 `progress.failed` 和每个 step 的状态；`status=complete` 不表示所有检查通过。所有接口只生成缓存与报告，`asset_written`、`approval_created` 均为 false；不能通过此工具批量精修、导出建筑或自动定稿。

## 待修复结构与归类

项目卡片对 bugged 或不可读取模型开放“尝试修复并归类”。该入口独立于上面的只读批量队列；归类是保存新候选副本，不移动或覆盖隔离区原件。可选择分类，auto优先沿用原目录或room_description中的有效shape，无可靠分类时使用standalone，不按尺寸猜测建筑拓扑。

```powershell
node scripts/cli.mjs --workspace D:/MyProject project-repair --source nbt_models/bugged/对象/source.master.json.gz --category auto
python .agents/skills/nbtcreator-workspace/nbt.py project-repair --source nbt_models/bugged/对象/source.master.json.gz --category square
```

应用和CLI共用 nbt_project_repair.repair。可恢复过期/缺失几何哈希、同坐标同材质重复记录，以及能明确读取为体素的Java1.20.1结构NBT。拒绝冲突重复、非法方块状态、越界、指向空气的墙mask、实体/方块实体、多套调色板和版本转换；不丢弃资料以换取成功。源文件和新候选回读、几何与墙层保持一致后才入库。缺少坐标/通路/开口资料时仍需人工补齐，recovered_candidate不代表通过设计、路线或游戏验收。只写新主模型，NBT须之后明确导出。

新候选保存于 `nbt_models/<分类>/recovered_<名称>/repair_<编号>/`；逐次报告保存在 `.nbtcreator/repairs/<编号>/report.json`，包含原文件SHA256、实际处理项、分类依据、候选或失败原因。可传 `--source-sha256` 绑定已知版本。CLI失败保留JSON报告并返回非零退出码。仅接受当前工作区nbt_models内的源文件。

项目页“生成并加载缩略图”处理本次筛选结果（不可读取项除外），复用现有哈希缓存，最多同时生成两项，可停止排队。分页默认滚动追加24项；手动按钮继续可用。缩略图不构成真实用户看图确认，也不修改主模型。
