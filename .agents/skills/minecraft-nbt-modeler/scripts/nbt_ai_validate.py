"""Read-only validation of AI-created geometry using the shared Python engine."""
import argparse,json,math
from pathlib import Path


class CandidateIssue(ValueError):
    def __init__(self,error,index,operation):
        kind=operation['kind'];label=str(operation.get('label','')).replace('\n',' ')[:60]
        super().__init__(f'第{index}步（{kind}，{label}）：{error}')
        self.issue=dict(code='invalid_geometry',step=index,kind=kind,
                        bounds={key:operation[key] for key in ('lo','hi') if key in operation})


def simulate(model,walls,plan,raw_operations,maximum):
    from nbt_detail_control import simulate_plan

    class Steps(list):
        current=None
        def __iter__(self):
            indexes=(index for index,op in enumerate(raw_operations,1) if op.get('enabled',True))
            for index,operation in zip(indexes,super().__iter__(),strict=True):
                self.current=(index,operation)
                yield operation
            self.current=None

    steps=Steps(plan['operations'])
    try:
        return simulate_plan(model,walls,dict(plan,operations=steps),
                             dict(mode='standalone',openings=[],max_changed_blocks=maximum))
    except (ValueError,KeyError,TypeError,AssertionError) as failure:
        if steps.current:raise CandidateIssue(failure,*steps.current) from None
        raise


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
    if mode=='selection_edit':
        from nbt_selection_edit import compile_operations
        from nbt_assembly import Volume
        from nbt_detail_control import compile_plan,default_settings
        summary=context['selection'];size=summary['size'];hi=[axis-1 for axis in size]
        operations=result['settings_patch']['operations']
        if not operations:return dict(block_states=True,geometry='no_operations',nbt_exported=False)
        local=compile_operations(operations,[0,0,0],hi,size,context['allow_overwrite'])
        if any(op['kind'] not in {'box','hollow_box','beam','frame','geometry','auto_stairs','auto_roof','replace'}
               for op in local if op.get('enabled',True)):
            return dict(block_states=True,geometry='requires_target_preview',nbt_exported=False)
        baseline=Volume(size);walls=set()
        for x,y,z,length,index,wall in summary['runs']:
            for p in ((u,y,z) for u in range(x,x+length)):
                baseline.put(p,summary['palette'][index])
                if wall:walls.add(p)
        plan=compile_plan(dict(default_settings(),operations=local),size)
        simulate(baseline,walls,plan,operations,65536)
        return dict(block_states=True,geometry='checked_locally_requires_target_preview',nbt_exported=False)
    if mode=='small_structure' and context.get('size'):
        from nbt_assembly import Volume
        from nbt_detail_control import compile_plan,default_settings
        from nbt_recipes import translate_operation
        patch=result['settings_patch'];lo,hi=patch['lo'],patch['hi'];size=[b-a+1 for a,b in zip(lo,hi)]
        operations=[dict(translate_operation(op,[-axis for axis in lo]),write_group='candidate') for op in patch['operations']]
        for index,op in enumerate(operations,1):
            if math.prod(b-a+1 for a,b in zip(op['lo'],op['hi']))>2000000:
                raise CandidateIssue('几何预检操作域超过200万格，请缩小此步骤范围',index,op)
        plan=compile_plan(dict(default_settings(),operations=operations),size)
        simulate(Volume(size),set(),plan,operations,math.prod(size))
        return dict(block_states=True,geometry='checked_locally_requires_target_preview',nbt_exported=False)
    if mode!='workbench' or context.get('task')!='draft':return dict(block_states=True,geometry='requires_target_preview',nbt_exported=False)
    from nbt_assembly import Volume
    from nbt_detail_control import default_settings,compile_plan
    size=result.get('project_patch',{}).get('size',context['project']['size'])
    settings=default_settings();settings.update(operations=result['operations'],max_changed_blocks=2000000)
    plan=compile_plan(settings,size)
    for index,operation in enumerate(plan['operations']):
        if all(isinstance(operation.get(key),list) and len(operation[key])==3 for key in ['lo','hi']) and math.prod(max(0,b-a+1) for a,b in zip(operation['lo'],operation['hi']))>2000000:
            raise ValueError('第'+str(index+1)+'步操作域超过200万格，请拆分或缩小单步范围')
    model,walls,_=simulate(Volume(size),set(),plan,result['operations'],2000000)
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
