"""Optional bounded NumPy/CuPy execution. GPU readback is always synchronized."""
from functools import lru_cache
import numpy as np


@lru_cache(maxsize=1)
def gpu():
    try:
        import cupy as cp
        if cp.cuda.runtime.getDeviceCount()<1:raise RuntimeError('no CUDA device')
        # Probe a real kernel, not just import or driver enumeration.
        cp.asnumpy(cp.arange(4,dtype=cp.float64)+1)
        return cp,None
    except Exception as error:
        return None,type(error).__name__+': '+str(error).split('\n')[0][:240]


def info():
    cp,error=gpu()
    return dict(cpu='numpy',gpu_available=cp is not None,gpu_backend='cupy_cuda' if cp is not None else None,
        device=cp.cuda.runtime.getDeviceProperties(0)['name'].decode() if cp is not None else None,
        reason=error,precision='float64',selection='auto is conservative; explicit gpu requires a working backend',
        accelerated=['image_convolution','pattern_coordinate_mapping','implicit_field_sampling'],
        cpu_checks=['block_states','budget','protection','half_block_collision','source_hashes'])


def execute(backend,large,calculate,estimated_bytes=0):
    """calculate(xp) returns an array. Auto failures return CPU + visible reason."""
    if backend not in ('auto','cpu','gpu'):raise ValueError('backend须为auto/cpu/gpu')
    cp=None;reason='explicit_cpu' if backend=='cpu' else 'below_gpu_work_threshold'
    if backend=='gpu' or backend=='auto' and large:
        cp,reason=gpu()
        if cp is not None:
            try:
                free,_=cp.cuda.runtime.memGetInfo()
                if estimated_bytes>min(free//2,512*1024**2):raise RuntimeError('GPU memory estimate exceeds safe operation budget')
                output=cp.asnumpy(calculate(cp),blocking=True)
                if not np.isfinite(output).all():raise RuntimeError('non-finite GPU result')
                return output,dict(requested=backend,actual='gpu',implementation='cupy_cuda',reason='explicit_gpu' if backend=='gpu' else 'work_threshold',precision='float64',synchronized_readback=True)
            except Exception as error:
                reason=type(error).__name__+': '+str(error).split('\n')[0][:240]
        if backend=='gpu':raise ValueError('GPU不可用或计算失败：'+str(reason))
    output=np.asarray(calculate(np))
    if not np.isfinite(output).all():raise ValueError('CPU计算产生非有限结果')
    return output,dict(requested=backend,actual='cpu',implementation='numpy',reason=reason,precision='float64',synchronized_readback=True)


if __name__=='__main__':
    import json
    print(json.dumps(info(),ensure_ascii=False,indent=2))
