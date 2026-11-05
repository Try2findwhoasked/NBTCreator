"""Check portable references, syntax, pinned state data and viewer dependency drift."""
import ast
import json
from pathlib import Path
import re
from urllib.parse import unquote
from nbt_registry import registry


def main():
    root = Path(__file__).resolve().parents[1]
    errors = []
    markdown = [root / 'SKILL.md', *sorted((root / 'references').glob('*.md'))]
    for file in markdown:
        for target in re.findall(r'\]\(([^)]+)\)', file.read_text(encoding='utf8')):
            if '://' in target or target.startswith('#'):
                continue
            path = unquote(target.split('#', 1)[0]).strip('<>')
            if not (file.parent / path).is_file():
                errors.append(f'{file.relative_to(root)}: missing {target}')
    for file in (root / 'scripts').glob('*.py'):
        try:
            ast.parse(file.read_text(encoding='utf8'), filename=str(file))
        except SyntaxError as error:
            errors.append(str(error))
    data = registry()
    if len(data['blocks']) != data['block_count']:
        errors.append('Registry count mismatch')
    viewer = root / 'assets/viewer'
    import hashlib
    wheel=root/'assets/python/nbtlib-2.0.4-py3-none-any.whl'
    if not wheel.is_file() or hashlib.sha256(wheel.read_bytes()).hexdigest()!='38d571fbf2f7ebd640639461b47fc79919a8ea8e74633ffcc8aa6b2acfc9c889':errors.append('Pinned SNBT parser wheel is missing or changed')
    git_pin=root/'assets/git-runtime.json'
    if not git_pin.is_file() or len(json.loads(git_pin.read_text(encoding='utf8')).get('executable_sha256',''))!=64:errors.append('Pinned Git runtime metadata is invalid')
    package = json.loads((viewer / 'package.json').read_text())
    lock = json.loads((viewer / 'package-lock.json').read_text())
    for name, version in package['dependencies'].items():
        if lock['packages'][''].get('dependencies', {}).get(name) != version:
            errors.append(f'Viewer lockfile root drift: {name}')
        if lock['packages'].get('node_modules/' + name, {}).get('version') != version:
            errors.append(f'Viewer resolved version drift: {name}')
    print(json.dumps(dict(passed=not errors, markdown_files=len(markdown), registry_blocks=len(data['blocks']),
                          errors=errors), ensure_ascii=False, indent=2))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
