# 分支合并核对（2026-11-04）

已执行 `git fetch --all --prune`，核对目标为当前 main（d6ecf7e）。以下是提交祖先关系；未合并不等于功能全部缺失，需另外比较代码。此次只核对，没有合并或删除分支。

| 本地分支 | main 外提交数 | API 输出约束 |
| --- | ---: | --- |
| codex/agent-task-return | 0 | JSON object 模式 + 提示词；本地校验 |
| codex/ai-reference-retrieval | 0 | JSON object 模式 + 提示词；本地校验 |
| codex/ai-request-efficiency | 3 | JSON object 模式 + 提示词；本地校验 |
| codex/ai-speed-constraints | 0 | JSON object 模式 + 提示词；本地校验 |
| codex/ai-transform-sliders | 0 | JSON object 模式 + 提示词；本地校验 |
| codex/auto-roads | 2 | JSON object 模式 + 提示词；本地校验 |
| codex/batch-workspaces | 0 | JSON object 模式 + 提示词；本地校验 |
| codex/comment-tasks | 0 | JSON object 模式 + 提示词；本地校验 |
| codex/diagnostic-guidance | 0 | JSON object 模式 + 提示词；本地校验 |
| codex/integrate-structure-agent | 0 | JSON object 模式 + 提示词；本地校验 |
| codex/modelling-alignment | 2 | JSON object 模式 + 提示词；本地校验 |
| codex/modelling-arrays | 3 | JSON object 模式 + 提示词；本地校验 |
| codex/modelling-integration | 17 | JSON object 模式 + 提示词；本地校验 |
| codex/modelling-roofs | 7 | JSON object 模式 + 提示词；本地校验 |
| codex/modelling-section-geometry | 6 | JSON object 模式 + 提示词；本地校验 |
| codex/modelling-selection | 1 | JSON object 模式 + 提示词；本地校验 |
| codex/modelling-stairs | 4 | JSON object 模式 + 提示词；本地校验 |
| codex/modelling-terrain-roads | 5 | JSON object 模式 + 提示词；本地校验 |
| codex/player-inspection | 0 | JSON object 模式 + 提示词；本地校验 |
| codex/portable-1-19 | 0 | JSON object 模式 + 提示词；本地校验 |
| codex/portable-1-20 | 0 | JSON object 模式 + 提示词；本地校验 |
| codex/production-frontend | 0 | JSON object 模式 + 提示词；本地校验 |
| codex/selection-edit | 1 | JSON object 模式 + 提示词；本地校验 |
| codex/selection-edit-finish | 0 | JSON object 模式 + 提示词；本地校验 |
| codex/shared-structure-agent | 4 | JSON object 模式 + 提示词；本地校验 |
| codex/ui-workspaces | 0 | JSON object 模式 + 提示词；本地校验 |

明确尚未整合的工作：

- `codex/modelling-integration` 及其 modelling 子分支：选区、对齐、阵列、楼梯、地形道路、截面和屋顶工具，以及参数定义与约束验证。main 当前工具清单为20项，不能认定这些扩展已集成。
- `codex/ai-request-efficiency`：3个 main 外提交，其中包含旧源码快照；不能直接以分支整树替换 main。后两次 AI 优化中的部分行为已见于 main，仍需逐项比对。
- `codex/selection-edit`、`codex/shared-structure-agent`、`codex/auto-roads` 留有非祖先提交，但 main 已含选区编辑、共享结构 Agent 和自动道路的后续实现；不能仅凭分支名称重复合并。

API 层的 JSON object 模式不约束字段 schema；本地格式、坐标、工具白名单和写入策略校验仍是执行前的硬校验。

## 本轮继续处理结果

集成目标为 `codex/ai-usability-integration`，不直接修改 main。先保存上一轮 AI 易用性、保护裁剪、手动工具入口启停改动，再合并 `codex/modelling-integration`。

- 建模扩展17个提交已进入当前集成分支（工具从20项增至26项）；保留主线新增的检索资产材质映射和来源校验，加入分支的完整操作参数定义与本地验证。
- `codex/ai-request-efficiency` 的 ai-input、workbench-contract、ai-metrics 核心文件与原 main 内容相同（忽略换行）。API服务的差异主要是旧分支缺少主线后续选区编辑、独立资产、资料检索等功能，不能倒退合并。
- `codex/auto-roads` 多出的2个提交是工具计数测试和换行维护；主线的对应计数测试已经采用目录动态计数。
- `codex/selection-edit` 是早期原型，主线已含完成版本及后续修复；`codex/shared-structure-agent` 的共用结构Agent功能也已在主线。保留这些分支，不用祖先关系标记代替功能审计。

注意：main仍未包含本轮集成提交；需审阅当前分支后再决定合入main。JSON Schema在本轮用于本地参数硬校验和API提示资料，API请求依然使用可选的json_object模式，未声称供应商侧严格schema约束。

验证结果：建模Python37项、参数Node3项、API42项、桌面冒烟30项、AI放置17项、选区桌面10项、精修36项检查通过；选区/覆盖/保护、结构Agent和配方回归通过。doctor、check:tools（26项）、skill检查、归档409文件哈希校验通过。工具启停偏好覆盖新增的6项工具。补修了保护裁剪与选区写入策略组合：先检查完整写入范围，再裁剪保护位置，并保留write_bounds中的覆盖开关。
