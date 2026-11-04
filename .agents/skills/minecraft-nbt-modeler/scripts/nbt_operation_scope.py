"""Optional operation write bounds, shared by candidate and final writers."""
def scoped_operation(operation,size):
    safe={key:value for key,value in operation.items() if key!='write_bounds'}
    bounds=operation.get('write_bounds')
    if bounds is None:return safe,None
    if not isinstance(bounds,dict) or set(bounds)!={'lo','hi','allow_overwrite'} or type(bounds['allow_overwrite']) is not bool:raise ValueError('工具写入范围字段无效')
    lo,hi=bounds['lo'],bounds['hi']
    if any(not isinstance(p,list) or len(p)!=3 or any(type(n) is not int for n in p) for p in (lo,hi)) or any(lo[i]<0 or hi[i]>=size[i] or lo[i]>hi[i] for i in range(3)):raise ValueError('工具写入范围超出模型')
    return safe,bounds

def enforce_scope(bounds,operation,edits):
    if bounds is None:return operation
    outside=[p for p,value in edits if any(p[i]<bounds['lo'][i] or p[i]>bounds['hi'][i] for i in range(3))]
    if outside:raise ValueError('步骤“'+operation.get('label',operation['kind'])+'”实际写入超出限定选区：'+str(outside[:8]))
    return dict(operation,overwrite=bounds['allow_overwrite'])
