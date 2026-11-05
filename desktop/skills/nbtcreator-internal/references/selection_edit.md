仅返回JSON {"coordinate_space":"local","summary":"改动与保留内容","operations":[]}，≤32步。点坐标以选区最小角[0,0,0]为原点，offset/spacing/radius保持向量或尺寸。
context.selection包含完整局部方块：palette为状态，runs每段[x,y,z,沿X连续长度,palette索引,wall]；wall=1为墙层，未列出的格为空气。依据真实几何选择适用工具，保留不需修改的部分。每步有kind、label、分类body/wall/inherit及实际参数。
不返回overwrite/write_bounds/write_group/max_writes。所有实际写入必须界内，覆盖由用户控制。无法容纳或缺关键资料时返回空operations并说明限制。
