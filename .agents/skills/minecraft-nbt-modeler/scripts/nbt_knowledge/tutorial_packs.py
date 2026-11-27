"""Validate tutorial release metadata without opening its upstream evidence."""

import json
import re


KIND = 'minecraft_tutorial_cards'
VERSION = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)')
CARD_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}')
SOURCE_ID = re.compile(r'[a-z][a-z0-9_-]*\.[A-Za-z0-9][A-Za-z0-9_.-]*')
SHA = re.compile(r'[a-f0-9]{64}')
TIME = re.compile(r'(\d{2,8}):([0-5]\d):([0-5]\d)(?:[,.](\d{3}))?', re.ASCII)


def matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def read_manifest(raw):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('教程知识包清单含重复字段')
            result[key] = value
        return result

    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique_pairs)


def release(data):
    if type(data.get('schema_version')) is not int or not matches(VERSION, data.get('version')):
        raise ValueError('教程知识包版本无效')
    return dict(package_kind=KIND, package_id=data['id'], package_version=data['version'])


def timecode(value):
    found = TIME.fullmatch(value) if isinstance(value, str) else None
    if not found:
        raise ValueError('教程证据时间码无效')
    h, m, s, ms = found.groups()
    return (int(h)*3600 + int(m)*60 + int(s))*1000 + int(ms or 0)


def evidence(ref):
    if (not isinstance(ref, dict) or not matches(SOURCE_ID, ref.get('source_id')) or len(ref['source_id']) > 128
            or not matches(SHA, ref.get('sha256')) or ref.get('status') not in ('explicit', 'visible', 'inferred')):
        raise ValueError('教程证据来源、状态或 SHA256 无效')
    path = ref.get('path')
    if (not isinstance(path, str) or not path.startswith('workspace/') or len(path) > 512
            or re.search(r'[\\:\x00-\x1f]', path) or any(part in ('', '.', '..') for part in path.split('/'))):
        raise ValueError('教程证据路径须为原始资料工作区中的相对位置')
    locator = ref.get('locator')
    if not isinstance(locator, dict):
        raise ValueError('教程证据缺少原始定位')
    modality, kind = ref.get('modality'), locator.get('kind')
    record = ref.get('record_key')
    projection = {key: ref[key] for key in ('source_id', 'sha256', 'status', 'modality', 'path')}
    if (modality, kind) == ('subtitle', 'timecodes'):
        ranges = locator.get('ranges')
        if not isinstance(ranges, list) or not 1 <= len(ranges) <= 32 or any(
                not isinstance(span, list) or len(span) != 2 or timecode(span[0]) >= timecode(span[1]) for span in ranges):
            raise ValueError('教程字幕证据时间范围无效')
        projection['locator'] = dict(kind=kind, ranges=ranges)
    else:
        if not isinstance(record, str) or not 1 <= len(record) <= 128:
            raise ValueError('教程图文证据缺少来源记录编号')
        projection['record_key'] = record
        if (modality, kind) == ('text', 'index_field') and locator.get('field') in ('body', 'description', 'summary'):
            projection['locator'] = dict(kind=kind, field=locator['field'])
        elif (modality, kind) == ('image', 'figure') and type(locator.get('number')) is int and locator['number'] >= 1:
            projection['locator'] = dict(kind=kind, number=locator['number'])
        else:
            raise ValueError('教程图文证据定位无效')
    return projection


def document_metadata(book, package):
    if (book['file'] != f"cards/{book['id']}.md" or not matches(CARD_ID, book.get('card_id'))
            or book['source_type'] != 'minecraft-tutorial-card' or book.get('kind') not in ('principle', 'component', 'building_case')
            or book.get('confidence') not in ('E1', 'E2', 'E3', 'E4') or book.get('review_status') not in ('checked', 'verified')):
        raise ValueError('教程卡身份或审核状态无效')
    related = book.get('related_card_ids')
    refs = book.get('evidence')
    applicability = book.get('applicability')
    if (not isinstance(related, list) or len(related) > 32 or any(not matches(CARD_ID, item) for item in related)
            or not isinstance(refs, list) or not 1 <= len(refs) <= 16 or not isinstance(applicability, dict)):
        raise ValueError('教程卡关联或出处声明无效')
    for key, value in applicability.items():
        values = value if isinstance(value, list) else [value]
        if key not in ('edition', 'version', 'mode', 'mods', 'tools') or len(values) > 16 or any(
                not isinstance(item, str) or len(item) > 150 for item in values):
            raise ValueError('教程卡适用范围无效')
    info = dict(package, **{key: book[key] for key in ('card_id', 'kind', 'confidence', 'review_status')},
                applicability=applicability, related_card_ids=related, evidence=[evidence(ref) for ref in refs])
    if 'review_note' in book:
        note = book['review_note']
        if not isinstance(note, str) or len(note) > 1000:
            raise ValueError('教程卡审核备注无效')
        info['review_note'] = note
    return info


def check_links(documents):
    ids = {doc['tutorial']['card_id'].casefold() for doc in documents}
    if len(ids) != len(documents):
        raise ValueError('教程卡原始编号重复')
    for doc in documents:
        info = doc['tutorial']
        related = {item.casefold() for item in info['related_card_ids']}
        if not related <= ids or info['card_id'].casefold() in related:
            raise ValueError('教程卡关联须指向同一发行包中的其他卡')


def body_start(lines):
    if lines and lines[0] == '---':
        try:
            return lines.index('---', 1) + 1
        except ValueError:
            raise ValueError('教程卡缺少 Markdown 元数据结束行') from None
    return 0
