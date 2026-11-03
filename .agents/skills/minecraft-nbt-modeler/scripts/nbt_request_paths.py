"""Workspace-relative persisted requests; absolute legacy inputs remain valid."""
import json
import os
from pathlib import Path
FIELDS=('source','context','cameras','review','reference_source')

def resolve_request_paths(data,workspace=None):
    value=dict(data);base=Path(workspace or Path.cwd()).resolve()
    for key in FIELDS:
        if value.get(key):value[key]=str((base/Path(value[key])).resolve())
    return value

def read_request(file,workspace=None):
    return resolve_request_paths(json.loads(Path(file).read_text(encoding='utf-8-sig')),workspace)

def portable_request(data,workspace=None):
    value=dict(data);base=Path(workspace or Path.cwd()).resolve()
    for key in FIELDS:
        if value.get(key):
            target=Path(value[key]).resolve()
            if target.is_relative_to(base):value[key]=target.relative_to(base).as_posix()
    value['path_base']='workspace'
    return value

def metadata_path(file,value):
    return (Path(file).parent/Path(value)).resolve()
