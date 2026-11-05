# 建筑版本历史与内置 Git

历史库独立放在当前工作区 `.nbtcreator/history/repository.git`，归档文件按 SHA256 放在 `.nbtcreator/history/objects/`。不操作项目根目录自己的 `.git`，不执行 checkout、reset、远程同步、用户 hooks 或仓库别名。便携版带锁定的 MinGit；工作区 Skill 可共享经哈希校验的包内 Git，不要求用户另装 Git。

## 同一份接口

在实际创作工作区调用生成的入口：

```text
python .agents/skills/nbtcreator-workspace/nbt.py history list --workspace . --source <当前主模型>
python .agents/skills/nbtcreator-workspace/nbt.py history record --workspace . --source <主模型> --message <真实修改说明> --actor external_agent
python .agents/skills/nbtcreator-workspace/nbt.py history get --workspace . --id <版本ID>
python .agents/skills/nbtcreator-workspace/nbt.py history current --workspace . --id <版本ID>
python .agents/skills/nbtcreator-workspace/nbt.py history derive --workspace . --id <版本ID> --message <继续制作的说明>
```

`record --request <JSON>` 还可声明 `parent`（已登记的同建筑父版本 ID）、`tasks`（关联任务编号）和 `set_current`。不凭目录日期猜父子关系。版本节点绑定实际源路径、源字节哈希和几何哈希；文件、说明、批注与关联提示词快照进入历史。相同快照重复登记不创建重复提交；普通自动保存不会逐字创建 Git 提交。

手动保存的新版本会登记父版本并更新当前工作版。外部 Agent 的 `agent-tasks record` 自动登记回传版和关联任务，但不自动切换当前工作版，处理声明仍待人工核对。任务、批注和版本记录是独立接口，历史登记不产生批准或替代模型检查。

## 从旧版继续

`derive` 先核对归档文件哈希，再按原建筑的版本规则分配新目录，恢复为 `master/model.snbt`。原版本保留；原版批注、提示词任务、Agent 交接不复制成新版反馈。恢复后的节点指向所选父版本。

原文件被外部覆盖时，旧节点会显示文件不符；仍可从已归档字节另存恢复。归档缺失或被修改时拒绝恢复，不能拿相似文件替代。当前工作版只是编辑选择，不表示定稿、验收或已完成全部标注。

迁移或完整备份工作区时，同时保留 `nbt_models/` 和 `.nbtcreator/history/`。Git 中保存的文本和元数据通过内容哈希引用模型、NBT 与图像归档；只复制 Git 仓库不能恢复这些二进制文件。
