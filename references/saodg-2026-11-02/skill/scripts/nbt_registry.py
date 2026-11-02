"""Version-pinned vanilla state validation; renderer support is a separate concern."""
import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile

REGISTRY = Path(__file__).resolve().parents[1] / 'references/block-registry-1.20.1.json'
STATE = re.compile(r'(?P<name>(?:minecraft:)?[a-z0-9_]+)(?:\[(?P<props>[^\[\]]+)\])?')


@lru_cache(maxsize=1)
def registry():
    data = json.loads(REGISTRY.read_text(encoding='utf8'))
    if data['minecraft_version'] != '1.20.1' or data['data_version'] != 3465:
        raise ValueError('Expected the Minecraft 1.20.1 registry')
    payload = json.dumps(data['blocks'], sort_keys=True, separators=(',', ':')).encode()
    if hashlib.sha256(payload).hexdigest() != data['blocks_sha256']:
        raise ValueError('Registry content hash mismatch; regenerate from the pinned server report')
    return data


@lru_cache(maxsize=8192)
def _validate(name, properties):
    if ':' not in name:
        name = 'minecraft:' + name
    entry = registry()['blocks'].get(name)
    if entry is None:
        raise ValueError(f'Unknown Minecraft 1.20.1 block: {name}')
    for key, value in properties:
        allowed = entry['properties'].get(key)
        if allowed is None or value not in allowed:
            raise ValueError(f'Invalid state {name}[{key}={value}]; allowed: {allowed}')
    return name + ('[' + ','.join(f'{k}={v}' for k, v in properties) + ']' if properties else '')


def normalize(value):
    """Validate supplied properties without silently inserting defaults into old assets."""
    if isinstance(value, dict):
        if set(value) - {'Name', 'Properties'}:
            raise ValueError('State object accepts only Name and Properties')
        name, props = value.get('Name'), value.get('Properties', {})
        if not isinstance(name, str) or not isinstance(props, dict):
            raise ValueError('Expected a block Name and a Properties object')
    elif isinstance(value, str):
        match = STATE.fullmatch(value)
        if not match:
            raise ValueError(f'Malformed state: {value}')
        name, props = match['name'], {}
        if match['props']:
            for item in match['props'].split(','):
                if item.count('=') != 1:
                    raise ValueError(f'Malformed property: {item}')
                key, val = item.split('=')
                if key in props:
                    raise ValueError(f'Duplicate property: {key}')
                props[key] = val
    else:
        raise ValueError('State must be a string or Name/Properties object')
    if any(not isinstance(k, str) or not isinstance(v, str) for k, v in props.items()):
        raise ValueError('Property names and values must be strings')
    return _validate(name, tuple(sorted(props.items())))


def effective(value):
    """Return the real version defaults plus supplied properties for diagnostic consumers."""
    canonical = normalize(value)
    name, _, tail = canonical.partition('[')
    props = dict(registry()['blocks'][name]['default'])
    props.update(dict(item.split('=') for item in tail.rstrip(']').split(',') if item))
    return name, props


def compile_report(report, server_jar, output):
    report, server_jar, output = Path(report), Path(server_jar), Path(output)
    with ZipFile(server_jar) as jar:
        version = json.loads(jar.read('version.json'))
    if version['id'] != '1.20.1' or version['world_version'] != 3465:
        raise ValueError('Generate reports using the Java 1.20.1 server')
    raw = report.read_bytes()
    entries = json.loads(raw)
    blocks = {}
    for name, entry in sorted(entries.items()):
        defaults = [s for s in entry['states'] if s.get('default')]
        if len(defaults) != 1:
            raise ValueError(f'Expected one default state: {name}')
        blocks[name] = dict(properties=entry.get('properties', {}), default=defaults[0].get('properties', {}))
    payload = json.dumps(blocks, sort_keys=True, separators=(',', ':')).encode()
    data = dict(minecraft_version='1.20.1', data_version=3465, block_count=len(blocks),
                source='Minecraft Java server net.minecraft.data.Main --reports; reports/blocks.json',
                server_sha256=hashlib.sha256(server_jar.read_bytes()).hexdigest(),
                report_sha256=hashlib.sha256(raw).hexdigest(), blocks_sha256=hashlib.sha256(payload).hexdigest(),
                blocks=blocks)
    if output.exists():
        raise FileExistsError('Choose a new output; review changes before replacing the bundled registry')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    return {k: v for k, v in data.items() if k != 'blocks'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    query = sub.add_parser('query')
    query.add_argument('block')
    compile_cmd = sub.add_parser('compile')
    for flag in ('report', 'server-jar', 'output'):
        compile_cmd.add_argument('--' + flag, required=True, type=Path)
    args = parser.parse_args()
    if args.command == 'compile':
        result = compile_report(args.report, args.server_jar, args.output)
    else:
        name, props = effective(args.block)
        result = dict(name=name, effective_properties=props, **registry()['blocks'][name])
    print(json.dumps(result, ensure_ascii=False, indent=2))
