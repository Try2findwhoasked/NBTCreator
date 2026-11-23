# 整栋建筑规划 Implementation Plan

> **For agentic workers:** Use an isolated task branch and execute the checkboxes in order. Review each interface against the spec before integrating it.

**Goal:** 在建筑方案编译前验证和生成可量化的整栋布局，复验成品并提供桌面和 Skill 入口。

**Architecture:** 在共享 Python 建筑模块内保存版本化的任务书与布局。布局校验、搜索、到建筑方案的转接和成品复验共用坐标与稳定 ID。Electron 使用现有建筑工具的受限路由。

**Tech Stack:** Python 3.14、NBTCreator WorkingModel 与碰撞检查、JavaScript、Electron、Vite、mise。

**Spec:** [整栋建筑规划设计](../specs/2026-11-23-whole-building-planning-design.md)

## Global Constraints

- Minecraft Java 1.20.1。平面盒使用含端点世界 XZ 整数坐标。
- 旧建筑方案可读且维持既有行为。新规划附在建筑方案上，使用既有方案和制作源哈希。
- 复用现有碰撞、构件、真实缩略图审阅和手动定稿流程。
- 只运行受限的桌面请求。临时文件沿用工作区机制。
- 软件源不作为创作项目。公共工具契约来自 tool-catalog.json。
- 验证入口使用 mise，按任务范围维护独立测试套件。

## Review Focus

- 同一空间的多个盒重叠时，面积按并集计且重复不增加面积。两间房重叠时逐格定位。
- 布局图上满足邻接和门位时，实际门洞受堵仍必须失败。
- 夹层空洞投影落在下层时，下层不因上层保留区而扣面积。
- 搜索步数耗尽与穷尽受支持的候选空间分别报告。
- 桌面快速切换候选或遇到过期源时，绑定仍对应当次请求。

## Task 1 · 量化任务书与布局

**Files:** nbt_building/planning.py、nbt_building/workflow.py、tool-catalog.json、tests/engine/whole-building-planning.py、tests/suites.mjs。

**Interface:** `assess_layout(program, layout)` 返回规则结果、布局绘制数据、两个内容哈希和通过标志。公共 `architect layout-check` 接收 `program` 与 `layout`。任务书的稳定 ID 包括楼层、空间、连接。分配区域和开口的表示基于含端点世界 XZ 矩形。

- [x] 写手工布局的正常、面积不足、空间重叠、跨层挑空及无邻接用例。
- [x] 运行 `mise run test -- whole-building-planning`，观察待实现失败。
- [x] 完成版本 1 契约、ID 和范围校验、矩形并集、房间排布判据和连接回执。检查顺序和结果保持确定性。
- [x] 使用公共 CLI 检查两个正常方案，确认回执可以直接绘制逐层区域和门位。

## Task 2 · 编译绑定和成品回读

**Files:** nbt_building/plan.py、nbt_building/planning_geometry.py、nbt_building/workflow.py、tool-catalog.json、tests/engine/whole-building-planning.py。

**Interface:** 建筑方案可选 `planning:{program,layout}`。成品报告由 `assess_geometry(model, planning, binding)` 生成，`plan-build` 和 `plan-check` 都使用它。公共 `layout-check` 也接受已有制作源及源哈希。

- [x] 增加归卷阁正常、面积不足、堵梯、回读和过期源反例。验证存在直通门要求时从别处绕行不足以通过。
- [x] 绑定布局与实际建筑空间，计算净地面面积，从必要入口验证真正可达的空间和路径。区分结构地面与家具造成的通行障碍。
- [x] 将硬失败交给现有模型冲突回执，确保失败候选无制作版副作用。
- [x] 验证无规划绑定的旧方案与现有建筑质量报告。运行 `mise run test -- architecture-workflow` 和 `mise run test -- whole-building-planning`。

## Task 3 · 搜索与候选转接

**Files:** nbt_building/planning_search.py、nbt_building/workflow.py、tool-catalog.json、tests/engine/whole-building-planning.py。

**Interface:** `architect program-layout-search` 接受任务书、可选基线布局与锁定集合、上限，返回可重复的合法候选及逐项结果。`architect layout-prepare` 接收已选布局，把空间、入口和构件留位转接给当前建筑方案，可与用户构造配方一同编译。

- [x] 测定相同输入输出、固定区域不移动、矛盾输入与预算耗尽、自动候选经建筑方案生成和落盘复验。
- [x] 实现有界矩形搜索。面积、边界、占用、邻接先剪枝。按偏差和稳定次序给出若干不同方案。
- [x] 接通候选到建筑方案，查出与固定结构、楼梯和用户输入不一致的范围。
- [x] 运行公共 CLI 的自动候选回执和 SNBT 端到端用例。

## Task 4 · 桌面规划与诊断

**Files:** viewer/src/building-planning.js、viewer/src/building-planning.css、viewer/src/architect-tools.js、viewer/detail-server.mjs、nbt_detail_control.py、tests/desktop/whole-building-planning.mjs、tests/suites.mjs。

**Interface:** 从现有建筑工具进入规划界面，允许编辑和导入任务书及手工布局、生成多个候选、在逐层平面与剖面切换、按失败定位，支持读取当前制作源证据。通过固定的后端动作发送请求。

- [x] 覆盖规划入口、无效输入、候选切换、剖面、失败位置和源绑定。
- [x] 实现小窗可用的图面、候选比较和规则反馈，使用同一套引擎报告。
- [x] 运行 `mise run build:web`，随后执行规划桌面套件和 `mise run test -- desktop`。

## Task 5 · Skill 接力和验证

**Files:** minecraft-nbt-modeler/SKILL.md、references/knowledge-map.md、references/architecture-workflow.md、规划专题、scripts/nbt_exposure.py、tool-catalog.json、README.md。

- [x] 用规划专题说明用户来源、硬条件、修改冲突、候选采纳和阶段回执。在共享和生成的工作区 Skill 中增加复杂建筑路线，简单亭子仍能沿原路径。
- [x] 运行 `mise run tools:sync`。在隔离创作项目验证生成入口能查询公共契约并运行规划检查。
- [x] 运行 `mise run doctor`、`mise run check`、规划完整套件和适用的建模、质量、工作区和桌面回归。核对最终 diff 与源项目的隔离。

## 验证记录

- 整栋规划套件的 8 项引擎用例和 Electron 规划面板通过。含锁定搜索、真实 SNBT、楼梯、挑空、直通门和未知碰撞。
- 建筑方案回归 34 项、工作区 24 项、通路引擎 8 项、建筑质量引擎 12 项通过。
- 生产前端、环境自检、工具目录及迁移档案检查通过。Electron 冒烟 33 项通过。
