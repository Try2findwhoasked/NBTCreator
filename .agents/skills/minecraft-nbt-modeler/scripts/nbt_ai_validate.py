"""Read-only validation of AI-created geometry using the shared Python engine."""
import argparse,json,math
from pathlib import Path


def check_materials(result):
    from nbt_registry import normalize
    errors={}
    def state(value,location):
        try:normalize(value)
        except (ValueError,TypeError) as error:errors.setdefault(str(error),location)
    def walk(value,location='结果'):
        if isinstance(value,list):
            for index,item in enumerate(value):walk(item,location+'['+str(index+1)+']')
        elif isinstance(value,dict):
            for key,item in value.items():
                if key in {'state','slab_state','stair_state','moss_state','crack_state'}:state(item,location+'.'+key)
                elif key in {'from_states','palette'} and isinstance(item,list):
                    for entry in item:
                        if isinstance(entry,str) or isinstance(entry,dict) and 'Name' in entry:state(entry,location+'.'+key)
                        else:walk(entry,location+'.'+key)
                elif key in {'material_map','slab_overrides'} and isinstance(item,dict):
                    for a,b in item.items():state(a,location+'.'+key);state(b,location+'.'+key)
                else:walk(item,location+'.'+key)
    walk(result)
    if errors:raise ValueError('材质须符合Java1.20.1，可用stone_bricks/cobblestone/andesite。请一次修正所有步骤中的无效材质：'+'；'.join(location+' '+error for error,location in list(errors.items())[:12]))


def validate(request):
    mode=request['mode'];result=request['result'];context=request['context']
    check_materials(result)
    if mode=='component':
        from nbt_structure_agent import build
        data=build(request['workspace'],result['spec'])
        return dict(blocks=len(data['blocks']),size=data['size'],nbt_exported=False)
    if mode!='workbench' or context.get('task')!='draft':return dict(block_states=True,geometry='requires_target_preview',nbt_exported=False)
    from nbt_assembly import Volume
    from nbt_detail_control import default_settings,compile_plan,simulate_plan
    size=result.get('project_patch',{}).get('size',context['project']['size'])
    settings=default_settings();settings.update(operations=result['operations'],max_changed_blocks=2000000)
    plan=compile_plan(settings,size)
    for index,operation in enumerate(plan['operations']):
        if all(isinstance(operation.get(key),list) and len(operation[key])==3 for key in ['lo','hi']) and math.prod(max(0,b-a+1) for a,b in zip(operation['lo'],operation['hi']))>2000000:
            raise ValueError('第'+str(index+1)+'步操作域超过200万格，请拆分或缩小单步范围')
    class Steps(list):
        # Track the engine's actual iteration without rebuilding prefixes or
        # changing write ownership, ordering, conflict or protection semantics.
        current=None
        def __iter__(self):
            for index,operation in enumerate(super().__iter__()):
                self.current=(index,operation)
                yield operation
    steps=Steps(plan['operations']);plan['operations']=steps
    try:model,walls,diff=simulate_plan(Volume(size),set(),plan,dict(mode='standalone',openings=[],max_changed_blocks=2000000))
    except (ValueError,KeyError,TypeError,AssertionError) as error:
        if steps.current:
            index,operation=steps.current
            raise ValueError('第'+str(index+1)+'步（'+operation['kind']+'，'+str(operation.get('label','')).replace('\n',' ')[:60]+'）：'+str(error)) from None
        raise
    if not model.blocks:raise ValueError('初稿工具序列没有生成实体，请保留有效主体构造')
    from nbt_registry import effective
    for state in set(model.blocks.values()):effective(state)
    return dict(blocks=len(model.blocks),wall_blocks=len(walls),size=list(size),nbt_exported=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--request',type=Path,required=True);args=parser.parse_args()
    try:
        if args.request.stat().st_size>4*1024*1024:raise ValueError('AI预检数据超过4MiB')
        result=validate(json.loads(args.request.read_text(encoding='utf8')));print(json.dumps(dict(ok=True,result=result),ensure_ascii=False))
    except (ValueError,KeyError,TypeError,AssertionError) as error:print(json.dumps(dict(ok=False,error=str(error)[:1000]),ensure_ascii=False))
