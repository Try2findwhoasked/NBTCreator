# 简单独立建筑初稿

先核对 AGENTS.md、本次约束与创作偏好。根据一次实际活动确定入口、玩家站位、物件使用侧、净空与顶构。参考图项目另记背面和室内如何补全。

- **已同步的创作项目**在创作项目根目录按生成 Skill 的前缀运行 `paths`。下面以 `mise run nbt --` 为例。有同名任务时使用 Skill 所示文件任务前缀。
- **从源码调用**在 NBTCreator 源码根目录运行 `mise run nbt -- --workspace "<创作项目根目录>" paths`。所有后续命令同样把全局 `--workspace` 放在子命令前。启动器在该创作目录执行，`--request` 的相对文件路径由此解析。

1. 用 `paths` 核对实际引擎和创作工作区。Java 1.20.1，DataVersion 3465。完整模型使用全局 XYZ、显式墙层和真实方块状态。按所选约束处理留白、保护、预算、通路及洞口。开放空间保留设计留空。要求密闭时先验密闭并保存开洞前证据。
2. 自由脚本用 `WorkingModel` 建造，随后调用 `open_declared()` 和 `save_draft()`。开放建筑即使声明 `openings: []` 也要执行 `open_declared`，进入完整验证阶段。无墙时将有实体的操作标为 `body`，模型会保留空墙层。有墙则显式标注 `wall`。同一流程也可用下方 JSON 经公开命令执行。
3. 需要把空间、构件和审阅绑定写成方案时，按下方入口亭示例用 `architect plan-build`。已有明确几何可用 `model` 直接装配，参见开放平台示例。
4. 实际查看落盘源的整体、完整入口、保留顶构的室内，以及代表节点或操作面。用真实脚位核对近景和通路。向用户展示对应缩略图、制作源与检查，说明未完成的取景和未实测的游戏项目。用户明确同意后才精修，明确要求定稿后才单独导出 NBT。

多层、多个空间、结构接口、专门的操作面或逐点取景需要 [建筑方案与审阅](architecture-workflow.md)。遇到纹样、SAODG 接入、交接或已有模型续版，再按入口选择已启用专题。

## 入口亭的请求与回执

把[入口亭 JSON](../assets/examples/entry-pavilion.json)复制到创作项目根目录为 `build.json`。文件已有 `save_draft: {}`，运行会发布一个可继续编辑的 SNBT 制作版。只编译和检查时，从副本删除 `save_draft`。

| 值从哪里来 | 如何填写 |
| --- | --- |
| 创作决定 | `plan.size` 以方块格数填写 XYZ。`spaces`、`style.materials`、`context.openings`、`activities` 与 `views` 由实际用途决定。示例逐段检查来访者从入口外、穿过门槛到亭内的脚位。 |
| 当前项目与坐标 | 从 `paths` 核对创作目录和冻结引擎。方案中的空间、开口、脚位、机位及构件 `position` 使用全模型坐标。`parts[].recipe.arguments.operations` 的方块坐标相对于该配方的原点，构件安装时转换一次。 |
| 上一步绑定 | 新建用内联 `plan`。改用已登记方案时，从 `plan-save` 回执取 `id`、`revision`，写成 `plan_id`、`revision`。从已保存制作版续版时，用同份回执的 `revision_request` 给出制作源、源哈希和父方案哈希。 |

在创作项目先创建 `nbt_models/_workspaces/draft-review/`。报告文件须使用新路径。

```powershell
mise run nbt -- capabilities --architect-action plan-build
mise run nbt -- architect plan-build --request build.json --compact-report nbt_models/_workspaces/draft-review/build.json
```

1. 若退出 1，先读简报的 `error`；有 `report.path` 时用 `diagnostics --kind model --report <report.path>` 定位完整证据。路径缺失先核对 `--request` 和工作目录；内容缺失再核对 `plan` 或 `plan_id`。
2. 保存成功后确认 `saved.source` 和 `saved.source_sha256`。将同份回执的 `next.request` 原样写成 `review.json`，运行 `mise run nbt -- architect review-prepare --request review.json --compact-report nbt_models/_workspaces/draft-review/review.json`。无 `saved` 或 `next` 的编译回执还不能据此审阅制作源。
3. 逐参数执行 `render_command`。确认渲染清单为 `status: complete` 且源与相机哈希对应，打开实际 PNG。用同份审阅准备回执的 `review_record_bindings` 作请求顶层，补真实观察的 `observations` 和 `issues`（无问题填 `[]`），提交 `architect review-record`。自动取景不确定但实际看清的细件可写进 `observations[].manual_locations`。
4. 核对观察是否齐全并把实际图像交给用户。本阶段记录观察。精修需等用户对同一源及图像明确确认。需准备交付绑定时可运行 `finalize --source <制作源> --inspect-inputs`，正式写 NBT 由明确的定稿要求触发。
5. 需要发布下一制作版时，将原保存回执的 `revision_request` 与修改后的 `plan`、新 `save_draft` 放在同一请求顶层。收到过期绑定时复查当前制作版和原任务后重建请求。

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
