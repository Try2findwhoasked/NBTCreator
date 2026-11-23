"""Build original architectural stencil masks. Run with mise exec -- python.

These are block-scale interpretations, not copies of reference photographs.
"""
import argparse
import hashlib
import json
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / '.agents/skills/minecraft-nbt-modeler/assets/ornament-patterns'
CATALOG = ROOT / '.agents/skills/minecraft-nbt-modeler/tool-catalog.json'


def draw_pattern(kind):
    image = Image.new('L', (32, 32), 0)
    d = ImageDraw.Draw(image)
    if kind == 'roman-coffer':
        for a, b in ((1, 30), (4, 27), (7, 24)):
            d.rectangle((a, a, b, b), outline=255, width=1)
        d.polygon([(15, 11), (20, 15), (16, 20), (11, 16)], fill=255)
    elif kind == 'byzantine-cross-mosaic':
        d.ellipse((2, 2, 29, 29), outline=255, width=2)
        d.ellipse((6, 6, 25, 25), outline=255, width=1)
        d.rectangle((14, 8, 17, 23), fill=255)
        d.rectangle((8, 14, 23, 17), fill=255)
        for x, y in ((3, 3), (27, 3), (3, 27), (27, 27)):
            d.rectangle((x-1, y-1, x+1, y+1), fill=255)
    elif kind == 'ottoman-eight-point-star':
        d.polygon([(16, 1), (20, 7), (27, 5), (25, 12), (31, 16), (25, 20),
                   (27, 27), (20, 25), (16, 31), (12, 25), (5, 27), (7, 20),
                   (1, 16), (7, 12), (5, 5), (12, 7)], outline=255, width=2)
        d.polygon([(16, 8), (24, 16), (16, 24), (8, 16)], outline=255, width=1)
        d.rectangle((14, 14, 18, 18), fill=255)
    elif kind == 'egyptian-lotus-band':
        d.line([(0, 28), (31, 28)], fill=255, width=2)
        for x in (8, 24):
            d.line([(x, 27), (x, 10)], fill=255, width=2)
            d.polygon([(x, 5), (x-3, 12), (x, 18), (x+3, 12)], outline=255, width=2)
            d.line([(x-6, 11), (x-5, 17), (x, 21), (x+5, 17), (x+6, 11)], fill=255, width=2)
    elif kind == 'chinese-window-lattice':
        for a, b in ((0, 31), (3, 28)):
            d.rectangle((a, a, b, b), outline=255, width=2)
        d.line([(0, 15), (31, 15)], fill=255, width=2)
        d.line([(15, 0), (15, 31)], fill=255, width=2)
        d.polygon([(15, 6), (25, 15), (16, 25), (6, 16)], outline=255, width=2)
    elif kind == 'japanese-asanoha-lattice':
        points = [(16, 1), (29, 8), (29, 23), (16, 30), (3, 23), (3, 8)]
        d.polygon(points, outline=255, width=2)
        for point in points:
            d.line([(16, 16), point], fill=255, width=2)
        d.ellipse((13, 13, 18, 18), fill=255)
    elif kind == 'art-deco-sunburst':
        d.line([(1, 31), (1, 20), (6, 20), (6, 14), (11, 14), (11, 8),
                (16, 8), (16, 2), (20, 2)], fill=255, width=2)
        for x in (4, 9, 14, 19, 24, 29):
            d.line([(16, 30), (x, 12 if x in (14, 19) else 18)], fill=255, width=2)
        d.line([(0, 31), (31, 31)], fill=255, width=2)
    elif kind == 'gothic-pointed-tracery':
        d.line([(3, 31), (3, 14), (4, 11), (16, 1), (27, 11), (28, 14), (28, 31)], fill=255, width=2)
        for x in (10, 21):
            d.line([(x-4, 31), (x-4, 19), (x, 14), (x+4, 19), (x+4, 31)], fill=255, width=1)
        d.ellipse((12, 6, 19, 13), outline=255, width=1)
        d.line([(3, 30), (28, 30)], fill=255, width=2)
    else:
        raise ValueError(kind)
    return image


PATTERNS = {
    'roman-coffer': ('罗马层框藻井', ['ceiling', 'wall']),
    'byzantine-cross-mosaic': ('拜占庭十字马赛克', ['wall', 'ceiling', 'floor']),
    'ottoman-eight-point-star': ('奥斯曼八角星纹', ['wall', 'ceiling', 'floor']),
    'egyptian-lotus-band': ('埃及莲花边带', ['wall', 'column', 'cylinder']),
    'chinese-window-lattice': ('中式菱心窗格', ['wall', 'ceiling']),
    'japanese-asanoha-lattice': ('日式麻叶格纹', ['wall', 'ceiling', 'floor']),
    'art-deco-sunburst': ('装饰艺术日芒纹', ['wall', 'ceiling']),
    'gothic-pointed-tracery': ('哥特尖拱窗棂', ['wall']),
}


def update_catalog(value):
    count = 0
    if isinstance(value, dict):
        for key, child in value.items():
            if key == 'preset' and isinstance(child, dict) and 'four-petal' in child.get('enum', []):
                entries = [entry for entry in child['enum'] if entry not in PATTERNS]
                index = next((i for i, entry in enumerate(entries) if entry.startswith('micro-')), len(entries))
                child['enum'] = entries[:index] + list(PATTERNS) + entries[index:]
                count += 1
            else:
                count += update_catalog(child)
    elif isinstance(value, list):
        count += sum(update_catalog(child) for child in value)
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    manifest_path = LIBRARY / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf8'))
    for key, (label, surfaces) in PATTERNS.items():
        buffer = BytesIO()
        draw_pattern(key).save(buffer, format='PNG')
        content = buffer.getvalue()
        entry = dict(file=key + '.png', sha256=hashlib.sha256(content).hexdigest(),
                     surfaces=surfaces, size_uv=[32, 32],
                     source='NBTCreator original architectural stencil', label=label)
        if args.check:
            assert (LIBRARY / entry['file']).read_bytes() == content, key + ': raster drift'
            assert manifest.get(key) == entry, key + ': manifest drift'
        else:
            (LIBRARY / entry['file']).write_bytes(content)
            manifest[key] = entry
    catalog = json.loads(CATALOG.read_text(encoding='utf8'))
    original = json.dumps(catalog, ensure_ascii=False, indent=2) + '\n'
    count = update_catalog(catalog)
    assert count >= 6, f'Unexpected preset schema count: {count}'
    updated = json.dumps(catalog, ensure_ascii=False, indent=2) + '\n'
    if args.check:
        assert original == updated, 'preset schema drift'
    else:
        manifest_path.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf8'))
        if original != updated:
            newline = '\r\n' if b'\r\n' in CATALOG.read_bytes() else '\n'
            CATALOG.write_bytes(updated.replace('\n', newline).encode('utf8'))
    print(json.dumps(dict(passed=True, patterns=len(PATTERNS), schemas=count, check=args.check)))


if __name__ == '__main__':
    main()
