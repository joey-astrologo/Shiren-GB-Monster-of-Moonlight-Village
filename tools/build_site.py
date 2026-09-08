#!/usr/bin/env python3
"""Stage the translation website and its bundled source TSV for GitHub Pages."""
import argparse
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
    'index.html', 'style.css',
    SOURCE_TSV,
    'prose/index.html', 'prose/style.css', 'prose/app.js',
    'prose/rules.js', 'prose/catalog.json', 'prose/font-license.txt',
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
    for row in data['records']:
        jp = source.get(row['loc'])
        if jp is None or hashlib.sha256(jp.encode('utf-8')).hexdigest() != row['sourceHash']:
            raise ValueError(f'{row["loc"]}: bundled Japanese source does not match the catalogue')


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
