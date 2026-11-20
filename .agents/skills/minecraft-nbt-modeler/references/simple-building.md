# 简单独立建筑初稿

先核对 AGENTS.md、本次约束与创作偏好。根据一次实际活动确定入口、玩家站位、物件使用侧、净空与顶构。参考图项目另记背面和室内如何补全。

- **已同步的创作项目**在创作项目根目录运行 `mise run nbt -- paths`。
- **从源码调用**在 NBTCreator 源码根目录运行 `mise run nbt -- --workspace "<创作项目根目录>" paths`。后面的命令同样把 `--workspace` 放在子命令前。创作文件和相对路径以指定的工作区为基准。

1. 用 `paths` 核对实际引擎和创作工作区。Java 1.20.1，DataVersion 3465。完整模型使用全局 XYZ、显式墙层和真实方块状态。按所选约束处理留白、保护、预算、通路及洞口。开放空间保留设计留空。要求密闭时先验密闭并保存开洞前证据。
2. 自由脚本用 `WorkingModel` 建造，随后调用 `open_declared()` 和 `save_draft()`。开放建筑即使声明 `openings: []` 也要执行 `open_declared`，进入完整验证阶段。无墙时将有实体的操作标为 `body`，模型会保留空墙层。有墙则显式标注 `wall`。同一流程也可用下方 JSON 经公开命令执行。
3. 采用建筑方案时，可把[入口亭示例](../assets/examples/entry-pavilion.json)复制为创作目录下的 `build.json`。在创作项目创建 `nbt_models/_workspaces/draft-review/`，执行 `mise run nbt -- architect plan-build --request build.json --compact-report nbt_models/_workspaces/draft-review/build.json`。从**落盘的**报告取 `next.request` 原样保存为 `review.json`，再运行 `mise run nbt -- architect review-prepare --request review.json --compact-report nbt_models/_workspaces/draft-review/review.json`。按报告的 `render_command` 出图，实际看图后以其中的 `review_record_bindings` 为基础补 `observations` 和 `issues`，再执行 `architect review-record`。续版时将首份报告的 `revision_request` 和改好的 `plan`、`save_draft` 放在同一个请求顶层。自动取景不确定但实际看清的细件可写入 `observations[].manual_locations`。
4. 实际查看落盘源的整体、完整入口、保留顶构的室内，以及代表节点或操作面。用真实脚位核对近景和通路。向用户展示对应缩略图、制作源与检查，说明未完成的取景和未实测的游戏项目。用户明确同意后才精修，明确要求定稿后才单独导出 NBT。

多层、多个空间、结构接口、专门的操作面或逐点取景需要 [建筑方案与审阅](architecture-workflow.md)。遇到纹样、SAODG 接入、交接或已有模型续版，再按入口选择已启用专题。

入口亭示例的活动从入口外经过门槛再到亭内。活动检查逐段验证已声明脚位之间的可达性，需要经过的位置应明确写入站点。示例两侧石栏也声明了朝向连接，以便预览呈现连续矮栏。

## 开放平台的最小命令示例

将以下内容保存为 `request.json`，执行 `mise run nbt -- model --request request.json`。这只演示建造、验证、保存及出图衔接。实际初稿按设计加入支承、顶构、操作面和专属视角。

```json
{
  "size": [8, 6, 8],
  "context": {"mode": "standalone", "require_enclosure": false, "openings": [], "allow_empty_wall_mask": true,
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

保存时自动验证，完整报告见制作版的 `validation/working-model.json`。需要在终端重验已保存的 SNBT 时，从 `result.saved` 原样取路径与哈希，填写 `{"source":"…","source_sha256":"…","validate":true}`，再运行 `mise run nbt -- model --request recheck.json`。可选 `positions` 查询具体坐标。独立的 `mise run nbt -- validate` 命令用于候选快照检查。

以下是可用的 `cameras.json`，实际任务按模型尺寸与玩家脚位另选具体视角。

```json
[{"id":"overview","role":"massing","eye":[11,7,-6],"target":[4,0.5,4],"fov":60}]
```

执行 `mise run nbt -- render --source <result.saved.source> --cameras cameras.json --output <新目录>`，用 `render --help` 查询其他参数。核对 `render_manifest.json` 的源哈希与 `result.saved.source_sha256`，打开实际 PNG。完整 API 示例可在已启用模型装配知识时查阅 `working-model.md`。
