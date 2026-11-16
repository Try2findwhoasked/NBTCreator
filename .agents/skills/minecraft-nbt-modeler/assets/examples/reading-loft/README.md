# 归卷阁：窗边收卷，再登梯归架

从已同步 NBTCreator 对外 Skill 的创作项目根目录运行。归卷阁三个情形共用[建筑方案](plan.py)；[归卷院](courtyard.py)演示两栋建筑和街道的连接。脚本通过当前项目的 `nbt.py` 调用公共接口，完整请求和原始回执在每次新建的 `nbt_models/_workspaces/examples/reading-loft-*` 目录。成功例另存一栋带本次运行编号的 SNBT 样例建筑。

```powershell
$entry = '.agents/skills/nbtcreator-workspace/nbt.py'
$engine = (python $entry paths | ConvertFrom-Json).engine
$example = Join-Path $engine 'assets/examples/reading-loft/run.py'
python -B $example open
python -B $example blocked
python -B $example wrong-side
python -B $example courtyard
```

## 成功例

`open` 依次保存方案、建模、从落盘 SNBT 回读检查、准备审阅包并出图。打开本次目录的 `review/render/`，先看外观和完整屋顶，再对照下表。对应的脚位、构件 ID 和机位都在 `plan-save.json`；活动各段的实际通路在 `plan-check-result.json` 的 `validation.architecture.checks` 中，查找 `file_books`。

| 机位 | 要核对的细节 |
| --- | --- |
| `outside` | 看两扇窗与中间入口的节奏，沿山面检查瓦坡、封檐木和通长檐口能否读成连续的屋盖。 |
| `window` | 从斜侧看石窗台的薄边、玻璃相对木柱的退进，以及窗柱底下的石座。 |
| `frame` | 在室内保留屋顶仰看跨厅梁，沿梁察看柱头托木，再看中央短柱与纵向脊檩的交接。 |
| `counter` | 浅木半砖形成台面薄边，深木端柜托住两头；后排分卷格朝向工作侧。核对从台前能否看清分格并留有放卷的台面。 |
| `landing` | 从夹层回望，核对最后一段踏步与平台是否接平，护边是否给转身留了出口。 |
| `cabinet` | 从平台朝书柜看，核对书格的使用面、顶部压条和柜前站位。 |

成功时脚本输出制作源和图片目录。Agent 实际看图后记录观察，把初稿缩略图交给用户审阅。玩家通路使用静态碰撞检查，游戏内放置、光照及精修批准各自另行记录。

`sections/` 另有同源的首层、夹层平面和沿梯纵剖。对照[相机及切面坐标](loft-sections.json)看柜台与梯脚的相对位置、夹层出口的转身空间和梯段上方余量。在 ID 为 `file_books` 的活动检查中读取 `use_faces`，可找到两处操作面的接口名、世界朝向、实际距离和命中半格。

## 堵梯口例

`blocked` 把同一只三格宽的书柜从后排 `[4, 5, 24]` 移到梯顶 `[4, 5, 19]`。它正好占住出口脚位 `[5.5, 5, 19.5]`。`plan-build` 应以非零状态退出；在本次 `plan-build-result.json` 中查找 `ROUTE_FAILED`、目标 `stair_landing` 和该脚位。看到文件路径、依赖或机位错误时，应按实际错误排查。

把柜子移回后排即可复验。保留原有踏步、活动脚位和检查条件，用同一段路判断摆放是否合适。阻塞例在候选阶段结束，制作源与图片取自成功例。

## 可以走通，但站在柜台背面

`wrong-side` 保留成功例的全部方块，只把收卷活动的第一站移到柜台背后 `[13.5, 2, 11.5]`。检查仍应找到全部三段通路，`return_desk.intake` 返回 `wrong_side`，建模以 `DESIGN_INVALID` 非零退出。复查使用者该站的位置或柜台本身的朝向。

## 两栋建筑与院路

`courtyard` 生成较高的阅览室和较低的值房。依次打开 `district`、`turn`、`entrance`、`intake` 四张图，从全景看主次、从街口看转向、从门前看石槛、从案前看工作面。`public_lane_without_guard_room` 在验证副本中暂时封住值房内部，复验访客仍可从街道走到收卷案。值房本身另有可达目标。

出图后的终端摘要会显示尚待观察的机位和位置。看清哪些就在 `review-record` 登记哪些，使用该回执的 `delivery_summary` 交付。即使已有代表性的整体、构造、细节三层观察，只要某台相机还未记录，摘要仍会逐名列出。
