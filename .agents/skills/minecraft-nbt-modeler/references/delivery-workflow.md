# 分层交付与分发

## 工作区加载与输出位置

NBTCreator 的活动源码维护位置为 `.agents/skills/minecraft-nbt-modeler/`。应用同步的工作区使用 `.agents/skills/nbtcreator-workspace/SKILL.md` 和 nbt.py 入口，具体实现/资料冻结在工作区 `.nbtcreator/runtimes/<版本>/`，通过相对链接定位，不依赖目录联接。本文旧路径示例按实际入口映射。

复制或打包整个minecraft-nbt-modeler文件夹即可；在其他工作区解压到其 `.agents/skills/` 下。所有脚本按本skill目录寻找共享模块与参考文件；当前工程tools里的兼容入口不属于分发包，也不是运行依赖。可使用 `$minecraft-nbt-modeler` 调用。

用户未指定输出位置时，新任务按用户时区的实际创建日期保存为 `nbt_models/<形状>/<中文房间名>/<版本>/`。新建NBT、预览和可下载汇总文件使用日期、房间编号及用途命名，例如 `2026-10-31_r001_p00_body.nbt`、`2026-10-31_r001_overview.png`；稳定的工具清单/报告名可保留在日期目录中。完整规则见[生成文件存放与世界转换](output-storage.md)。不自动迁移或重命名旧资产，不把生成物写入skill安装目录；部署到其他工作区时按新工作区解析路径。

新任务的文件分区、迭代版本与超平坦制作世界规则见 [生成文件存放与世界转换](output-storage.md)。涉及游戏内制作或结构/存档互转时先读该文件；已有任务不自动迁移。

- `.nbt`：存放于该任务目录，可自定义资源子目录；分片附偏移清单。
- `coordinates.json`：记录尺寸、局部Y、地板/平台、门高及适用的关键坐标。
- 校验记录、可选预览和配套JSON：存放于同一任务目录；校验记录分别注明开洞前密闭检查、开洞后端口检查及未执行项目。
- 结束时给出实际生成的绝对路径与可点击NBT链接，不只报告默认路径或占位符。

用户要求墙面单独保存时，在整体生成阶段显式记录全局墙体/洞壁坐标，并跟踪后续几何覆盖：后建地板、梁、设备等即使使用相同材质，也必须撤销该坐标的墙归属，可用nbt_wall_layers.WallMask。墙与其余结构层从同一主模型同步切割，不按最终材质猜测墙。制作层省略非选中坐标，不能用满体积空气互相擦除；保留完整合成NBT。当前SAODG支持schema 5：每项parts同时引用body_template、wall_template和offset，两层同尺寸同原点且坐标不重叠，不再填写template；旧schema仍使用完整模板。交付清单注明墙面是否含厚岩体、地板、顶盖及装饰。墙层不是独立门模型；当前门洞连接、封墙和门禁仍由引擎处理。

最终交付目录delivery中每个有效分片恰好两份NBT：`<日期>_<房间编号>_pXX_body.nbt`（不含墙的主体）和`<日期>_<房间编号>_pXX_walls.nbt`（墙面）。单格2份、1×3三格6份、L形三格6份、2×2四格8份；按实际有效cells计数，不为L形缺角生成空文件。新任务调用`nbt_delivery.export_delivery(..., file_prefix='2026-10-31_r001_')`并回读逐块重建；旧无前缀交付继续可验证。完整合成模板保留在独立runtime/parts目录，不混入delivery，也不把“完整模板+墙+主体”三份算作两层交付。JSON、预览与验证报告不计入NBT数量。

不自动写入存档、活动资源目录或房间池。NBT中的显式空气会替换放置范围内原方块，游戏导入在空白制作区域进行。输出文件和Python缓存不加入源码提交。

依赖Python、numpy、Pillow；依赖清单为同目录requirements.txt。需要时在所用Python环境执行 `python -m pip install -r .agents/skills/minecraft-nbt-modeler/requirements.txt`。
