仅改已有步骤参数时，省略operations，优先返回operation_patch:{changes:[{step:12,set:{state:"minecraft:andesite"}}]}。
step从1开始，≤16步，只给变化字段，不改kind/overwrite/write_group/max_writes。baseline与expected由本地脚本从原请求绑定，无需复制或计算；若主动提供则必须匹配。operation_patch与operations互斥。只改设计文字时都省略；新增、删除或重排才返回完整operations(≤64步)。
