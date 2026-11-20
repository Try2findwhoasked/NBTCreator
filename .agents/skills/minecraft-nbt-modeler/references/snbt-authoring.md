# SNBT 制作源与 NBT 定稿交付

新建筑制作源使用 `nbt_models/<形状>/<中文建筑名>/<版本>/master/model.snbt`。使用 Java 1.20.1 的 DataVersion 3465、标准 size/palette/blocks/entities 标签；`nbtcreator` 附属数据保存显式墙层与几何指纹。引擎仍以完整模型全局处理，不逐片重建。

调用 `nbt_refine.save_master(<.snbt路径>, model, walls)` 或 `nbt_snbt.save_snbt` 写出后会回读真实文件，核对解析后的方块状态、尺寸与墙层。固定坐标排序和一块一行，已有材质表编号保留，新材质追加，减少 Git 中无关差异。旧 JSON.GZ、NBT 继续可读；原文件不会因打开或查看历史而被迁移或删除。

同一 Python 进程按实际 SNBT 字节的 SHA256 复用已解析内容，最多8项、估算驻留大小64MiB。保存时核验过的临时文件与改名后的相同内容共用解析结果，连续安装无需因路径变化再次解析整栋模型。每次打开仍读取真实文件、核对大小和内容；同尺寸或同时间戳不能复用不同内容。返回的方块、墙 mask、材质表和附加标签均与缓存隔离。此缓存不跨进程，不替代源/上下文哈希、保护、碰撞及看图检查。

```text
python .agents/skills/nbtcreator-workspace/nbt.py snbt --source <旧主模型> --output <新的model.snbt>
```

CLI `library register --master <旧JSON.GZ/NBT> --name-zh <中文名>` 会保留原稿，并创建/登记 SNBT 制作源。若已经存在不同内容的 SNBT，拒绝覆盖，须使用新版本目录。制作源的中文描述、坐标、显式墙层、预览和正式标注留在原版本。

## 保存制作版

编辑器“保存制作版”核对候选和原保护规则后保存 SNBT、坐标、修改记录和版本历史。`control revision` 默认保存制作版，等同于 `draft_only: true`。仅当用户明确要求将当前参数效果定稿时，才用 `draft_only: false`。

## 定稿

审阅时用 `finalize --source <已保存制作源> --inspect-inputs` 记录 `source_sha256` 和 `inputs_sha256`；后者同时绑定主模型、保护配置、外部墙层和受管清单。只读检查不会导出。仅在用户明确要求定稿时，使用审阅时保留的哈希，不要用重新计算的哈希替换失效审阅：

```text
python .agents/skills/nbtcreator-workspace/nbt.py finalize --workspace . --source <已保存制作源> --source-sha256 <source_sha256> --inputs-sha256 <inputs_sha256>
python .agents/skills/nbtcreator-workspace/nbt.py history finalize --workspace . --id <已登记版本ID> --inputs-sha256 <inputs_sha256>
```

受管建筑须保存为 `opened` 阶段才能定稿。要求密闭的建筑先对原始未开洞主模型执行 `seal`，再执行 `open_declared`。无声明洞口时，仍用 `open_declared` 进入完整验证阶段。定稿回读并复查清单绑定的原始封闭证据，有证据时在验证报告中记录 `preopening`。旧式源没有制作阶段清单时，继续按保存的坐标约束检查；重盖洞口得到的密闭报告只证明复验模型的围护。

定稿重新检查完整主模型和坐标约束，再在临时目录生成并回读完整 NBT、运行分片及 body/walls 两层。通过后发布到 `nbt_models/_exports/<形状>/<建筑>/<版本>/`，其中包含 `master/model.nbt`、墙层附属数据、验证结果和 `release.json`。实际参与校验的配置随包写入 `coordinates.json`，交付版描述通过相对路径引用它。重复定稿核对制作源、坐标约束、二进制墙层附属文件以及交付文件的哈希。

`_exports` 不作为新的可编辑主模型加入建筑库。后续修改从原制作源或历史节点另存版本，再生成该版本自己的交付目录。定稿不等于游戏实走通过，也不生成 `approval.json`；外部 Agent 不得自行把提示词、批注或任务状态当作精修批准。

转换遇到实体或方块实体会拒绝。引擎随包提供锁定的 SNBT 解析库。Python 与 NumPy 依赖按项目的运行环境配置安装。
