# 各区域 AI 创作偏好

应用和外部 Agent 共用工作区 `.nbtcreator/ai-style.json`，它只有创作偏好，不含 API Key、内部资料或批准信息。修改后下一次生成读取最新值，不必复制参数到两个位置。

区域对应：draft=完整初稿，workbench=控件配置，prompt=文字提示词，structure=局部编辑，small_structure=小型构件/3D放置，component=资产管理独立结构，selection_edit=选区自然语言工具编辑。按当前任务选择区域，不将所有区域的偏好同时套入一次任务。

每项是0～100的整数：creativity=保守↔天马行空，detail=简洁↔详细，ornament=朴素↔丰富，variation=延续现有↔探索变化。缺少配置时使用引擎默认值。

```powershell
python .agents/skills/nbtcreator-workspace/nbt.py ai-style show
python .agents/skills/nbtcreator-workspace/nbt.py ai-style prompt --workflow small_structure
python .agents/skills/nbtcreator-workspace/nbt.py ai-style set --workflow small_structure --creativity 80 --detail 70
```

`--workspace <目录>` 放在 ai-style 后、子命令前，默认 Agent 当前工作目录。prompt 返回通俗偏好说明与实际数值；set 更新同一份配置，应用下一次 API 生成会读取。UI 中“重新读取”可刷新外部修改后的滑块显示。

用户本次明确要求优先。偏好只能调整创作与表达，不扩大选区、不允许修改原稿、不放宽保护或变化预算、不取代真实看图确认。即使要求简洁，结构化返回仍须包含所有必需字段；即使天马行空，构造支承和玩家通路仍需合理并由引擎检查。
