"""Explicit, workspace-local collection of citable web passages."""

from contextlib import closing
import sqlite3

from nbt_architecture_knowledge import expression
from nbt_knowledge.text_search import han_bigrams
from .public_web import WEB_TERMS
from .web_research import ID, read, raw_json, sha

SCHEMA = '''CREATE VIRTUAL TABLE IF NOT EXISTS saved_web USING fts5(
    workflow UNINDEXED, entry UNINDEXED, identifier UNINDEXED, title, heading, text, han
)'''
UNAVAILABLE = '无法读取网页收藏索引，其他资料仍可检索'


def index_path(workspace):
    root = (workspace/'.nbtcreator/retrieval/web').resolve()
    path = (root/'saved.sqlite').resolve()
    if not root.is_relative_to(workspace) or not path.is_relative_to(root):
        raise ValueError('网页收藏索引越过工作区')
    return path


def entry_key(item):
    return sha(raw_json([item['locator'],item['heading'],item['passage_sha256']]))


def indexed_text(item):
    title = ' '.join((item['label'],item['bibliography']['publisher']))
    heading,text = item['heading'],item['text']
    return title,heading,text,' '.join(han_bigrams(' '.join((title,heading,text))))


def load_rows(workspace, flow, limit, query=None, offset=0):
    try:
        path = index_path(workspace)
        if not path.is_file():
            return [],[],False
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=2)) as db:
            if query is None:
                rows = db.execute('SELECT entry, identifier, title, heading, text, han FROM saved_web WHERE workflow=? ORDER BY rowid DESC LIMIT ? OFFSET ?',
                                  (flow,limit+1,offset)).fetchall()
            else:
                match = expression(query.strip()[:300],extra_aliases=WEB_TERMS,include_numbers=True)
                if not match:
                    return [],[],False
                rows = db.execute('''SELECT entry, identifier, title, heading, text, han FROM saved_web
                    WHERE saved_web MATCH ? AND workflow=?
                    ORDER BY bm25(saved_web,0,0,0,2,2,1,1), rowid DESC LIMIT ?''',
                    (match,flow,limit*2)).fetchall()
    except (OSError,ValueError,sqlite3.Error):
        return [],[dict(message=UNAVAILABLE)],False
    items,errors = [],[]
    for key,identifier,*indexed in rows[:limit] if query is None else rows:
        try:
            item = read(workspace,flow,identifier)
            if entry_key(item)!=key or tuple(indexed)!=indexed_text(item):
                raise ValueError('网页证据编号与收藏不对应')
            items.append(dict(item,saved=True))
            if len(items)>=limit:
                break
        except (ValueError,KeyError,TypeError):
            errors.append(dict(id=identifier,message='一条网页收藏的证据已丢失或被修改'))
    return items,errors,query is None and len(rows)>limit


def search(workspace, flow, query, limit):
    items,errors,_ = load_rows(workspace,flow,limit,query=query)
    return items,errors


def mark_research(workspace, flow, items):
    if not items:
        return []
    try:
        path = index_path(workspace)
        if not path.is_file():
            return items
        keys = [entry_key(item) for item in items]
        slots = ','.join('?' for _ in keys)
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=2)) as db:
            saved = dict(db.execute(f'SELECT entry, identifier FROM saved_web WHERE workflow=? AND entry IN ({slots})', (flow,*keys)))
        return [dict(item,saved=True,saved_id=saved[key]) if key in saved else item for item,key in zip(items,keys)]
    except (OSError,ValueError,sqlite3.Error):
        return items


def manage(workspace, flow, request):
    action = request.get('action','list')
    if action=='list':
        if set(request)-{'workflow','action','limit','offset'}:
            raise ValueError('收藏列表仅支持 limit 和 offset')
        limit,offset = request.get('limit',12),request.get('offset',0)
        if type(limit) is not int or not 1<=limit<=32 or type(offset) is not int or offset<0 or offset>2147483647:
            raise ValueError('收藏列表需要1～32项及有效的偏移量')
        items,errors,has_more = load_rows(workspace,flow,limit,offset=offset)
        return dict(workflow=flow,knowledge=items,errors=errors,next_offset=offset+limit if has_more else None)

    identifier = request.get('id')
    if (action not in ('add','remove') or set(request)-{'workflow','action','id'}
        or not isinstance(identifier,str) or not identifier.startswith('web:') or not ID.fullmatch(identifier[4:])):
        raise ValueError('请指定 add 或 remove 及有效的网页证据编号')
    path = index_path(workspace)
    if action=='remove' and not path.is_file():
        return dict(id=identifier,saved=False)
    try:
        item = read(workspace,flow,identifier)
    except ValueError:
        if action=='add':
            raise
        item = None  # A missing snapshot can still be removed by its stored ID.

    key = entry_key(item) if item else ''
    path.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(path,timeout=2)) as db,db:
        db.execute('BEGIN IMMEDIATE')
        db.execute(SCHEMA)
        if action=='remove':
            db.execute('DELETE FROM saved_web WHERE workflow=? AND (entry=? OR identifier=?)',(flow,key,identifier))
        else:
            current = db.execute('SELECT identifier,title,heading,text,han FROM saved_web WHERE workflow=? AND entry=?',(flow,key)).fetchone()
            values = (identifier,*indexed_text(item))
            if current!=values:
                db.execute('DELETE FROM saved_web WHERE workflow=? AND entry=?',(flow,key))
                db.execute('INSERT INTO saved_web VALUES (?,?,?,?,?,?,?)',(flow,key,*values))
    return dict(id=identifier,saved=action=='add')
