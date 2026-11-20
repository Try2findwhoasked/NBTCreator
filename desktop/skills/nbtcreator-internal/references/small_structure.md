原点为选区最小角[0,0,0]，X宽Y高Z深。不得用全局坐标或palette索引。合并相邻同材质体积，通常≤24步，需要开口可用air。
仅用box/beam/frame：beam提供start/end和width(1/3/5)，端点及梁厚须界内；frame提供thickness且选区有一轴仅1格厚。operations归属body/wall。保留净空和支承，不用细节填满整个范围。
名称≤120字；相机只给azimuth(-180..180，0从+Z看，90从+X看)与elevation(-90..90，正值俯视)，应用补齐真实机位，机位不是可站立坐标。覆盖只取context.allow_overwrite，不能扩大保护或预算权限。

## 普通 JSON

紧凑示例 {"coordinate_space":"local","settings_patch":{"boxes":[[0,0,0,0,3,0,"stone_bricks"]]}}。每项填 loXYZ、hiXYZ、state。也可返回 operations 或 blocks:[{pos:[x,y,z],state:"stone_bricks"}]，最多128步。名称、相机、summary、总lo/hi及常规步骤字段可由应用补齐。
