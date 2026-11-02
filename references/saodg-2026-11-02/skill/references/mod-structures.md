# 模组内已接入结构管理

此入口管理 SAODG 源码已登记的房间与实际 NBT 引用。它与 `nbt_models` 作者素材库分开：主数据来自 `src/main/resources/data/saodg/rooms`、`dungeons` 和 `structures`，中文名优先使用实际 `zh_cn.json`。没有可靠名称时保留资源ID，不猜测与作者历史版本的对应关系。

管理器和作者结构库已合并到工作区 `tools/structures/workbench/`，与原细节控制台分开存放、分开启动。双击仓库根目录的 `启动结构工作台.cmd`，或运行：

```powershell
python tools/structures/workbench/launch.py
```

支持 `--workspace`、`--port`、`--no-open`。Python/Node/可选viewer依赖与[细节控制台](detail-control.md)一致。本地服务仍只绑定127.0.0.1、拒绝跨站请求，用参数数组启动Python。

## 房间池与用途

1. 选择实际地牢定义；卡片复选框表示该房间是否在这个地牢的 `layout.room_pool` 中。“未选用”不等于删除，未入池的功能房及其模板完整保留。
2. 按已入池、未选用、待修改、用途和形状筛选，搜索中文名、房间ID或模板ID；卡片每页24项，支持批量加入/移出本页。
3. 点击卡片查看用途、尺寸、单元、端口、门高、旋转、遭遇/谜题引用，以及每个分片的完整模板或主体/墙面配对、作者偏移与实际文件路径。
4. 可编辑 `selection_priority`，范围与当前加载器一致为0～100整数。优先级不是概率权重，修改房间定义会影响所有引用该房间的地牢。
5. 所有选择和优先级先是页面草稿。“查看并保存修改”列出加入、移出与优先级差异；再点“确认写入源码配置”才写文件。刷新/切换地牢时遇到未保存草稿会要求先保存或放弃，避免静默丢失。

不提供删除房间、删除NBT、改端口、自动迁移资产或伪造精修批准的入口。已有结构的造型修改继续遵守主skill的真实看图确认与完整主模型流程。

## 预览来源

卡片封面直接回读当前模组的NBT，按房间parts与48格作者偏移组合完整几何；schema 5在同一part合并互斥的主体/墙面并保留墙归属，检查层尺寸和非空气重叠，不按材质猜墙。封面为纯色几何剖视，剖切高度约为房高60%；它与纹理图、实际运行光照及设计验收分别报告。不会把作者库另一版本的图片用作模组当前结构的证据。

封面按需计算、最多并发2项，缓存于 `build/structure_workbench/mod_structure_thumbs`，键绑定实际房间定义和模板内容哈希。“查看实际结构3D”另生成只读快照并按需打开基础viewer，不启动细节控制台；可用原预览的剖切、主体/墙面、相机工具。关闭后释放iframe和预览服务。大结构与纹理资源加载仍有成本；快照使用48连续作者坐标，不等于49格运行展开验证。

## 保存与恢复

- 保存范围限于选中地牢的room_pool，以及明确编辑的房间selection_priority；保留其他JSON字段，不写NBT，不更新现有JAR或存档。
- 目录修订号绑定所有房间、地牢及引用NBT的实际内容哈希。提交时重新扫描，源已变化即拒绝；准备临时文件后再次核对，避免覆盖其他任务的新修改。
- 检查房间池1～256项、ID不重复、已登记且模板存在；从实际各难度sequence检查每种必要用途至少有一个候选，不允许移除最后一个入口、封印厅、首领等必要类型。它不执行Java布局生成器，不证明特定端口组合、布局种子或游戏重载一定通过。
- 写入前将原文件的完整字节备份到 `build/structure_workbench/mod_structure_changes/<时间_UUID>/backup`；保留request、changes及result。唯一临时文件原子替换，失败时回滚已替换文件；进程锁避免同时保存。异常崩溃遗留锁时先检查相应进程与日志再处理，不自动盲删锁。
- 修改的是源码资源。需重新构建并更新实际模组；这里不会自动部署，运行中的游戏也不会自动读取源码路径。实际资源重载及布局检查按当前加载器另验收。

## 工具专项验证

```powershell
python tools/structures/workbench/tests/check_backend.py --output <新后端目录>
node tools/structures/workbench/tests/test-mod-structures.mjs --fixture <上述目录>/workspace --output <新浏览器目录>
python tools/verification/content_audit.py --check
```

此专项已移至独立工作台tests，不再由skill的nbt_task.py regress发现。测试只改合成工作区，涵盖实际NBT回读合成、草稿不写、仅修改目标字段、精确字节备份、过期修订拒绝、部分写入失败回滚、缺失模板/必要类型拦截、原NBT和未选功能房保留。浏览器另测筛选、审核再保存、3D加载/释放、窄屏和跨站写入拒绝。生产引用审计与工具测试不替代Java/游戏验收。
