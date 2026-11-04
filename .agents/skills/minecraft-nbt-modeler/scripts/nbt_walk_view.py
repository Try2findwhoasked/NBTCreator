"""Read-only player/route visualization, using the authoring collision engine."""
from pathlib import Path
import hashlib
import json
import math

SUPPORTED_INSPECTION_TOOLS = frozenset({'walk-inspect'})


def inspect_walk(request, snapshot=None):
    from nbt_refine import read_master
    from nbt_library import canonical_context
    from nbt_assembly import Volume
    from nbt_collision import _Space, check_routes, RADIUS, PLAYER_HEIGHT

    def sha(file):
        return hashlib.sha256(Path(file).read_bytes()).hexdigest()

    source = Path(request['source']).resolve()
    source_hash = sha(source)
    if request.get('source_sha256') != source_hash:
        raise ValueError('源建筑已改变，请重新打开后检查通路')
    model, _ = read_master(source)
    snapshot_hash = sha(snapshot) if snapshot else None
    if snapshot:
        data = json.loads(Path(snapshot).read_text(encoding='utf-8-sig'))
        if data.get('source_sha256') != source_hash or data.get('size') != list(model.size):
            raise ValueError('检查快照不属于当前建筑')
        candidate = model
        if data.get('preview_only'):
            if not isinstance(data.get('master_blocks'),list):
                raise ValueError('候选快照缺少完整主模型')
            candidate = Volume(model.size)
            for p, value in data['master_blocks']:
                candidate.put(p, value)
        if candidate.fingerprint() != data.get('geometry_sha256'):
            raise ValueError('检查快照几何指纹不一致')
        model = candidate
    geometry = model.fingerprint()
    if request.get('geometry_sha256') and request['geometry_sha256'] != geometry:
        raise ValueError('画面已变化，请对当前画面重新检查通路')
    context = Path(request['context']).resolve() if request.get('context') else None
    context_hash = sha(context) if context else None
    config = canonical_context(context) if context else {}
    start = request.get('start', config.get('start'))
    targets = request.get('targets', config.get('targets'))
    if start is None or not targets:
        raise ValueError('请填写玩家脚底起点和至少一个终点，或关联包含 start / targets 的坐标资料')
    if not isinstance(targets, (dict, list)) or len(targets) > 32:
        raise ValueError('通路检查最多接受32个终点')

    def position(p):
        if (not isinstance(p, (list, tuple)) or len(p) != 3
                or any(isinstance(n, bool) or not isinstance(n, (int, float))
                       or not math.isfinite(n) or n < 0 or n > model.size[i]
                       for i, n in enumerate(p))):
            raise ValueError('玩家脚底坐标须为模型边界内的有限 XYZ 数字')
        return list(p)

    start = position(start)
    if isinstance(targets, dict) and any(not isinstance(name,str) or not name.strip() or len(name)>120 for name in targets):
        raise ValueError('终点名称须为1～120字，不会截断或合并不同终点')
    targets = {str(name): position(p) for name, p in
               (targets.items() if isinstance(targets, dict) else enumerate(targets))}
    report = check_routes(model, start, targets, max_poses=250000)
    space = _Space(model)

    def pose(name, feet):
        lo = [feet[0]-RADIUS, feet[1], feet[2]-RADIUS]
        hi = [feet[0]+RADIUS, feet[1]+PLAYER_HEIGHT, feet[2]+RADIUS]
        outside = any(a < 0 or b > size for a, b, size in zip(lo, hi, model.size))
        cells = []
        for y in range(max(0, math.floor(lo[1]*2)), min(space.sy, math.ceil(hi[1]*2))):
            for z in range(max(0, math.floor(lo[2]*2)), min(space.sz, math.ceil(hi[2]*2))):
                row = space.rows[y*space.sz+z]
                for x in range(max(0, math.floor(lo[0]*2)), min(space.sx, math.ceil(hi[0]*2))):
                    if row & (1 << x):
                        # A cell touching only an AABB face is not a collision.
                        if all(min((c+1)*.5, b)-max(c*.5, a) > 1e-8
                               for c, a, b in zip((x,y,z), lo, hi)):
                            cells.append([x*.5,y*.5,z*.5])
        return dict(name=name, feet=feet, lo=lo, hi=hi, outside=outside,
                    supported=space.supported(feet), clear=space.clear_player_sweep(feet,feet),
                    standing=space.standing(feet), collisions=cells)

    result = dict(schema_version=1, source_sha256=source_hash, geometry_sha256=geometry,
                  context_sha256=context_hash, size=list(model.size), report=report,
                  poses=[pose('起点', start)]+[pose(name, p) for name,p in targets.items()],
                  available=True, asset_written=False, runtime_verified=False,
                  inspected_snapshot=bool(snapshot))
    if sha(source) != source_hash or (context and sha(context) != context_hash) or (snapshot and sha(snapshot) != snapshot_hash):
        raise ValueError('检查期间建筑或坐标资料已改变，请重新检查')
    return result
