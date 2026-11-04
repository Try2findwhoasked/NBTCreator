"""Semantic organization without changing geometry or component IDs."""
import hashlib,json,uuid
from pathlib import Path
from nbt_project_batch import write
ROOT=Path(__file__).resolve().parents[1]
TAXONOMY=json.loads((ROOT/'config/asset-taxonomy.json').read_text(encoding='utf8'))

def semantic_tags(data):
    tags=[t for t in data.get('tags',[]) if not t.isdecimal() and t not in TAXONOMY['generic_tags'] and t!=data['name']]
    if tags:return list(dict.fromkeys(tags))
    return [next((group['name'] for group in TAXONOMY['groups'] if any(word in data['name'] for word in group['words'])),TAXONOMY['fallback'])]

def organize(workspace):
    import nbt_components as components
    import nbt_recipes as recipes
    from nbt_asset_batches import organize as snapshot
    from nbt_effect_assets import dispatch as effects
    workspace=Path(workspace).resolve()
    if not components.library_root(workspace).resolve().is_relative_to(workspace):raise ValueError('构件库超出工作区，未执行整理')
    folder=workspace/'nbt_models/asset_library';folder.mkdir(parents=True,exist_ok=True)
    if not folder.resolve().is_relative_to(workspace):raise ValueError('资产组织目录越界')
    identifier=uuid.uuid4().hex;backup=folder/'_migration'/identifier;changes=[];items=components.listing(workspace)
    for item in items['items']:
        file=components.component_file(workspace,item['id']);raw=file.read_bytes();data=json.loads(raw);tags=semantic_tags(data)
        if data.get('tags',[])==tags:continue
        old=components.load(workspace,item['id'])['content_sha256'];write(backup/(item['id']+'.json'),data);components.update(workspace,item['id'],tags=tags)
        if components.load(workspace,item['id'])['content_sha256']!=old:raise ValueError('整理改变了构件几何')
        changes.append(dict(id=item['id'],name=item['name'],before_tags=data.get('tags',[]),after_tags=tags,original_sha256=hashlib.sha256(raw).hexdigest()))
    from nbt_effect_assets import validate as validate_effect,fingerprint
    existing=effects(workspace,'list',{})['items'];known={fingerprint(item['settings']) for item in existing};legacy=[];legacy_errors=[]
    allowed={'strength','seed','style_note','operations','structure','replace','pattern','weathering','floor'}
    for relative in ['nbt_models/_workspaces/effects','nbt_models/_workspaces/desktop','nbt_models/_workspaces/bootstrap','nbt_models/effects']:
        directory=workspace/relative
        if not directory.resolve().is_relative_to(workspace):continue
        for file in sorted(directory.glob('*.json'))[:1000]:
            if file.is_symlink() or not file.resolve().is_relative_to(workspace):continue
            try:
                if file.stat().st_size>8*1024*1024:continue
                raw=json.loads(file.read_text(encoding='utf-8-sig'));settings=raw.get('settings') if isinstance(raw,dict) else None
                if not isinstance(settings,dict) or not any(k in settings for k in ['operations','structure','pattern','weathering','floor','replace']):continue
                settings={k:v for k,v in settings.items() if k in allowed}
                if 'operations' in settings:settings['operations']=[{k:v for k,v in op.items() if k not in ('overwrite','write_group','write_bounds','max_writes','skip_protected')} for op in settings['operations']]
                value=validate_effect(dict(name=file.stem[:80],settings=settings));key=fingerprint(value['settings'])
                if key in known:continue
                result=effects(workspace,'save',dict(asset=value));known.add(key);legacy.append(dict(source=file.relative_to(workspace).as_posix(),effect_id=result['id'],source_sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
            except Exception as error:legacy_errors.append(dict(source=str(file),error=str(error)))
    migrated_recipes=[]
    for item in recipes.listing(workspace)['items']:
        if item['asset_type']!='recipe' or item.get('archived'):continue
        try:
            recipe=recipes.load(workspace,item['id']);specs=recipe['parameters'];values={k:recipes.parameter_value(v,v['default']) for k,v in specs.items()};operations=recipes.resolve(recipe['operations'],specs,values)
            operations=[{k:v for k,v in op.items() if k not in ('overwrite','write_group','write_bounds','max_writes','skip_protected')} for op in operations];settings=dict(operations=operations);key=fingerprint(settings)
            if key in known:continue
            saved=effects(workspace,'save',dict(asset=dict(name=recipe['name'],settings=settings,tags=[t for t in recipe['tags'] if not t.isdecimal()],source_recipe_id=item['id'])))
            native=workspace/'nbt_models/asset_library/tool_effects'/saved['id'];write(native/'source-recipe.json',recipe);known.add(key);migrated_recipes.append(dict(recipe_id=item['id'],effect_id=saved['id'],name=recipe['name']))
        except Exception as error:legacy_errors.append(dict(recipe_id=item['id'],error=str(error)))
    batch=snapshot(workspace);component_list=components.listing(workspace);recipe_list=recipes.listing(workspace);effect_list=effects(workspace,'list',{})
    catalog=dict(schema_version=1,components=[{k:v for k,v in item.items() if k not in ('file','thumbnail')} for item in component_list['items']],tool_effects=effect_list['items'],recipes=[{k:v for k,v in item.items() if k!='file'} for item in recipe_list['items']])
    write(folder/'catalog.json',catalog)
    report=dict(migrated_recipes=migrated_recipes,migrated_effects=legacy,legacy_errors=legacy_errors,changed=len(changes),changes=changes,components=len(component_list['items']),tool_effects=len(effect_list['items']),recipes=len(recipe_list['items']),component_ids_preserved=True,geometry_unchanged=True,archive=batch,report=(folder/('organization-'+identifier+'.json')).relative_to(workspace).as_posix())
    write(workspace/report['report'],report);return report
