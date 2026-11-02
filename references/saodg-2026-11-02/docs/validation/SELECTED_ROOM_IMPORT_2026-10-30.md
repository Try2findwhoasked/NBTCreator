# 已选房间检查与注册（2026-10-30）

术语同步（2026-10-31）：正文采用现用名称；版本、验证结果及代码/日志原文仍按当时记录。

来源为 `build/选择/选择清单.json` 的63个图册条目；49/50合并后为62座独立建筑。本次通过53座，其中17座复用已有ID，新增36座。

原NBT按字节保留；主体/墙层分片合成与完整原件逐块核对。原编号、中文名称、来源、占地形状、建筑主题和出口类别保存在房间 `identity` 中。

只声明原朝向0度。玩法类型以现有规则配置，建筑名称不会自动产生谜题、秘密、封印大厅或首领机制。原有功能房和历史资源保留。

## 查询与识别

需要管理员权限2。目录条目可以点击填入详情命令。

```mcfunction
/saodg admin rooms selected
/saodg admin rooms cross
/saodg admin rooms waterworks
/saodg admin rooms dead_end
/saodg admin rooms 001
/saodg admin roominfo <房间ID>
/saodg admin validate
```

形状：`single`、`line_2`、`line_3`、`square`、`l`、`t`、`cross`；主题：`forge`、`tomb`、`archive`、`waterworks`、`garden`、`sacred`、`guild`、`crystal`、`ruins`。

## 注册目录

| 图册编号 | 名称 | 玩法 / 形状 / 主题 / 出口 | 房间ID |
| --- | --- | --- | --- |
| 001 | 十字铸造殿 | combat / cross / forge / junction | `saodg:selected/cross/cross_t_dungeons_20261030/cross_01` |
| 002 | 十字墓庭 | combat / cross / tomb / junction | `saodg:selected/cross/cross_t_dungeons_20261030/cross_02` |
| 003 | 十字分拣厅 | combat / cross / archive / junction | `saodg:selected/cross/cross_t_dungeons_20261030/cross_04` |
| 004 | 十字蓄水殿 | combat / cross / waterworks / junction | `saodg:selected/cross/cross_t_dungeons_20261030/cross_05` |
| 005 | 丁字装配殿 | combat / t / forge / junction | `saodg:selected/t/cross_t_dungeons_20261030/t_02` |
| 006 | 斜层晶隙 | combat / t / crystal / junction | `saodg:selected/t/cross_t_dungeons_20261030/t_03` |
| 007 | 回声裁判所 | combat / t / guild / junction | `saodg:selected/t/cross_t_dungeons_20261030/t_04` |
| 009 | 悬渠检修殿 | combat / single / waterworks / straight | `saodg:selected/single/distinct_ten_subagents_20261029/01_dry_aqueduct` |
| 025 | 根瘤育房 | combat / single / garden / straight | `saodg:selected/single/diverse_rooms_20261030/13_branch_nursery` |
| 026 | 折轴纪念墓室 | combat / single / tomb / corner | `saodg:selected/single/diverse_rooms_20261030/14_folded_memorial` |
| 027 | 沉星潮汐机 | combat / square / waterworks / straight | `saodg:selected/square/linked_trial` |
| 032 | 远征货运站 | combat / line_3 / guild / straight | `saodg:selected/line_3/nine_distinct_20261029/long/expedition_station` |
| 033 | 地下子午仪廊 | combat / line_3 / archive / straight | `saodg:selected/line_3/nine_distinct_20261029/long/meridian_observatory` |
| 055 | 废弃神社长殿 | combat / line_3 / sacred / dead_end | `saodg:selected/line_3/ruined_shrine_1x3` |
| 056 | 废弃神社长殿·精修 | combat / line_3 / sacred / dead_end | `saodg:selected/line_3/ruined_shrine_1x3/refined_01` |
| 057 | 折轴关隘 | combat / l / guild / corner | `saodg:selected/l/sao_batch_14/elbow/gate` |
| 058 | 月影回廊 | combat / l / guild / corner | `saodg:selected/l/sao_batch_14/elbow/moon` |
| 059 | 剑碑转运站 | combat / l / guild / corner | `saodg:selected/l/sao_batch_14/elbow/sword` |
| 060 | 黑铁锻剑工场 | combat / square / forge / corner | `saodg:selected/square/sao_batch_14/large/black_iron_forge` |
| 061 | 誓约骑士大殿 | combat / square / sacred / corner | `saodg:selected/square/sao_batch_14/large/oath_cathedral` |
| 062 | 沉降水都船坞 | combat / square / waterworks / corner | `saodg:selected/square/sao_batch_14/large/sunken_dry_dock` |
| 069 | 星纹阶库 | combat / single / archive / dead_end | `saodg:selected/single/sao_batch_14/single/04_star_archive` |
| 071 | 凯旋阶廊 | combat / line_3 / sacred / straight | `saodg:selected/line_3/sao_nine_drafts_20261030/long/01_triumph_stairs` |
| 072 | 银辉大教堂 | combat / line_3 / sacred / straight | `saodg:selected/line_3/sao_nine_drafts_20261030/long/02_silver_cathedral` |
| 074 | 王城·折剑高架 | combat / l / guild / corner | `saodg:selected/l/sao_nine_drafts_20261030/lshape/l01_folded_sword_viaduct` |
| 097 | 翠阶育种庭 | combat / line_2 / garden / straight | `saodg:selected/line_2/sao_skill_trial_20261030/rooms_1x2/verdant_seed_terraces` |
| 099 | 银肋扇形大厅 | combat / square / crystal / straight | `saodg:selected/square/sao_skill_trial_20261030/rooms_2x2/silver_rib_fan_hall` |
| 100 | 苔冠巡行庭 | combat / l / garden / junction | `saodg:selected/l/sao_skill_trial_20261030/rooms_lshape/moss_crown_patrol` |
| 101 | 潮阶闸渠 | combat / l / waterworks / junction | `saodg:selected/l/sao_skill_trial_20261030/rooms_lshape/tide_step_sluice` |
| 102 | 剑士行会誓约厅 | combat / single / guild / straight | `saodg:latest/01_oath_hall` |
| 103 | 麦穗层磨坊 | combat / single / guild / straight | `saodg:latest/02_grain_mill` |
| 104 | 染织阶场 | combat / single / guild / straight | `saodg:latest/03_dye_terraces` |
| 107 | 攻略使驿站 | combat / single / guild / straight | `saodg:latest/06_courier_interchange` |
| 108 | 攻略地形议室 | combat / single / archive / straight | `saodg:latest/07_expedition_cartography` |
| 109 | 锻刃修复工坊 | combat / single / forge / corner | `saodg:latest/08_blade_workshop` |
| 110 | 艾恩葛朗特药草阶地 | combat / single / garden / dead_end | `saodg:latest/09_herb_terraces` |
| 111 | 骑士驻营套间 | combat / single / guild / corner | `saodg:latest/10_knight_quarters` |
| 112 | 双脊封存档案库 | combat / single / archive / dead_end | `saodg:latest/11_twin_archive` |
| 113 | 山城折街 | combat / single / guild / dead_end | `saodg:latest/12_switchback_street` |
| 114 | 古城低穹浴场 | combat / single / waterworks / dead_end | `saodg:latest/13_vault_baths` |
| 115 | 水晶筛炼工序厅 | combat / single / forge / dead_end | `saodg:latest/14_crystal_process` |
| 116 | 龙骨拱仓栈 | combat / single / guild / straight | `saodg:latest/15_dragon_rib_store` |
| 117 | 月影礼拜套殿 | combat / single / sacred / straight | `saodg:latest/16_moon_suite_chapel` |
| 118 | 古代闸渠检修场 | combat / single / waterworks / straight | `saodg:latest/17_ancient_sluice` |
| 119 | 森林根系隐修所 | combat / single / garden / corner | `saodg:latest/18_root_hermitage` |
| 121 | 沉降遗迹勘探站 | combat / single / waterworks / straight | `saodg:latest/20_sunken_excavation` |
| 122 | 茶药共庭 | combat / single / garden / dead_end | `saodg:selected/single/skill_ceiling_forward_test` |
| 123 | 逆潮铸钟井 | combat / single / forge / dead_end | `saodg:selected/single/skill_trial_a` |
| 124 | 悬星测潮井 | combat / single / waterworks / straight | `saodg:selected/single/skill_trial_b` |
| 125 | 闸机工坊 | combat / single / forge / straight | `saodg:selected/single/three_rooms_20261030/01_lockworks` |
| 126 | 阶层档案馆 | combat / single / archive / straight | `saodg:selected/single/three_rooms_20261030/02_archive` |
| 128 | 双生育种房 | combat / single / garden / straight | `saodg:selected/single/twin_seedhouse_1x1` |
| 129 | 跨层潮汐工场 | combat / square / waterworks / straight | `saodg:selected/square/whole_cut_trial` |

## 未通过的建筑

| 图册编号 | 名称 | 原因 |
| --- | --- | --- |
| 049, 050 | 残破教堂转角走廊 | 占地/高度不符合48格单元规范，原尺寸=[31, 14, 31] |
| 051 | 残破教堂直廊 | 占地/高度不符合48格单元规范，原尺寸=[31, 14, 31] |
| 052 | 残破教堂三岔廊 | 占地/高度不符合48格单元规范，原尺寸=[31, 14, 31] |
| 053 | 神秘地下室 | 占地/高度不符合48格单元规范，原尺寸=[39, 18, 39] |
| 054 | 残破教堂 | 占地/高度不符合48格单元规范，原尺寸=[41, 34, 47] |
| 080 | 艾恩葛朗特·迷宫区 | 封闭声明外门后，49格放置计划仍与外界空气连通 |
| 082 | 黑剑士·双剑修炼室 | 封闭声明外门后，49格放置计划仍与外界空气连通 |
| 083 | 转移水晶·传送广场 | 封闭声明外门后，49格放置计划仍与外界空气连通 |
| 084 | 起始之镇·公会大厅 | 封闭声明外门后，49格放置计划仍与外界空气连通 |

## 检查边界

运行时门槛使用 Forge 1.20.1 的真实注册表和碰撞形状检查当前 StructurePlacer 的49格最终写入计划，包括主体/墙层、拼缝、凹角和关闭的外门。空气洪水检查封闭性；0.6×1.8玩家体积在半格图上检查到达点、所有外门和所有刷怪点，不使用跳跃、飞行或穿墙。

这是静态放置计划和碰撞复核，未逐间在实体世界放置并真人走访；不涵盖液体动态、怪物寻路、双客户端、重连或重启验收。

129号 `whole_cut_trial` 的原交付报告仍保留“不兼容49格”的旧结论。本次原NBT未变，以当前铺缝/凹角处理后的放置计划重新复核，通过本次封闭性和声明目标通路检查；不将旧报告改写为已通过。

[逐文件来源、SHA256、分类和运行时结果](SELECTED_ROOM_IMPORT_2026-10-30.json)。
