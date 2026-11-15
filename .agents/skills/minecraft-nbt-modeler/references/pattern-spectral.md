# 纹样频域滤波

`pattern_filter` 读取带实际图像SHA的纹样资产，生成一个新的灰度纹样资产。默认可用已有NumPy；backend=gpu/auto可使用[可选GPU后端](compute-transforms.md)，compute回执记录实际运行位置。它不新增SciPy依赖、不覆盖源图或建筑。内置ID可由 pattern_assets get 读取；工作区资产同样使用 id / image_sha256。外部图片先按原资产导入流程保存。

```json
{
  "name":"圆盘去噪纹样",
  "source":{"id":"<资产ID或builtin:预设ID>","image_sha256":"<实际SHA256>"},
  "filter":"lowpass","kernel":"disk","radius":12,
  "boundary":"reflect","method":"auto","normalize":false
}
```

| 参数 | 含义 |
| --- | --- |
| filter | lowpass 平滑；highpass 取原图减平滑图的绝对值；bandpass 取两个平滑尺度之差的绝对值 |
| kernel | gaussian 可分离高斯核（sigma=max(0.5,radius/3)）；disk 为非分离的圆盘均值核 |
| radius | 1～64像素，有限核宽为2×radius+1；与建筑格数不同 |
| outer_radius | 仅bandpass必填，须大于radius，最大128 |
| boundary | reflect 镜像扩展（默认）、wrap 周期扩展、zero 零扩展；只有wrap显式作周期处理 |
| method | auto 按估算工作量选择；spatial 显式空间卷积；fft 显式实数FFT线性卷积 |
| normalize | 默认false，保持灰度量级；true将非恒定结果线性拉伸到0～255，会改变阈值的相对作用 |
| resolution | 可选8～512的目标宽高，显式拉伸；省略时保留原尺寸，过大则等比缩至最长512 |
| crop / channel | 可选归一化裁取范围，channel 为 luminance（亮度乘透明度）或 alpha |

auto 对高斯核使用可分离空间算法，对小圆盘核也使用空间算法；只有估算更合适时才使用FFT。显式空间圆盘卷积若工作量超过2亿次会拒绝，改用auto或fft；不以无限计算满足过大请求。显式FFT仍有扩展、变换和浮点开销，不能保证每个8×8小图都更快。

FFT实现使用实数 rfft2 / irfft2，按线性卷积补齐足够长度再裁回原图，避免意外把左边图案卷到右边。reflect不会像zero那样引入边缘外黑色，但滤波本身仍可能模糊笔画、填孔或改变连通关系。highpass / bandpass 返回绝对残差的灰度图，不保留正负频率响应，不能当作可逆傅里叶谱。

返回原生资产、fitting_input、processing（实际算法、核、半径、边界、变换尺寸）和source_modified=false。每次创建新ID；处理前后都核对真实源图。空白结果、参数错误或源图被改动时不创建资产。返回的源参数与处理记录保存在新资产recipe，方便后续对象绑定；它不会自动跟随源资产更新。

滤波后使用 pattern_microfit / pattern_mount 的原拓扑、覆盖误差和质量门槛，不修改这些门槛。先比较实际图与拟合近景，再更新对象图命名绑定。纹样处理会写资产，所以不加入只读/纯候选JSON-lines会话；用原单次 `components agent --tool pattern_filter --request <JSON>` 调用。

算法范围参考：[NumPy FFT](https://numpy.org/doc/stable/reference/routines.fft.html)、[FFT卷积及规模取舍](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.fftconvolve.html)。文档引用解释算法；实际速度以本项目同输入、同边界、数值一致的基准为准。工具不通过FFT跳过楼梯/半砖匹配、支承或玩家路线搜索。
