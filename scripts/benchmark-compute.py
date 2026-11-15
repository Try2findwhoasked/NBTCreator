"""Reproducible host-to-host CPU/GPU timings, including synchronized readback."""
import argparse,copy,json,statistics,sys,time
from datetime import datetime
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
if 'nbt_structure_agent' not in sys.modules:
    sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_compute import info
from nbt_deform import warp_pixels
from nbt_field_compute import sample
from nbt_spectral import smooth
from nbt_structure_agent import dispatch


def column_request(backend='cpu'):
    from math import cos,sin,tau
    nodes=[dict(id='core',shape='cylinder',centre=[16,20,16],radius=6,height=34)]
    cutters=[]
    for i in range(8):
        key=f'cut{i}';cutters.append(key)
        nodes.append(dict(id=key,shape='cylinder',centre=[16+6*cos(tau*i/8),20,16+6*sin(tau*i/8)],radius=1.3,height=36))
    nodes.extend([dict(id='cuts',shape='union',children=cutters),
        dict(id='shaft',shape='difference',children=['core','cuts'],transforms=[dict(kind='twist',axis='y',centre=[16,20,16],length=34,degrees=135),dict(kind='taper',axis='y',centre=[16,20,16],length=34,amount=.2)]),
        dict(id='base',shape='box',min=[7,0,7],max=[25,3,25]),dict(id='cap',shape='box',min=[8,37,8],max=[24,40,24]),
        dict(id='column',shape='union',children=['shaft','base','cap'])])
    return dict(name='扭花柱·计算变换样件',size=[32,40,32],root='column',nodes=nodes,material='quartz_block',backend=backend)


def measure(fn,repeats=5):
    start=time.perf_counter();result=fn();cold=time.perf_counter()-start
    values=[]
    for _ in range(repeats):
        start=time.perf_counter();result=fn();values.append(time.perf_counter()-start)
    return result,dict(first_seconds=cold,warm_median_seconds=statistics.median(values),warm_samples_seconds=values)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);args=parser.parse_args()
    output=args.output or ROOT/'build'/('compute-bench-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    output.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter();device=info();startup=time.perf_counter()-start
    if not device['gpu_available']:raise SystemExit('Real GPU required: '+str(device['reason']))
    report=dict(device=device,device_probe_seconds=startup,measurement='host inputs to synchronized host outputs, float64',cases=[])
    def record(kind,size,fn,compare):
        cpu,ct=measure(lambda:fn('cpu'));actual,gt=measure(lambda:fn('gpu'));error=compare(cpu,actual)
        row=dict(kind=kind,size=size,cpu=ct,gpu=gt,max_error=error,speedup=ct['warm_median_seconds']/gt['warm_median_seconds'])
        report['cases'].append(row);print(json.dumps(dict(kind=kind,size=size,speedup=round(row['speedup'],3)),ensure_ascii=False),flush=True)
        (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    def numeric(a,b):
        np.testing.assert_allclose(a,b,atol=1e-8,rtol=1e-10);return float(np.max(np.abs(a-b)))
    def exact(a,b):np.testing.assert_array_equal(a,b);return 0
    rng=np.random.default_rng(32)
    for n in (8,128,512):
        image=rng.uniform(0,255,(n,n))
        record('disk_fft',[n,n],lambda backend:smooth(image,'disk',min(24,max(2,n//8)),'reflect','fft',backend)[0],numeric)
    transforms=[dict(kind='swirl',radius=.7,degrees=150),dict(kind='wave',amplitude=.04,wavelength=.3),dict(kind='polar_repeat',sectors=8,mirror=True)]
    for n in (32,512):
        image=rng.uniform(0,255,(n,n,4))
        record('pattern_maps_rgba',[n,n],lambda backend:warp_pixels(image,dict(transforms=transforms,backend=backend,boundary='clamp'),False)[0],numeric)
    for n in (24,64):
        query=dict(size=[n]*3,root='relief',nodes=[dict(id='body',shape='superellipsoid',centre=[n/2]*3,radii=[n*.3,n*.45,n*.25],power=6),dict(id='lattice',shape='gyroid',wavelength=n/3,thickness=.6),dict(id='relief',shape='intersection',children=['body','lattice'])],
            transforms=[dict(kind='twist',centre=[n/2]*3,degrees=160,length=n),dict(kind='wave',axis='x',driver='y',amplitude=1,wavelength=n/3)])
        record('implicit_field',[n]*3,lambda backend:sample(dict(query,backend=backend))[0],exact)
    # Full public tool includes Python voxel materialization and validation.
    record('field_public_tool',[32,40,32],lambda backend:dispatch(output,'field_compile',column_request(backend))['content_sha256'],lambda a,b:0 if a==b else (_ for _ in ()).throw(AssertionError('candidate geometry differs')))
    report['notes']=['First operation timings include lazy kernel compilation/FFT setup after device probe; the existing CuPy disk cache is retained.','Warm medians include input transfer and blocking output transfer.','No speedup is claimed for source writing, collision routes, rendering or the full application.']
    (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    rows='\n'.join(f"| {r['kind']} {r['size']} | {r['cpu']['warm_median_seconds']*1000:.3f} | {r['gpu']['warm_median_seconds']*1000:.3f} | {r['speedup']:.2f}× |" for r in report['cases'])
    (output/'report.md').write_text('# CPU/GPU计算基准\n\n设备：'+device['device']+f'；探测及初始化：{startup:.3f}秒。以下是包含上传和同步读回的预热后中位数。\n\n| 任务 | CPU毫秒 | GPU毫秒 | CPU/GPU |\n| --- | ---: | ---: | ---: |\n'+rows+'\n\n完整工具还包含CPU方块展开与校验；不是整栋建筑建造速度。首次调用与全部样本见results.json。\n',encoding='utf8')
    print(json.dumps(dict(output=str(output),passed=True),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
