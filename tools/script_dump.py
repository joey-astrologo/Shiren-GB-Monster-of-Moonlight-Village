#!/usr/bin/env python3
"""Export a spreadsheet of Japanese source, inserted English and proposed edits.

Uses the normal local extraction and project Python dependencies. English is the
readable, uncompressed insertion text, including renderer-supplied spacing. This
does not read a built ROM or apply spreadsheet edits to the translation files.
"""
import argparse
import csv
import io
from itertools import chain
import json
from pathlib import Path
import tempfile

import dotfont
import fontaudit
import intro
import textlayout

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'script/script_full.tsv'
FIELDS = ('id', 'loc', 'bytes', 'jp', 'en', 'edited_en')


def read_table(path, fields):
    with path.open(encoding='utf-8-sig', newline='') as source:
        first = next(source, '')
        while first.startswith('#'):
            first = next(source, '')
        reader = csv.DictReader(chain([first], source), delimiter='\t')
        if tuple(reader.fieldnames or ()) != fields:
            raise ValueError(f'{path}: expected columns {fields}')
        rows = list(reader)
    if any(None in row or None in row.values() for row in rows):
        raise ValueError(f'{path}: malformed TSV row')
    for key in ('id', 'loc'):
        if any(not row[key] for row in rows) or len({row[key] for row in rows}) != len(rows):
            raise ValueError(f'{path}: missing or duplicate {key}')
    return rows


def dump_rows():
    manifest = json.loads((ROOT / 'script/script.json').read_text())
    source = read_table(ROOT / 'script/script.tsv', FIELDS[:5])
    native = {row['loc']: row for row in manifest['strings']}
    if {row['loc'] for row in source} != set(native):
        raise ValueError('Extraction TSV and manifest disagree; rerun tools/extract.py')
    translated, _, unknown = fontaudit.load_translations(
        manifest, str(ROOT / 'script/en.tsv'), str(ROOT / 'script/glossary.tsv'))
    if unknown:
        raise ValueError(f'Translation addresses missing from extraction: {unknown}')
    rows = []
    for row in source:
        original = native[row['loc']]
        if any(row[key] != str(original[key]) for key in FIELDS[:4]):
            raise ValueError(f"{row['loc']}: extraction TSV differs from manifest")
        english = translated.get(original['id'])
        rows.append({**row, 'en': textlayout.renderer_text(english, bytes.fromhex(original['hex']))
                     if english is not None else '', 'edited_en': ''})

    # Cinematics have a separate alphabet and renderer. Preserve their stable IDs
    # and expose the actual occupied lines, including automatically wrapped ones.
    opening = read_table(ROOT / 'script/intro.tsv', intro.TSV_COLUMNS)
    events = {event['id']: event for event in intro.EVENTS}
    if {row['id'] for row in opening} != set(events):
        raise ValueError('Cinematic TSV does not cover the current events')
    lines, _ = intro.layout({row['id']: row['english'].strip() for row in opening},
                            dotfont.load_approved())
    for row in opening:
        event = events[row['id']]
        if row['loc'] != event['loc']:
            raise ValueError(f"{row['id']}: cinematic source address changed")
        english = '<page>'.join('<br>'.join(lines[(clip, screen, line)]
                                for clip, screen, line, _ in page) for page in event['pages'])
        rows.append({'id': row['id'], 'loc': row['loc'],
                     'bytes': str(sum(len(bytes.fromhex(part)) for part in row['source_hex'].split('/'))),
                     'jp': row['japanese'], 'en': english, 'edited_en': ''})
    if any(len({row[key] for row in rows}) != len(rows) for key in ('id', 'loc')):
        raise ValueError('Extracted and cinematic entries have overlapping keys')
    return rows


def retain_edits(rows, previous):
    """Carry edits forward only while their complete reference row still matches."""
    current = {row['loc']: row for row in rows}
    for old in previous:
        if old['edited_en'] == '':
            continue
        row = current.get(old['loc'])
        if row is None or any(row[key] != old[key] for key in FIELDS[:-1]):
            raise ValueError(f"{old['loc']}: reference changed for an edited row; "
                             'keep this spreadsheet and use --output for a fresh dump')
        row['edited_en'] = old['edited_en']
    return rows


def serialize(rows):
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=FIELDS, delimiter='\t', lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    # A BOM lets spreadsheet applications reliably identify Japanese UTF-8 text.
    return output.getvalue().encode('utf-8-sig')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--check', action='store_true', help='check reference columns without changing the file')
    args = parser.parse_args()
    try:
        rows = dump_rows()
        previous = read_table(args.output, FIELDS) if args.output.exists() else []
        rows = retain_edits(rows, previous)
        if args.check:
            if rows != previous:
                raise ValueError(f'{args.output}: dump is missing or stale; regenerate it')
        else:
            payload = serialize(rows)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=args.output.parent, delete=False) as staged:
                    temporary = Path(staged.name)
                    staged.write(payload)
                temporary.chmod(args.output.stat().st_mode & 0o777 if args.output.exists() else 0o644)
                temporary.replace(args.output)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        populated = sum(bool(row['en']) for row in rows)
        print(f'{args.output}: {len(rows)} entries; {populated} English references; '
              f'{len(rows) - populated} without a standalone English translation; '
              f'{sum(row["edited_en"] != "" for row in rows)} proposed edits retained.')
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f'script_dump: {exc}\n')


if __name__ == '__main__':
    main()
