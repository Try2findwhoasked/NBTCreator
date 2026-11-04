# 本地参考检索与构件复用

用途：按当前任务搜索工作区资产、挑选相关资料片段，并保留可追溯的出处。应用模型编辑、提示词方案及资产创作的“检索本地参考”，与外部 Agent 的 `retrieve` 命令使用同一 Python 实现。检索不调用 API，不授予建模、精修批准或导出权限。

## 检索范围与人工选择

- 资产复用用于 `component`（资产管理的独立结构创作）：按名称、标签和目标 XYZ 尺寸匹配，排除回收站，必要时建议绕 Y 旋转 90°；不隐式缩放或裁切。匹配只是建议，实际方块朝向、碰撞与位置由结构预览引擎再次检查。
- 资料检索用于所有已开放 AI 工作流：仅搜索 `.nbtcreator/internal-ai/config.json` 中该工作流已勾选的内置或导入资料，不扩大到对外 Skill 的全部知识或任意工作区文件。
- 资料按标题和任务词匹配，每份最多推荐两段，显示原文行号、内容 SHA256、匹配理由及完整原文入口。长行会明确标为截取；片段不代表已经阅读整份文档。
- 用户勾选 1～16 项后，保存为本次工作流的参考集合。下一次该工作流生成会发送已选片段，代替其默认全文资料；其他流程不沿用它。本次选择保留在当前应用会话；集合文件与保存资产的来源配方随工作区保留。未使用检索集合时保留原工作流配置行为。

资产只向模型发送编号、内容哈希、名称、尺寸、锚点及少量材质信息，不发送完整体素或本地绝对路径。资料只发送所选片段及编号、标题、行号与哈希。应用把这些显示为“本次提供的参考”，不声称模型已经采纳。实际引用的资产由返回 placements 和其真实哈希核对，不能猜 ID 或冒用其他资产。

## 无界面接口

统一入口：`python .agents/skills/nbtcreator-workspace/nbt.py retrieve --workspace <项目根目录> <动作> --request <JSON>`。工作区默认当前 Agent 目录；Electron 无需启动。

`search` 请求：

```json
{"workflow":"component","query":"水渠桥 支承","size":[4,6,10],"limit":12}
```

返回 `assets` 与 `knowledge`，各最多 limit 项；limit 范围 1～32。size 可省略，省略时不做尺寸适配筛选。query 最多 12000 字。其他工作流只返回已启用资料，不将资产元数据当成模型编辑中的实际粘贴；在建筑中复用构件仍通过资产管理或 structure_place。

`source` 请求 `{"workflow":"component","document_id":"<检索结果document_id>","sha256":"<资料SHA256>"}`，读取仍在本流程启用且哈希相符的完整文档。只接收编号，不接收任意路径。

`bundle` 在原 search 请求中增加 `selected:["<结果id>","<结果id>"]`。返回 `id`、`sha256`、提供给模型的来源说明、资料片段与资产引用元数据。集合保存为工作区 `.nbtcreator/retrieval/bundles/<id>.json`；locator 为相对路径或 skill 内部标识，不保存临时缩略图 URL 或安装路径。

`read` 请求 `{"workflow":"component","id":"<集合id>","sha256":"<集合SHA256>"}`，重新校验集合、资产状态和资料选择。资产内容改变／被回收、资料内容改变／取消启用、集合被修改或工作流不符时拒绝，不静默改绑。工作区整体移动后相对引用仍可使用。

来源的 R1、R2 等编号仅对应当前集合；跨集合引用时同时保留集合 ID 与 SHA256，不只复制一个 R 编号。外部 Agent 可完整读取本文件和实际使用的建模专题，再用集合元数据与 `structure_read` 读取选中资产。

## 复用与适配

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

structure_preview 仅生成真实候选供看图；用户查看后才按授权 structure_write 保存新资产。放入建筑仍走保护、占用、总预算、预览／验证和显式导出下一版流程。集合登记、AI 输出、资产保存及任务日志都不代表精修获批或游戏内验收通过。
