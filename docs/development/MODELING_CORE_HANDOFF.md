# 建模内核改造交接

本页说明建模内核的版本事务、机器接口和外置教程知识包的接入方式。

## 版本、审阅和恢复

旧 `model` CLI、公开 `nbt_working_model` 导入和桌面编辑调用同一 `WorkingModel`。单体 SNBT 与组装清单共用全局 XYZ、方块状态归一化、墙层归属、保护和路线校验。`nbt_project/model_versions.py` 管理发布锁、不可变版本校验、头指针与 Git 历史补登。历史派生在暂存区回读后发布，沿用旧目录命名和父链。

| 状态 | 行为 |
| --- | --- |
| 制作版目录已写入，历史登记失败 | 保存返回 `history_pending`。重放可补登原版本及其缺失的父链。 |
| 目录已就位，头指针未更新 | 用原请求恢复，仍适用原父版本和任务租约检查。后来产生的头指针优先。 |
| 版本已发布，机器回执未写入 | 从请求登记的目录及修订读回结果。已完成请求按内容哈希读取原回执。 |
| 两个新候选源于同一父版 | 发布锁内核对父版。胜出的子版本成为当前头，另一个收到 `STALE_PARENT`。 |
| 历史中有旧稿或源文件损坏 | 可从已归档字节派生。复制与回读失败时不会出现半成品版本目录。 |

`model.preview` 发布待审阅的临时主稿和机位。交给渲染器时传递 `source`、`source_sha256`、`cameras` 和 `cameras_sha256`，并对照真实渲染清单。人工缩略图确认继续通过原审阅入口记录。正式 NBT 仍由显式 `finalize` 入口生成，候选提交只产生制作版。

## MCP 和桌面调用约定

从源码根目录运行 `mise run nbt -- --workspace <创作工作区> machine --request <UTF-8 JSON>`。`machine --schema` 随工具目录生成方法定义。传输保留 `protocol_version: 1` 和 `request_id/ok/data/error`。`params.model` 复用 `working_model.parameters` 与 `working_model.actions`，包含新建 `size` 或现有 `source` 和 `source_sha256`。路径优先使用工作区相对路径。写操作各用一个 16–128 字符的 `request_id`。

| 方法 | 请求字段 | 回执要点 |
| --- | --- | --- |
| `model.inspect` | `model`，可含 `positions` | `model.samples[].value` 为 `[规范方块状态, 墙层布尔值]`，`source` 包含原制作源、哈希、修订和 `source_kind`。 |
| `model.candidate` | `model`，可含 `actions` | `candidate_sha256`、`model.model_sha256`、`diff`、`validation`。差异包含几何格数、墙层格数及最多 32 个全局位置样本。 |
| `model.preview` | 同一 `model`、`candidate_sha256`、`cameras` | `source`、`snapshot`、`cameras` 及各自 SHA‑256，`source_kind` 为 `master` 或 `assembly`。`visual_review` 为 `pending`。 |
| `model.commit` | 同一 `model`、`candidate_sha256`、`save`，可选 `task_session` | `source`、`source_sha256`、`revision`、`history_pending`、`draft_only`。`task_session` 引用已领取的本地修改会话。 |

最小候选请求如下。预览沿用同一 `model` 和指纹，加入机位数组。新建筑提交在 `save` 中提供 `name_zh`，续版可用原有名称。模型操作里的预览路径应改用 `model.preview` 的服务分配目录。受限分区会话继续由 `authoring.*` 处理。

```json
{"protocol_version":1,"method":"model.candidate","params":{"model":{"size":[8,6,8],"kind":"component"}}}
```

```json
{"protocol_version":1,"request_id":"handoff-preview-0001","method":"model.preview","params":{"model":{"size":[8,6,8],"kind":"component"},"candidate_sha256":"<上一步返回值>","cameras":[{"id":"overview","eye":[10,7,10],"target":[2,1,2]}]}}
```

恢复连接后用完全相同的 `model.commit` 参数和原 `request_id` 重试。`STALE_CANDIDATE` 需要重算候选，`STALE_SOURCE` 需要重读源和哈希，`STALE_PARENT` 需要核对当前版本后产生新的候选。相同编号承载不同内容返回 `IDEMPOTENCY_CONFLICT`。受管文件或预览回执损坏可返回 `RECEIPT_CHANGED`。`PROTECTED_SPACE`、`CHANGE_BUDGET`、`ROUTE_FAILED` 等保留位置、计数或冲突内容，调用方可用 `error.code` 和 `error.details` 建立诊断。

## 教程知识包

知识线发布 `knowledge.json` v1 与 `cards/*.md`。库 ID 为 `minecraft-tutorials`，发布版本采用 `MAJOR.MINOR.PATCH`。引擎验证清单、卡片路径及 UTF‑8 字节、卡片 SHA‑256、审核元数据和证据定位。登记和查找只访问本地目录，离线 SQLite 索引位于创作工作区。

`retrieve library` 的 `add`、`list` 返回 `package_kind`、`package_id` 和 `package_version`。`retrieve search/source/bundle/read` 沿用 `reference_type: architecture_library` 和原有出处绑定，并在教程结果中增加 `tutorial`。界面可从中取 `card_id`、`confidence`、`review_status`、`applicability` 与 `evidence[].locator`。`evidence[].path` 表示知识生产侧原始资料库的相对位置。现有书库和已保存的旧引文兼容。若曾用旧引擎给标记为教程包的版本建索引，从 `retrieve library` 显式执行 `build` 即可迁移索引。

在外部 Agent 范围内，检索回执和引用集合可通过以下请求衔接。内部 UI 仍可使用 `document_id`、`manifest_sha256`、`sha256` 读取出处。

| 操作 | 最小请求 |
| --- | --- |
| `library` | `{"workflow":"prompt","action":"add","path":"<已发布的本地版本目录>"}` |
| `search` | `{"workflow":"prompt","source_kind":"library","query":"屋顶坡度"}` |
| `source` | `{"workflow":"prompt","receipt":"<search.receipt>","ref":"<search.knowledge[].ref>"}` |
| `bundle` | `{"workflow":"prompt","receipt":"<search.receipt>","selected":["<search.knowledge[].ref>"]}` |
| `read` | `{"workflow":"prompt","id":"<bundle.id>","sha256":"<bundle.sha256>"}` |

## 验证入口

在源码根目录运行以下命令。桌面与 MCP 预览共用预构建前端。

```powershell
mise run check
mise run build:web
mise run test -- agent-protocol
mise run test -- model-workflow
mise run test -- large-assembly
mise run test -- retrieval
```

可在独立创作工作区登记外置教程包，依次核对检索、原文、选集和回读。回读结果可用原文行号和片段哈希复核。组装回归覆盖跨分区楼梯通路、制作版本恢复、同请求重放和实纹理渲染。
