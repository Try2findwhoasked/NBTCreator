仅改已有步骤参数时，省略operations，优先返回operation_patch:{baseline:"照抄context.operation_base.baseline",changes:[{step:12,expected:"照抄该步expected",set:{state:"minecraft:andesite"}}]}。
step从1开始，≤16步，只给变化字段，不改kind/overwrite/write_group/max_writes，不猜指纹。operation_patch与operations互斥。只改设计文字时都省略；新增、删除或重排才返回完整operations(≤64步)。
