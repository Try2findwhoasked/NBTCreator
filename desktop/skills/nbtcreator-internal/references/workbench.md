仅返回JSON {"summary":"修改","project_patch":{设计字段},"operations":[工具步骤]}。可改设计字段以随附字段定义或严格 Schema 为准。buildingShape 仅用规范键。已有模型保持尺寸与归档形状，固定尺寸也须保留。不改source/output/context/stage/budget/批准。
提供 operations 时填写完整序列，包含每步的 kind 和实际参数。无需调整操作时，普通 JSON 省略 operations，严格模式按 Schema 使用 null（完整初稿须填非空序列）。
完整operations最多64步；初稿优先24步以内，用连续区域表达主构造，细部留待后续增量。超出限制不能靠截断丢失步骤。
classification 表示方块归属，取 body（主体、地板、屋顶或道具）、wall（墙层）或 inherit（保留归属）。普通 JSON 可以省略操作的 label 和 classification，由脚本补齐。严格 JSON 的每条完整操作按 Schema 填写这两个字段。project_patch 中 size 使用尺寸数组，其余已填写字段使用对应文字或形状键。严格 JSON 始终包含 project_patch，未修改的可空设计项逐键填 null；初稿仍须填写所列必填设计项。
