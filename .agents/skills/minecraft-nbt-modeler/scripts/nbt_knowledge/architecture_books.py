"""Offline indexing and retrieval of explicitly selected architecture references."""

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from tempfile import TemporaryDirectory

from nbt_knowledge import tutorial_packs
from nbt_knowledge.text_search import chunks, han_bigrams

INDEX = 'architecture.sqlite'
TUTORIAL_INDEX_SCHEMA = 2
MAX_DOCUMENT_BYTES = 8*1024**2
MAX_MANIFEST_BYTES = 2*1024**2
MAX_LIBRARY_BYTES = 256*1024**2
IDENTIFIER = re.compile(r'[a-z0-9][a-z0-9_-]{0,63}')
WINDOWS_DEVICE = re.compile(r'(?:con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])(?:\..*)?$', re.I)
START = re.compile(r'^\*\*\*\s*start of', re.I)
END = re.compile(r'^\*\*\*\s*end of|^end of (?:the|this) project gutenberg', re.I)
HEADING = re.compile(r'^(?:chapter|book|part|section)\s+(?:[ivxlcdm]+|\d+)(?:\b|[.])', re.I)
PAGE_LIST = re.compile(r'\S\s{3,}(?:\d{1,4}|[ivxlcdm]{1,8})\s*$', re.I)
ALIASES = {
    '斗拱': ('bracket', 'brackets'), '屋檐': ('eaves', 'cornice'), '屏风': ('screen', 'partition'),
    '拉门': ('sliding screen', 'sliding doors', 'shoji', 'fusuma'),
    '隔扇': ('sliding screen', 'sliding doors', 'shoji', 'fusuma'),
    '榻榻米': ('mats', 'tatami'), '壁龛': ('alcove', 'niche', 'tokonoma'),
    '尖拱': ('pointed arch', 'pointed arches'), '飞扶壁': ('flying buttress', 'flying buttresses', 'arc boutant'),
    '交叉拱': ('groined vault', 'cross vault', 'intersecting vaults'),
    '肋拱': ('ribbed vault', 'rib vault', 'vaulting ribs'),
    '穹顶': ('dome', 'domes', 'cupola'), '鼓座': ('drum', 'tambour', 'pendentives'),
    '柱式': ('orders', 'doric', 'ionic', 'corinthian'), '柱头': ('capital', 'capitals'),
    '柱础': ('bases of the columns', 'base of the column', 'base of a column', 'column base', 'column bases'),
    '玫瑰窗': ('rose window', 'rose windows', 'wheel window', 'circular window', 'rosace'),
    '放射式': ('rayonnant', 'radial tracery', 'radiating tracery'),
    '花窗': ('tracery', 'stained glass'), '窗饰': ('tracery', 'window tracery'),
    '嵌纹': ('inlay', 'mosaic'), '纹样': ('ornament', 'pattern'),
    '院落': ('courtyard', 'court yard'), '庭院': ('courtyard', 'cloister'),
    '木构': ('timber', 'wood framing'), '庙塔': ('pagoda', 'temple tower'),
    '石窟': ('rock cut', 'cave temple'), '转角': ('corner', 'angle'),
    '中殿': ('nave', 'central aisle'), '中厅': ('nave', 'central aisle'),
    '侧廊': ('side aisle', 'aisles'), '后殿': ('apse', 'apsidal'),
    '横翼': ('transept', 'transepts'), '回廊': ('cloister', 'ambulatory'),
    '券廊': ('arcade', 'arcades'), '石柱': ('stone column', 'columns'),
    '柱束': ('clustered pier', 'clustered columns', 'clustered shafts'),
    '仿古柱': ('classical columns', 'classic orders', 'orders'),
    '挡水': ('dam', 'weir'), '排水': ('drainage', 'drain'),
    '悬挑': ('cantilever', 'overhang'), '基座': ('pedestal', 'plinth'),
    '拱顶推力': ('thrust of the vault','thrust of the main vault'),
    '三陇板': ('triglyphs','triglyph'), '间板': ('metopes','metope'),
}


def manifest(library):
    library = library.resolve()
    name = 'knowledge.json' if (library/'knowledge.json').is_file() else 'books.json'
    file = (library/name).resolve()
    if file.parent != library or file.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError('Invalid architecture library manifest path or size')
    raw = file.read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('Invalid architecture library manifest')
    books = data.get('documents' if name == 'knowledge.json' else 'books')
    if data.get('schema_version') != 1 or not isinstance(books, list) or not 1 <= len(books) <= 1000:
        raise ValueError('Architecture library has no supported book manifest')
    portable = name == 'knowledge.json'
    tutorial = None
    if portable:
        identifier, version = data.get('id'), data.get('version')
        if not isinstance(identifier, str) or not IDENTIFIER.fullmatch(identifier):
            raise ValueError('Invalid knowledge library id')
        if not isinstance(version, str) or not version.strip() or len(version) > 80:
            raise ValueError('Invalid knowledge library version')
        if data.get('package_kind') == tutorial_packs.KIND:
            if (library/name).is_symlink():
                raise ValueError('教程知识包清单不能使用符号链接')
            tutorial = tutorial_packs.release(tutorial_packs.read_manifest(raw))
    selected = {}
    paths = set()
    for book in books:
        if not isinstance(book, dict):
            raise ValueError('Invalid knowledge document')
        identifier = book['id']
        relative = book['file']
        if portable:
            valid_id = isinstance(identifier, str) and IDENTIFIER.fullmatch(identifier)
            valid_file = (isinstance(relative, str) and len(relative) <= 240 and not re.search(r'[<>:"\\|?*\x00-\x1f]',relative)
                          and all(part and not part.endswith((' ','.')) and not WINDOWS_DEVICE.fullmatch(part)
                                  for part in relative.split('/'))
                          and Path(relative).suffix.lower() in ('.txt', '.md'))
        else:
            valid_id = type(identifier) is int and identifier > 0
            valid_file = relative == f'pg{identifier}.txt'
        if not valid_id or not valid_file or identifier in selected or relative.casefold() in paths:
            raise ValueError('Invalid book id or source filename')
        if (type(book.get('bytes')) is not int or not 1 <= book['bytes'] <= MAX_DOCUMENT_BYTES
            or not re.fullmatch(r'[0-9a-f]{64}', str(book.get('sha256', '')))
            or not isinstance(book.get('title'), str) or not book['title'].strip() or len(book['title']) > 250):
            raise ValueError('Invalid knowledge document metadata')
        normalized = {key: value for key, value in book.items() if key != 'tutorial'}
        for key in ('author', 'source', 'edition', 'region', 'source_type', 'language', 'license'):
            value = book.get(key, book.get('rights', '') if key == 'license' else '')
            if not isinstance(value, str) or len(value) > 1000:
                raise ValueError('Invalid knowledge document '+key)
            normalized[key] = value
        styles = book.get('styles', [])
        if not isinstance(styles, list) or len(styles) > 50 or any(not isinstance(style, str) or len(style) > 64 for style in styles):
            raise ValueError('Invalid knowledge style tags')
        if 'year' in book and (type(book['year']) is not int or not -9999 <= book['year'] <= 9999):
            raise ValueError('Invalid knowledge document year')
        normalized['styles'] = styles
        normalized['library_id'] = data['id'] if portable else 'architecture-books'
        normalized['version'] = data['version'] if portable else ''
        if tutorial:
            normalized['tutorial'] = tutorial_packs.document_metadata(normalized, tutorial)
        paths.add(relative.casefold())
        selected[identifier] = normalized
    if sum(book['bytes'] for book in selected.values()) > MAX_LIBRARY_BYTES:
        raise ValueError('Architecture library exceeds the indexing size limit')
    if tutorial:
        tutorial_packs.check_links(selected.values())
    return selected, hashlib.sha256(raw).hexdigest()


def source(library, book):
    library = library.resolve()
    declared = library/book['file']
    file = declared.resolve()
    if not file.is_relative_to(library) or ('tutorial' in book and file != declared):
        raise ValueError('Book resolves outside the selected library')
    if not 1 <= book['bytes'] <= MAX_DOCUMENT_BYTES or file.stat().st_size != book['bytes']:
        raise ValueError('Book size changed: '+book['file'])
    with file.open('rb') as stream:
        raw = stream.read(book['bytes']+1)
    if len(raw)!=book['bytes'] or b'\x00' in raw or hashlib.sha256(raw).hexdigest() != book['sha256']:
        raise ValueError('Book hash changed: '+book['file'])
    return file, raw.decode('utf-8-sig')


def sections(book, text):
    lines = text.splitlines()
    if 'tutorial' in book:
        start = tutorial_packs.body_start(lines)
        marked = lines[start:]
        if not any(line.strip() for line in marked):
            raise ValueError('教程卡正文为空')
    else:
        start = next((i+1 for i,line in enumerate(lines) if START.match(line.strip())), 0)
        end = next((i for i in range(start,len(lines)) if END.match(lines[i].strip())), len(lines))
        marked = ['# '+line.strip() if HEADING.match(line.strip()) and len(line)<120 else line
                  for line in lines[start:end]]
    doc = dict(id=str(book['id']), label=book['title'], sha256=book['sha256'],
               locator=book['file'], text='\n'.join(marked))
    for piece in chunks(doc):
        lo, hi = start+piece['line_start'], start+piece['line_end']
        passage = lines[lo-1:hi]
        populated = [line for line in passage if line.strip()]
        page_entries = sum(bool(PAGE_LIST.search(line)) for line in populated)
        if 'tutorial' not in book and page_entries >= 2 and page_entries * 2 >= len(populated):
            continue
        original = '\n'.join(passage)
        yield (book['id'], lo, hi, piece['heading'], original[:2600], len(original)>2600)


def build(library, index=None):
    library = library.resolve()
    index = index or library/INDEX
    books, receipt = manifest(library)
    count = 0
    index.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=index.parent) as tmp:
        file = Path(tmp)/INDEX
        with closing(sqlite3.connect(file)) as db, db:
            db.execute('CREATE TABLE meta (manifest_sha256 TEXT NOT NULL, tutorial_schema INTEGER NOT NULL)')
            db.execute('INSERT INTO meta VALUES (?, ?)', (receipt, TUTORIAL_INDEX_SCHEMA))
            db.execute('CREATE VIRTUAL TABLE passages USING fts5(book UNINDEXED, first UNINDEXED, last UNINDEXED, heading, text, han)')
            for book in books.values():
                _, original = source(library, book)
                title = book['title'] if 'tutorial' in book else ''
                for identifier, first, last, heading, passage, _ in sections(book, original):
                    terms = ' '.join(han_bigrams(' '.join((title, heading, passage))))
                    db.execute('INSERT INTO passages VALUES (?,?,?,?,?,?)',
                               (identifier, first, last, heading, passage, (title+' '+terms).strip()))
                    count += 1
        file.replace(index)
    return dict(books=len(books), passages=count, manifest_sha256=receipt)


def expression(query, *, extra_aliases=None, include_numbers=False):
    native = re.findall(r'[^\W\d_\u3400-\u9fff]+', query.casefold())
    phrases = [phrase for aliases in (ALIASES,extra_aliases or {})
               for term,values in aliases.items() if term in query for phrase in values]
    if '槽' in query and any(term in query for term in ('隔扇','拉门','移门')):
        phrases[:0] = ['grooves in the floor','sliding screens which run','and overhead']
    english = [' '.join(native)] if 1 < len(native) <= 5 else []
    english.extend(phrases)
    if include_numbers:
        english.extend(re.findall(r'(?<!\d)\d{2,6}(?!\d)',query))
    english.extend(word for word in native if len(word)>2)
    english = list(dict.fromkeys(english))[:24]
    han = list(dict.fromkeys(han_bigrams(query)))[:24]
    return ' OR '.join('"'+term+'"' for term in english+han)


def describe(book):
    return {key: book[key] for key in ('title','author','styles','region','edition','source_type','source','sha256','language','license','year') if key in book}


def index_receipt(db, tutorial=False):
    fields = 'manifest_sha256, tutorial_schema' if tutorial else 'manifest_sha256'
    row = db.execute(f'SELECT {fields} FROM meta').fetchone()
    if not row or (tutorial and row[1] != TUTORIAL_INDEX_SCHEMA):
        raise sqlite3.DatabaseError('Missing or outdated knowledge index metadata')
    return row[0]


def index_manifest(index, *, tutorial=False):
    with closing(sqlite3.connect(index.as_uri()+'?mode=ro', uri=True)) as db:
        return index_receipt(db, tutorial)


def search(library, query, style=None, limit=8, *, index=None, region=None, year=None, catalog=None):
    library = library.resolve()
    if not 1 <= limit <= 20 or not 1 <= len(query.strip()) <= 300:
        raise ValueError('Query must have 1–300 characters, with 1–20 results')
    books, receipt = catalog if catalog is not None else manifest(library)
    tutorial = 'tutorial' in next(iter(books.values()))
    eligible = [identifier for identifier,book in books.items()
                if (not style or style.casefold() in (tag.casefold() for tag in book['styles']))
                and (not region or region.casefold() in book['region'].casefold())
                and (not year or 'year' in book and year[0] <= book['year'] <= year[1])]
    match = expression(query)
    hits, errors = [], {}
    if eligible and match:
        filters = ','.join('?' for _ in eligible)
        with closing(sqlite3.connect((index or library/INDEX).as_uri()+'?mode=ro', uri=True)) as db:
            if index_receipt(db, tutorial) != receipt:
                raise ValueError('Book manifest changed; rebuild the offline index')
            rows = db.execute(f'''SELECT book, first, last, heading, text FROM passages
                                 WHERE passages MATCH ? AND book IN ({filters})
                                 ORDER BY bm25(passages, 0, 0, 0, 2, 1, 1), rowid LIMIT ?''',
                              (match, *eligible, -1 if tutorial else limit))
            verified = {}
            for identifier,first,last,heading,text in rows:
                book = books[identifier]
                if identifier not in verified:
                    try:
                        _, original = source(library, book)
                        verified[identifier] = original.splitlines()
                    except (OSError, ValueError):
                        if 'tutorial' not in book:
                            raise
                        verified[identifier] = None
                        errors[identifier] = '教程卡原文已变化或不可用，请核对发行包'
                lines = verified[identifier]
                if lines is None:
                    continue
                if not 1 <= first <= last <= len(lines):
                    raise ValueError('Indexed passage differs from its source; rebuild the offline index')
                original = '\n'.join(lines[first-1:last])
                if text != original[:2600]:
                    raise ValueError('Indexed passage differs from its source; rebuild the offline index')
                hits.append(dict(book=identifier, **describe(book), heading=heading, line_start=first,
                                 line_end=last, text=text, clipped=len(original)>2600))
                if len(hits) == limit:
                    break
    return dict(style=style, hits=hits, evidence_type='historical_reference', manifest_sha256=receipt,
                **({'document_errors': errors} if errors else {}))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('build')
    query = commands.add_parser('search')
    query.add_argument('query')
    query.add_argument('--style')
    query.add_argument('--limit', type=int, default=8)
    original = commands.add_parser('source')
    original.add_argument('--book', type=int, required=True)
    args = parser.parse_args(argv)
    library = args.library.resolve()
    try:
        if args.action == 'build':
            result = build(library)
        elif args.action == 'search':
            result = search(library, args.query, args.style, args.limit)
        else:
            book = manifest(library)[0][args.book]
            file, _ = source(library, book)
            result = dict(book, path=str(file))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, sqlite3.Error, KeyError, TypeError) as error:
        print(json.dumps(dict(error=str(error)), ensure_ascii=False))
        return 1
