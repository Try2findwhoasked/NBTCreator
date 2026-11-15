# GPU计算与组合变换

`compute_info` 查询当前Python进程的真实GPU后端；`pattern_filter`、`pattern_warp` 和 `field_compile` 支持 backend=auto/cpu/gpu。这些接口服务外部Agent的建模脚本，与3D预览的WebGL渲染分开。

auto 仅对达到规模门槛的任务尝试CuPy CUDA；小图不初始化GPU。依赖、设备、显存或运行错误会回退CPU并在 compute.reason 记录原因。显式gpu失败则拒绝，不能把CPU结果写成GPU验收。返回前完成同步读回，最终方块状态、预算、保护、源图SHA、半格碰撞和路线仍由现有CPU工具检查。GPU不跳过微型纹样拓扑搜索，也不加速SNBT文本写入。

## 复杂体场构件

`field_compile` 接收 size、root 和 nodes 图，返回纯 spec 候选。每轴1～64格、最多32个节点、依赖深度16、每处最多8个变换，总采样工作量最多3200万。方块预算最多65536，不静默删减。节点id唯一且全部接入root；循环、缺失引用、不匹配的参数和奇异变换会拒绝。

形状包括 box、ellipsoid、cylinder、torus、superellipsoid、gyroid，以及 union/intersection/difference/smooth_union。后四种用children引用节点id；difference和smooth_union恰好两个子场，后者另给blend。superellipsoid用radii和power定义L^p轮廓；gyroid用wavelength及无量纲thickness定义周期薄层，通常与实体边界intersection。不将这些符号正确的隐式场统称为精确距离场，平滑融合仍需实际看图。

顶层transforms作用于整体，节点transforms仅作用于该节点及其子场。列表按设计中的正向顺序书写，脚本逆序反向采样，减少前向搬动体素造成的空格；仍有体素分辨率损失，不保证任何变换后都连通。新构件只使用已知完整方块，不把已有楼梯/半砖任意弯曲后伪造其朝向。

| kind | 参数与语义 |
| --- | --- |
| affine | 可逆3×3 matrix；centre默认原点，offset默认零。正向为 centre + matrix × (原点坐标-centre) + offset，可组合旋转、缩放、剪切和平移。 |
| twist | axis默认y，degrees、length；相对centre沿轴线性扭转，每length格转degrees度。 |
| bend | plane=xy/yz/xz、正radius、centre；将平面第一轴弯成半径radius的圆弧，第二轴是径向厚度。采样经过圆心奇点时拒绝；大于一圈的绕回不能由此单值逆映射表示。 |
| taper | axis、amount、正length、centre；横截面比例为1+amount×轴向距离/length，比例接近零或反转时拒绝。 |
| shear | axis、driver、amount、centre；axis位移为amount×driver距离，两个轴必须不同。 |
| wave | axis、driver、amplitude、wavelength、phase；位移沿driver变化，phase按度，两个轴必须不同。 |

```json
{
  "size": [32, 40, 32],
  "root": "shaft",
  "nodes": [{"id":"shaft","shape":"superellipsoid","centre":[16,20,16],"radii":[5,18,5],"power":6}],
  "transforms": [
    {"kind":"twist","axis":"y","centre":[16,20,16],"degrees":135,"length":36},
    {"kind":"taper","axis":"y","centre":[16,20,16],"amount":0.25,"length":36}
  ],
  "backend": "auto"
}
```

画布是显式采样域：形状可在域外继续延展，边缘截断不会自动封口。需要完整柱头、弯梁或通路时，主动留足域并检查边界。GPU用float64采样，接近零的体素判定回到CPU同一公式复核；这只消除边界舍入差异，不证明支承或审美。field_compile可作为scene_compile/save/update的对象配方，尺寸与实际接触仍按对象图约束处理。

## 纹样透视、旋涡与组合

`pattern_warp` 使用实际 source={id,image_sha256}，创建新RGBA资产，保留源图；可先crop裁取局部。resolution每轴8～1024，源图裁后每轴最多2048。所有通道共用同一坐标映射，透明图用预乘alpha采样，避免黑边。CPU/GPU浮点插值容许最终8位颜色出现一级舍入差异，不将插值当作原图无损变换。

- affine：可逆3×3齐次matrix，同时支持平面仿射及透视。坐标为归一化UV，图左上(0,0)、右下(1,1)，采样域经过无穷远时拒绝。
- swirl：centre默认[0.5,0.5]，radius和degrees；旋转强度向半径边缘平滑减小。
- wave：axis=x/y、amplitude、wavelength、phase，距离按归一化UV、相位按度。
- polar_repeat：sectors、rotation及mirror；围绕centre复制一个扇区，可生成放射/镜像组合，改变原拓扑是预期行为。

transforms按正向顺序组合，boundary=zero/clamp/wrap明确处理域外取样。wrap适合原本可平铺素材；不会自动补齐素材接缝。返回资产可直接用fitting_input继续pattern_compile/microfit，或保存为对象图命名绑定。变换后重新检查孔洞、楼梯/半砖拟合、质量分项及实际安装预览，不能沿用变换前的拓扑通过结论。此工具写资产，不开放于纯候选session，也不自动跟随源资产更新。

## 可选运行环境与速度验证

软件源码目录的开发入口：

```powershell
mise run gpu:setup
mise run gpu:info
mise run gpu:test
mise run gpu:benchmark
```

gpu:setup在build/gpu-env创建独立环境，沿用当前Python的NumPy/Pillow并使用pip缓存；config/requirements-gpu.txt声明可选CuPy及CUDA运行/FFT/编译组件。首次缺少的组件需要下载，不安装系统CUDA工具链、不改用户或系统环境变量。普通CPU环境和发行包不自动包含这些依赖。

用GPU环境调用CLI：`mise run gpu:cli -- <原CLI参数>`；该子进程设置已有的NBTCREATOR_PYTHON入口。创作项目也可直接使用build/gpu-env中的Python运行其工作区nbt.py。普通CLI/桌面环境不会因安装此可选环境而改写Python选择，需使用该入口或已有的运行环境配置。GPU库不跟随Skill冻结副本复制；目标Python须自己具备依赖，新增脚本和目录仍须正常同步。个人运行环境可写mise.local.toml，该文件被Git忽略；不将本机路径写进公共配置。

benchmark记录设备探测、各类操作首次调用、预热后中位耗时、包含传输的结果读回以及完整工具耗时。小任务可能更慢，单次进程启动也可能抵消收益，优先用现有session复用进程。参考[CuPy安装](https://docs.cupy.dev/en/stable/install.html)与[异步计时注意事项](https://docs.cupy.dev/en/stable/user_guide/performance.html)，加速结论只依据本项目实测。

## CPU方块展开与校验

引擎按不可变状态字符串复用解析结果，状态字典每次仍重新校验；接口目录按文件大小和修改时间等标记更新内部快照，公开查询返回独立副本。粘贴与构件校验直接拆解坐标行，保留整数类型、界内、重复、材质编号和墙层检查。候选模拟使用put_many统一预检再写入普通模型；有自定义put或来源追踪时继续调用对应钩子。保护、覆盖、全局变化预算和源哈希不会因批量写入省略。

`mise run cpu:test`验证这些边界；`mise run gpu:materialization`比较完整field_compile、密集/混材build、组件validate和paste_plan。基准支持`--engine <共享引擎目录>`与`--compare <旧results.json>`，同输入比较完整返回值SHA，保存每次样本，不只比较方块数量。CPU/GPU采样、Python方块展开、原生源读写、空间/碰撞验证及渲染分别计时，不能把局部微基准加速解释为整栋建筑同比加速。
