仅返回JSON {"summary":"修改说明","settings_patch":{"lo":[x,y,z],"hi":[x,y,z],"structure":{"enabled":true,"mode":"fill","state":"stone_bricks","classification":"body","thickness":1,"offset":[0,0,0]}}}。
structure.mode可选fill/carve/hollow/move/floor/ceiling/walls/frame；或使用replace:{enabled:true,from_states:["stone_bricks"],state:"andesite",scope:"surface"}。只改这些字段，坐标及移动目标都在context.lo/hi界内，无法确定时说明限制，不捏造操作。
