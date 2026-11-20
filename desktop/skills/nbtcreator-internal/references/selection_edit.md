仅返回JSON {"coordinate_space":"local","summary":"改动与保留内容","operations":[]}，≤32步。点坐标以选区最小角[0,0,0]为原点，offset/spacing/radius保持向量或尺寸。
context.selection包含完整局部方块：palette为状态，runs每段[x,y,z,沿X连续长度,palette索引,wall]；wall=1为墙层，未列出的格为空气。依据真实几何选择适用工具，保留不需修改的部分。每步有kind、label、分类body/wall/inherit及实际参数。
不返回overwrite/write_bounds/write_group/max_writes。所有实际写入必须界内，覆盖由用户控制。无法容纳或缺关键资料时返回空operations并说明限制。

普通 JSON 可省略 coordinate_space、summary、步骤 label 及 classification，由脚本补齐。严格 JSON 要填写 coordinate_space、summary、operations；没有可行操作时使用 {"coordinate_space":"local","summary":"选区缺少安全施工空间","operations":[]}。完整步骤按 Schema 填全键，并提供该工具实际所需的参数。
