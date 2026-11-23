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

def read_request_json(file, *, max_bytes=None):
    """Read an explicitly supplied CLI request from the command's working directory."""
    path = Path(file).resolve()
    try:
        with path.open('rb') as stream:
            payload = stream.read() if max_bytes is None else stream.read(max_bytes + 1)
    except FileNotFoundError as error:
        raise ValueError(f'--request 文件不存在：{path}。请核对请求路径和命令的工作目录。') from error
    except OSError as error:
        raise ValueError(f'无法读取 --request 文件 {path}：{error.strerror}') from error
    if max_bytes is not None and len(payload) > max_bytes:
        raise ValueError(f'--request 文件超过 {max_bytes // (1024 * 1024)} MiB：{path}')
    try:
        data = json.loads(payload.decode('utf-8-sig'))
    except UnicodeDecodeError as error:
        raise ValueError(f'--request 文件须以 UTF-8 保存：{path}') from error
    except json.JSONDecodeError as error:
        raise ValueError(f'--request JSON 无效：{path}（第 {error.lineno} 行，第 {error.colno} 列，{error.msg}）') from error
    if not isinstance(data, dict):
        raise ValueError(f'--request JSON 顶层须为对象：{path}')
    return data

def read_request(file,workspace=None):
    return resolve_request_paths(read_request_json(file),workspace)

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
