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
