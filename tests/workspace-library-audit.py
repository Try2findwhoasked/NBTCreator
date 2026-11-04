"""Read-only census of the requested workspace, including migration evidence."""
import argparse,json,hashlib,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
import nbt_components as components
import nbt_effect_assets as effects
import nbt_recipes as recipes

p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args();workspace=args.workspace.resolve()
files=[*components.library_root(workspace).glob('*.json'),*effects.root(workspace).glob('*/effect.json'),*(workspace/'.nbtcreator/reusable').glob('*.json')]
before={str(file):hashlib.sha256(file.read_bytes()).hexdigest() for file in files}
library=[components.load(workspace,file.stem) for file in components.library_root(workspace).glob('*.json')]
native=[effects.load(workspace,file.parent.name) for file in effects.root(workspace).glob('*/effect.json')]
reusable=[recipes.load(workspace,file.stem) for file in (workspace/'.nbtcreator/reusable').glob('*.json')]
assert all(not tag.isdecimal() for item in library for tag in item['tags']),'Numeric component categories remain'
backups={}
for file in (workspace/'nbt_models/asset_library/_migration').glob('*/*.json'):
 try:
  data=json.loads(file.read_text(encoding='utf8'));backups.setdefault(file.stem,set()).add(components.validate(data)['content_sha256'])
 except (ValueError,KeyError,TypeError):pass
matched=[item['id'] for item in library if item['id'] in backups and item['content_sha256'] in backups[item['id']]]
assert all(item['content_sha256'] in backups[item['id']] for item in library if item['id'] in backups),'Component geometry differs from its migration backup'
assert before=={str(file):hashlib.sha256(file.read_bytes()).hexdigest() for file in files},'Audit modified an asset'
result=dict(passed=True,workspace=str(workspace),components=len(library),native_effects=len(native),recipes=sum(item['asset_type']=='recipe' for item in reusable),themes=sum(item['asset_type']=='theme' for item in reusable),migration_geometry_matches=len(matched),asset_files_unchanged=True,checks=dict(all_assets_readable=True,no_numeric_component_categories=True,migration_geometry_preserved=True,read_only=True))
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False))
