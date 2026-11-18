"""Offline indexing and retrieval of an explicitly selected architecture book library."""

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from tempfile import TemporaryDirectory

from nbt_text_search import chunks

INDEX = 'architecture.sqlite'
START = re.compile(r'^\*\*\*\s*start of', re.I)
END = re.compile(r'^\*\*\*\s*end of|^end of (?:the|this) project gutenberg', re.I)
HEADING = re.compile(r'^(?:chapter|book|part|section)\s+(?:[ivxlcdm]+|\d+)(?:\b|[.])', re.I)
PAGE_LIST = re.compile(r'\S\s{3,}(?:\d{1,4}|[ivxlcdm]{1,8})\s*$', re.I)
ALIASES = {
    '斗拱': 'bracket timber', '屋檐': 'eaves cornice', '屏风': 'screen partition',
    '拉门': 'sliding screen shoji fusuma', '尖拱': 'pointed arch', '飞扶壁': 'flying buttress',
    '穹顶': 'dome vault', '柱式': 'column order', '柱头': 'capital column',
    '窗饰': 'tracery window', '嵌纹': 'inlay mosaic', '纹样': 'ornament pattern',
    '院落': 'courtyard court', '庭院': 'courtyard garden', '木构': 'timber wood framing',
    '庙塔': 'temple tower', '石窟': 'rock cut cave', '转角': 'corner angle',
}


def manifest(library):
    raw = (library/'books.json').read_bytes()
    data = json.loads(raw)
    books = data.get('books')
    if data.get('schema_version') != 1 or not isinstance(books, list) or not 1 <= len(books) <= 1000:
        raise ValueError('Architecture library has no supported book manifest')
    selected = {}
    for book in books:
        identifier = book['id']
        if type(identifier) is not int or identifier in selected or book['file'] != f'pg{identifier}.txt':
            raise ValueError('Invalid book id or source filename')
        selected[identifier] = book
    return selected, hashlib.sha256(raw).hexdigest()


def source(library, book):
    library = library.resolve()
    file = (library/book['file']).resolve()
    if not file.is_relative_to(library):
        raise ValueError('Book resolves outside the selected library')
    if not 1 <= book['bytes'] <= 8*1024**2 or file.stat().st_size != book['bytes']:
        raise ValueError('Book size changed: '+book['file'])
    raw = file.read_bytes()
    if hashlib.sha256(raw).hexdigest() != book['sha256']:
        raise ValueError('Book hash changed: '+book['file'])
    return file, raw.decode('utf-8-sig')


def sections(book, text):
    lines = text.splitlines()
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
        if page_entries >= 2 and page_entries * 2 >= len(populated):
            continue
        yield (book['id'], lo, hi, piece['heading'], '\n'.join(passage)[:2600])


def build(library):
    library = library.resolve()
    books, receipt = manifest(library)
    count = 0
    with TemporaryDirectory(dir=library) as tmp:
        file = Path(tmp)/INDEX
        with closing(sqlite3.connect(file)) as db, db:
            db.execute('CREATE TABLE meta (manifest_sha256 TEXT NOT NULL)')
            db.execute('INSERT INTO meta VALUES (?)', (receipt,))
            db.execute('CREATE VIRTUAL TABLE passages USING fts5(book UNINDEXED, first UNINDEXED, last UNINDEXED, heading, text)')
            for book in books.values():
                _, original = source(library, book)
                entries = list(sections(book, original))
                db.executemany('INSERT INTO passages VALUES (?,?,?,?,?)', entries)
                count += len(entries)
        file.replace(library/INDEX)
    return dict(books=len(books), passages=count, manifest_sha256=receipt)


def expression(query):
    aliases = ' '.join(value for key,value in ALIASES.items() if key in query)
    terms = list(dict.fromkeys(re.findall(r'[^\W\d_]+', query.lower()+' '+aliases)))
    words = [term for term in terms if len(term)>2 or any('\u3400' <= c <= '\u9fff' for c in term)]
    return ' OR '.join('"'+term+'"' for term in words[:24])


def search(library, query, style=None, limit=8):
    library = library.resolve()
    if not 1 <= limit <= 20 or not 1 <= len(query.strip()) <= 300:
        raise ValueError('Query must have 1–300 characters, with 1–20 results')
    books, receipt = manifest(library)
    eligible = [identifier for identifier,book in books.items() if not style or style in book['styles']]
    match = expression(query)
    hits = []
    if eligible and match:
        filters = ','.join('?' for _ in eligible)
        with closing(sqlite3.connect((library/INDEX).as_uri()+'?mode=ro', uri=True)) as db:
            if db.execute('SELECT manifest_sha256 FROM meta').fetchone() != (receipt,):
                raise ValueError('Book manifest changed; rebuild the offline index')
            rows = db.execute(f'''SELECT book, first, last, heading, text FROM passages
                                 WHERE passages MATCH ? AND book IN ({filters})
                                 ORDER BY bm25(passages, 0, 0, 0, 2, 1), rowid LIMIT ?''',
                              (match, *eligible, limit))
            verified = {}
            for identifier,first,last,heading,text in rows:
                book = books[identifier]
                if identifier not in verified:
                    _, original = source(library, book)
                    verified[identifier] = original.splitlines()
                lines = verified[identifier]
                if not 1 <= first <= last <= len(lines) or text != '\n'.join(lines[first-1:last])[:2600]:
                    raise ValueError('Indexed passage differs from its source; rebuild the offline index')
                hits.append(dict(book=identifier, title=book['title'], author=book['author'],
                                 styles=book['styles'], region=book['region'], edition=book['edition'],
                                 source_type=book['source_type'], source=book['source'], sha256=book['sha256'],
                                 heading=heading, line_start=first, line_end=last, text=text))
    return dict(style=style, hits=hits, evidence_type='historical_reference')


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


if __name__ == '__main__':
    raise SystemExit(main())
