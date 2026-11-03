# Agent 批量出图与用户交互预览

NBTCreator 1.1的桌面包和已构建skill使用web-dist静态页面/资源，由本机HTTP服务加载，不需要Vite运行服务。工作区同步会带上构建资源；无构建的源码副本仍可按下方npm ci安装开发依赖，或在NBTCreator根目录运行npm run build:web。批量出图仍需Node、Playwright及可用浏览器，不把移除Vite服务解释成移除了这些依赖。

通过应用同步工作区 Skill 时，会同时保存 `.nbtcreator/render-runtime.json`：以该配置文件为基准的相对路径关联应用已安装的 Playwright、Node 和可选便携浏览器。外部 Agent 直接使用 `python .agents/skills/nbtcreator-workspace/nbt.py render ...`；无需打开 Electron、手工找安装路径或给每个工作区复制 node_modules。渲染脚本和前端仍使用工作区冻结版本，只共享依赖，并核对 Playwright 版本。跨磁盘无法相对表示时才保留绝对路径。

将应用和工作区一起保持相对位置移动，关联仍可解析；单独搬走工作区或卸载应用后若依赖不存在，在新应用中重新同步暴露配置，或按下方锁文件安装独立依赖。不要把工作区绑定文件或环境变量当作跨机器自带运行时的保证。需要显式指定共享 Playwright 时可设置 `NBTCREATOR_PLAYWRIGHT_MODULE` 为其模块目录，版本仍须匹配本 skill 的 package.json。

纹理渲染使用Lodestone 0.6.0默认资源包，只辅助视觉判断，不认证游戏碰撞、完整光照、通行或设计质量。原有 `nbt_preview.py` 纯色几何诊断与 `nbt_sections.py` 保留。

## Agent 默认走批量入口

需要多角度纹理质检时，优先调用 `nbt_task.py render`，之后直接用图像查看工具读取输出PNG。不要为了常规出图启动computer use逐个切相机、点击下载、再从浏览器下载目录搬图。网页交互用于用户自由查看，或明确测试网页本身；仅生成图片不需要网页操作。

```powershell
python .agents/skills/minecraft-nbt-modeler/scripts/nbt_task.py render --source <完整NBT或主模型JSON.GZ> --cameras <相机列表JSON> --output <任务目录>/previews/texture_v01 --file-prefix YYYY-MM-DD_r001_
```

control preview 的 before.json/after.json 是展示快照，不能传给 --source 或冒充已落盘主模型。候选出同相机图使用 `nbt.py render --snapshot <before或after.json> --cameras <相机列表JSON> --output <全新目录>`。此入口核对原稿 SHA256、预览原始几何指纹、实际展示状态与尺寸，仍只输出图片，不生成 NBT 或批准，也不认证候选通路。原稿或快照变化后重新计算候选。--snapshot 不和 --source/--provenance 混用。

将日期、房间编号、路径替换为本次实际值。输出目录必须不存在；已审阅的图像与哈希不覆盖，重出图另建版本目录。`--provenance <operations.json>` 可附带匹配当前几何的操作来源；不匹配则拒绝，不从材质猜墙或从单个稀疏层冒充完整来源。

一个批次复用一个临时本地服务、一个离屏浏览器和一个页面，顺序完成各视角。不会打开用户窗口或连接用户浏览器账号，不出现下载对话框；图片直接写任务目录。正常结束或异常会关闭创建的浏览器和服务；不会替用户关闭已有网页服务。

首次安装可选依赖：

```powershell
npm ci --prefix .agents/skills/minecraft-nbt-modeler/assets/viewer
```

独立复制 skill 时保留 viewer/package.json 和 package-lock.json；生成入口的相对 viewer 路径以实际 runtime 为准。安装失败应检查锁文件、Node 和网络，不改用未锁定的最新依赖。源代码副本没有 web-dist 时上述安装支持开发前端；应用同步副本已带预构建前端。

批量入口自动选用已安装的Playwright Chromium；Windows无该运行时时，选用已安装的Edge或Chrome，以新临时配置无头启动。若都没有，在viewer目录执行 `npx playwright install chromium`，或指定 `--browser-executable <浏览器可执行文件>`。不全局安装，不自动下载其他版本，不复制node_modules进分发包。状态/NBT核心工具无需浏览器。

## 相机列表

输入为1～64项的JSON数组。以下仅为48×24×48模型的语法示例，实际相机必须按源模型和站位选择：

```json
[
  {"id":"overview","role":"整体剖视","eye":[65,38,-22],"target":[24,9,24],"cuts":[{"axis":"y","position":20,"removed_side":"above"}]},
  {"id":"entry","role":"未剖切入口","eye":[24.5,3.62,2.5],"target":[24.5,4,22],"fov":60},
  {"id":"ceiling","role":"完整顶构仰视","eye":[24.5,3.62,18.5],"target":[24.5,15,24],"lighting":"day"}
]
```

- `eye`、`target`：Minecraft XYZ有限坐标，Y向上；玩家视角由真实脚位加约1.62确定，不把浮空QA机位冒充可站立视角。
- `id`：可选、批次内唯一，只允许小写字母、数字、下划线、连字符；省略时依次为view_001等。`role`为可选说明文字，可用中文，不参与文件路径。
- `up`：默认[0,1,0]；垂直俯视需换成不平行于视线的向上向量，如[0,0,-1]。eye/target不能重合。
- `fov`：垂直视场角，默认60°，范围10～120°。
- `lighting`：day/night，默认day；`layer`：all/body/walls，默认all。walls/body需要源主模型中声明的墙mask，工具不自动识别墙。
- `cuts`：可选整数方块边界剖切列表，axis为x/y/z，removed_side为above/below。above移除坐标大于等于position的方块，below移除小于position的方块；多个剖面累加。`side`为兼容别名。
- `cut_y`：可选的最大保留方块层，含该层，相当于Y轴position=cut_y+1的above剖切。

纹理入口只支持整数切面，遇到半格切面会明确拒绝；不能静默近似。需半格诊断时用原nbt_preview，并如实记录它的几何近似。剖切只改变显示，不写入源模型。批量各视角独立应用默认值，上一张的剖切、图层、昼夜不会泄漏到下一张；无cuts的入口和仰视图保持完整顶构。

## 输出与成本控制

每个视角输出 `<前缀><id>.png` 和同名JSON。JSON记录源/几何/快照哈希、实际相机和FOV、剖切、图层、昼夜、像素尺寸、可见方块数、网格构建次数、帧号、图片SHA-256及耗时。相机计算可能有Float32精度差，记录实际值而非伪造为精确输入。

批次保存 `snapshot.json` 和 `render_manifest.json`。清单status=complete才表示全部请求的图像已输出；失败时非零退出并在可建立输出目录的情况下记录failed及已有结果，不能把部分图当作整批通过。输入参数在创建渲染目录前验证；已经存在的输出拒绝重写。源或快照在渲染中变化会拒绝成功结论。

默认960×640、像素倍率1，`--width/--height` 可设64～4096。`--quality balanced`默认关闭阴影贴图，保留纹理和基础照明；high启用1024阴影贴图。模型构建和光栅化仍消耗CPU/GPU，批量入口减少的是交互、重复加载和重复网格生成，不是免除渲染成本。

`--timeout-ms` 控制单次初始化/视角的等待上限，默认60000，范围1000～300000；遇到浏览器或WebGL不可用时报告失败，不自动退回computer use点图或谎称渲染完成。可用纯色诊断作为明确标注的替代，纹理质检继续写未执行。

图片生成与文件哈希不代表已经看图。agent须实际查看整体、未剖切入口、代表节点与完整顶构；相机遮挡或尺度不清时改相机新出图。精修仍需要对应图像之后的真实用户对话确认，批量出图不授予approve/apply权限。

## 网页保留给用户交互

```powershell
python .agents/skills/minecraft-nbt-modeler/scripts/nbt_task.py preview --source <完整主模型> --cameras <相机列表JSON> --output <任务目录>/previews/新网页快照.json
```

可加 `--no-open`只打印地址。服务绑定127.0.0.1；用户可旋转缩放、改Y剖切/墙层、切昼夜、查坐标与操作ID、下载截图/相机记录。任务结束用Ctrl+C关闭本次服务，重复看同一快照复用地址，不为每个相机新开服务。

网页相机按钮只更新相机并立即绘制完成帧，保留用户当前剖切和图层，不调用setStructure。只有剖切/图层真的改变才重建网格；静止时不持续渲染。新图像不依赖“下载截图”按钮触发刷新。浏览器公开的setCamera/renderView/capture接口由批量工具复用，不要求agent手写CDP调用。

人工细节控制台默认用图片评审和版本绑定的编号意见，3D改为按需开启，可释放资源；其中轻量几何3D只用于结构诊断，不替代纹理图片。详见[细节控制台](detail-control.md)。批量render仍使用原balanced/high纹理输出，不因控制台轻量模式改变质量。

## 专项验证

在已装可选依赖和浏览器的环境运行：

```powershell
node .agents/skills/minecraft-nbt-modeler/assets/viewer/test-render.mjs --output <全新的合成测试目录>
```

专项检查相机不重建、网页自动重绘、剖切保持、默认值还原、同视角图片一致、非法输入/覆盖拒绝和异常资源清理。它独立于Python核心回归，不把未安装浏览器时未跑的专项检查写成通过。测试只使用合成场景，不修改已有用户模型，不批准资产精修。
