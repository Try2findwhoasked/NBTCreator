"""Rebuild original small grayscale motifs without external images or APIs.

Run from the repository root: mise exec -- python scripts/build-micro-patterns.py
Logical pixels represent half-block samples at the preferred wall size.
"""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / '.agents/skills/minecraft-nbt-modeler/assets/ornament-patterns'
CATALOG = ROOT / '.agents/skills/minecraft-nbt-modeler/tool-catalog.json'

# White = relief, black = recess. Deliberate broad strokes and open centres
# replace the hairlines and shading of large architectural reference images.
MOTIFS = {
    'micro-diamond': ('阶梯菱花', [
        '...##...', '..####..', '.######.', '########',
        '########', '.######.', '..####..', '...##...']),
    'micro-diamond-ring': ('镂空菱环', [
        '...##...', '..####..', '.######.', '###..###',
        '###..###', '.######.', '..####..', '...##...']),
    'micro-quatrefoil': ('四瓣连结', [
        '..####..', '..####..', '########', '###..###',
        '###..###', '########', '..####..', '..####..']),
    'micro-crosslet': ('十字花结', [
        '..##..', '..##..', '######', '######', '..##..', '..##..']),
    'micro-leaf': ('单叶与叶柄', [
        '...##...', '..####..', '.######.', '.######.',
        '########', '########', '.######.', '..####..',
        '...##...', '...##...', '...##...', '...##...']),
    'micro-bud': ('分枝花蕾', [
        '..####..', '.######.', '..####..', '...##...',
        '##.##.##', '########', '.######.', '..####..',
        '...##...', '...##...', '...##...', '...##...']),
    'micro-chevron': ('折线边带', [
        '##....##', '##....##', '###..###', '.######.',
        '..####..', '...##...']),
    'micro-key': ('方回钩', [
        '########', '########', '##......', '##......',
        '##..####', '##..####', '##....##', '########']),
    'micro-link': ('方环链扣', [
        '####', '#..#', '#..#', '####']),
    'micro-palmette': ('扇叶棕榈饰', [
        '.....##.....', '##..####..##', '###.####.###', '############',
        '.##########.', '..########..', '...######...', '....####....',
        '.....##.....', '.....##.....', '...######...', '...######...']),
    'micro-scroll': ('开口卷钩', [
        '..########..', '.##########.', '####....####', '###......###',
        '##...###..##', '##...#######', '##....#####.', '##..........',
        '###.........', '.####.......', '..##########', '...#########']),
    'micro-fleur-de-lis': ('百合莨苕花冠', [
        '.......##.......','......####......','.....##..##.....','..##.##..##.##..',
        '.######..######.','##...######...##','##..###..###..##','.#####....#####.',
        '..###..##..###..','...##.####.##...','....########....','...####..####...',
        '..###.####.###..','..##...##...##..','.....######.....','.....######.....']),
    'micro-rose-window': ('重瓣玫瑰窗花', [
        '....####....','..###..###..','.##.####.##.','.#.##..##.#.',
        '####.##.####','#.#.####.#.#','#.#.####.#.#','####.##.####',
        '.#.##..##.#.','.##.####.##.','..###..###..','....####....']),
    'micro-rosette': ('八向花章', [
        '....####....', '....####....', '..########..', '..########..',
        '#####..#####', '####....####', '####....####', '#####..#####',
        '..########..', '..########..', '....####....', '....####....']),
}


def recommended_sizes(key, size):
    if key=='micro-fleur-de-lis':return dict(wall=[8,8],column=[8,8],ceiling=[8,8])
    if key=='micro-rose-window':return dict(wall=[12,12],column=[12,12],ceiling=[12,12],floor=[12,12])
    floor = {'micro-diamond-ring': [8, 8], 'micro-quatrefoil': [8, 8],
             'micro-leaf': [6, 8], 'micro-bud': [6, 9],
             'micro-chevron': [8, 6], 'micro-link': [3, 3],
             'micro-palmette': [8, 8]}.get(key, size)
    return dict(wall=size, column=size,
                ceiling={'micro-link': [3, 3], 'micro-diamond-ring': [5, 5]}.get(key, size), floor=floor)


def raster(rows):
    assert len({len(row) for row in rows}) == 1
    assert all(set(row) <= {'.', '#'} for row in rows)
    image = Image.new('L', (len(rows[0]), len(rows)))
    image.putdata([255 if pixel == '#' else 0 for row in rows for pixel in row])
    # Nearest expansion keeps every logical half-cell exact and avoids gray
    # halos/alpha fringe. Source remains inspectable at a practical PNG size.
    return image.resize((image.width * 4, image.height * 4), Image.Resampling.NEAREST)


def update_catalog(value):
    count = 0
    if isinstance(value, dict):
        for key, child in value.items():
            if key == 'preset' and isinstance(child, dict) and 'four-petal' in child.get('enum', []):
                child['enum'] = [item for item in child['enum'] if item not in MOTIFS] + list(MOTIFS)
                count += 1
            else:
                count += update_catalog(child)
    elif isinstance(value, list):
        count += sum(update_catalog(child) for child in value)
    return count


def pillar_form_count(value):
    if isinstance(value,dict):
        properties=value.get('properties',{})
        return int('base_pattern' in properties and 'capital_pattern' in properties)+sum(pillar_form_count(child) for child in value.values())
    if isinstance(value,list):return sum(pillar_form_count(child) for child in value)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    manifest_path = LIBRARY / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf8'))
    for key, (label, rows) in MOTIFS.items():
        from io import BytesIO
        buffer = BytesIO()
        raster(rows).save(buffer, format='PNG')
        content = buffer.getvalue()
        entry = dict(file=key + '.png', sha256=hashlib.sha256(content).hexdigest(),
                     surfaces=list(recommended_sizes(key,[len(rows[0])//2,len(rows)//2])),
                     size_uv=recommended_sizes(key,[len(rows[0])//2,len(rows)//2])['wall'],
                     source='NBTCreator original micro mask', label=label,
                     microfit=dict(preferred=True, logical_pixels=[len(rows[0]), len(rows)],
                                   recommended_size_uv=recommended_sizes(key, [len(rows[0]) // 2, len(rows) // 2]),
                                   material='quartz_block',
                                   minimum_ink_overlap=0.8, maximum_coverage_error=0.15,
                                   size_policy='Per-surface tested sizes; wall and column use automatic stairs/slabs, floor stays flush'))
        if args.check:
            assert (LIBRARY / entry['file']).read_bytes() == content, key + ': raster drift'
            assert manifest.get(key) == entry, key + ': manifest drift'
        else:
            (LIBRARY / entry['file']).write_bytes(content)
            manifest[key] = entry
    catalog = json.loads(CATALOG.read_text(encoding='utf8'))
    original = json.dumps(catalog, ensure_ascii=False, indent=2) + '\n'
    count = update_catalog(catalog)
    architectural=sum('preset' in value.get('properties',{}) for tool in ('vault_compile','bay_compile')
        for key,value in catalog['agent_tools'].get(tool,{}).get('parameters',{}).get('properties',{}).items() if key.endswith('_pattern'))
    expected=6+2*pillar_form_count(catalog)+architectural
    assert count == expected, f'Unexpected number of preset schemas: {count}, expected {expected}'
    updated = json.dumps(catalog, ensure_ascii=False, indent=2) + '\n'
    if args.check:
        assert original == updated, 'preset schema drift'
    else:
        manifest_path.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf8'))
        # Preserve the catalogue bytes when its enums are already current.
        if original != updated:
            newline = '\r\n' if b'\r\n' in CATALOG.read_bytes() else '\n'
            CATALOG.write_bytes(updated.replace('\n', newline).encode('utf8'))
    print(json.dumps(dict(passed=True, motifs=len(MOTIFS), schemas=count, check=args.check)))


if __name__ == '__main__':
    main()
