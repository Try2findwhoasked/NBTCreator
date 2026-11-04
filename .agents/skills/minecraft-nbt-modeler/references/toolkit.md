# 通用工具：自创几何，复用文件与验证能力

本文 `.agents/skills/minecraft-nbt-modeler/` 示例是活动引擎源码路径。生成的工作区只有 nbtcreator-workspace 入口时，通过 `nbt.py` 调命令；`nbt.py paths` 返回实际冻结运行时的 scripts 等路径，不要假定旧目录存在，也不要修改冻结引擎。

本目录工具只负责通用机制，不提供默认建筑骨架。把所需构想写成当前任务的独立生成器。在工作区根目录执行时可按下面方式导入；记录返回的 runtime_bundle_sha256 以追溯所用工具版本。Python 标准库用于NBT；渲染和碰撞工具需要 numpy，预览另需 Pillow。

```python
import json, subprocess, sys
runtime = json.loads(subprocess.check_output(
    [sys.executable, '.agents/skills/nbtcreator-workspace/nbt.py', 'paths'],
    text=True, encoding='utf8'))
sys.path.insert(0, runtime['scripts'])
from nbt_model import Model
```

## nbt_refine.py：用户确认后的整体精修

先出缩略图给用户，明确同意后才从完整未切割主稿恢复精修，最后重验、重切。prepare仅冻结初稿与生成缩略图；approve记录真实用户对话的确认；apply执行全局局部构件/表面计划并输出新版本、差异、前后对照及2N分层文件。没有确认不得调用apply，也不能拿其他agent/测试fixture的确认代替用户。

详细config、计划操作、命令和输出见 [精修工作流](refinement.md)。这不是逐片编辑器；入口是完整主模型，不是49展开体或单个稀疏分层片。工具保留原稿与确认哈希，保护门洞和指定通路，精修后仍需实际看图。合成回归：`python .agents/skills/minecraft-nbt-modeler/scripts/check_refine_fixtures.py`。

## nbt_tools.py：几何编辑与扩散/破坏效果

提供CSG球/椭球/柱/锥/圆环、折线/贝塞尔扫掠、多边形拉伸、精确替换、快照复制/阵列、保守状态旋转/镜像、六邻接膨胀/侵蚀/表皮/开闭、带衰减扩散、静态爆炸裂缝和带间距散落。只读计划与design阶段API分开，已有资产统一接入nbt_refine；详细参数、保护语义、坐标和支持限制见[建模与效果工具](modelling-tools.md)。不是Minecraft物理或自动建筑设计器。

## nbt_model.py：模型与文件

`Model((size_x,size_y,size_z))` 保存每轴不超过48的单片模型。`put((x,y,z),state)`、`box(lo,hi,state)` 使用整数坐标，box上下界均包含。未写位置默认为空气；落盘自动写满体积。

方块状态可写 `stone_brick_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]` 或 `{'Name':'minecraft:stone_brick_slab','Properties':{'type':'top','waterlogged':'false'}}`。palette从实际状态生成，不受颜色表限制。方块ID、属性名和属性值由随包的原版1.20.1注册表索引校验；省略的属性保持原文件写法，诊断时使用该版本真实默认值。注册合法性、SAODG导入许可、渲染支持与碰撞支持是四项独立结果，不能互相替代。详见 [状态、邻接与工具维护](state-and-maintenance.md)。

顺序如下；几何由你设计，本例只展示API：

```python
from nbt_model import Model, ports, load
model = Model((48, 40, 48))
# 自行制作完整封闭的外壳、室内结构和抵达外边界内侧的端口喉道。
# 此时边界面保持封闭，喉道预先留空气与地板。
seal = model.check_sealed(interior_points=[(24, 12, 24)])
openings = ports(['west', 'east'], door_y=12)
port_check = model.open_ports(openings, door_y=12)
disk_report = model.save(output_dir / 'my_design.nbt')
actual = load(output_dir / 'my_design.nbt')
```

`interior_points` 要覆盖所有设计室内腔体，不仅选择一个安全角落。密闭检查使用一层外围空气，允许完整方块、玻璃及不规则封闭形状；它仅把air/cave_air/void_air看成通路，半砖、楼梯间的亚方块空隙不在此检查范围内。因此外边界使用完整闭合方块层，或对这些部位额外按实际碰撞检查，不能用半砖壳声称无缝密闭。

`open_ports` 当前只适用48×48单片，检查完整外边界开口规格以及紧邻门后的空气/地板。厚墙喉道要在设计阶段打通至边界内侧；整个内部喉道和必要目标之间仍需做通路检查。多片房按整体封闭体检查、根据逻辑端口开洞，再写各片；不要把单片工具错误用于多格逻辑空间。

独立建筑的自定义入口使用 `nbt_openings.open_declared_openings`，不为调用 SAODG 专用 API 扩大门洞或将内部围护强行移到48格包围盒边缘。该 API 仅用于新建密闭主模型的声明开洞，不改变已有作品的修改授权。

```python
from nbt_openings import open_declared_openings
# closed master 已完成室内、门后/外侧平台并真实 check_sealed；此处只展示参数。
opening_report = open_declared_openings(model, [
    {'id':'entry', 'lo':[6,2,2], 'hi':[8,5,2], 'facing':'north'}
], wall_positions=walls)  # walls 为显式坐标set，可省略但不能按材质猜墙
```

lo/hi 含边界，可覆盖不在包围盒边缘的厚墙；facing 从室内朝室外。所有声明先校验，再一次性写入：要求未变化的真实密闭记录、唯一名称、范围合法且不重叠、门下有非空气地板格、两侧在模型范围内的相邻喉道已留空气和地板；外侧落在模型外时明确记未检查。返回实际每格前后状态及全局指纹，并移除被挖空气的墙mask归属。函数不自动认证支撑碰撞、净宽或路线；仍须按原状态封回验证副本复验、检查真实脚位路线和回读。已有资产修改继续按精修或明确手动导出流程，不能借新建开口函数绕行。

`save` 要求已通过密闭检查，防止检查后几何被修改却继续导出；先密闭检查后标准开洞是允许的阶段转换。它写出完整gzip NBT并用另一解析器回读对比，包括Properties。设计返工时使用 `begin_redesign()` 使旧检查失效；已经开洞的结构须恢复原有外边界后再重验，不可掩盖无关漏口。

`check_full_block_routes` 只是完整方块专用的简易检查，默认不允许把一格高跳跃当作步行；遇到带状态几何会拒绝。复杂结构使用碰撞工具，不把空格连通当作玩家可通过。

## nbt_preview.py

从最终落盘NBT渲染，提供可配置透视相机。生成后必须通过图像查看工具审阅；输出元数据标明源NBT哈希和几何近似。先用 `python <skill>/scripts/nbt_preview.py --help` 查看实际可用参数，再给每个模型选取恰当相机。

相机与target都使用Minecraft X/Y/Z，Y向上。入口视角设置在真实落脚点上方约1.62格，近景针对实际构造节点，剖视用于理解竖向路线。入口被墙挡住、剖切删掉主体、相机拍到天花或近景只有材质色块时，应调整相机，不能把无效视图当验收。

程序化颜色预览不等于Minecraft光照或纹理效果。纯色渲染无法评估的内容保留未验证项；不要用渲染器不认识的方块近似效果掩盖实际结构问题。

需要同时移除多个遮挡面时，可重复传入 `--cut z:44:above --cut x:44:above`；这些平面与旧参数的剖切累加，删除各半空间的并集，元数据cuts记录全部平面。只删除遮挡所需部位，别把要验收的屋顶支架一并切掉。玩家视角不使用剖切，浮动QA视角另行标注。

## nbt_fields.py：曲面与自由形空腔

`Grid(size)`在体素中心X/Y/Z取样；场值<=0表示内部。它不预设“房间”，也不会自动放置平台或修好路线。

```python
from nbt_fields import Grid, bezier, union, apply_mask, connectivity
g = Grid(model.size)
axis = bezier([(8,12,12),(15,7,32),(29,23,14),(37,20,32)], samples=64)
void = union(g.ellipsoid((10,12,12),(7,6,8)),
             g.tube(axis, radii=3),
             g.ellipsoid((36,20,31),(7,9,6)))
mask = g.mask(void, boundary_margin=2)
# model已按设计填入岩体；将mask选中部分挖空。
apply_mask(model, mask, 'air')
topology = connectivity(mask, [(10,12,12),(36,20,31)])
```

这是API示意，不是推荐复用的洞穴布局。ellipsoid支持正交旋转矩阵；tube可逐控制点设置半径；torus为Y轴环面；extruded_polygon使用凹形简单XZ多边形；warped进行可复现的低频坐标形变。布尔组合与平滑并集允许自由混合。字段生成不等于NBT写入，只有apply_mask写入模型；边界margin仅在明确指定时清除mask边缘，不会默默更改设计。

字段box采用连续边界面，Model.box采用包含两端的整数坐标，不能混淆。字段椭球/变半径扫掠/形变不是严格SDF；smooth_union的radius需结合尺度自行检查。connectivity只验证六邻接空气连通，不认证玩家通行。

`air_components(model, probes)`枚举实际模型的全部空气组件，记录边界连通、包围范围、设计探针与未声明封闭气泡，不修改几何。用于未开洞的模型，或恢复了合法门洞的检查副本；开门后的室内当然会接通外界。外围空气是正常的，未声明气泡需由作者判断是否为意外残留，不自动填充或连通。它补充探针密闭检查，不能替代玩家通路。

修改几何工具后运行 `python .agents/skills/minecraft-nbt-modeler/scripts/check_field_fixtures.py --output nbt_models/_tests/field_validation`，涵盖弯曲多腔连通、断开反例、CSG、旋转、环孔、凹形缺角、形变复现、边界余量和落盘回读。

## nbt_sections.py：空腔多层切片

用实际NBT切片检查各高度空腔轮廓与顶底变化，不依赖透视相机猜测：

```powershell
python .agents/skills/minecraft-nbt-modeler/scripts/nbt_sections.py --nbt <最终NBT> --ys 6,14,22,30 --zs 24 --output <任务目录>/sections.png
```

`--ys/--xs/--zs`接受逗号分隔的整数方块索引，可同时使用；越界报错。深蓝为空气，其他色为保存方块；XZ平面北在上、东在右，竖剖Y向上。旁JSON记录源NBT哈希与全部切片。它展示方块层，不表达楼梯/半砖内部的亚方块空气，也不是可行走地图。按模型选择有意义的高度和剖切位置，不能把任意空层截图当作结构已验收。

## nbt_roof_preview.py：随高程剥离顶壳

当平面剖切删掉高层地板、却仍留下低处顶壳时，可由作者提供每列保留高度，用通用脚本从最终NBT诊断渲染：

```powershell
python .agents/skills/minecraft-nbt-modeler/scripts/nbt_roof_preview.py --nbt <最终NBT> --heights <高度场JSON> --output <任务目录>/route_cutaway.png --eye 65,45,65 --target 24,14,24
```

高度JSON为 `[size_x][size_z]` 数组，每值为局部Y，必须为0～size_y范围的0.5倍数；该列中半格单元底Y大于等于该值就被隐藏。作者可依据实际地板高度加合适净空生成该场，但没有单一地板高度的叠层/交叉通道不能盲用同一列阈值。工具不自动识别屋顶，也不修改NBT；视图可能同时隐藏高处其他建筑，需保留未剖切玩家视角、完整外观/其他截面作为补证。

旁JSON记录最终NBT、完整高度场路径和各自SHA256、精确删格规则及相机。像平面剖切一样实际查看结果；不能用删掉的部分来验收顶壳、承重连接或真实可见性。

## 碰撞与通路

`nbt_collision.py` 为有状态方块和多层路线提供保守的脚位/头部净空检查。使用前读取其API与限制，声明实际检查的start/targets。工具未支持的形态不能据此声称游戏碰撞完全通过；针对目标、楼梯转折和门后喉道保存检查结果，必要时做游戏验收。

```python
from nbt_collision import check_routes
routes = check_routes(actual,
    start=(5.5, 12, 24.5),
    targets={'upper_landing': (35.5, 24, 12.5)})
assert routes['passed'], routes
```

这里是玩家脚部实际坐标，不是方块索引；站在方块 `(5,11,24)` 上的居中脚位是 `(5.5,12,24.5)`。工具用半格横向与高度采样、0.6宽1.8高AABB和连续支撑检查，允许半格自动步进，不允许跳跃、攀爬、游泳或长距离落下。它返回报告而不是自动抛异常，调用方要检查passed。对有限的已核实单格内细件，默认可用完整格障碍上包络，但支撑仅来自已支持几何；`conservative_obstacles` 列出这些细件，`exact_geometry_supported=false`，不能称精确形状通过。其他未知形状仍列入unknown_shapes并使passed=False。名单、版本依据和严格模式见[保守碰撞上包络](collision-envelopes.md)。不能把代理当真实支撑，也不能为了报告变绿删掉设计中的细节。

该API只保证start至targets有某条路径，不保证经过作者预期的某段桥或坡道。对回路、双路线与捷径需另做指定连接检查，保存对应路径；必要时在副本阻断替代路线后验证该段，不能把全局可达报告扩展解释成所有设计路径都通畅。

改动碰撞工具后可运行：

```powershell
python .agents/skills/minecraft-nbt-modeler/scripts/check_collision_fixtures.py --output nbt_models/_tests/toolkit_validation/collision_regression.json
```

回归用例含上下行半砖楼梯、半格净空、头部阻断、断桥、完整块跳跃误判、未知形态和40种楼梯状态；这验证的是工具的几何假设，仍不等于Minecraft运行时验证。

NBT读写与阶段顺序回归可运行 `python .agents/skills/minecraft-nbt-modeler/scripts/check_model_fixtures.py --output nbt_models/_tests/toolkit_validation/io`，验证状态往返、六面漏口、未验先开洞、错误门宽和验后修改拦截。

## 输出与迭代

每个任务保存设计笔记、独立生成脚本、NBT、coordinates.json、验证报告和内部质检图。先由主agent实际查看一件代表初稿的整体、入口和构造/主题近景，修复共性设计缺项，再展开其余主体建模。阅读落实按 [委派与阅读落实](delegation-and-review.md)，初稿质量与证据按 [初稿设计验收](spatial-detail-design.md#初稿设计验收) 和 [设计验收记录](spatial-detail-design.md#设计验收记录)。工具的passed、格式回读、密闭与通路只证明其检查范围；不认证空间、构造细节或主题表达完成。验证报告区分源模型、最终文件回读、门洞、通路近似、48/49兼容和游戏未验证项，并单独报告设计未达标项目。

## nbt_whole_cut.py：先生成整体，再纯切割

大建筑先用nbt_assembly.Volume(size)在连续的全局坐标中完成。完成整体密闭检查后用open_master_ports(master,definitions,door_y)开外门，再调用：

```python
from nbt_whole_cut import slice_master, reassemble_contiguous
parts, manifest = slice_master(master, output_dir,
    'saodg:custom/whole_building', wall_positions=global_wall_mask,
    wall_semantics='Explicit global enclosing-wall skin; floor/roof/equipment excluded')
actual, placement = reassemble_contiguous(parts, height=master.size[1])
assert actual.blocks == master.blocks
```

slice_master保存真正完整的master_geometry.json.gz（含全局尺寸、实体状态、默认空气、墙mask与指纹），然后按48网格只做坐标转换。切割循环没有建筑生成、隔墙或补路逻辑。各片完整NBT回读后，48连续重组须逐块等于源主模型；墙层同步切到layers目录。

当前工具支持完整矩形包围的整体，X/Z为48倍数、高8～48；不存在的稀疏单元不能静默删掉，需要明确的占地排除设计。JSON里仅选择parts清单的template/offset；file和sha256保留在制作清单中。48连续还原通过不代表49运行放置通过，后者另行assemble检查。别为掩盖引擎接缝限制先分建小房间。

独立自由尺寸模型使用 `nbt_standalone_delivery.export_standalone(master, explicit_walls, version_dir, file_prefix=...)`；它沿XYZ各48格分块，边块保留实际尺寸，runtime与body/walls分层均逐状态回读重建，不强制48倍数。master须先经 `nbt_whole_validation.validate_whole` 对显式独立上下文验证并冻结；`verify_standalone(version_dir)` 复查清单和实际文件。整件无墙素材需显式 `allow_empty_wall_mask=True`，不影响SAODG严格交付。

若独立上下文已有非空cells（例如L形三格），export_standalone还须传 `active_cells=config['cells']`；只切这些XZ格的各Y层，缺角不补空片。该占地必须合法、连通并覆盖全部非空气几何，注册建筑时同样传入以保留有效cells。省略/空active_cells才切完整自由尺寸包围盒。

回归：`python .agents/skills/minecraft-nbt-modeler/scripts/check_whole_cut_fixtures.py --output nbt_models/_tests/whole_cut_validation`。检查完整主模型保存、逐块连续重建、跨切面状态保留、切割不自动砌墙、全局墙mask同步拆层及49不兼容反例。

## nbt_assembly.py：49格运行诊断与旧的单元式工具

`LogicalAssembly(cells,height)`在48作者网格中设计一个连通的稀疏逻辑房间，沿用Model的put/box/check_sealed。缺角不可写入。整体密闭通过后，`open_external_ports(definitions,door_y)`仅切合法外门；`export_parts(directory,resource_prefix)`导出<=48格分片，返回包含file/template/offset/cell/sha256的清单。JSON的parts只取template/offset，其他字段保留在检查清单中。

```python
from nbt_assembly import LogicalAssembly, assemble, expand
logical = LogicalAssembly([(0,0),(1,0),(0,1)], height=40)
# 自行设计联合空间、必要内部通路，封住全部外门后检查。
logical.check_sealed(interior_points=all_chamber_probes)
logical.open_external_ports(outer_ports, door_y=10)
parts = logical.export_parts(output_dir / 'parts', 'saodg:custom/my_linked_room')
physical, placement = assemble(parts, height=40, door_y=10)
```

`assemble`回读真实分片，按49放置，复现内部桥的地板、顶板和侧墙，不自动清除模板两侧墙。`expand(point)`将作者XYZ标记或玩家脚位映射到运行局部XYZ；世界Y仍为66-door_y+局部Y。

返回的physical是只用于诊断的Volume，可传给check_routes、air_components及nbt_preview的make_grid/render API；它的save会拒绝巨型NBT导出。需要重封外门做诊断时，在副本用expand后的门坐标填回，不能修改实际分片。当前仅镜像0度连接；它没有执行Forge、外部房间布局图、钥匙门或动态方块更新。

`parts`每项的offset必须是48倍数，实际文件应为48×height×48；脚位高度必须与作者door_y一致。物理重组前后各区的独立设计不变，不能把49格间距误写到作者JSON偏移中。

## nbt_wall_layers.py：墙面独立NBT

生成墙面/洞壁时保留明确坐标mask，再在最终文件回读后的单片上拆层。设备、梁柱、地板、顶盖与厚岩体的归属由作者明确记录；同一材质可以同时用于墙与地板，不能通过材质名推断类别。门洞打通后mask中的空气会被丢弃。

仅在早期捕获mask而不更新，会把后来覆盖该位置的设备/地板误拆进墙层。可用WallMask(model, initial_positions)跟踪捕获后的put/box：每次成功后写都会撤销该坐标的墙归属，即使前后材质相同。mark(coords)用于有意重涂/重建后明确归墙的部位，finish()返回mask并恢复原写入方法。捕获后不要绕过put/box直接修改blocks字典。整体作品使用全局mask，在slice_master中同步转为局部mask，不对四个分片重新猜墙。

```python
from nbt_wall_layers import export_wall_layers
layers = export_wall_layers(actual_part, wall_positions,
    output_dir / 'layers', stem='p00',
    semantics='Vertical enclosing wall skin and cave walls; roof/floor/equipment excluded')
```

输出p00_walls.nbt、p00_interior.nbt和p00_layers.json，每片每轴<=48。两个制作层都是稀疏Java结构：没有选中的位置省略，不写air。独立回读检查两层无重叠、在空体积重建等于原始实体、Properties保留、源模型不变。放置到已有建筑时，省略位置不会主动清空旧方块；需要整体替换时使用原完整模板。

CLI支持 `--nbt <完整单片> --wall-mask <XYZ列表JSON> --output <目录> --stem p00`。`read_sparse(path)`仅用于制作层诊断读取；通用load仍坚持SAODG完整体积规则。

当前SAODG支持schema 5：在同一项room.parts中使用body_template、wall_template、offset引用两层，不再填写template。加载器补空气并合成为完整分片。不能把两层作为两项普通parts重叠放置；旧schema和template方式仍使用完整显式体积模板。多格房每片各一份墙面，保持与原片相同原点与尺寸，不导出96格的单一墙层模板。

回归：`python .agents/skills/minecraft-nbt-modeler/scripts/check_wall_layer_fixtures.py --output nbt_models/_tests/wall_layer_validation`。用例包括同材质内部道具不误拆、门口不填回、层间不擦除、状态往返、越界mask拒绝与源不变。

## nbt_delivery.py：严格的最终文件清单

`export_delivery(master,cells,global_wall_mask,output_dir,semantics,file_prefix='')`将已完成主模型机械切为每cell一份body及一份walls。新任务显式传入日期和房间编号前缀，如`file_prefix='2026-10-31_r001_'`，生成`2026-10-31_r001_p00_body.nbt`与对应walls；实际日期按output-storage取值。空前缀兼容旧调用和旧清单。`slice_master`接受相同参数并传给其内部delivery，完整分片和制作层保持一致日期前缀。

输出目录只包含这2N份NBT及delivery.json；1×3与三格L形都为6份，缺角不输出。调用前仍须按主流程完成密闭、开洞、通路检查；这是最终分层打包器，不代替建筑验收。

`verify_delivery(directory)`从实际文件读取并检查数量、哈希、原点/尺寸、层间互斥及重组后的源几何指纹，不接受重复的完整模板混入目录。主体和墙均为稀疏原版结构，同原点在空区域叠加，省略位置不会清除另一层。完整显式体积的运行模板单独保留在delivery外部，schema 5可在同一个part中用body_template/wall_template引用这一对稀疏层；旧schema或template字段继续引用完整模板。

目录有未知/陈旧NBT时拒绝继续，不自动删除用户文件。检查命令：`python .agents/skills/minecraft-nbt-modeler/scripts/nbt_delivery.py <交付目录>`。

## 统一入口与纹理预览

`nbt_task.py`集中提供inspect、snapshot、render、preview、regress；不自动批准精修，也不把只读检查写成密闭/通路已通过。Agent纹理出图优先走render并直接读取落盘PNG，网页preview用于用户交互；相机格式与限制见 [渲染与交互](rendering.md)，操作来源见 [状态、邻接与工具维护](state-and-maintenance.md)。原有纯色nbt_preview、剖面和49诊断继续可用。

## nbt_patterns.py：通用方块模式

新生成器可用pattern_plan只读规划，或在完整design阶段用apply_pattern执行带权fill/replace，返回新墙mask与统计。支持源状态/区域/表面/mask筛选、独立随机和连片噪声、固定全局种子及兼容属性保留。旧surface_palette保持原行为；新带权需求不要用重复材质列表或临时random循环代替。已有作品的CLI apply委托真实批准后的nbt_refine；转换默认不处理材质。参数、比例分母及限制见[通用方块模式](patterns.md)。

## nbt_floors.py：地面自动识别与风格破损

使用start、必要targets、ports和interior_probes，检测室内可达的多层完整承托面，并匹配真实的同家族下半砖。auto_floor_plan只读规划，apply_floor_damage用于design阶段，返回更新墙mask和密闭/路径复核报告。门口、必要实际路径和支撑自动保护；maintained/worn/ruined/cavern提供起始预算。大型可走工作台需显式exclude_boxes，未知材质保持不变、未知碰撞拒绝认证。新建房间主动按风格评估，不等逐项提示；参数、阶段与已有作品精修入口见[自动地面](floors.md)。
