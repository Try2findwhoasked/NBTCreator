"""Describe the active exposed engine for task scripts, without guessing an install path."""
import argparse
import json
from pathlib import Path
import sys


def paths(workspace=None):
    engine = Path(__file__).resolve().parents[1]
    manifest = engine/'runtime-manifest.json'
    return dict(schema_version=1, workspace=str(Path(workspace or Path.cwd()).resolve()),
                engine=str(engine), scripts=str(engine/'scripts'), references=str(engine/'references'),
                viewer=str(engine/'assets/viewer'), python=sys.executable,
                runtime_bundle_sha256=json.loads(manifest.read_text(encoding='utf8')).get('bundle_sha256') if manifest.is_file() else None,
                commands=json.loads((engine/'tool-catalog.json').read_text(encoding='utf8'))['commands'],
                note='Read-only discovery. Import task APIs from scripts; keep generated files outside this engine.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(paths(args.workspace), ensure_ascii=False))
