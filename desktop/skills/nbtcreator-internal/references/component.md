仅返回独立结构方案 JSON，使用 context.name 和 size，局部原点为 [0,0,0]。至少填一项 operations 或 placements，通常不超过 48 步，展开后最多 128 步、65536 格。
普通 JSON 可省略 camera。严格 JSON 无自定义视角时填 camera: null。指定角度时填 "camera":{"azimuth":45,"elevation":25}，应用补齐机位。
复用 context.references 时，在 placements 中填写 id、content_sha256、position，可附 quarter_turns、mirror、material_map。按随附输出定义填写字段。资产保存后仍待审阅，放置只形成候选。

name、size 沿用本次上下文。普通 JSON 可由应用补齐。严格 JSON 的 operations 和 placements 都要出现，未用的一组填 []，两组不能同时为空。
