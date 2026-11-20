# 简单独立建筑初稿

从创作项目根目录执行。先核对 AGENTS.md、本次约束与创作偏好。根据一次实际活动确定入口、玩家站位、物件使用侧、净空与顶构。参考图项目另记背面和室内如何补全。

1. 运行 `python .agents/skills/nbtcreator-workspace/nbt.py paths` 定位冻结引擎，下文的 `nbt.py` 指同一工作区入口。使用项目的运行环境。Java 1.20.1，DataVersion 3465。完整模型使用全局 XYZ、显式墙层和真实方块状态。按所选约束处理留白、保护、预算、通路及洞口。开放空间保留设计留空。要求密闭时先验密闭并保存开洞前证据。
2. 自由脚本用 `WorkingModel` 建造，随后调用 `open_declared()` 和 `save_draft()`。开放建筑即使声明 `openings: []` 也要执行 `open_declared`，进入完整验证阶段。无墙时将有实体的操作标为 `body`，模型会保留空墙层。有墙则显式标注 `wall`。同一流程也可用下方 JSON 经公开命令执行。
3. 若采用建筑方案，用 `nbt.py capabilities --architect-action plan-build` 查请求，填写 `plan` 和 `save_draft: {}`。创建 `nbt_models/_workspaces/draft-review/`，执行 `nbt.py architect plan-build --request build.json --compact-report nbt_models/_workspaces/draft-review/build.json`。把回执 `next.request` 原样保存为 review.json，再执行 `nbt.py architect review-prepare --request review.json --compact-report nbt_models/_workspaces/draft-review/review.json`。准备审阅会重开并校验保存源，返回同一入口的 `render_command` 参数。实际看图后，以 `review_record_bindings` 为请求基础，按 `capabilities --architect-action review-record` 补 `observations` 和 `issues`，再执行 `architect review-record --request <请求文件>`。根据回执 `review_locations` 填写实际看到的位置。
4. 实际查看落盘源的整体、完整入口、保留顶构的室内，以及代表节点或操作面。用真实脚位核对近景和通路。向用户展示对应缩略图、制作源与检查，说明未完成的取景和未实测的游戏项目。用户明确同意后才精修，明确要求定稿后才单独导出 NBT。

多层、多个空间、结构接口、专门的操作面或逐点取景需要 [建筑方案与审阅](architecture-workflow.md)。遇到纹样、SAODG 接入、交接或已有模型续版，再按入口选择已启用专题。

## 开放平台的最小命令示例

将以下内容保存为 `request.json`，执行 `nbt.py model --request request.json`。这只演示建造、验证、保存及出图衔接。实际初稿按设计加入支承、顶构、操作面和专属视角。

```json
{
  "size": [8, 6, 8],
  "context": {"mode": "standalone", "require_enclosure": false, "openings": [],
              "start": [2.5, 1, 2.5], "targets": {"platform": [5.5, 1, 5.5]}},
  "actions": [
    {"method": "apply_operations", "operations": [
      {"kind": "box", "label": "平台", "classification": "body",
       "lo": [1, 0, 1], "hi": [6, 0, 6], "state": "minecraft:stone_bricks"}
    ]},
    {"method": "open_declared"}
  ],
  "save_draft": {"name_zh": "开放平台示例"}
}
```

保存时自动验证，完整报告见制作版的 `validation/working-model.json`。需要在终端重验已保存的 SNBT 时，从 `result.saved` 原样取路径与哈希，填写 `{"source":"…","source_sha256":"…","validate":true}`，再运行 `nbt.py model --request recheck.json`。可选 `positions` 查询具体坐标。独立的 `nbt.py validate` 命令用于候选快照检查。

以下是可用的 `cameras.json`，实际任务按模型尺寸与玩家脚位另选具体视角。

```json
[{"id":"overview","role":"massing","eye":[11,7,-6],"target":[4,0.5,4],"fov":60}]
```

执行 `nbt.py render --source <result.saved.source> --cameras cameras.json --output <新目录>`，用 `render --help` 查询其他参数。核对 `render_manifest.json` 的源哈希与 `result.saved.source_sha256`，打开实际 PNG。完整 API 示例可在已启用模型装配知识时查阅 `working-model.md`。
