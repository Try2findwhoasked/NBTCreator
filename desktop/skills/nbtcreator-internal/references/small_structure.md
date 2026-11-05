仅返回JSON {"coordinate_space":"local","structure_name":"构件名","camera":{"azimuth":45,"elevation":25},"summary":"改动","settings_patch":{"boxes":[[0,0,0,0,3,0,"stone_bricks"]]}}。
原点是选区最小角[0,0,0]，X宽Y高Z深；不得用全局坐标或palette索引。优先合并同材质体积，通常≤24步、硬上限128步。boxes每项为loXYZ、hiXYZ、state；需要开口可用air。也可用operations或blocks:[{pos:[x,y,z],state:"stone_bricks"}]，常规label/classification和总lo/hi由应用补齐。
仅用box/beam/frame：beam提供start/end和width(1/3/5)，端点及梁厚须界内；frame提供thickness且选区有一轴仅1格厚。operations归属body/wall。保留净空和支承，不用细节填满整个范围。
名称≤120字；相机只给azimuth(-180..180，0从+Z看，90从+X看)与elevation(-90..90，正值俯视)，应用补齐真实机位，机位不是可站立坐标。覆盖只取context.allow_overwrite，不能扩大保护或预算权限。

structure_name、camera、summary及总lo/hi可省略，由脚本补齐；只有需要特定名称或观察角度时再给出。
