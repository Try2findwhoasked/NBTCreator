# 拓展资产库协议 v1

拓展库维护可独立发布的数据，应用维护编译与预览引擎。现有官方模块配方源位于独立仓库 `NBTCreator-AssetLibrary`；Skill 的 `assets/extension-library/` 是发行快照，运行时不依赖相邻开发仓库。新配方和构件先写入拓展库，再按需更新应用快照。

素材库的“建筑构件”页统一显示本地构件、应用自带配方与构件、已连接拓展来源。使用同一搜索框、分类树及来源/类型筛选；点击素材在同一“查看与放置”窗口中查看真实三维。配方可调整尺寸、材质、样式与构造参数，预览后直接放置候选，或将当前参数结果保存为本地构件。固定构件可直接预览和放置，也可显式复制到本地编辑。复制结果标记为待审阅，并保留来源记录。

“素材库工具 → 来源管理”负责连接、显式联网刷新、停用、回退与移除。查看本地目录、library.json 的 HTTPS 地址或 registry.json 的 HTTPS 地址，选择来源后连接，素材直接进入主列表。目录默认查找 library.json；本地库登记绝对路径，连接、内容寻址缓存与惰性生成的几何缩略图保存在当前创作项目 `.nbtcreator/asset-libraries/`。切换工作区使用各自的连接与缓存。

官方公开资产库：[NBTCreator-AssetLibrary](https://github.com/Try2findwhoasked/NBTCreator-AssetLibrary)。在软件中连接公开[库目录 registry.json](https://raw.githubusercontent.com/Try2findwhoasked/NBTCreator-AssetLibrary/refs/heads/feat/initial-library/registry.json)，或连接[单库 library.json](https://raw.githubusercontent.com/Try2findwhoasked/NBTCreator-AssetLibrary/refs/heads/feat/initial-library/library.json)。分支入口用于后续显式刷新；固定复现可将 refs/heads/feat/initial-library 换成已验证提交 SHA。

## 三层格式

1. 库目录 `nbtcreator.asset-registry`：列出可选择的库，不递归连接，不自动下载全部库。
2. 库清单 `nbtcreator.asset-library`：描述一个版本的完整资产集合，钉住每项资产的原始字节大小和 SHA256。
3. 资产数据：当前开放 `parametric_recipe` 和 `component`。只读取 JSON，不加载脚本、Python、JS、归档或原生扩展。

所有文件为 UTF-8 JSON，schema_version 必须是整数1。重复字段、NaN、未知字段和未知格式会被拒绝；不得通过资产声明已经完成看图验收。库版本为 `major.minor.patch`，不接受前导零、v前缀或预发布后缀。每个已发布版本的清单字节不可变。

目录示例：

```json
{
  "schema_version": 1,
  "kind": "nbtcreator.asset-registry",
  "name": "团队库目录",
  "libraries": [{
    "id": "team.architecture",
    "name": "团队建筑库",
    "version": "1.0.0",
    "path": "architecture/library.json",
    "manifest_sha256": "<library.json的64位小写SHA256>"
  }]
}
```

目录最多32项，id 不重复；支持可选 name。path 为同目录下的相对 JSON 路径，库可放在子目录。查看目录只返回库条目；连接时再次核对 manifest_sha256，清单已变更则需重新查看。

库清单示例：

```json
{
  "schema_version": 1,
  "kind": "nbtcreator.asset-library",
  "id": "team.architecture",
  "name": "团队建筑库",
  "version": "1.0.0",
  "license": "LicenseRef-Team",
  "compatibility": {"minecraft": "1.20.1", "app_min": "3.1.0"},
  "assets": [{
    "id": "stone-pillar",
    "name": "石柱",
    "type": "parametric_recipe",
    "category": "柱与基座",
    "tags": ["pillar"],
    "status": "stable",
    "path": "assets/recipes/pillar/stone-pillar.json",
    "bytes": 213,
    "sha256": "<资产文件的64位小写SHA256>",
    "requires": []
  }]
}
```

bytes 与哈希须由实际文件生成，示例中的数值和占位符不可直接发布。库必需字段为 schema_version、kind、id、name、version、license、assets；可选 description（最多2000字）及 compatibility。compatibility 可含 minecraft、app_min、app_max；Minecraft 仅支持1.20.1，应用上下限为闭区间。省略 compatibility 表示作者接受当前协议的1.20.1默认目标。

当前引擎按应用版本 4.3.1 检查上述边界。此前引擎错误地固定使用 3.1.0；因此升级后，原来侥幸通过、但 `app_max` 小于 4.3.1 的库会被拒绝，已验证的缓存和本地副本仍保留。应由库维护者发布兼容版本，再显式刷新；不要删除用户数据或绕过版本声明。

每库1～512项资产，单项最多8MiB，总量最多32MiB；清单最多2MiB，每工作区最多32个外部库。库和资产 id 为1～96个小写英文、数字、点、横线或下划线，首位须为英文或数字。资产名称最多80字，分类最多80字，标签最多16个、每个32字。status 可为 draft、stable、recommended、deprecated，省略为 stable。状态描述作者推荐程度，不构成审阅或游戏验证证明。

资产必需字段为 id、name、type、path、bytes、sha256；category、tags、status、requires 可选。requires 仅引用同库资产 id，最多32项；缺失依赖和循环依赖阻止整库激活。v1 不提供跨库依赖解算、自动更新或脚本钩子。整个库作为一次事务安装，因此依赖也在同一版本中锁定。

参数化资产内容：

```json
{
  "schema_version": 1,
  "kind": "nbtcreator.parametric-recipe",
  "arguments": {"kind": "pillar", "name": "石柱", "size": [3, 12, 3], "material": "stone_bricks"},
  "controls": {"style": false, "spacing": false}
}
```

arguments 使用当前 tool-catalog.json 中 parametric_compile 的参数 Schema，controls 可省略，内部只支持 style 和 spacing 布尔值。v1 配方须自包含，暂不接受 ornament.sample 本地图源引用；含图源的纹样应先编译成 component 后发布。只有引擎已经实现的构件类型/参数可用；Schema 校验通过还须实际编译和预览，不能据此宣称几何、承托或通路正确。

component 资产使用 [构件规范](component-assets.md) 的 schema_version/name/size/anchor/palette/blocks，支持其中已有 tags、archived、content_sha256 等字段，内容通过同一 `nbt_components.validate` 校验。导入生成新本地资产，强制标记 pending_visual_review；来源、库版本、资产 SHA256 存在 `.nbtcreator/asset-libraries/imports/<本地资产id>.json`。导入不会生成 NBT 或审批。

## 地址、传输和缓存

- 本地来源支持绝对目录或清单文件路径，不支持 UNC 网络路径；资产可位于库目录内的子目录。符号链接最终路径必须仍在库目录内。
- 远端使用 HTTPS 静态文件服务；HTTP 仅允许 localhost、127.0.0.1、::1，便于本机服务和测试。暂不接入需要鉴权的私人库。URL 不得包含用户名、密码、查询或片段，配置文件不保存凭据。
- 资产和目录条目只允许相对 JSON 路径，远端中文及空格文件名按 UTF-8 URL 编码读取；拒绝 ../、绝对路径、百分号编码、反斜线、跨源链接及 Windows 设备名。清单及资产的重定向必须同源。服务器需返回未压缩 JSON；网络单次连接/读取最多10秒；最多4个文件并发下载，共享60秒刷新预算，超限取消排队任务。失败时保留已经校验的内容缓存，再次连接或刷新可复用；活动版本始终等整库通过后才切换。
- 查看已连接资产只读取经 SHA256 再校验的本地缓存，不触网。远端删除、断网或证书错误时保留现有版本；刷新为显式用户操作。
- 新版资产先写入不可变内容寻址缓存，全部验证后原子替换 state.json 中的 active 指针。并发写操作以跨进程锁互斥；中断遗留的未引用 blobs 不参与资产列表。
- 保留最多3个历史版本供回退，并在连接配置中绑定这些版本的清单哈希；回退后再次刷新仍拒绝同版本换内容。清单缓存损坏时，刷新可依据原子保存的版本与哈希绑定修复它。刷新不允许降版、同版本内容变化或库 id 改变；回退只激活已验证的旧缓存。移除连接保留已导入的本地构件及缓存，方便重连；v1 尚无缓存清理界面。
- 资产使用 `<library-id>/<asset-id>` 命名空间，名称和分类可重名。同一个库 id 只允许一个外部连接。统一浏览接口 browse 并列保留自带与外部版本，以 source_id 区分同名同编号的来源；UI 的唯一键结合来源和资产编号。旧 list 与 parametric_list 延续官方外部版本优先的行为，parametric_list 为官方配方保留旧 asset-id。
- 统一浏览、缩略图与三维预览均从本地数据生成。缩略图按可见卡片请求，缓存键包含资产字节哈希和引擎实现哈希。新预览、调参、复制与放置操作同时校验 source_id、version、manifest_sha256、资产 sha256；放置和复制还校验当前参数生成的 content_sha256。来源停用、移除或换版后，旧选择会拒绝使用，可通过“载入当前版本”重新查看。
- 读取/导入必须同时提供 id 和 sha256，更新后旧选择会报 STALE_ASSET。受损库整体隔离，其余库继续显示，界面显示错误。SHA256 提供完整性及版本锁定，不是发布者身份签名。

| 情况 | 处理/错误代码 |
| --- | --- |
| 清单/资产丢失、断网、TLS或权限错误 | SOURCE_UNAVAILABLE，保留旧版 |
| 文件截断、大小/哈希不一致 | HASH_MISMATCH，整库不激活 |
| 缓存被修改 | CACHE_CORRUPT，隔离来源，刷新可修复 |
| 重复库/来源/资产编号 | DUPLICATE_LIBRARY / DUPLICATE_SOURCE / DUPLICATE_ID |
| 未实现类型、版本或不兼容目标 | UNSUPPORTED_ASSET / UNSUPPORTED_SCHEMA / INCOMPATIBLE |
| 缺失或循环依赖 | INVALID_DEPENDENCY |
| 同版本换内容、降版或变更库id | VERSION_REUSED / DOWNGRADE / IDENTITY_CHANGED |
| 路径越界、危险地址或跨源重定向 | UNSAFE_PATH / UNSAFE_URL / UNSAFE_REDIRECT |
| 超限、并发刷新 | SIZE_LIMIT / LOCK_BUSY |

## Agent 与维护入口

在软件仓库根目录使用 `mise exec -- node scripts/cli.mjs --workspace <创作项目> asset-libraries <action> --request <JSON文件>`，创作项目也可用生成的 `mise run nbt -- asset-libraries ...`，无需 Electron。action 为 list/browse/discover/add/refresh/enable/remove/rollback/read/import/thumbnail/preview/resolve/place/copy。返回统一 `{ok,result}` 或 `{ok:false,error,code}`。

外部 Agent 先把 `{"query":"尖拱","limit":4}` 写入 UTF-8 请求文件，再执行 `mise run nbt -- asset-libraries browse --request <JSON文件>`。按名称和标签返回少量带版本和哈希的候选；具体尺寸仍需回读或预览。无 `query` 的完整目录留给素材浏览器或明确需要全量的调用。

| action | request |
| --- | --- |
| list | `{}`，离线读取，延续旧版本的官方来源优先行为 |
| browse | `{}`，统一 UI 的离线目录，包含自带和已启用的外部版本及来源管理信息 |
| discover | `{source:"绝对路径或HTTPS地址"}` |
| add | `{source:"library.json地址",manifest_sha256?:"目录钉住的哈希"}` |
| refresh | `{id:"连接id",manifest_sha256?:"预期清单哈希"}` |
| enable | `{id:"连接id",enabled:true}` |
| remove / rollback | `{id:"连接id"}` |
| read / import | 旧请求 `{id:"库id/资产id",sha256:"资产原始字节哈希"}` 继续可用；也支持下述完整来源绑定。import 保留固定构件导入行为 |
| thumbnail | `ref`，生成或读取实际几何缩略图缓存 |
| preview | `{...ref,arguments?:{...}}`，生成带实际三维快照与内容哈希的候选预览 |
| resolve | `{...ref,arguments?:{...},content_sha256:"预览的构件内容哈希"}`，读取用于三维手柄的构件数据 |
| place | `{...ref,arguments?:{...},content_sha256,position:[x,y,z],size:[x,y,z]}`，生成放置候选；支持 counts/spacing/theme/quarter_turns/mirror/overwrite |
| copy | `{...ref,arguments?:{...},content_sha256}`，将当前参数结果显式保存为待审阅的本地构件，记录来源及参数 |

`ref` 是 browse 返回的完整绑定 `{id,sha256,source_id,version,manifest_sha256}`。source_id 为 bundled 或连接编号。arguments 可覆盖配方顶层字段，form/ornament 对象整体替换；省略时采用来源配方。固定构件不接收 arguments。桌面放置还需当前已打开建筑的 source 与 source_sha256，由服务重新校验原文件并填入真实 size；CLI 的 place 只返回候选。

配方通过 parametric_list.object_library 发现，使用 arguments 调用 parametric_compile/preview，再按原流程保存。外部配方的来源库、版本和SHA256随行返回；生成新资产时原有预览/保存规范继续适用。

独立库新增数据并登记 library.json 后执行 `mise run index`、`mise run check`；软件仓库执行 `mise run assets:sync -- --source <独立库路径>`、`mise run assets:check`、`mise run assets:test`。快照、引擎 Schema 和实际编译回归应一并检查。发布时将同一版本的 library.json、registry.json 及其引用的 assets 目录部署到同源 HTTPS 路径，使用固定版本/提交地址可避免托管缓存混用版本。
