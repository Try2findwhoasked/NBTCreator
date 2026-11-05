仅返回独立结构方案JSON，使用context.name和size，局部原点[0,0,0]。至少有operations或placements；通常≤48步，展开≤128步、65536格。给一个camera:{azimuth:45,elevation:25}，应用补齐机位。
复用context.references时在placements中给id、content_sha256、position；可给quarter_turns、mirror、material_map，不逐块复制已有资产。方案合法字段见随附spec定义。独立资产不依赖当前建筑；保存新资产仍是待审阅，放置只形成候选。

不必重复name、size或默认camera：名称、尺寸取本次上下文，相机由脚本补齐。只返回必要结构数据。
