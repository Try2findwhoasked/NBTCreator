"""Synthetic registered-room management: snapshots, narrow edits and safe failure."""
import argparse
import copy
import json
from pathlib import Path
from unittest.mock import patch
import os
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from backend import catalog,assemble,snapshot,plan,apply_changes,sha,dump
from nbt_wall_layers import _write_sparse


def refuses(fn):
    try:fn()
    except (ValueError,KeyError):return True
    return False


def fixture(workspace):
    data=workspace/'src/main/resources/data/saodg';(data/'dungeons').mkdir(parents=True);(data/'rooms').mkdir()
    language={};rooms=[]
    for index,kind in enumerate(['entrance','combat','puzzle','outpost','boss','safe','combat']):
        name=f'room_{index}';rid='saodg:'+name;rooms.append(rid);key='room.saodg.'+name;language[key]=['入口','战斗厅','谜题厅','封印厅','首领厅','未选安全房','备用战斗厅'][index]
        body={(x,0,z):'minecraft:stone_bricks' for x in range(48) for z in range(48)}
        walls={(0,y,z):'minecraft:stone_bricks' for y in range(1,8) for z in range(48)}
        for layer,blocks in [('body',body),('walls',walls)]:_write_sparse(data/f'structures/{name}/p00_{layer}.nbt',(48,8,48),blocks)
        dump(data/f'rooms/{name}.json',dict(schema_version=5,type=kind,size=[48,8,48],cells=[[0,0]],rotations=[0],ports=[],selection_priority=10,
             identity=dict(display_name=key),parts=[dict(body_template=f'saodg:{name}/p00_body',wall_template=f'saodg:{name}/p00_walls',offset=[0,0,0])],keep_me={'unknown':['preserve',index]}))
    dump(data/'dungeons/ruins.json',dict(schema_version=2,content_version='synthetic',display_name='测试地牢',layout=dict(room_pool=rooms[:5],grid=[6,6]),difficulties=dict(trial=dict(sequence=['entrance','combat','puzzle','outpost','boss'])),keep_me=['all other fields']))
    lang=workspace/'src/main/resources/assets/saodg/lang/zh_cn.json';lang.parent.mkdir(parents=True);dump(lang,language)
    return rooms


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);out=parser.parse_args().output.resolve();out.mkdir(parents=True,exist_ok=False)
    workspace=out/'workspace';ids=fixture(workspace);data=workspace/'src/main/resources/data/saodg';checks={};initial={str(p):sha(p) for p in data.rglob('*') if p.is_file()}
    listing=catalog(workspace);checks['registered_and_inactive_rooms_listed']=len(listing['rooms'])==7 and len(listing['dungeons'][0]['pool'])==5 and listing['templates']==14
    model,walls,source_hash=assemble(workspace,ids[1]);checks['actual_layered_nbt_assembled']=len(model.blocks)==48*48+7*48 and len(walls)==7*48
    result=snapshot(workspace,ids[1],out/'snapshot.json');checks['read_only_snapshot_has_actual_geometry']=result['geometry_sha256']==model.fingerprint() and len(json.loads((out/'snapshot.json').read_text())['wall_positions'])==len(walls)
    request=dict(revision=listing['revision'],dungeon='saodg:ruins',pool=[*ids[:5],ids[6]],priorities={ids[1]:70})
    original_bytes=(data/'dungeons/ruins.json').read_bytes();original_dungeon=json.loads(original_bytes);original_room=json.loads((data/'rooms/room_1.json').read_text())
    checks['planning_does_not_write_resources']=len(plan(workspace,request)['files'])==2 and all(sha(Path(p))==value for p,value in initial.items())
    invalid=copy.deepcopy(request);invalid['pool'].remove(ids[0]);checks['last_required_type_cannot_be_removed']=refuses(lambda:plan(workspace,invalid))
    invalid=copy.deepcopy(request);invalid['priorities']={ids[1]:101};checks['priority_range_matches_loader']=refuses(lambda:plan(workspace,invalid))
    invalid=copy.deepcopy(request);invalid['pool'].append(ids[0]);checks['duplicate_room_pool_refused']=refuses(lambda:plan(workspace,invalid))
    checks['unsafe_resource_id_refused']=refuses(lambda:assemble(workspace,'saodg:../../outside'))
    saved=apply_changes(workspace,request,out/'saved');after_dungeon=json.loads((data/'dungeons/ruins.json').read_text());after_room=json.loads((data/'rooms/room_1.json').read_text());after_dungeon['layout']['room_pool']=original_dungeon['layout']['room_pool'];after_room['selection_priority']=original_room['selection_priority']
    checks['only_pool_and_priority_fields_change']=saved['changed_files']==2 and after_dungeon==original_dungeon and after_room==original_room
    checks['original_bytes_backed_up']=(out/'saved/000_before.json').read_bytes()==original_bytes
    checks['stale_revision_refused']=refuses(lambda:apply_changes(workspace,request,out/'stale'))
    checks['inactive_definition_and_all_nbt_preserved']=all(sha(Path(p))==value for p,value in initial.items() if p.endswith('.nbt') or p.endswith('room_5.json'))
    fresh=catalog(workspace);broken=dict(revision=fresh['revision'],dungeon='saodg:ruins',pool=ids[:5],priorities={ids[2]:60});before={str(p):p.read_bytes() for p in [data/'dungeons/ruins.json',data/'rooms/room_2.json']};real_replace=os.replace
    def fail_second(source,target):
        if str(target).endswith('rooms'+os.sep+'room_2.json') and str(source).endswith('.tmp'):raise OSError('synthetic replace failure')
        return real_replace(source,target)
    try:
        with patch('backend.os.replace',side_effect=fail_second):apply_changes(workspace,broken,out/'rollback')
    except OSError:pass
    checks['partial_write_failure_restores_exact_bytes']=all(Path(p).read_bytes()==value for p,value in before.items())
    template=data/'structures/room_6/p00_body.nbt';template_bytes=template.read_bytes();template.unlink();listing=catalog(workspace);bad=dict(revision=listing['revision'],dungeon='saodg:ruins',pool=[*ids[:5],ids[6]],priorities={})
    checks['missing_template_blocks_pool_save']=refuses(lambda:plan(workspace,bad))
    template.write_bytes(template_bytes)
    dump(out/'results.json',dict(passed=all(checks.values()),checks=checks));assert all(checks.values()),checks
    print(json.dumps(dict(passed=True,checks=len(checks),fixture=str(workspace),report=str(out/'results.json'))))


if __name__=='__main__':main()
