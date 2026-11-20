# 本地参考检索与构件复用

用途：按当前任务搜索工作区资产、挑选相关资料片段，并保留可追溯的出处。应用模型编辑、提示词方案及资产创作的“检索本地参考”，与外部 Agent 的 `retrieve` 命令使用同一 Python 实现。检索不调用 API，不授予建模、精修批准或导出权限。

## 检索范围与人工选择

- 资产复用用于 `component`（资产管理的独立结构创作）：按名称、标签和目标 XYZ 尺寸匹配，排除回收站，必要时建议绕 Y 旋转 90°；不隐式缩放或裁切。匹配只是建议，实际方块朝向、碰撞与位置由结构预览引擎再次检查。
- 外部 CLI 默认检索对外 Skill 已启用的知识组和自定义文档；内置 AI 检索只读该工作流勾选的内部资料。两者都可查本工作流启用的书库与网页收藏。阅读范围不会自动变成 API 发送授权。
- `knowledge_errors` 标出已启用但无法读取的自定义资料。其他命中和回执仍可使用。若回执引用了缺失文档，先在「AI 与知识库 → 外部建造助手」恢复原文件或重新导入，再检索或核对原回执。停用或移除登记会撤回引用资格，移除登记保留文件。
- 资料按标题和任务词匹配，每份最多推荐两段，显示原文行号、内容 SHA256、匹配理由及完整原文入口。长行会明确标为截取；片段不代表已经阅读整份文档。
- 用户勾选 1～16 项后，保存为本次工作流的参考集合。下一次该工作流生成会发送已选片段，代替其默认资料；其他流程不沿用它。本次选择保留在当前应用会话；集合文件与保存资产的来源配方随工作区保留。未使用检索集合时，读取该工作流勾选的资料：短文全文发送，长文在本地按本次要求选取相关片段并标记省略，正文总预算12000字、单篇最多4000字；去除内容完全相同的重复资料。规则和用户补充要求保持完整。已明确选择并校验哈希的检索集合不再二次摘取。

资产只向模型发送编号、内容哈希、名称、尺寸、锚点及少量材质信息，不发送完整体素或本地绝对路径。资料只发送所选片段及编号、标题、行号与哈希。应用把这些显示为“本次提供的参考”，不声称模型已经采纳。实际引用的资产由返回 placements 和其真实哈希核对，不能猜 ID 或冒用其他资产。

## 无界面接口

从创作项目根目录按 `SKILL.md` 的前缀运行。`--request` 接收 **UTF-8 JSON 文件路径**，不是把 JSON 直接接在参数后；也可传 `-` 从标准输入读取。PowerShell 例子：

```powershell
$request = Join-Path $env:TEMP 'nbt-reference-query.json'
'{"workflow":"prompt","query":"飞扶壁 拱顶推力","source_kind":"library","limit":3}' | Set-Content -LiteralPath $request -Encoding utf8
mise run nbt -- retrieve search --request $request
```

建筑方案参考使用 `prompt`，独立构件使用 `component`。以下是同时匹配构件资产和参考摘录的 `search` 请求。

```json
{"workflow":"component","query":"水渠桥 支承","size":[4,6,10],"limit":12}
```

返回 `assets` 与 `knowledge`（各默认最多 6 条，`limit` 为 1～32，每文档至多两段），以及本次 `receipt`。各条有简短出处和 `ref`（如 `R1`）；没有命中时 `receipt` 为 `null`。查历史资料传 `source_kind:"library"`，无需抄书库编号；只查 Skill 文档或已收藏网页分别传 `"skill"` 或 `"web"`。有多个库时可再用 `library_id` 指定。书库使用 `query` 前 300 字，`filters` 支持 `style`、`region`、`year:[起始年,结束年]`。检查 `library_errors` 区分无匹配与来源不可用。

`source` 请求 `{"workflow":"component","receipt":"<检索回执>","ref":"R1"}`，默认从命中行附近读取不超过 12000 字。继续阅读传 `line` 为返回的 `next_line`；确需整篇才加 `full:true`。网页引用直接返回已保存的原页、章节和短摘录，不造行号。每次仍校验当前范围与原文。

`bundle` 请求 `{"workflow":"component","receipt":"<检索回执>","selected":["R1","R2"]}`，不重跑检索，但仍回查选中证据。返回 `id`、`sha256`、出处、片段与资产元数据。可在 `selected` 混入本流程的 `web:` 证据号。旧版带查询和长编号的请求也可读。回执与集合保存在工作区 `.nbtcreator/retrieval/`，不保存安装绝对路径。两个阶段的 `R1` 各自独立，最终引用以集合返回的 `citation` 为准。

`read` 请求 `{"workflow":"component","id":"<集合id>","sha256":"<集合SHA256>"}`，重新核验集合和来源，并回显已验证的 `id` 和 `sha256`。内置 AI 交接的集合用 `retrieve read --audience internal_ai --request <JSON文件>` 核对，旧集合也使用此范围；外部集合不可直接提交给内置 AI 生成。先区分哈希不匹配和来源已变，再重试，不静默改绑。

来源的 R1、R2 等编号仅对应当前集合；跨集合引用时同时保留集合 ID 与 SHA256，不只复制一个 R 编号。外部 Agent 可完整读取本文件和实际使用的建模专题，再用集合元数据与 `structure_read` 读取选中资产。

## 复用与适配

从历史书籍或图版摘出构件名、别名后，可另用 `asset-libraries browse --request <JSON文件>`。把 `{"query":"尖拱","limit":4}` 写入 UTF-8 请求文件，再传文件路径，不要传内联 JSON 或省略 `query`（会列出完整目录）。该命令离线查捆绑和已连接的资产，返回用于进一步回读和预览的 `id`、`source_id`、版本与哈希，不返回完整配方。历史证据、资产候选和当前建筑的实际检查分别记录，不能互相代替。

独立结构继续使用共用 `components agent --tool structure_preview`。将 bundle 编号作为 `reference_bundle` 传入，预览时再核验来源；来源说明随候选哈希绑定，并在显式保存新资产后保留到 `.nbtcreator/components/recipes/<新资产id>.json`。不覆盖旧资产。之后独立查看该资产时会显示保存时的来源记录，并明确其为历史记录，不表示来源仍启用或未发生变化。

```json
{
  "reference_bundle":{"id":"<集合id>","sha256":"<集合SHA256>"},
  "spec":{
    "name":"金色水渠桥",
    "size":[4,6,10],
    "placements":[{
      "id":"<原构件id>",
      "content_sha256":"<原构件内容哈希>",
      "position":[1,0,4],
      "quarter_turns":1,
      "material_map":{"minecraft:stone_bricks":"minecraft:gold_block"}
    }]
  }
}
```

position 是原资产锚点在目标空间中的坐标，quarter_turns 是绕 Y 的 90° 次数，可按原协议镜像。material_map 最多 32 项，把原始规范方块状态映射到新状态，在旋转前应用；所有状态仍由注册表验证，旧资产及其哈希保持不变。不合适时应调整方案或新建结构，不强行挤入尺寸。

## 外部建筑书库

桌面“检索本地参考 → 本地书库 → 连接书库”选择目录后，在当前工作流启用并建立离线索引。其他工作流可以针对同一书库另行启用。原文留在所选目录，索引写在当前创作工作区的 `.nbtcreator/retrieval/libraries/`。以相对路径登记的书库随工作区一起移动。更新清单或原文后，使用“更新索引”。源不可读或校验失败时保留已有索引，检索跳过不可核验的来源。

Agent 在创作项目根目录调用 `mise run nbt -- retrieve library --request <JSON文件>`。`workflow` 必填，`path` 支持绝对目录或相对于创作根目录的目录。运行 `list` 查看连接编号、启用状态和索引状态。

| action | 请求示例 |
| --- | --- |
| `list` | `{"workflow":"prompt","action":"list"}` |
| `add` | `{"workflow":"prompt","action":"add","path":"reference-books","name":"建筑书库"}` |
| `build` | `{"workflow":"prompt","action":"build","id":"<连接编号>"}` |
| `enable` | `{"workflow":"component","action":"enable","id":"<连接编号>","enabled":true}` |
| `remove` | `{"workflow":"prompt","action":"remove","id":"<连接编号>"}`。移除连接后保留原文和工作区索引文件 |

兼容既有 `books.json` 和 `illustrated-originals.json`。图版索引供看图，本地全文检索使用电子文本。自建库在选定目录提供 `knowledge.json`，顶层包含 `schema_version:1`、`id`、`version`、`documents`。每个文档需要 `id`、`title`、`file`、`bytes` 和 `sha256`，可选 `author`、`edition`、`year`、`language`、`region`、`styles`、`source` 和 `license`。`id` 由小写字母、数字、`-`、`_` 组成，以字母或数字开头。`file` 为库内相对的 UTF-8 `.md` 或 `.txt`。`source` 使用可直接打开的公开原页地址。文档样例见现有建筑书库目录的 `books.json` 对应字段。

索引以章节和原文行切分，支持中文双字词项和中英建筑术语扩展。风格标签绑定到书或文档，综合性著作的命中仍需核对章节。选入 `bundle` 后，书库集合记录原文、清单和片段的 SHA256，生成前验证出处和当前工作流授权。早期本地参考集合沿用原格式。

在 NBTCreator 源码根目录下载和建索引：

```powershell
mise run knowledge:fetch
mise run knowledge:index
mise run nbt -- retrieve architecture --library workspace/architecture-knowledge search "飞扶壁 尖拱" --style gothic --limit 4
```

单次历史书库查询继续用 `mise run nbt -- retrieve architecture --library <书库目录> search <部位或做法>`，用 `source --book <编号>` 查原文位置，用 `build` 重建该目录的旧式索引。资料下载为单独操作，查询无需 API 或网络。历史著作可能使用过时分类，方块尺度、可用资产和安装效果按主模型工具验证。

## 联网补查

用户明确要求查网页、核对公开史实或主动打开「联网补查」时才执行。桌面的公开查询框独立填写。本地检索词、任务说明、模型、路径和凭据留在各自流程。已知公开 HTTPS 原页时，直接填链接。Agent 在创作项目根目录运行 `mise run nbt -- retrieve research --request <JSON文件>`。

```json
{"workflow":"prompt","query":"圣礼拜堂 玫瑰窗 重建年代","limit":1}
```

可用 `urls` 提供至多 6 个已知原页，`fallback_queries` 提供至多 2 条备用公开查询。`limit` 默认为 1，最大为 6。`timeout_ms` 默认为 9000，范围为 500～12000 毫秒。相同请求的完整证据可复用 24 小时。需要更新时传 `refresh:true` 或勾选「重新读取」。优先读指定链接与已知官方来源，其余走搜索服务。未配置广域搜索时使用维基百科发现候选。部署侧如已配置 `NBTCREATOR_BRAVE_SEARCH_KEY`，可使用 Brave 广域搜索。密钥只由搜索服务读取，应用的生成服务配置单独管理。

`complete` 表示达到证据数量，`partial` 表示只得到一部分，`no_evidence` 表示未获取可引用原文。`failures` 说明超时、限流、访问或正文匹配问题。`metrics.first_evidence_ms` 是首条证据可用时间，`metrics.elapsed_ms` 是本次研究总时间。页面候选至少要成功读取正文且找到匹配段落，搜索摘要只用于发现链接。当前读取公开 HTML 和纯文本，图版、动态网页及 PDF 可用宿主打开后登记。摘录保留 URL、页面标题、章节、机构或域名、访问时间和哈希。

宿主已经读过原页时可离线执行 `retrieve import-web --request <JSON文件>`。请求包含 `workflow` 和 `evidence` 数组。每项填 `source_url`、`title`、`publisher`、`section`、`text`、`accessed_at`（带时区的 ISO 8601）、`content_kind`（`excerpt` 或 `summary`）与 `reader`。宿主记录标为 `host_reported`，应用实际读取正文标为 `app_opened`。只登记可保留的短引文或自己撰写的提要。

将返回的 `web:` 证据编号放入 `bundle` 的 `selected`。可和当前本地检索结果一起选择，也可只传 `workflow` 与网络证据编号。`source` 和 `read` 按原有哈希机制离线查看证据快照。网络结果保存在当前工作区的证据集合中。要复查最新原页，显式再做一次 `research`。

## 收藏网页证据

对核对过的摘录点「收藏到本地」。之后可以用「已收藏网页」浏览本工作流的收藏，或在本地参考检索中按标题、机构、构造词和年代关键词查找。书库的风格、地区、出版年筛选只适用于书库资料。原页、章节、机构、访问时间和哈希仍与摘录一起显示。

Agent 在创作项目根目录调用 `mise run nbt -- retrieve saved-web --request <JSON文件>`。`workflow` 与已有证据编号所用流程一致。

| action | 请求示例 |
| --- | --- |
| `add` | `{"workflow":"prompt","action":"add","id":"web:<证据编号>"}` |
| `list` | `{"workflow":"prompt","action":"list","limit":12,"offset":0}`，可继续使用返回的 `next_offset` |
| `remove` | `{"workflow":"prompt","action":"remove","id":"web:<证据编号>"}` |

同一原页、同一位置、同一摘录只保留一条收藏。重新取证后可主动更新收藏的访问记录。取消收藏后，已有引用集合仍可回读原快照。收藏和索引随工作区迁移，操作无需访问原页。若某条收藏的快照丢失，检索会显示错误并继续返回其余资料，可用 `remove` 清理错误中报告的编号。

structure_preview 仅生成真实候选供看图；用户查看后才按授权 structure_write 保存新资产。放入建筑仍走保护、占用、总预算、预览／验证和显式导出下一版流程。集合登记、AI 输出、资产保存及任务日志都不代表精修获批或游戏内验收通过。
