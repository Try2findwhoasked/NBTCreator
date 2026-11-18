"""Acquire the curated Project Gutenberg corpus. This is the network step only."""

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import monotonic

CATALOG = Path(__file__).resolve().parents[1]/'config/architecture-books.json'
MIRROR = 'https://gutenberg.pglaf.org'
RIGHTS = 'Project Gutenberg editions of historical works; retain the included terms and attribution.'


def fetch(url, target, maximum, validate):
    request = urllib.request.Request(url, headers={'User-Agent': 'NBTCreator-ArchitectureLibrary/1.0'})
    deadline = monotonic()+90
    with urllib.request.urlopen(request, timeout=12) as response:
        raw = bytearray()
        while chunk := response.read1(min(1024**2, maximum+1-len(raw))):
            raw.extend(chunk)
            if len(raw)>maximum or monotonic()>deadline:
                raise ValueError('Download exceeded its size or time limit: '+url)
    if len(raw)>maximum or not validate(raw):
        raise ValueError('Unexpected download content: '+url)
    with NamedTemporaryFile(dir=target.parent, delete=False) as stream:
        stream.write(raw)
        temporary = Path(stream.name)
    try:
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return dict(file=target.name, download=url, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def complete_text(raw):
    text = raw.decode('utf-8-sig', errors='replace')
    return (len(text)>10000 and '\ufffd' not in text and 'PROJECT GUTENBERG' in text.upper()
            and re.search(r'(?:\*\*\*\s*end of|end of (?:the|this) project gutenberg)', text, re.I))


def complete_illustration(raw, format):
    if format == 'pdf':
        return raw.startswith(b'%PDF-') and b'%%EOF' in raw[-4096:]
    if format == 'zip':
        try:
            with zipfile.ZipFile(BytesIO(raw)) as archive:
                return any(name.endswith(('.htm','.html')) for name in archive.namelist()) and archive.testzip() is None
        except (OSError, ValueError, zipfile.BadZipFile):
            return False
    return False


def illustrated(folder, record, existing):
    target = folder/record['file']
    validate = lambda raw: complete_illustration(raw, record['format'])
    if target.exists():
        if target.is_symlink() or target.stat().st_size>110*1024**2:
            raise ValueError('Existing illustrated edition is invalid or too large')
        raw = target.read_bytes()
        if not validate(raw):
            raise ValueError('Existing illustrated edition has an unexpected format')
        checksum = hashlib.sha256(raw).hexdigest()
        if existing and checksum != existing['sha256']:
            raise ValueError('Existing illustrated edition differs from its recorded download')
        obtained = dict(file=target.name, download=record['url'], bytes=len(raw), sha256=checksum)
    else:
        obtained = fetch(record['url'], target, 110*1024**2, validate)
    return record | obtained


def acquire(folder, book, existing):
    number = str(book['id'])
    metadata = dict(book, source=f'https://www.gutenberg.org/ebooks/{number}', rights=RIGHTS)
    if existing:
        target = (folder/f'pg{number}.txt').resolve()
        if not target.is_relative_to(folder) or existing['file'] != target.name or target.stat().st_size != existing['bytes']:
            raise ValueError('Existing book filename or size changed: '+number)
        raw = target.read_bytes()
        if (len(raw)!=existing['bytes'] or hashlib.sha256(raw).hexdigest()!=existing['sha256']
                or not complete_text(raw)):
            raise ValueError('Existing book differs from its recorded download: '+number)
        return metadata | {key: existing[key] for key in ('file', 'download', 'bytes', 'sha256')}
    prefix = f"{MIRROR}/{'/'.join(number[:-1])}/{number}"
    last = None
    for name in (number+'-0.txt', number+'.txt'):
        try:
            return metadata | fetch(prefix+'/'+name, folder/f'pg{number}.txt', 8*1024**2, complete_text)
        except (OSError, ValueError) as error:
            last = error
    raise ValueError(f'Could not download {number}: {last}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, default=Path('workspace/architecture-knowledge'))
    args = parser.parse_args()
    folder = args.library.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    file = folder/'books.json'
    previous = json.loads(file.read_text(encoding='utf-8')) if file.exists() else {'books': []}
    existing = {book['id']: book for book in previous['books']}
    catalogue = json.loads(CATALOG.read_text(encoding='utf-8'))
    with ThreadPoolExecutor(max_workers=4) as pool:
        downloads = {pool.submit(acquire, folder, book, existing.get(book['id'])):book for book in catalogue['books']}
        books, errors = [], []
        for job, book in downloads.items():
            try:
                books.append(job.result())
            except (OSError, ValueError) as error:
                errors.append(dict(id=book['id'], error=str(error)))
                if book['id'] in existing:
                    books.append(existing[book['id']])
    staging = file.with_suffix('.tmp')
    staging.write_text(json.dumps(dict(schema_version=1, books=books), ensure_ascii=False, indent=2)+'\n',
                       encoding='utf-8')
    staging.replace(file)
    illustrations = []
    illustration_errors = []
    scans_file = folder/'illustrated-originals.json'
    prior_scans = json.loads(scans_file.read_text(encoding='utf-8')) if scans_file.exists() else []
    prior_scans = {scan['file']:scan for scan in prior_scans}
    with ThreadPoolExecutor(max_workers=3) as pool:
        scans = {pool.submit(illustrated, folder, record, prior_scans.get(record['file'])):record
                 for record in catalogue.get('illustrated_originals', [])}
        for job, record in scans.items():
            try:
                illustrations.append(job.result())
            except (OSError, ValueError) as error:
                illustration_errors.append(dict(file=record['file'], error=str(error)))
                if record['file'] in prior_scans:
                    illustrations.append(prior_scans[record['file']])
    scans_staging = scans_file.with_suffix('.tmp')
    scans_staging.write_text(
        json.dumps(illustrations, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    scans_staging.replace(scans_file)
    print(json.dumps(dict(library=str(folder), verified=len(catalogue['books'])-len(errors),
                          illustrated=len(illustrations), errors=errors, illustration_errors=illustration_errors), ensure_ascii=False))
    return bool(errors or illustration_errors)


if __name__ == '__main__':
    raise SystemExit(main())
