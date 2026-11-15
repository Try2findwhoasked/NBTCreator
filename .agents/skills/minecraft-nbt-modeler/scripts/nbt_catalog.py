"""Process-local read-only catalogue snapshots; invalidate on file changes."""
from functools import lru_cache
import hashlib,json
from pathlib import Path

FILE=Path(__file__).resolve().parents[1]/'tool-catalog.json'

@lru_cache(maxsize=2)
def _read(path,size,mtime,ctime):
    raw=Path(path).read_bytes()
    return json.loads(raw),hashlib.sha256(raw).hexdigest()

def snapshot():
    stat=FILE.stat()
    return _read(str(FILE),stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)

def catalog():
    """Internal borrowed data only. Public query functions must return copies."""
    return snapshot()[0]
