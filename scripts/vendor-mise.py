"""Bundle the pinned upstream Windows x64 mise executable."""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify(file, expected):
    with file.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
            raise ValueError('mise executable SHA256 mismatch: ' + file.name)


def vendor(destination, cache):
    lock = json.loads((ROOT/'config/portable-runtime.json').read_text(encoding='utf8'))['mise']
    cache.mkdir(parents=True, exist_ok=True)
    file = cache/Path(lock['url']).name
    if not file.is_file():
        with tempfile.TemporaryDirectory(dir=cache) as staging:
            candidate = Path(staging)/file.name
            request = urllib.request.Request(lock['url'], headers={'User-Agent':'NBTCreator-build'})
            with urllib.request.urlopen(request, timeout=120) as source, candidate.open('xb') as target:
                shutil.copyfileobj(source, target)
            verify(candidate, lock['sha256'])
            candidate.replace(file)
    verify(file, lock['sha256'])
    destination.mkdir(parents=True, exist_ok=False)
    executable = destination/'mise.exe'
    shutil.copyfile(file, executable)
    shutil.copyfile(ROOT/'config/licenses/mise-LICENSE.txt', destination/'LICENSE.txt')
    version = subprocess.check_output([str(executable.resolve()), '--no-config', 'version'],
                                      encoding='utf8', timeout=30).strip()
    if version.split()[:2] != [lock['version'], 'windows-x64']:
        raise ValueError('Unexpected bundled mise version: ' + version)
    print(json.dumps(dict(version=version, executable=str(executable), sha256=lock['sha256'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    args = parser.parse_args()
    vendor(args.destination, args.cache)
