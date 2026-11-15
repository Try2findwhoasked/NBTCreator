# 罗马与古典柱式参数

`parametric_compile` 的 pillar 支持 `form.order`，直接选柱式，不必手画柱础、柱头和各层叶饰。它是 Minecraft 方块化语汇，不是历史比例或承载验算。`parametric_list --kind pillar` 对应工具请求返回 column_orders 和严格字段。

| form.order | 默认构造与装饰 |
| --- | --- |
| tuscan | 圆柱身、简洁柱头、阿提卡启发柱础，默认不刻槽 |
| roman_doric | 圆柱凹槽、环带与外张柱头、珠卷颈饰；是带柱础的罗马启发版本 |
| ionic | 四面成对涡卷、颈部卵镖饰及承托板 |
| corinthian | 钟形柱头、交错两层莨苕叶、角部小涡卷和珠卷颈饰 |
| composite | 莨苕叶与较大的爱奥尼式涡卷组合，默认卵镖颈饰 |

```json
{
  "kind":"pillar", "size":[13,56,13],
  "material":"quartz_block", "accent":"smooth_sandstone",
  "form":{
    "order":"corinthian", "leaf_count":8,"leaf_layers":2,
    "flute_count":12,"flute_depth":0.75,"entasis":0.04,
    "neck_pattern":"bead_reel","detail_material":"quartz_block"
  }
}
```

size 为完整画布X/Y/Z；柱子高最多64、宽深最多32，其余参数化构件各轴仍最多32。柱式预设自动选择圆截面、柱础/柱头高度、收分和微鼓，返回 resolved_form。显式提供的参数优先；若改成通用柱头造型，则成为定制组合，不保证仍保留整套柱式特征。

| 参数（位于form） | 用法 |
| --- | --- |
| section | round 为真正圆/椭圆截面；square、cross 保持原功能 |
| shaft_ratio | 0.3～1，乘在扣除inset后的柱身半径；半径不足或超出画布拒绝 |
| taper / entasis | round 的taper平滑收分；entasis=0～0.2增加中段微鼓，避免只加一条材质色带 |
| flutes / flute_count / flute_depth | flutes=true后按角度削减半径，形成实际凹槽；数量4～32、深度0.1～1.5格。受体素分辨率限制，指定数量不等于每条槽都可分辨 |
| base_height / capital_height | 保持原部件划分与局部重生成；总和须小于柱高 |
| base_profile | 额外支持attic；包括底部方台、圆鼓和收腰，至少4格高 |
| capital_profile | 除通用造型外支持tuscan、doric、ionic、corinthian、composite；按类型检查最低尺寸 |
| neck_pattern | none / bead_reel / egg_dart，分别为无、珠卷、卵镖启发颈饰，生成真实凸出构件 |
| leaf_count / leaf_layers | 莨苕叶每层4～16片、1～3层，仅科林斯/复合柱头；各层交错，根部、分枝和卷尖连接到钟形芯体 |
| volute_scale / volute_turns | 涡卷相对最小宽深的尺度0.08～0.3、圈数0.5～2.5；仅有涡卷的柱头。默认尺度按柱头高度适配，显式尺度越界拒绝 |
| detail_material | 叶饰、涡卷和颈饰材质，默认使用柱身主材；柱头芯体与柱础使用原capital_material / base_material或accent |

叶饰、涡卷不是悬空装饰板：脚本生成实际曲线/分枝、与芯体或承托板连接，并检查六邻接连通。该检查不证明重力、工程承载或游戏内效果。小尺寸不能表达指定柱头时拒绝，不悄悄退化成方帽；复杂叶片和涡卷仍会呈现阶梯化近似，应看真实近景。

通用 `base_pattern` / `capital_pattern` 仍用于上一节的平面微型嵌纹。雕塑式古典柱端采用本页的立体叶饰、涡卷与颈饰，不把它们压成完整方盒以容纳平面贴图；需要自定义平面嵌纹时，显式覆盖该端为通用profile。`parametric_regenerate part=capital` 继续检查所选部件外的柱身未改变，对象图也可保存整根柱子的参数配方。

造型参考：[Met关于柱式及科林斯叶饰](https://www.metmuseum.org/ko/essays/architecture-in-ancient-greece)、[Edward Worth Library的古典柱式说明](https://architecture.edwardworthlibrary.ie/classical-orders/)。这里只提炼柱子及装饰的方块表达，不把完整柱式中柱与檐部的比例关系自动施加到建筑上。
