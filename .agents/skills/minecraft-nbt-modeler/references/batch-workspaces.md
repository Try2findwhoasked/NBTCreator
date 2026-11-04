# 制作批次与过程工作区

批量创作或需要跨会话继续制作时使用 `batches`。应用“项目管理 → 制作批次”与外部 Agent 共用此登记，不需要启动 Electron。

## 存放规则

```text
<项目根目录>/
  .agents/skills/nbtcreator-workspace/    对外 Skill 入口
  .nbtcreator/                          项目配置
  nbt_models/
    <形状>/<中文名>/<版本>/              正式作者模型、坐标、版本内预览与交付
    _workspaces/
      batches/
        index.json                     批次索引与已查看状态
        YYYY-MM-DD_<批次名>_<唯一编号>/
          task.json                    关联模型、产物、状态、哈希及相对路径
          scripts/                     本批次生成器
          design/                      设计说明与参数
          validation/                  批次验证汇总
          previews/                    批次预览汇总
          intermediate/                不作为正式版本的过程模型
          deliverables/                图册、汇总压缩包
          runs/manifests/              不可变登记修订；索引绑定对应哈希
          runs/<时间_阶段_唯一编号>/     单次尝试的独立目录
```

项目根目录仍是 Agent 的工作目录。不要在 `_workspaces` 或批次目录内再初始化 `.agents`、`.nbtcreator`、`nbt_models`。批次目录集中过程与汇总文件，正式模型继续由 `library new/register` 按形状／名称／版本归档；不移动已有资产或复制模型来建立关联。正式版本内的脚本、验证、预览和交付仍可保留为该版本的证据，批次只登记实际路径。

每次重试先分配独立 run。已有登记文件不可原地替换；新模型使用新版本，新报告或图册用新 run／文件名。登记不授予精修批准，也不运行生成器、执行脚本或自动导出 NBT。

## Agent 调用

工作区入口统一为 `python .agents/skills/nbtcreator-workspace/nbt.py`；以下使用 `nbt.py` 简写。`--workspace` 省略时为当前项目目录，也可显式指定项目根目录。

1. `nbt.py batches create --request <创建JSON>`，请求 `{"name":"残败地牢30间"}`。返回稳定的 `id`、`revision`、`workspace_dir` 和 `absolute_workspace`。
2. 将本批次生成器和设计资料写到返回目录。需要重试时执行 `nbt.py batches run --request <runJSON>`，请求 `{"id":"<批次id>","revision":1,"stage":"draft"}`；返回的 `runs` 含新分配目录。阶段用英文小写字母、数字、下划线或短横线。
3. 用已有建模接口生成、检查与实际审阅模型。将正式模型与产物通过 `batches record` 登记。每次写请求使用最近返回的 `revision`，并发修改会拒绝过期请求；先 `get` 刷新，核对后重试。

```json
{
  "id": "<批次id>",
  "revision": 2,
  "run_id": "<可选的run id>",
  "status": "review",
  "models": [
    {"source":"nbt_models/single/中文名/v_日期时间/master/master_geometry.json.gz","name":"中文名","kind":"formal"}
  ],
  "artifacts": [
    {"path":"nbt_models/_workspaces/batches/<批次目录>/deliverables/<实际图册>.html","role":"gallery"},
    {"path":"nbt_models/_workspaces/batches/<批次目录>/validation/<实际报告>.json","role":"report"}
  ]
}
```

`models[].kind` 可为 `formal` 或 `intermediate`，后者必须在本批次目录内，只提供只读预览，不影响正式模型最新版本。登记读取真实完整主模型并绑定文件 SHA256、几何哈希和尺寸；可额外提供 `sha256`、`geometry_sha256` 作为预期值校验。不要把 `delivery/`、`runtime/`、`parts/` 内的副本登记为正式主模型。

`artifacts[].role` 支持 `gallery/archive/report/script/design/preview/other`。路径须在当前项目 `nbt_models/` 内；可提供 `sha256`。状态为 `authoring/review/delivered/failed/cancelled`，只是任务进度，不能据此宣称技术、设计、真实看图或游戏运行已验收。

## 扫描、继续任务与打开产物

- `batches list`：读取已登记批次及其模型、图册实际地址；只读文件元信息，不解压全部模型。
- `batches get --request <JSON>`：`{"id":"<批次id>","verify":true}` 重新校验该批次的全部文件哈希，适用于接手或交付核对。
- `batches locate --request <JSON>`：`{"id":"<批次id>","kind":"artifact","item_id":"<产物id>"}` 返回重新核验后的实际文件地址。`kind` 也可为 `model`、`workspace`。文件缺失或被改动时拒绝打开；不悄悄改绑到另一版。
- `batches ack --request <JSON>`：`{"id":"<批次id>","model_ids":["<模型id>"]}` 标记已查看；`all:true` 标记本批次全部已查看。

新增提示仅绑定新批次创建后实际新写入并登记的正式版本，最多显示 7 天，成功打开预览／编辑后消除，也可手动全部标为已查看。不会把全部历史版本标成新增，不影响创作阶段或最新版本筛选。

## 旧目录兼容

`batches discover` 只读扫描 `_workspaces` 和 `_workspaces/batches` 的直接子目录，发现 `*_catalog.json` 或未进入索引的 `task.json`。不会自动迁移或登记。

`batches import --request <JSON>` 请求含 `name`、`workspace_dir`，可带同目录内的 `catalog`（模型数组，支持 `master/name_zh/master_sha256/geometry_sha256`）及 `gallery`。导入在原批次目录新增登记和过程子目录，核验并关联已有正式模型，保留原文件原路径。默认旧模型不标为新增；用户明确需要时传 `highlight_existing:true`。中断造成 task.json 已保存但索引未写入时，同一入口会核验并恢复登记。

应用显示“未登记的旧批次”，由用户点击登记；本地脚本在系统文件管理器中定位，只有图册、图片、PDF 或 ZIP 才使用系统关联程序打开，不会从批次入口执行脚本。
