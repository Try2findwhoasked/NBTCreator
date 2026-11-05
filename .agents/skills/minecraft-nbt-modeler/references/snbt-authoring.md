# SNBT 制作源与 NBT 定稿交付

新建筑制作源使用 `nbt_models/<形状>/<中文建筑名>/<版本>/master/model.snbt`。使用 Java 1.20.1 的 DataVersion 3465、标准 size/palette/blocks/entities 标签；`nbtcreator` 附属数据保存显式墙层与几何指纹。引擎仍以完整模型全局处理，不逐片重建。

调用 `nbt_refine.save_master(<.snbt路径>, model, walls)` 或 `nbt_snbt.save_snbt` 写出后会实际解析回读，核对方块状态、尺寸与墙层。固定坐标排序和一块一行，已有材质表编号保留，新材质追加，减少 Git 中无关差异。旧 JSON.GZ、NBT 继续可读；原文件不会因打开或查看历史而被迁移或删除。

```text
python .agents/skills/nbtcreator-workspace/nbt.py snbt --source <旧主模型> --output <新的model.snbt>
```

CLI `library register --master <旧JSON.GZ/NBT> --name-zh <中文名>` 会保留原稿，并创建/登记 SNBT 制作源。若已经存在不同内容的 SNBT，拒绝覆盖，须使用新版本目录。制作源的中文描述、坐标、显式墙层、预览和正式标注留在原版本。

## 保存制作版

编辑器“保存制作版”先核对当前候选和原保护规则，在新版本目录保存 SNBT、坐标与修改记录，不生成定稿 NBT；同时记录 Git 父版本。`control revision` 的请求可显式设置 `draft_only: true` 使用同一实现。

## 定稿

仅在用户明确要求定稿时调用：

```text
python .agents/skills/nbtcreator-workspace/nbt.py finalize --workspace . --source <已保存制作源>
python .agents/skills/nbtcreator-workspace/nbt.py history finalize --workspace . --id <已登记版本ID>
```

定稿重新检查完整主模型、保护/通路配置，输出到 `nbt_models/_exports/<形状>/<建筑>/<版本>/`，与制作版本保持相同相对层级。目录含 `master/model.nbt`、墙层附属数据、runtime 分片、body/walls 两层、验证结果和 `release.json`。实际从 NBT 回读核对几何，分片重组继续核对；SNBT、批注和证据不移动。重复定稿核对已有产物哈希，拒绝覆盖不同内容。

`_exports` 不作为新的可编辑主模型加入建筑库。后续修改从原制作源或历史节点另存版本，再生成该版本自己的交付目录。定稿不等于游戏实走通过，也不生成 `approval.json`；外部 Agent 不得自行把提示词、批注或任务状态当作精修批准。

当前几何引擎与旧流程一样不处理实体和方块实体；遇到这些数据会明确拒绝转换，不静默丢失。运行环境内置锁定的 SNBT 解析库及 NumPy，无需在用户电脑临时安装依赖。
