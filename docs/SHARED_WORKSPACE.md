# 桌面与Agent共用工作区

NBTCreator继续使用原minecraft-nbt-modeler的模型与导出协议。主模型JSON.GZ、显式墙mask、room_description.json、coordinates/cameras、runtime分片、body/walls分层和delivery/validation清单不因Electron或AI接入而改为另一种格式。提示词方案的AI稿是额外文本元数据，不改变模型格式。

## 对齐目录和工具版本

建议Codex在当前项目目录工作，使用生成的 `.agents/skills/nbtcreator-workspace/SKILL.md` 和统一CLI；工具实现与清单位于NBTCreator的minecraft-nbt-modeler目录。原SAODG旧副本不自动双向同步，也不是新应用的活动接口。

0.3.0默认使用调用Agent的项目根目录，资产为该目录的nbt_models。支持显式--workspace、NBTCREATOR_WORKSPACE及手动选择；应用不会默认把安装资源或系统目录当资产根目录。旧默认workspace和文档目录已弃用，旧用户资产应通过迁移命令转入新根目录。

当前项目根目录的 `.nbtcreator/skill-exposure.json` 保存知识组选择，AI助手配置页负责修改并同步生成入口。它是路由与阅读范围配置，不是文件访问权限控制，不删除资料库。所有知识组共享同一份18类工具能力；`tool-catalog.json`为源，`sync:tools`生成网页目录与工具接口文档，`check:tools`阻止版本漂移后打包。

保存的request/settings文件尽量使用工作区相对source/context/cameras/review路径，room_description.master相对描述文件定位；旧绝对路径仍可读取。外部文件或跨盘引擎无法相对化时保留绝对定位，不宣称任意单文件都可独立搬迁。Agent应在项目根目录执行，或对统一CLI使用前置 `--workspace <根目录>`。

共用时选择一个明确的磁盘根目录（其中包含nbt_models），在桌面通过“选择工作区…”指定；误选nbt_models、缓存或房间子目录时会自动识别项目根目录。Agent在同一根目录调用，保存参数使用工作区相对引用；旧绝对路径保持兼容。

切换工作区会同时复制经哈希校验的skill脚本、资源、数据与知识库，保存在目标 `.nbtcreator/runtimes/<内容哈希>/`，再生成指向该本地副本的skill入口。新工作区携带当前知识组，已有目标配置保留。旧工作区及旧运行时不删除；手动改过的生成入口先备份到 `.nbtcreator/skill-backups`。完整项目搬迁后相对入口可直接调用，不再依赖上一个工作区或应用安装目录。

运行时副本不包含node_modules、Python缓存和任务产物；纯Python调用仍需系统Python/NumPy/Pillow，离线批量纹理渲染的Node依赖需按skill说明另装。不要把“已同步skill”解释成完整打包了所有第三方运行环境。

规范资产目录为 `nbt_models/<形状>/<中文建筑名>/<版本>/`；既有建筑从源目录按原版本规则另存下一版。临时预览与任务在 `_workspaces`，不把它们当正式交付。

顶部的“模型编辑 / 提示词方案 / AI助手 / 任务记录”是同一磁盘项目上的功能页，不会自动建立或切换磁盘项目。

## 协作边界

两边可以读取同一版本，但当前没有桌面/CLI统一写锁或自动合并。对同一建筑应轮流修改和导出，完成后重新扫描/打开新版本；不要同时改同一源文件、覆盖已有版本或在另一边保留旧预览继续导出。源哈希和新目录分配能发现部分冲突，不能当作完整并发协作协议。

Agent自主精修继续要求真实看图确认；用户手动调整的明确导出按原网页转换流程。AI建议、参数JSON、意见文件和界面标签都不代替批准或实际验证。
