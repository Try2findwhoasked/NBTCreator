仅返回JSON {"summary":"修改","project_patch":{设计字段},"operations":[工具步骤]}。可改buildingShape/layout/circulation/name/theme/purpose/footprint/style/ceiling/floor/wall/props/preserve/extras；buildingShape仅用规范键；新建可改size，existing_model=true时保持尺寸。不改source/output/context/stage/budget/批准。
operations省略表示保留；提供时是完整序列，每步有kind/label/classification和实际参数。不要无故清空或重写未改变步骤。
完整operations最多64步；初稿优先24步以内，用连续区域表达主构造，细部留待后续增量。超出限制不能靠截断丢失步骤。
classification表示方块归属，仅body（主体/地板/屋顶/道具）、wall（需单独交付的墙层）、inherit（保留归属）；不是用途分类，不写structure/decor/opening/props/surface。可省略label和classification，由脚本补齐。project_patch中除size外所有字段均为文字，不用数组或对象。
