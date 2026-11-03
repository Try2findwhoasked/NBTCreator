# 工作区构件资产

资产管理保存可复用的体素构件，不覆盖源建筑。库位于工作区 `.nbtcreator/components/`，随工作区移动，不进入应用安装包。

## 保存与读取

```powershell
python .agents/skills/nbtcreator-workspace/nbt.py components list
python .agents/skills/nbtcreator-workspace/nbt.py components save --source nbt_models/形状/建筑/版本/master/master_geometry.json.gz --name 石柱 --lo 8,4,8 --hi 10,10,10 --tags 支承,石构
python .agents/skills/nbtcreator-workspace/nbt.py components get --id <构件编号>
python .agents/skills/nbtcreator-workspace/nbt.py components place --id <构件编号> --position 20,4,20 --size 48,24,48 --quarter-turns 1
```

`--workspace <目录>` 放在 components 后、子命令前；默认当前 Agent 工作目录。`place` 只返回 operations/lo/hi，不执行写入。将返回的操作合入 control 请求，按原 preview/validate/新版本导出流程使用。

构件的 position 是锚点在目标模型内的坐标，默认锚点为底部中心。不静默裁切或收拢越界构件。原主体与墙 mask 拆为不同操作以保留归属。默认不包含空气；显式保存空气时，空气也是实际写入。默认拒绝目标实体冲突，需要用户明确选用 overwrite 才允许覆盖，仍不能修改保护区。

需要一次放置多份或复用材质映射时，使用 `components batch`，详见 [参数化配方、主题与XYZ阵列](reusable-recipes.md)。构件详情可设置数量和锚点间距；配方与主题入口在资产管理左侧，不占用顶部浏览空间。

每轴最多64格，总计最多65536个记录。旋转为绕Y轴90°的整数倍，可选 X/Z 镜像；采用保守状态转换，暂不支持的楼梯、门、轨道等状态明确拒绝，不猜朝向。

## 数据与管理

JSON schema_version=1，包含 name、tags、size、anchor、palette、blocks 和 content_sha256。blocks 是 `[x,y,z,材质编号,是否墙层]`。导入会验证哈希、坐标、状态和尺寸；不接收代码或脚本。缩略图是本地简化材质示意，不代替正式纹理审阅图。

```powershell
python .agents/skills/nbtcreator-workspace/nbt.py components import --file 柱子.component.json
python .agents/skills/nbtcreator-workspace/nbt.py components update --id <编号> --name 新名称 --tags 石构,支承
python .agents/skills/nbtcreator-workspace/nbt.py components update --id <编号> --archived true
python .agents/skills/nbtcreator-workspace/nbt.py components update --id <编号> --archived false
```

回收操作保留几何和缩略图，可以恢复。UI 与 CLI 读取同一库和索引；已缓存列表不重复解析体素。导入/放置后的作品仍需真实预览、相应检查及用户导出，保存资产不代表批准精修。

## 3D 手柄与选区移动

模型编辑的“构件”菜单提供复制选区、移动选区；资产管理也可选择“3D 手柄调整后放置”。拖动箭头移动，绿色圆环按90°旋转，支持X/Z镜像、整数网格及表面贴放。示意仅在视口显示；取消不添加步骤。应用后由同一引擎生成真实候选，满意后手动导出下一版。“应用后继续复制”保留已应用的副本，取消只关闭下一份示意。

无界面接口增加 `components extract` 和 `components transform`，具体参数用 `--help` 查询。extract仅返回构件而不保存库；transform返回移动/复制所需的操作，不直接修改文件。网页接口绑定当前显示模型的源哈希与快照；移动只清除提取的实体格，再放置到目标，保留选框内空气和无关结构。旋转/镜像同步转换方块朝向和墙层归属。

## AI 构件写入与整体移动

AI返回选区内相对坐标的box/beam/frame或少量离散方块，本地引擎负责合法状态、坐标平移、保护、预算与NBT导出。应用保存最近构件的原始坐标基础，整体移动使用相对于该基础的偏移；归零恢复原位，不重复堆叠步骤。草稿恢复后仍可移动。

“允许AI构件覆盖现有方块”仅允许替换实际写到的格子，不清空整个选区，也不放宽保护和改动预算。API不能自行授予覆盖权限。write_group由应用生成，使一份构件的柱帽等步骤可以覆盖本组刚添加的柱身，而不能占用旧建筑的方块。

小型结构建议压缩为不超过48步，同材质连续体积优先使用box。如果API明确因长度上限截断，应用最多额外请求一次24步以内的精简完整方案；不续写或应用半截JSON。任务详情记录API阶段、本地预览阶段、重试次数和接口提供的令牌统计；其中任何一次预览失败都不等于正式建筑被修改。
