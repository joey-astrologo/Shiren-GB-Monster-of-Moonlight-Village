#!/usr/bin/env python3
"""Stage only public workshop assets for GitHub Pages. No ROM or dependencies needed."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import shutil
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'site'
OUTPUT = ROOT / 'build/pages'
PUBLIC_FILES = (
    'index.html', 'style.css',
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
    # Source text and extracted bytes must never be added to public records.
    fields = {'loc', 'bank', 'event', 'speaker', 'draft', 'current', 'editable', 'base',
              'sourceHash', 'sourceIndent', 'sourceHasEnd', 'sourceTrailingEnd',
              'terminalSuffix', 'significant', 'sequence'}
    for row in data['records']:
        if set(row) != fields:
            raise ValueError(f'{row.get("loc")}: unexpected public record fields')


def main():
    files = {}
    for name in PUBLIC_FILES:
        path = SOURCE / name
        if path.is_symlink() or path.resolve() != path.absolute():
            raise ValueError(f'Public assets must be regular files: {name}')
        files[name] = path.read_bytes()
    validate(files)
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
