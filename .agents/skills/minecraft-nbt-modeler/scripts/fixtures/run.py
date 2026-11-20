"""Run a portable synthetic fixture from the caller's workspace."""
from pathlib import Path
import runpy
import sys


def main():
    directory = Path(__file__).resolve().parent
    suites = {path.name: path for path in directory.glob('check_*_fixtures.py')}
    name = sys.argv[1] if len(sys.argv) > 1 else ''
    if name not in suites:
        raise SystemExit(f'Usage: {Path(__file__).name} <fixture> [args]\nFixtures: {", ".join(sorted(suites))}')
    sys.argv.pop(1)
    sys.path.insert(0, str(directory.parent))
    runpy.run_path(str(suites[name]), run_name='__main__')


if __name__ == '__main__':
    main()
