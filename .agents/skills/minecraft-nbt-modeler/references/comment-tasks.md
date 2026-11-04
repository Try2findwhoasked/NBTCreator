# 将标注整理为意见任务

模型编辑的评论区提供“整理意见”，汇总当前源版本在各张图片和3D画面中保存的评论。先选择原评论，再填写任务标题与分类；分类支持构造、材质、通路、光照、道具或自定义文字。任务状态包括待处理、处理中、需核对和已完成；说明可记录阻塞原因，关联冲突任务可记录需要一起决策的事项。

重复候选要求文字、标注位置/画面、3D选中面和引用文件一致。不同图片中的相同文字、不同XYZ或同一方块不同面的意见不会仅因文字相同而合并。“选择重复候选”只帮助选中，用户创建任务后才建立分组。同位置的不同意见会提示人工核对，不把“位置重叠”自动判定为语义互斥。合并任务保留各份原评论与被合并的任务，保留首选任务并回到待处理，便于重新核对新增内容。

任务存放在当前结构版本的 `修改意见/意见任务.json`。每次整理保存操作历史，任务中的原评论按内容指纹复制到 `任务证据/`，图像、快照和效果引用继续沿用已有证据归档。原评论后来更新时会显示提示，任务创建时保留的文字、坐标和引用仍能读取。任务完成状态独立于原评论状态；核对原评论及新版本后再更新相关记录。整理不写NBT、不批准精修，也不代表游戏通行或设计验收通过。

应用与外部Agent共用 `feedback-tasks` 引擎，无需启动Electron：

```text
python .agents/skills/nbtcreator-workspace/nbt.py feedback-tasks --workspace . list --request task-request.json
python .agents/skills/nbtcreator-workspace/nbt.py feedback-tasks --workspace . create --request create-task.json
python .agents/skills/nbtcreator-workspace/nbt.py feedback-tasks --workspace . update --request update-task.json
python .agents/skills/nbtcreator-workspace/nbt.py feedback-tasks --workspace . evidence --request task-evidence.json
```

所有请求包含 `source`（工作区相对路径）和当前 `source_sha256`。list返回原评论、证据指纹、重复/重叠候选、任务、历史和 `revision`。其他请求在同一基础上补充：

- create：当前revision、title、category，以及members数组；每项使用list返回的key和evidence_sha256。创建只接受已核对的评论证据，最多200条。
- update：当前revision、任务id和patch。允许修改title、category、status（todo/working/blocked/done）、reason和conflicts（关联任务id数组）。
- merge：当前revision和至少两个任务id组成的ids；首个为保留任务，其他原任务记录merged_into，原证据不删除。
- evidence：任务id；返回创建时保留的完整原评论、标注、文件引用及重新核对的资产状态。默认每页50份，可用offset和limit（1～100）继续读取，返回total和next_offset。界面原评论与任务列表也按需逐批显示，搜索覆盖整个当前源版本。

不要根据标题猜ID或把旧revision强行覆盖；记录被另一页面/Agent更新时重新list再操作。源文件变化后旧任务显示stale并保留只读，应在新版本重新整理。图像、快照或引用缺失/变化时不能称证据已验证。组内意见、未分组意见和真实源几何分别核对，任务状态不取代原始证据或现有审批流程。
