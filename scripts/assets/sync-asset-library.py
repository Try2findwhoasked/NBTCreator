"""Import a verified release snapshot; never reads a sibling repository implicitly."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_assets.libraries import BUNDLED, bundled, manifest, payload, fetch, child_location, atomic, encode, digest, MAX_MANIFEST, MAX_ASSET

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path)
parser.add_argument('--check', action='store_true')
args = parser.parse_args()
if args.check:
    data, assets = bundled()
else:
    if args.source is None: parser.error('--source is required for snapshot import')
    source = args.source.resolve()
    if source.is_dir(): source /= 'library.json'
    raw = fetch(str(source), MAX_MANIFEST); data = manifest(raw)
    if data['id'] != 'nbtcreator.modular': raise ValueError('Bundled pack must be nbtcreator.modular')
    contents = [(entry, fetch(child_location(str(source), entry['path']), MAX_ASSET)) for entry in data['assets']]
    for entry, content in contents: payload(entry, content)
    # Validation finishes before any snapshot file is replaced. Remove no user assets.
    if not BUNDLED.resolve().is_relative_to(ROOT): raise ValueError('Snapshot must stay inside the application source root')
    BUNDLED.mkdir(parents=True, exist_ok=True)
    for entry, content in contents:
        target = (BUNDLED / entry['path']).resolve()
        if not target.is_relative_to(BUNDLED.resolve()): raise ValueError('Snapshot path escapes destination')
        atomic(target, content)
    atomic(BUNDLED / 'library.json', raw)
    atomic(BUNDLED / 'registry.json', encode(dict(schema_version=1, kind='nbtcreator.asset-registry', name='NBTCreator 拓展库清单', libraries=[dict(
        id=data['id'], name=data['name'], version=data['version'], path='library.json', manifest_sha256=digest(raw))])))
    assets = contents
print(json.dumps(dict(passed=True, library=data['id'], version=data['version'], assets=len(assets))))
