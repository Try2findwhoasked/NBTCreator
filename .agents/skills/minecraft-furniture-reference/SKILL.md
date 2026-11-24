---
name: minecraft-furniture-reference
description: 从现实家具参考图制作 Minecraft Java 1.20.1 原版两格高室内椅、桌、柜。适用于需要拆分部件、记录遮挡推断、对比局部配方、复跑实纹理图或复核家具安装位的任务。
---

# 参考图家具

1. 看原图与目标视角，按[使用说明与输出契约](references/workflow.md)冻结部件意图和配方。区分可见细节与遮挡补全。先保留椅背与低座、桌下通透、柜身贴地等类别轮廓，再取舍原图的细节。家具和审阅镜头均限制在距地面两格内。
2. 用显式 NBTCreator 引擎执行 `scripts/furniture.py build --spec <JSON> --output <新目录> --render`。同工作区的相邻 `minecraft-nbt-modeler` 技能可自动定位。其他安装先用创作工作区的 `paths` 查实际引擎，再把 `--engine <目录>` 放在子命令前。
3. 在与地面相距约 1.62 格的正面和两侧斜视看实际 PNG。从几个格子的常用距离核对类别轮廓。预算允许时，让两个候选共享包围盒、机位和光照，逐项检查可读特征、接缝与牺牲。用第一次输出的 `spec.json` 重跑并执行 `compare`，保留来源、图像和模型哈希。
4. 只有用户要求安装进已有建筑时运行 `host-check`。读取宿主源、保护、可写盒、精确底部支点、相邻通路和必要站位。按宿主已有的 WorkingModel 或选区工作流复核并提交制作版。定稿形态与是否导出按 `minecraft-nbt-modeler` 的显式流程处理。

交付 SNBT 制作源、部件配方、实际缩略图与复跑报告。外观、已验证的静态几何和游戏行为分别说明。用[论文笔记](references/research.md)追溯方法，用[实测记录](references/validation.md)查看已知表现。
