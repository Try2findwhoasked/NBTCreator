"""Bounded, process-local reuse of pure modelling results. Never caches writes."""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path


class ModellingSession:
    """Reuse compilation and route evidence; every tool still checks bindings.

    Calls return ordinary candidates. This session does not apply, save, approve
    or export them. Geometry and source/context SHA checks remain in the tools.
    """
    def __init__(self,workspace=None,max_entries=32,max_bytes=32*1024*1024):
        if type(max_entries) is not int or not 1<=max_entries<=128:raise ValueError('会话缓存上限须为1～128')
        if type(max_bytes) is not int or max_bytes<1024:raise ValueError('会话缓存容量须至少1024字节')
        self.workspace=Path(workspace).resolve() if workspace is not None else None
        self.max_entries=max_entries;self.max_bytes=max_bytes;self._bytes=0;self._items=OrderedDict();self.stats=dict(hits=0,misses=0,evictions=0)

    def get(self,namespace,key):
        full=(namespace,key)
        if full not in self._items:self.stats['misses']+=1;return None
        self.stats['hits']+=1;self._items.move_to_end(full)
        return deepcopy(self._items[full][0])

    def put(self,namespace,key,value,weight=None):
        weight=weight if weight is not None else len(canonical(value).encode('utf8'))*6
        if weight>self.max_bytes:return
        full=(namespace,key)
        if full in self._items:self._bytes-=self._items.pop(full)[1]
        self._items[full]=(deepcopy(value),weight);self._bytes+=weight
        while len(self._items)>self.max_entries or self._bytes>self.max_bytes:
            self._bytes-=self._items.popitem(last=False)[1][1];self.stats['evictions']+=1

    def clear(self):self._items.clear();self._bytes=0

    def call(self,tool,arguments):
        if self.workspace is None:raise ValueError('调用工具前须指定创作工作区')
        from nbt_agent.structure import dispatch
        if _active.get() is self:return dispatch(self.workspace,tool,arguments)
        with self:return dispatch(self.workspace,tool,arguments)

    def __enter__(self):
        if hasattr(self,'_token'):raise ValueError('同一建模会话不能嵌套进入')
        self._token=_active.set(self);return self

    def __exit__(self,*error):
        _active.reset(self._token);del self._token


_default=ModellingSession()
_active=ContextVar('nbt_modelling_session',default=None)
_engine_snapshot = ContextVar('nbt_engine_snapshot', default=None)
def current():return _active.get() or _default
def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)


@lru_cache(maxsize=256)
def _file_digest(file,size,mtime,ctime):return sha256(Path(file).read_bytes()).hexdigest()


def engine_revision():
    snapshot = _engine_snapshot.get()
    return _scan_engine_revision() if snapshot is None else snapshot


@contextmanager
def engine_revision_scope():
    """Reuse one revision during a request and expose its publication guard."""
    revision = engine_revision()

    def verify():
        if _scan_engine_revision() != revision:
            raise ValueError('引擎版本在构建期间发生变化，请重新运行当前请求')

    token = _engine_snapshot.set(revision)
    try:
        yield verify
    finally:
        _engine_snapshot.reset(token)


def _scan_engine_revision():
    # Include implementation, registry and contract changes in cache identity.
    # Python implementation updates still require restarting the process.
    directory=Path(__file__).resolve().parents[1]
    files=[*directory.rglob('*.py'),directory.parent/'tool-catalog.json',directory.parent/'references/block-registry-1.20.1.json']
    from nbt_extensions import revision_token
    registrations=sha256(canonical(revision_token()).encode('utf8')).hexdigest()
    entries = []
    for path in sorted(files):
        stat = path.stat()
        file_digest = _file_digest(str(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        entries.append((path.relative_to(directory.parent).as_posix(), file_digest))
    return (*entries, ('extension_registry', registrations))
