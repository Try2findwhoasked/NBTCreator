# 整栋生成与修改基准

归卷阁首批基准把四条固定的自然语言任务映射到可复验的建筑条件。它借鉴 MineCEraft 的程序验收方式，并复用 NBTCreator 的实际方块、操作面、静态通路和整栋质量检查。[MineCEraft](https://arxiv.org/abs/2608.28884)

| 任务 | 验收重点 |
| --- | --- |
| `open-activity` 正常活动 | 入口可达。收卷台到梯脚、梯脚到梯顶、梯顶到书柜三段走通。两个操作面都可用。 |
| `blocked-stair` 堵梯口 | 梯顶可落脚，原收卷站位和梯脚到梯顶的连接通过。书柜操作面重新可达。 |
| `wrong-side` 错误操作侧 | 收卷站位落在实际台面的可用侧。其余站位及实际方块和墙层一致。三段通路即使全通过，台背站位仍会失败。 |
| `cabinet-trim` 三格局部修改 | 从共同初稿续版。三个指定位置为云杉下半砖，之外的方块和全体墙层一致，原路线和操作面仍可用。 |

`technical` 组获得共同任务和技术诊断。`building` 组同时获得失败初稿的整栋质量回执。每组每例最多提交两份按顺序排列的候选，每轮一份，首个通过即结束。两种反例共用 24 格修改上限，局部修改上限为 3 格。变更成本以候选相对原始初稿变动的方块或墙层位置数计算。生成任务没有制作源差异预算。两组使用同一个固定外观、入口玩家视角和书柜机位，分辨率均为 800 × 520。

## 从仓库根目录运行

```powershell
mise run test -- building-generation-benchmark
mise run ci:build
mise run ci:renderer
mise exec -- python -B tests/support/building-generation-benchmark.py --output build/building-generation-example --render
```

回归覆盖本地夹具、错误侧与通路的独立判断、墙层越界、不同布局候选回放、预算与输入绑定。完整命令要求全新输出目录。`report.json` 包含任务和案例版本、引擎与夹具哈希、预算、输入哈希、每轮命中条件和保留约束。制作源及其哈希、原始渲染、匿名审阅绑定均留在隔离目录 `workspace/`。报告中的输入和机位路径相对于报告目录，制作源和审阅路径相对于 `workspace/`。

评审只需解压 `blind-review.zip`，在每例的 `review.json` 查看问题和 A/B 图像顺序。协调者可以用既有的 `reference review-record` 登记实际观察，再用私有绑定核对。机器报告的 `scores` 初始为 `null`，有图包时显示 `pending_human_review`。真实缩略图确认以及手动 NBT 定稿仍由原工作流负责。

## 布局分支与真实 Agent 接入

```powershell
mise exec -- python -B tests/support/building-generation-benchmark.py --prepare --output build/building-generation-inputs
mise exec -- python -B tests/support/building-generation-benchmark.py --candidates build/building-generation-inputs/submissions.json --output build/building-generation-replay --render
```

`prepared.json` 指出两组的输入文件及 SHA-256。协调者把对应组的输入、共同附件及制作源交给操作者。`contract.fixed_plan` 列出必须成立的方案条件，`movable_stop_indices` 给出可以在同层调整的操作站位。候选可使用完整 `plan`，也可提交带 `plan` 字段的 `layout-search` 单条候选。候选必须仍能由当前共享引擎构建。此处的冻结检查保留楼梯系统、活动次序、开口及路线锚点，能比较这些条件内的布局变化。

提交清单采用 `schema_version: 1` 和 `arms` 对象。`technical` 或 `building` 可设成 `null` 以运行内置操作者。下面的清单在 `building` 组提交一个堵梯口候选，其余案例留空。

```json
{
  "schema_version": 1,
  "arms": {
    "technical": null,
    "building": {
      "operator": {"kind": "layout", "id": "local-layout-replay"},
      "cases": {
        "open-activity": {"input_sha256": "<prepared.json 对应组哈希>", "candidates": []},
        "blocked-stair": {"input_sha256": "<prepared.json 对应组哈希>", "candidates": ["candidate-1.json"]},
        "wrong-side": {"input_sha256": "<prepared.json 对应组哈希>", "candidates": []},
        "cabinet-trim": {"input_sha256": "<prepared.json 对应组哈希>", "candidates": []}
      }
    }
  }
}
```

`operator.kind` 可用 `agent`、`layout`、`fixture` 或 `human`。候选路径相对提交清单目录，顺序代表实际提交轮次。空列表表示未提交，缺一侧的案例不会出匿名图。基准重新构建并验收每份候选，忽略附带的候选评分。真实 Agent 对照由协调者为两组各开独立运行，采用同一模型、环境和候选预算，按实际过程逐轮收集候选。离线回放能核对提交个数、候选内容和实际改动量，Agent 的工具调用和推理预算由协调者记录。

## 2026-11-24 本地实测

| 组 | 首轮通过 | 修复轮数 | 最终通过 | 实际评估候选 |
| --- | ---: | ---: | ---: | ---: |
| 技术诊断 | 2/4 | 2 | 4/4 | 6 |
| 技术诊断与整栋反馈 | 2/4 | 2 | 4/4 | 6 |

两组均定位梯口阻塞和 `return_desk.intake` 的 `wrong_side`，各自修复用了 18 格和 0 格。局部修改在首轮准确变更 3 格，保留其他方块、墙层、路线和操作面。本地操作者 `scripted-diagnostic-replay-v1` 重演已知夹具。四对真实渲染的三幅对应图均像素一致，人工评分留空。这次实测覆盖基准的程序验收和图证链路，真实 Agent 表现仍待实测。

另一次完整回放从独立目录提交预制布局夹具，通过全部输入哈希检查，并复现了相同的首轮、修复和最终通过数。其中堵梯口候选把修复后的书柜再沿 X 轴移一格，仍在 24 格预算内。按外观、入口玩家视角、书柜机位的顺序，匿名 A/B 图相差 0、371 和 125,192 个像素。两次回放的报告、图包及图像哈希均已核对，真人评审待进行。
