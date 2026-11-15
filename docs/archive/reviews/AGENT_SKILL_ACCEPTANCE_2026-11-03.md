# 外部 Skill 阻塞修复与 Agent 前向验收

日期：2026-11-03，Asia/Shanghai。

## 结论

应用与外部 Agent 共用工具的两条主要链路已实跑：提示词首次创建完整 NBT 初稿；工作台评论索引到候选计划、验证和同相机图。原建筑与原意见保持，已有建筑只生成候选，没有批准、apply 或正式下一版。

初轮验收的源码与知识同步到 NBTCreator、SAODG 两个工作区，当时活动 runtime 为 `1cf964568eebf48d`；后续改进见文末复查记录。测试过程保留旧冻结 runtime 和失败证据，未把旧报告改为通过。未创建 GitHub 发布或新版 portable ZIP。

## 修复内容

- **共享渲染环境**：同步生成 `.nbtcreator/render-runtime.json`，相对关联安装的锁定 Playwright、Node/Electron 和浏览器。工作区无需复制 node_modules。独立安装保留 package-lock.json；打包时显式补回 Electron Packager 默认排除的 viewer 锁文件。
- **候选出图**：公开 `render --snapshot` 接受 control preview 的 before/after 展示快照，核对原稿哈希、尺寸、原始几何指纹和展示状态，仍仅出图。无需 Agent 手工拼接底层 renderer 命令。
- **保守通路**：仅对经本机官方 1.20.1 类字节码核实的有限名单建立障碍上包络，代理不提供支撑。云杉栅栏包络明确为 1×1.5×1；其余未支持形状继续拒绝。报告区分保守路线证明与精确几何支持，未知细件不当空气、不删细节。
- **评论索引**：工作台保存、修改状态及导出评论时更新当前结构版本 `修改意见/评论索引.json`。原图/3D快照/@引用按哈希归档到版本内，sidecar 使用相对路径，保留原评论/快照字节。
- **模型调用脚本**：`nbt_feedback.py` 经共用 tool-catalog 和工作区 facade 暴露为 feedback scan/collect/archive。scan 查版本索引；collect 校验源/评论/证据并给出原图像素与3D坐标；archive 给旧意见补稳定证据和版本索引。
- **使用说明**：补入首次创建、已有标注、版本内交接、生成入口路径和独立入口适配边界。模板路径不再被解释为所有工作区都存在旧引擎目录。

```powershell
python .agents/skills/nbtcreator-workspace/nbt.py feedback scan --workspace .
python .agents/skills/nbtcreator-workspace/nbt.py feedback collect --version nbt_models/形状/中文名/版本 --output nbt_models/_tasks/意见报告_新编号
python .agents/skills/nbtcreator-workspace/nbt.py render --snapshot <候选after.json> --cameras <相机JSON> --output <新出图目录>
```

## 真实建筑复验

SAODG 的“错断引水廊” draft04b 源 SHA256 始终为 `36761152c220180ab05f15397201cc7dba552b944c39fd669194d4ada5523d8a`。两条意见和全部证据校验通过；已新增版本索引及稳定证据，不改原意见。

工作区 facade 直接批量渲染8视角成功。基线 validate 通过、prepare 可生成 awaiting_user_review、零操作计划由 planned_unverified 恢复为 planned。37格原有细件仍明确作为保守障碍，exact_geometry_supported=false，不声称薄形状精确碰撞或游戏验收。

原证据及修复复验保存在 SAODG `build/nbtcreator-audit-20261103/`；本次源码测试与独立工作区在 NBTCreator `build/skill-unblock-20261103/`。

## 独立前向测试

两个测试 Agent 均不继承修复讨论，只从独立工作区的 AGENTS、实际任务提示词与暴露 Skill 开始。它们按 Skill 阅读，保留阅读记录、脚本、真实产物与失败；主 Agent 实际查看代表图并额外回读最终 NBT。

### 首次创建

工作区：`build/skill-unblock-20261103/forward-workspace/`。

提示词要求“雨后检修水亭”：48×16×48包围盒、紧凑石木使用区、低位检修槽、高半层、连续栏护、可解释的排水修补和支承顶构。Agent 自行编写任务生成器并通过公开入口出图，按初稿问题保留前三版，最终版为 `nbt_models/single/雨后检修水亭/v_2026-11-03_112949/`。

最终主模型几何 SHA256：`4cf46dd8e19be307672e78397e180b40e4e10cbde3fd9248a95f38b21634fdb2`。完整 NBT、主体/墙两层均真实落盘。密闭前检查、声明入口差分、重封复查、10个目标通路、90个两格净宽断面、指定阶梯路线、回读和分层重建通过。Agent 实看14张最终纹理图，主 Agent 复核整体、入口、顶构/支承及关键节点，并用当前引擎重新回读完整 NBT 和两层确认逐状态/墙mask一致。

限制：当前自定义独立入口由任务脚本做受限开洞与差分检查，现有 open_ports 是 SAODG 6×5端口专用；文档已明确这个适配边界。静态玻璃表达水，不声称实际水流或可操作闸门。没有用户精修批准或游戏验证。

### 真实评论交接

工作区：`build/skill-unblock-20261103/comment-forward-workspace/`，仅使用真实建筑和意见的隔离副本。

Agent 自行 scan/collect 找到两条意见。图片意见最初误读为显眼木件，主 Agent 要求按原始像素复核后纠正到凝灰岩墙；这一过程保留在报告中，不能声称首次语义定位全自动正确。工具因此增加 locations 中的精确像素信息，但二维图点仍不等于原生3D命中。

Agent 生成36项操作、66格候选：整段阶梯两侧连续栏护及墙面浅层成片变化。中央三格路线和外边界保持，113个输入文件哈希未变。首次候选因云杉栅栏未支持而失败；补足有依据的1.5格障碍后，对**同一份未修改候选**复验：基线与候选 validate 通过，7个目标和额外阶梯连接通过。公开 render --snapshot 完成前后各4图，与原底层入口图像素一致。

报告及图：`nbt_models/_tasks/2026-11-03_comment_forward/2026-11-03_cf_retest-v2.md`。旧失败保留，不覆盖；意见仍open，没有批准或正式导出。主 Agent 已实际查看墙面和梯段对比图，具体风化处理仍属于可审阅的候选设计。

## 实际检查

| 检查 | 结果 |
| --- | --- |
| doctor、工具清单同步、Skill语法/路由 | 通过，18类建模工具和37份知识文件 |
| 桌面回归 | 23项通过，`build/desktop-1793675971052/results.json` |
| API/方案合约 | 16项通过，无真实API模型调用 |
| 工作区合约 | 8项通过 |
| 碰撞回归 | 18个场景、40个楼梯状态组合，含必须拒绝的阻挡/假支撑/未知/严格模式反例 |
| 精修/网页回导合成回归 | 34项/10项通过，确认记录仅用于合成数据 |
| 渲染环境/快照校验 | 4项通过，含无环境变量的同步 facade 实际出图及篡改拒绝 |
| 评论存储/证据/迁移 | 14项存储检查、11项证据断言、2项Python合约、4项浏览器集成通过 |
| 新打包应用 | 打包成功，viewer锁文件保留；新打包Electron/Playwright结合现有便携私有Python/浏览器，在PATH仅System32且清空NBTCREATOR环境后，工作区facade出图通过 |
| 最终人工复核 | 两类前向产物实际看图；原模型/两条意见保持，最终初稿NBT及墙mask重新回读通过 |

打包验证不是新版完整ZIP发布验收；结果在 `build/skill-unblock-20261103/packaged-private-result.json`。本轮没有重跑真实Minecraft、49布局、旋转、多人、重连或重启验收，不将保守路线和纹理图作为这些项目的替代。

## 根据 Agent 原始汇报继续改进

再次核对首次创建的 forward_acceptance_report.json、评论交接的原始报告和复验报告；已解除的渲染/栅栏阻塞不重复记为当前失败。agent 自己任务脚本中的临时语法错误不转化为 Skill 通用限制。

仍有依据的三项使用摩擦已改进：

1. **不再猜引擎目录**：新增 `nbt.py paths`，返回当前 scripts/references、Python 及冻结 bundle 指纹。迁移后按实际入口定位，任务脚本可记录工具版本，不需解读包装器。
2. **补齐独立入口 API**：新增 `nbt_openings.open_declared_openings`，支持任意位置/尺寸、四方向和厚墙的声明开口。仅接纳未变的真实密闭主模型；全量预检范围、两侧喉道和地板格后才改块，维护显式墙mask，返回逐块前后状态。无效的后续声明、缺地板或堵喉道均整体拒绝，不留下部分开洞。支撑碰撞、净宽和路线仍需独立验收。
3. **阶段阅读更清楚**：生成入口增加新建、已有标注、已批准精修、交付和只读维护五条路线；基础知识启用不等于每次全部阅读。保留新建四份完整设计阅读，以及实际阶段相关的完整章节，不再让长原型库、精修和 SAODG 接入成为每次默认负担。

补充验证：6项独立开口合约、9项工作区合约通过，含迁移后的 paths 可调用及 API 可导入；桌面23项重跑通过，记录在 `build/desktop-1793677925090/results.json`。对已生成水亭的内存副本封回声明门洞、重新检查密闭，再由新 API 开门，得到与原 agent 结果逐状态相同的几何和墙mask（12格差异），原文件哈希未变；此为副本回放，不重写原始开洞前验收记录。证据为 `build/skill-review-20261103/aperture-replay.json`。

更新已同步两工作区，活动 runtime 为 `b4ef6238dd149ec3`。未用新 API 修改真实建筑，也未改写旧测试报告。二维标注仍需实际看图确认对象；计划 planned 仍不等于候选通路/设计通过，候选需要显式验证。独立开口本身也不授予已有资产修改授权。
