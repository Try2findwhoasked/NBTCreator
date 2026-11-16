# 建筑方案到主模型、审阅与回查

适用完整建筑或需要稳定构件身份的重设计。先按[整体流程](whole-model-workflow.md)完成用途、玩家站位、通路、空间与顶构的设计，再把能执行和检查的内容写入建筑方案。文本风格仍由 Agent 和用户判断；尺寸、材质、承托及路线交给实际几何检查。

## 入口与设计责任

在创作项目根目录使用冻结入口，先查询契约：

```powershell
mise exec -- python .agents/skills/nbtcreator-workspace/nbt.py capabilities --architecture
mise exec -- python .agents/skills/nbtcreator-workspace/nbt.py architect plan-save --request plan-save.json
mise exec -- python .agents/skills/nbtcreator-workspace/nbt.py architect plan-build --request build.json
```

软件维护使用 `mise exec -- node scripts/cli.mjs --workspace <隔离创作项目> architect <action> --request <JSON>`。全部参数以 `tool-catalog.json` 的 `architecture` 为准，不把 schema 复制进脚本或提示词。无需启动 Electron。

Agent 把自然语言设计转为以下数据，而不是直接猜一串工具调用：

| 设计内容 | 方案中的表达 | 实际落实 |
| --- | --- | --- |
| 用途、层级与可用空间 | `spaces`、`levels`、站位样本与净高，以及 context 的 start/targets | 在最终方块上验站立、支撑、采样净空和起点到各样本的通路；空间包围盒是声明范围，不冒充完整净面积测量 |
| 清晰风格 | `style.materials`、`parameters`、`principles` | 用材质角色和共享尺寸生成构件；`palette` 检查实际材质，`argument`/`ratio` 检查配方，`extent`/`proportion` 检查实际包围尺寸与比例 |
| 整体围护和顶构 | `envelope.volumes` | 对设计空气体积求并集，再生成一次全局边界；闭合屋面台阶与相交体积，不按存储分片重复补墙 |
| 稳定的构件和对象 | `parts` 的 ID、配方、位置和接口 | 调用现有纯配方编译器，保留对象图和世界坐标，安装进同一个 WorkingModel |
| 跨层通行与承托 | `stairs`、`connections` | 生成踏步、可选支承/护栏、跨高梁或托座；逐段走路和实际接口接触复检 |
| 能看见的设计目标 | `views` 的层级、脚位/眼位和目标构件 | 生成真实相机；检查站位、取景范围和采样遮挡，再使用原渲染器出图 |

`standards_snapshot` 可绑定项目规范的完整修订；它保留设计依据，不把自然语言自动转换成“已通过”。需要硬约束的条目应由 Agent 明确译为 style 参数、设计规则和上下文约束。

## 共享参数与构造边界

共享引用只接受 `{"design_ref":"style.parameters.beam_width"}`，可选数值 `add`。引用根限于 `style`、`levels`、`spaces.<空间ID>`，无表达式求值、Python 模块路径或脚本执行。引用循环、未知字段、不适用的规则参数、无效目标、越界和倒置范围均拒绝。解析后再次验证类型和数值。

围护支持矩形或简单多边形平面，以及平顶、双坡、四坡和穹面剖面。它生成一格厚的封闭边界，不自动设计瓦檐、排水、复杂相贯曲线或现实结构荷载。玻璃补丁必须命中实际围护。命名接口选取当前真实表面。

完整梯段复用 `auto_stairs`。可声明支承基底、间距与材质；基底必须有实际支撑。自动护栏当前支持直梯，包含整块侧缘与栅栏/石墙/铁栏杆；半格高差不伪造斜向邻接。转弯梯需要显式设计平台和护栏构件。每次检查都重验各相邻脚位，避免一条捷径替代整个梯段。

`beam_link` 在两个真实向上承托面之间生成有厚度的阶梯形跨高梁；`bearing_block` 在朝上与朝下接口的共同截面内生成托座。接口需满足整格高度、对齐、居中、净跨及最大间隙条件；不舍入半格接口，不把保守碰撞包络当成接触证明。当前没有受力求解。

## 编译、修改与制作版

`plan-save` 使用父 `revision` 保存不可变方案修订，`plan-get` 可取指定版本。它们位于 `nbt_models/_workspaces/project_design/plans/`。`plan-build` 使用内联 `plan` 或 `plan_id`，两者选一；包含 `save_draft:{}` 时才发布 SNBT 制作版。

生成顺序是围护、普通构件、梯段、连接件、密闭检查、按声明开口、全模型与设计检查、可选保存。候选在临时工作模型中组合，提交仍由原 WorkingModel 执行总预算、保护、留白、原对象图政策和路线检查。任何失败都不发布新制作版。生成几何超过构件存储尺度时，只机械分组，不重新设计接缝。

已有源必须同时提供 `source`、`source_sha256`、`expected_plan_sha256`。续版不能暗改画布、保护、开口或路线。构件保留 ID；受管位置若被手改则报冲突，由 Agent 先判断保留或调整方案。无关自由几何保留，旧源不覆盖。重建也保留原对象图声明的保护、留白和路线。

`architect plan-check` 或普通工作模型的检查/保存会重新执行空间样本、当前构件、梯段、附属构造、承托和风格规则。制作版的 `model-instances.json` 记录方案绑定，核心清单继续校验文件哈希。`inspect` 返回 `architecture_sha256`。没有规则时明确报告风格未作机器验证。

## 三层真实看图与问题回写

1. `review-prepare` 绑定制作源和方案，按 `massing`、`structure`、`detail` 生成审阅包和 cameras.json。脚位须能站立；眼位不能埋在实体内。可见度是有限采样，未知细件和透光/光照限制单独报告。
2. 执行回执中的 `render_command`，生成保留顶构的实际纹理图片。相机通过只说明可取景，不说明建筑美观。
3. Agent 实际查看整体、构造和细节图片后，用 `review-record` 提交 `observations` 与 `issues`。每条问题绑定已看图像、层级及可选构件 ID/世界坐标。接口校验制作源、相机、快照、PNG、图片元数据与哈希；观察修订另存不可变历史。文字声明本身不能证明“已看图”。
4. 修改后保存新制作版，`review-compare` 使用原审阅包、原问题记录的 `notes_sha256` 和新源，按稳定构件 ID 返回当前范围。旧坐标只作对照，不自动成为新版标注；问题保持待新图核对。
5. 新版重新准备同一组相机并出图，再记录实际观察。`review-compare` 不自动关闭问题，也不创建精修批准。用户看到对应缩略图并明确同意后，才进入[精修](refinement.md)。

审阅包与图片放在 `nbt_models/_workspaces/` 的新目录，不能写入已发布版本的核心目录。图像缺失、元数据不一致、记录被更改或父修订过时会拒绝回写。

## 目标游戏验收

`game-checklist` 给出放置、邻接更新、旋转、行走、光照五项，初始均为 `not_checked`。`game-record` 记录目标运行版本、报告状态、说明和实际证据文件哈希；没有证据不能报告通过或失败。记录是外部观察台账，不证明引擎见证了游戏执行，也不授权导出。

本流程默认交付 SNBT 制作源。真实游戏测试仍需隔离的 Minecraft Java 1.20.1 环境及明确授权的测试 NBT；最终导出使用独立的显式定稿入口。静态路线、纹理图和游戏内表现分别报告。

维护回归从软件根目录运行 `mise run architecture:test`；真实出图、公共 CLI 与冻结入口回归运行 `mise run architecture:preview`。测试输出放在隔离的 `build/architecture-*` 项目，不写入用户作品。
