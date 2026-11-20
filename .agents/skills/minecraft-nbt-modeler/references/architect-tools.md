# 建筑师辅助工具

这些入口复用现有建筑库、创作方案和建筑编辑面板，不增加必经阶段。

## 可执行建筑方案

复杂整栋使用[建筑方案、构造与审阅闭环](architecture-workflow.md)。`capabilities --architecture` 查询 `architect plan-*`、`review-*` 和 `game-*` 的严格契约；与项目文字规范、桌面批注和显式定稿各保留自己的责任。无需启动 Electron。

## 项目约束

在建筑库左侧选中项目或形状文件夹，再点「管理约束」。例如「SAODG / L 形」对应 `nbt_models/SAODG/l_shape/项目约束.json`。可用 1×1、L 形模板填入初始尺寸和网格，也可只填写通行或净高要求。选「全部项目」时，「共用约束」打开兼容旧版的 `nbt_models/_workspaces/project_design/constraints.json`。

在创作方案的「项目约束」中先选文件夹，再勾选要写入提示词的约束。「Agent 创建约束」在所选文件夹中填写草稿，核对后手动保存。切换文件夹会保留勾选，冲突的尺寸、形状或网格不能同时引用。取消勾选后恢复原设计参数。已有建筑的尺寸和形状仍取自模型。批量编写沿用当前方案的勾选，空白方案由用户勾选。

方案 JSON 的 `constraints` 保存已选约束的版本和内容。文件夹中的约束改版或移除后，旧方案仍使用当时的版本。在方案里点击「改用第 N 版」才会替换。选择约束文件夹只改变可选的规则，建筑保存目录仍由方案的形状和建筑名称确定。

外部 Agent 可直接使用工作区入口。先准备 `folder.json`，写入 `{"folder":"nbt_models/SAODG/l_shape"}`。读取该文件夹的 `revision` 后，在 `constraint.json` 中填入下方保存参数。

```powershell
mise run nbt -- architect constraints-registry --request registry.json
mise run nbt -- architect constraints-list --request folder.json
mise run nbt -- architect constraints-save --request constraint.json
```

`constraints-registry` 统一查询内置与工作区约束。请求可包含 `folders`（例如 `["", "nbt_models"]`）、`summary` 和 `id`。返回的 `groups` 按来源列出 `builtin` 和 `workspace`，每条完整规则使用相同的快照格式。常用形状来自 `constraint-presets.json`，SAODG 接入单独来自 [扩展约束](../constraint-extensions/saodg.json)，在实际需要接入的任务中显式引用。工作区规则继续用 `constraints-list`、`constraints-save` 和 `constraints-delete` 管理。

项目可以单独约束密闭（`require_enclosure`）、是否设置通行洞口（`openings_policy`）及其净宽、净高（`opening_size`）。这些字段随已选修订进入交接上下文。实际洞口坐标和朝向由执行 Agent 在 `coordinates.json` 中补齐，见[验证流程](validation-workflow.md)。

```json
{
  "folder": "nbt_models/SAODG/l_shape",
  "revision": 0,
  "name": "L 形 32 格院落",
  "actor": "agent",
  "rules": {
    "buildingShape": "l_shape",
    "size": [64, 24, 64],
    "size_policy": "fixed",
    "cell_size": 32,
    "cells": [[0, 0], [0, 1], [1, 1]],
    "footprint": "缺角留作庭院，不放方块",
    "requirements": "主入口净宽至少 3 格"
  }
}
```

`folder` 使用工作区内已存在的 `nbt_models` 相对路径。省略时读写工作区共用约束。修改时加上原约束 `id`。删除用 `constraints-delete`，传 `folder`、最新的 `revision` 和 `id`，此前的版本仍保存在该文件夹的 `.project-constraints/constraint-revisions/`。`size_policy` 需要 `size`，只填 `size` 时按固定尺寸处理。`cells` 需要 `cell_size`，坐标不能重复或超出尺寸。每个文件夹最多保存 256 项，每份方案最多引用 16 项。字段契约见能力目录的 `project_constraints`。

## 项目设计规范

建筑库“建筑工具 → 项目设计规范”，或创作方案列表中的“项目设计规范”。统一记录材质、尺度、通行、风格、参考说明和其他要求。保存形成新的修订，位于 `nbt_models/_workspaces/project_design/`；新建方案引用最新修订，已有方案保留自己保存的规范快照。

在创作方案中打开规范，可明确引用当前修订，填写“当前建筑的例外”，或移除当前方案的引用。引用/例外改变后需重新审查该提示词。引用会进入提示词全文、方案 JSON 和 AI 的设计上下文；参考文件内容不会自动读取。项目规范是设计要求，不改变引擎的保护、改动预算、格式约束或真实看图确认条件。Agent 接手时使用任务内的快照，不用最新项目规范静默替换旧任务要求。

无界面读取：`mise run nbt -- architect standards-get`。保存使用 `architect standards-save --request <JSON>`，参数为当前 `revision` 和完整 `fields`（name、materials、dimensions、circulation、style、references、notes）；每项最多4000字，修订冲突时重新读取核对。

## 集中审查

建筑编辑左侧选择“审查”，在同一面板查看任务、回传说明、Agent 对原批注的处理声明和人工核对状态。筛选待核对或仍需修改的意见；启动同镜头版本对比后，面板仍保留，3D 画布可操作。关闭审查面板时结束对比并回到工具。它复用 `agent-tasks` 的原评论和人工核对接口，状态不自动解决正式标注或批准整座建筑。

## 交付清单与继续修改

建筑库“建筑工具 → 交付清单”按当前筛选核对制作版本，单次最多300项；超过时请缩小筛选。显示未定稿、交付完整、制作源或交付变化、缺失及无法核对。清单核对源哈希及 release.json 声明的全部文件，可下载 JSON；不会自动导出。游戏内表现仍单独确认。

在完整的定稿项目行或“版本”面板选择“从定稿版继续修改”，复用版本历史派生新的 SNBT 制作版，保留父版本关系并设为当前工作版。旧源和 `_exports` 交付副本保持原位，原版标注不复制为新版坐标。完成后由用户明确再次定稿。

CLI：`architect deliveries --request <JSON>`，参数 `sources` 是工作区内制作源列表；`architect continue --request <JSON>` 使用 `source`、`source_sha256` 和可选 `message`。continue 是明确分配新版本的操作，不自动重试。

## 批注跨版本核对

建筑编辑“标注”面板或“版本”面板打开“批注跨版本核对”。从同一建筑实际版本目录选择原版本（旧文件无需先登记 Git 历史），读取正式批注及证据，记录新版符合、仍需修改、不再适用或待核对，以及人工备注。原位置只供对照，不能自动成为新版正式标注；需要新位置时在新版重新选点。

核对保存在目标制作版本的 `修改意见/跨版本核对.json`，分别绑定原源哈希、新源哈希、原批注身份和内容哈希。任一建筑或原批注变化后，旧结论不自动沿用。证据无效的批注不能保存为已核对。原批注、原证据与原状态保持独立。

CLI：`architect cross-list --request <JSON>` 使用 `source`、`source_sha256`、`reference_source`；省略 reference_source 时仅扫描同一建筑的版本文件元信息（最多200个，不读取完整模型）；`cross-save` 还需 `reference_sha256`、最新 `revision`、`key`、`content_sha256`、`state`（pending/accepted/rejected/obsolete）和可选 `note`。全部调用可通过当前工作区 Skill 或独立 CLI 完成，无需 Electron。
