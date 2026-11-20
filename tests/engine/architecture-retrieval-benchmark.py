"""Score annotated queries on the optional historical corpus, without network access."""

import argparse
import json
from pathlib import Path
import re
import statistics
import sys
import tempfile
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_retrieval import dispatch


# Each case lists an eligible style, a query, and text that must actually occur in the hit.
CASES = (
    ('gothic', '飞扶壁 受力', r'flying buttress|arc.boutant'),
    ('gothic', '尖拱', r'pointed arch'),
    ('gothic', '放射式 玫瑰窗', r'rose.window|rayonnant|wheel.window'),
    ('gothic', '肋拱', r'rib(?:bed)? vault|vaulting.ribs|ribs of the vault'),
    ('gothic', '交叉拱', r'groined vault|cross vault|intersecting vault'),
    ('gothic', '中殿', r'nave'),
    ('gothic', '侧廊', r'side.aisle|\baisles\b'),
    ('gothic', '后殿', r'\bapse\b|apsidal'),
    ('gothic', '横翼', r'transept'),
    ('gothic', '柱束', r'clustered (?:pier|column|shaft)'),
    ('gothic', '花窗 玻璃', r'stained.glass|tracery'),
    ('gothic', 'flying buttresses at the nave', r'flying buttress'),
    ('gothic', 'pointed arch 尖拱', r'pointed arch'),
    ('classical', '柱式 多立克', r'doric order|orders of architecture'),
    ('classical', '柱头 科林斯', r'(?:corinthian.{0,90}capital|capital.{0,90}corinthian)'),
    ('classical', '柱础', r'bases? of (?:the|a)\s+columns?|column.bases?'),
    ('classical', 'Doric triglyph', r'triglyph'),
    ('classical', 'Ionic volute', r'volute'),
    ('classical', '仿古柱 column orders', r'orders of architecture|columnal|orders of columns|classic(?:al)? orders'),
    ('byzantine', '穹顶 鼓座', r'pendentive|\bdome\b'),
    ('byzantine', 'dome on pendentives', r'pendentive'),
    ('venetian', '石柱 柱头 capital', r'capital'),
    ('japanese', '榻榻米', r'tatami|floor.mats|mats upon the floor'),
    ('japanese', '拉门 隔扇', r'shoji|fusuma|sliding (?:door|screen)'),
    ('japanese', '壁龛', r'tokonoma|toko.no.ma|alcove'),
    ('japanese', '屋檐 悬挑', r'eaves|overhang'),
    ('japanese', 'Japanese verandah', r'verandah'),
    ('south-asian', '石窟', r'rock.cut|cave.temple|cut out of the rock'),
    ('south-asian', '庙塔 pagoda', r'pagoda'),
    ('ornament', '嵌纹 mosaic', r'inlay|mosaic'),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory() as temp:
        workspace = Path(temp).resolve()
        indexed = dispatch(workspace, 'library', dict(workflow='prompt', action='add', path=str(arguments.library.resolve())))
        measured, report = [], []
        for style, query, evidence in CASES:
            start = perf_counter()
            result = dispatch(workspace, 'search', dict(workflow='prompt', query=query, filters={'style':style}, limit=5))
            measured.append((perf_counter()-start)*1000)
            rank = next((rank for rank,hit in enumerate(result['knowledge'],1)
                         if re.search(evidence, hit['text'], re.I|re.S)), None)
            report.append(dict(query=query,style=style,rank=rank))
        empty = dispatch(workspace, 'search', dict(workflow='prompt', query='neutrino hadron baryogenesis', limit=5))
    matched = sum(item['rank'] is not None for item in report)
    misses = [item for item in report if item['rank'] is None]
    print(json.dumps(dict(books=indexed['documents'],passages=indexed['passages'],passed_at_5=matched,
                         cases=len(CASES),no_match_passed=not empty['knowledge'],
                         median_ms=round(statistics.median(measured),1),
                         p95_ms=round(statistics.quantiles(measured,n=20)[18],1),misses=misses,
                         details=report),ensure_ascii=False))
    return 0 if matched>=24 and not empty['knowledge'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
