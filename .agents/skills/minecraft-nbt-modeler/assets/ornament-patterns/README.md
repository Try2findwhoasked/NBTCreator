# 建筑纹样库

纹样优先按2～8格的微型单元拟合，再铺排。外部 Agent 使用 pattern_microfit，素材库也默认4×4格单元；pattern_create 默认16×16像素小样。复杂图片先裁取一个基础单元，不把整幅大图当成微型纹样。完整参数见[微型拟合说明](../../references/parametric-components.md)。

```json
{"surface":"wall","size_uv":[4,4],"sample":{"path":"micro.png","sha256":"<原图SHA256>","noise_strength":0},"tile_counts":[4,4],"gap_uv":[1,1],"preview":true}
```

上例供 pattern_microfit 使用。脚本保留主孔洞、连通性和对称性，自动选择楼梯与半砖状态；先做一个单元，再逐份复制。微型墙饰、吊顶贴到既有表面时复用原背板。无法保留主纹时会拒绝并提示裁取更简单的区域或适量增加单元尺寸。

## 小尺寸专用纹样

新增 12 项 `micro-` 原创黑白轮廓，直接按半格采样设计，避免大图缩小后的细线、阴影和碎孔。`pattern_list` 返回的 `microfit.recommended_size_uv` 分别给出墙饰、平面柱饰、吊顶和平齐地板的已测尺寸；`size_uv` 是默认墙饰尺寸，不代表每个安装面都适用。平面柱饰不等于已验证圆柱环绕。

| ID | 纹样 | 墙饰单元 | 使用位置 |
| --- | --- | --- | --- |
| micro-link | 方环链扣 | 2×2 | 小门饰、边带、家具嵌饰 |
| micro-crosslet | 十字花结 | 3×3 | 地砖点缀、梁端、柜门 |
| micro-diamond | 阶梯菱花 | 4×4 | 墙面中心、腰线 |
| micro-diamond-ring | 镂空菱环 | 4×4 | 连续边饰、小窗格 |
| micro-quatrefoil | 四瓣连结 | 4×4 | 吊顶格心、墙裙、门板 |
| micro-key | 方回钩 | 4×4 | 檐下、地板边缘、家具 |
| micro-chevron | 折线边带 | 4×3 | 横向腰线、台座收边 |
| micro-leaf | 单叶与叶柄 | 4×6 | 壁柱、植物主题饰板 |
| micro-bud | 分枝花蕾 | 4×6 | 门侧、竖向饰带 |
| micro-palmette | 扇叶棕榈饰 | 6×6 | 柱头平面饰板、檐饰 |
| micro-scroll | 开口卷钩 | 6×6 | 拱肩、角饰、卷草单元 |
| micro-rosette | 八向花章 | 6×6 | 吊顶格心、墙面花章 |

```json
{"surface":"wall","preset":"micro-quatrefoil","size_uv":[4,4],"tile_counts":[4,2],"gap_uv":[1,1],"material":"quartz_block","preview":true}
```

楼梯与半砖由脚本按材质自动配对并定向。方环在墙上 2×2 格可用四个楼梯保留孔洞；平齐地板和吊顶推荐 3×3 格，2×2 会拒绝。复杂花章仍需要 6×6 格，不能把所有纹样强缩成 2×2。已测尺寸在默认石英材质下保留源连通分量和孔洞，墨迹交并比至少 0.8、覆盖误差不高于 0.15；这些数值不是视觉美感或其他材质、尺寸、环绕方式的保证。测试没有提高微型拟合的允许误差。

源码根目录执行 `mise exec -- python scripts/build-micro-patterns.py` 可重建图片、清单和预设枚举，再运行 `mise exec -- npm run sync:tools`。`--check` 只验证，不写文件。针对性回归为 `mise exec -- python -B tests/micro-presets.py`；完整构件回归已包含该项。

本目录保留 8 张由内置 ImageGen 生成的大幅灰度掩模，以及 12 项基础几何掩模和上述 12 项微型轮廓，供外部 Agent 通过 `pattern_list`、`pattern_compile`、`pattern_preview`、`pattern_mount` 使用。清单记录每张图片的 SHA256、用途及推荐格数，随工作区冻结运行时一起复制。源码维护时不在本仓库生成创作工作区 facade。

圆柱环绕也通过 pattern_compile / pattern_preview 调用，设置 surface=cylinder。既有圆柱用 pattern_cylinder_mount 绑定源建筑和三维目标框。

另有棋盘、条带、砖缝、编织、人字、菱形、回折、之字、十字和四瓣等 12 项基础几何掩模，共用同一清单和拟合接口。各项来源在 manifest 的 source 字段中区分。

| ID | 设计要点 | 适用部位 |
| --- | --- | --- |
| cosmati-floor | 相交菱形、环带和几何边框 | 地板镶嵌 |
| braided-shaft | 竖向编织带、棕榈叶和收边 | 柱身、壁柱 |
| acanthus-capital | 对称莨苕叶、卷涡和水平檐线 | 柱头平面饰板 |
| coffer-rosette | 方格框、中心玫瑰和角部饰纹 | 吊顶、地板 |
| gothic-rose | 放射玫瑰花窗与交织窗棂 | 墙面 |
| acanthus-frieze | 横向卷草和莨苕叶 | 腰线、檐饰 |
| baroque-pilaster | 竖向巴洛克卷草 | 壁柱 |
| pointed-spandrel | 尖拱边框与植物拱肩 | 墙面拱饰 |

生成要求为正交正视、黑底白纹、无文字和透视、没有光照阴影的轮廓样本。导入时拆出单张纹样，裁去空边并补黑边，保留灰度抗锯齿。它们是受建筑风格启发的生成素材，不是历史构件测绘，也不保证可无缝平铺。`repeat` 仅重复样本单元。

从创作工作区运行命令，通过 mise 加载项目环境。`empty.json` 内容为 `{}`。

```powershell
mise exec -- python .agents/skills/nbtcreator-workspace/nbt.py components agent --tool pattern_list --request empty.json
mise exec -- python .agents/skills/nbtcreator-workspace/nbt.py components agent --tool pattern_preview --request pattern.json
```

以下为大尺寸整图拟合示例，微型单元优先使用上面的 pattern_microfit：

```json
{"surface":"ceiling","preset":"coffer-rosette","size_uv":[64,64],"max_changed_blocks":8192,"shapes":{"stairs":"quartz_stairs"},"preset_options":{"threshold":50,"noise_strength":0}}
```

`preset_options` 可调整灰度阈值、反相、镜像、噪声、缩放和配色。自定义图片通过 `sample` 提供同类参数及工作区相对路径、SHA256。先查看真实预览，再将绑定预览交给 `structure_save` 或 `structure_write`。`pattern_mount` 复用 `parametric_surface` 查询出的安装面，返回经保护、开口和占用检查的候选操作；地板镶嵌会声明原层覆盖。

提供楼梯材质后，脚本根据半格轮廓和灰度覆盖率自动选择朝向与上下半部，安装时再转换到世界坐标。无需逐块指定方向。

圆柱请求示例：

```json
{"surface":"cylinder","preset":"braided-shaft","size_uv":[13,32],"repeat":[4,1],"shapes":{"stairs":"quartz_stairs","slab":"quartz_slab"}}
```

圆柱的 size_uv 表示柱芯直径和高度，直径4～30格，实际外径增加2格。周长、局部法线、切线及楼梯状态均由脚本计算。repeat 控制绕周和竖向重复次数，seam_degrees 调整接缝位置。支持竖直等直径柱，现有柱芯需与此离散截面匹配；原版半砖只能选择上下半部。

复杂平面纹样建议先用清单推荐尺寸，再按整体建筑尺度缩小。`fitting` 统计的是重采样二值掩模与所选方块轮廓之间的半格遗漏和多出量，不是与原始图片的视觉相似度。原图边缘未闭合时，环绕后仍可见图样接缝。

维护验证在软件源码根目录运行 `mise exec -- npm run test:parametric`、`mise exec -- npm run check:tools`。
