#!/usr/bin/env python3
"""Stage the translation website and its bundled source TSV for GitHub Pages."""
import argparse
import csv
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import shutil
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'site'
OUTPUT = ROOT / 'build/pages'
SOURCE_TSV = 'data/script.tsv'
PUBLIC_FILES = (
    'index.html', 'style.css', 'coverage.html',
    'controls/index.html', 'controls/style.css', 'controls/links.js',
    SOURCE_TSV, 'data/intro.tsv',
    'prose/index.html', 'prose/style.css', 'prose/app.js',
    'prose/rules.js', 'prose/catalog.json', 'prose/font-license.txt',
    'workbench/index.html', 'workbench/style.css', 'workbench/app.js',
    'workbench/rules.js', 'workbench/catalog.json',
)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        self.urls.extend(value for key, value in attrs if key in ('href', 'src') and value)


def validate(files):
    # Check navigation against a project subdirectory, not just a domain root.
    for name, content in files.items():
        if not name.endswith('.html'):
            continue
        parser = Links()
        parser.feed(content.decode('utf-8'))
        for url in parser.urls:
            target = urlsplit(url)
            if target.scheme or target.netloc or not target.path:
                continue
            if target.path.startswith('/'):
                raise ValueError(f'{name}: root-relative link will break project Pages: {url}')
            path = SOURCE / PurePosixPath(name).parent / unquote(target.path)
            if path.is_dir():
                path /= 'index.html'
            relative = str(path.resolve().relative_to(SOURCE.resolve()))
            if relative not in files:
                raise ValueError(f'{name}: link is outside the public artifact: {url}')

    data = json.loads(files['prose/catalog.json'])
    revision = data.pop('revision')
    actual = hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    if data['format'] != 1 or revision != actual or not data['records'] or not data['events']:
        raise ValueError('Invalid public catalogue; regenerate it with prose_editor.py export')
    # Japanese text lives in the bundled TSV; catalogue records retain their schema.
    fields = {'loc', 'bank', 'event', 'speaker', 'draft', 'current', 'editable', 'base',
              'sourceHash', 'sourceIndent', 'sourceHasEnd', 'sourceTrailingEnd',
              'terminalSuffix', 'significant', 'sequence'}
    for row in data['records']:
        if set(row) != fields:
            raise ValueError(f'{row.get("loc")}: unexpected public record fields')

    # Check every editor row before publishing, without needing the ROM or manifest.
    payload = files[SOURCE_TSV]
    if len(payload) > 2_000_000:
        raise ValueError('Bundled source TSV exceeds the browser import limit of 2 MB')
    lines = payload.decode('utf-8-sig').splitlines()
    header = lines.pop(0).split('\t') if lines else []
    if header.count('loc') != 1 or header.count('jp') != 1:
        raise ValueError('Bundled source TSV must have loc and jp columns')
    loc_index, jp_index = header.index('loc'), header.index('jp')
    source = {}
    for number, line in enumerate(lines, 2):
        if not line:
            continue
        fields = line.split('\t')
        if len(fields) != len(header) or fields[loc_index] in source:
            raise ValueError(f'Bundled source TSV has a malformed or duplicate row at line {number}')
        source[fields[loc_index]] = fields[jp_index]
    def project_column(name, column, trim=False):
        result = {}
        for line in (ROOT / 'script' / name).read_text().splitlines():
            if not line or line.startswith('#') or '\t' not in line: continue
            fields = line.split('\t', column)
            if len(fields) <= column or fields[0].strip() in result:
                raise ValueError(f'{name}: malformed or duplicate project row')
            if fields[column].strip(): result[fields[0].strip()] = fields[column].strip() if trim else fields[column]
        return result
    project_en = project_column('en.tsv', 1)
    project_draft = project_column('prose_draft.tsv', 1)
    project_glossary = project_column('glossary.tsv', 3, trim=True)
    for row in data['records']:
        jp = source.get(row['loc'])
        if jp is None or hashlib.sha256(jp.encode('utf-8')).hexdigest() != row['sourceHash']:
            raise ValueError(f'{row["loc"]}: bundled Japanese source does not match the catalogue')
        if row['current'] != project_en.get(row['loc']) or row['draft'] != project_draft.get(row['loc'], '').strip():
            raise ValueError('Stale prose translation snapshot; regenerate both catalogues')

    work = json.loads(files['workbench/catalog.json'])
    revision = work.pop('revision')
    if work['format'] != 'shiren-workbench-edits-v1' or revision != hashlib.sha256(json.dumps(work, ensure_ascii=False, sort_keys=True).encode()).hexdigest():
        raise ValueError('Invalid workbench catalogue; run tools/workbench.py export')
    rules_hash = hashlib.sha256()
    for name in work['ruleSources']:
        path = ROOT / name
        if path.is_symlink() or path.resolve().is_relative_to(ROOT.resolve()) is False:
            raise ValueError('Invalid rule source path')
        rules_hash.update(name.encode() + b'\0' + path.read_bytes() + b'\0')
    if rules_hash.hexdigest() != work['rulesRevision']:
        raise ValueError('Stale workbench rules; run tools/workbench.py export')
    owners = {r['loc']: r['subject'] for r in work['coverage']}
    if len(owners) != len(work['coverage']) or set(owners) != set(source) or len(source) != work['extractedCount']:
        raise ValueError('Every extracted entry must have exactly one workbench owner')
    subjects = {r['id']: r for r in work['subjects']}
    if len(subjects) != len(work['subjects']) or set(owners.values()) - set(subjects):
        raise ValueError('Invalid workbench subjects')
    prose = {r['loc'] for r in data['records'] if r['editable']}
    if prose != {loc for loc, subject in owners.items() if subject == 'prose'}:
        raise ValueError('Prose ownership disagrees with the prose catalogue')
    opening = list(csv.DictReader((line for line in files['data/intro.tsv'].decode('utf-8-sig').splitlines()
                                  if line and not line.startswith('#')), delimiter='\t'))
    intro = {r['id']: r for r in opening}
    if len(intro) != len(opening) or len(intro) != work['cinematicCount'] or any(None in r or None in r.values() for r in opening):
        raise ValueError('Malformed, missing or duplicate cinematic sources')
    if files['data/intro.tsv'] != (ROOT / 'script/intro.tsv').read_bytes():
        raise ValueError('Stale cinematic snapshot; run tools/workbench.py export')
    keys = set()
    for row in work['records']:
        key = row['key']
        if key in keys: raise ValueError('Duplicate workbench record')
        keys.add(key)
        if row['subject'] == 'cinematic':
            original = intro.get(key, {}).get('japanese')
            if intro.get(key, {}).get('english') != row['current']:
                raise ValueError('Cinematic translation snapshot does not match the catalogue')
        else:
            original = source.get(key)
            if owners.get(key) != row['subject'] or key != row['loc']:
                raise ValueError('Workbench record does not match its coverage owner')
            current = project_en.get(key, project_glossary.get(key, ''))
            base = hashlib.sha256(json.dumps([original, current, row['destination'], project_glossary.get(key), project_en.get(key), project_draft.get(key)], ensure_ascii=False).encode()).hexdigest()
            if current != row['current'] or base != row['base']:
                raise ValueError(f'{key}: stale workbench translation snapshot')
        if original is None or original != row['jp'] or hashlib.sha256(original.encode()).hexdigest() != row['sourceHash']:
            raise ValueError(f'{key}: workbench source mismatch')
        if row['subject'] not in subjects or row['editable'] == bool(row['reason']):
            raise ValueError(f'{key}: invalid subject or missing reference explanation')
    if keys != (set(owners) - prose) | set(intro):
        raise ValueError('Workbench records omit or add entries beyond the source census')
    for sid, subject in subjects.items():
        actual = len(intro) if sid == 'cinematic' else sum(s == sid for s in owners.values())
        if actual != subject['count']: raise ValueError('Incorrect workbench entry count')
        href = 'prose/' if sid == 'prose' else 'workbench/?subject=' + sid
        if ('href="' + href + '"').encode() not in files['index.html']:
            raise ValueError(f'Home page is missing the {sid} workbench link')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-source', action='store_true',
                        help='update the bundled TSV from local script/script.tsv after validating it')
    args = parser.parse_args()
    files = {}
    for name in PUBLIC_FILES:
        path = ROOT / 'script/script.tsv' if args.refresh_source and name == SOURCE_TSV else SOURCE / name
        if path.is_symlink() or path.resolve() != path.absolute():
            raise ValueError(f'Public assets must be regular files: {name}')
        files[name] = path.read_bytes()
    validate(files)
    if args.refresh_source:
        target = SOURCE / SOURCE_TSV
        if target.is_symlink() or target.parent.is_symlink():
            raise ValueError('Bundled source TSV must not be a symlink')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(files[SOURCE_TSV])
        print(f'Updated bundled source: {target.relative_to(ROOT)}')
    # Never upload site/ or the repository wholesale: test fixtures stay local.
    if OUTPUT.is_symlink() or OUTPUT.parent.is_symlink():
        raise ValueError('Pages output must not be a symlink')
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    for name, content in files.items():
        target = OUTPUT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    (OUTPUT / '.nojekyll').touch()
    print(f'Pages artifact: {OUTPUT.relative_to(ROOT)} ({len(files) + 1} public files)')


if __name__ == '__main__':
    main()
