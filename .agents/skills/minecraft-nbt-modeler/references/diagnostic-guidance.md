# 检查结果解释与定位

玩家／通路、保护冲突和候选检查报告附带 `diagnostics`，由确定性检查字段生成中文解释与调整方向，不调用 API，不写建筑或创建批准。适用于外部 Agent 接手失败报告、用户在应用中定位具体问题。

每项含 `code/title/severity/certainty/explanation/suggestions/bounds/evidence`。`automatic_repair:false` 表示建议不会自动执行。

- `observed`：已有实际证据，如玩家占位与碰撞小格相交、缺少可靠支撑、身体超出边界、步骤触及保护体积。bounds 来自这些明确位置，定位只调整视角，不修改选区或几何。
- `incomplete`：搜索上限、未能接入半格网格或本次没找到步行路线。不能据此断言游戏中绝对不通，更不能猜哪一堵墙必须删除；宜用门洞、转角、平台等分段终点缩小区间。
- `unknown`：尚未支持的碰撞形状，保守计算不足以认证；应核对实际状态与游戏内碰撞。

玩家占位宽0.6、高1.8格。身体被挡时先核对脚底是否误放在地板内部；无支撑时核对真实地面顶面及半砖高度。必要改动仍须考虑支承、保护和路线，采用后重新检查。复制碰撞小格不是自动删块清单。

候选检查分别解释输入绑定、预览与参数匹配、变化预算、保护、墙层归属、原建筑／候选整体验证及检查期间输入稳定性。没有明确位置证据时不提供定位按钮，不从错误文字中的数字猜坐标；原始错误保留供核对。

应用“玩家／通路”和“保护区”中可定位单项、复制含源／几何绑定的证据；当前画面变化后须重新检查。候选检查解释位于检查状态下方。解释中的建议不放宽保护、预算或真实看图流程，不表示已修复、获批准或游戏运行通过。

## 无界面入口

`control walk-inspect` 继续读取实际源／已绑定候选并输出报告，报告内含同样的解释。其他检查由原命令执行；无需为阅读解释再运行 GUI。

```powershell
mise run nbt -- diagnostics --kind walk --report nbt_models/_workspaces/<任务>/walk-inspection.json
mise run nbt -- diagnostics --kind candidate --report nbt_models/_workspaces/<任务>/validation.json
mise run nbt -- diagnostics --kind protection --report <保存的结构化冲突details.json>
```

这个命令只解释已保存报告，输出 `input_report_sha256` 以绑定所读文件，并明确 `report_reverified:false`。它不重新读取模型，不能证明旧报告对当前版本仍有效。Agent 应先核对报告的 source_sha256、geometry_sha256、context_sha256 与当前任务；缺少绑定则重新运行实际检查。不得把通俗解释当作已经定位了唯一故障、已经完成修复或新的授权。

## 增量诊断

在已同步 Skill 的创作项目根目录运行。先把每次 CLI 的 JSON 原始回执保存为文件。`model` 接受工作模型与建筑方案建模或验证回执。`review` 接受审阅包或 `review-record` 的观察记录。

```powershell
mise run nbt -- diagnostics --kind model --report <当前回执> --baseline <同一任务上次回执>
mise run nbt -- diagnostics --kind review --report <review-notes.json>
```

结果按错误码与目标身份分组，列出 `new` 和 `ongoing`。装配失败保留实例、子对象与接口，附报告已有的未知碰撞或缺失半格面样本。取景失败可定位到受影响机位，附报告已有的失败类型、目标方块与遮挡位置。坐标变化时同一目标仍可归入持续问题，证据取自本次回执。`evidence_pointer` 是 `report.path` 文件中的 JSON Pointer，空字符串表示报告根。省略 `--baseline` 时只汇总本次问题。`walk`、`protection`、`candidate` 使用 `--baseline` 或 `--incremental` 时也输出分组视图。使用建筑命令的 `--compact-report` 时，`--report` 传简明回执中 `report.path` 指向的完整文件。

审阅结果另外列出 `pending_views` 和原始 `delivery_summary`。本命令读取既有证据，实际看图后才登记观察。一次运行缺少某条问题可能只是未执行相关检查，继续核对本次检查覆盖范围和源绑定。
