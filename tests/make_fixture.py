"""Generate an isolated, synthetic model with no copied user assets."""
import json
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assembly import Volume
from nbt_refine import save_master
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
model=Volume((48,16,48));model.box((0,0,0),(47,15,47),'stone_bricks');model.box((2,4,2),(45,13,45),'air')
walls={p for p in model.blocks if 4<=p[1]<=13 and (p[0] in (0,1,46,47) or p[2] in (0,1,46,47))}
save_master(out/'synthetic.master.json.gz',model,walls)
config=dict(cells=[[0,0]],door_y=4,ports=[],start=[5.5,4,5.5],targets={'centre':[24.5,4,24.5]},interior_probes=[[12,8,12]],protected_boxes=[],protected_paths=[],max_changed_blocks=4096,
 cameras=[dict(role='whole',eye=[70,42,-20],target=[24,7,24],cuts=[['y',13,'above']]),dict(role='entry',eye=[5.5,5.62,5.5],target=[24,7,24])])
(out/'coordinates.json').write_text(json.dumps(config),encoding='utf8')
(out/'room_description.json').write_text(json.dumps(dict(name_zh='迁移合成测试厅',shape='single',display_name='迁移合成测试厅-单格',master=str(out/'synthetic.master.json.gz'),audit={'compliant':True}),ensure_ascii=False),encoding='utf8')
print(out/'synthetic.master.json.gz')
