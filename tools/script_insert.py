#!/usr/bin/env python3
"""Validate a full-script spreadsheet; --apply imports it and runs the ROM build.

Only edited_en is a proposal. Reference columns must match the current export.
Uses the existing workbench/prose validators and transactional TSV writer without
changing their download formats. Run with the normal extraction/build setup.
"""
import argparse
import csv
import difflib
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import prose_editor
import script_dump
import textlayout
import workbench

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ('shiren_en.gb', 'shiren_en.ips', 'shiren_en.gb.relocmap.tsv', 'shiren_en.gb.ram')


def read_proposals(path, baseline):
    if path.stat().st_size > 2_000_000:
        raise ValueError('Spreadsheet exceeds 2 MB')
    rows = script_dump.read_table(path, script_dump.FIELDS)
    current = {row['loc']: row for row in baseline}
    incoming = {row['loc']: row for row in rows}
    if set(incoming) != set(current):
        missing = sorted(set(current) - set(incoming))
        unknown = sorted(set(incoming) - set(current))
        raise ValueError(f'Full spreadsheet coverage differs: missing {missing[:5]}, '
                         f'unknown {unknown[:5]}. Keep every exported row.')
    proposals = {}
    for row in rows:
        loc = row['loc']
        for field in script_dump.FIELDS[:-1]:
            if row[field] != current[loc][field]:
                raise ValueError(f'{loc}: reference column {field} is stale or modified; '
                                 'restore the reference or refresh the spreadsheet first')
        text = row['edited_en']
        if text == '' or text == row['en']:
            continue
        if not text.strip() or len(text) > 40000 or re.search(r'[\t\r\n]', text):
            raise ValueError(f'{loc}: edited_en needs nonempty text, at most 40,000 '
                             'characters, without literal tabs/newlines; use control tokens')
        proposals[loc] = text
    return proposals


def authored_text(text, original):
    """Undo only spacing which renderer_text adds; preserve authored spaces."""
    indent = textlayout.source_indent(original)
    if indent and not text.startswith(indent):
        raise ValueError('Keep the native leading space shown in en')
    authored = text[len(indent):]
    if '<$81>' in authored:
        authored = authored.replace('<br>  ', '<br> ')
    if textlayout.renderer_text(authored, original) != text:
        raise ValueError('Keep the two-space selector continuation shown in en')
    return authored


def prose_draft(text, record):
    """Convert copied insertion layout into a draft accepted by the prose wrapper."""
    text = text.replace('<end><brk>', '<brk>')
    suffix = record['terminalSuffix']
    if suffix and text.endswith('<end>' + suffix):
        text = text[:-len('<end>' + suffix)] + suffix
    if '<end>' in text:
        raise ValueError('In prose, <end> may precede <brk> or the required terminal '
                         'effect sequence only; the wrapper supplies those controls')
    # The wrapper owns continuation indents. Retaining <br>/<brk> keeps explicit
    # breaks while letting a longer rewritten line wrap into additional lines.
    return re.sub(r'(<br>|<brk>) +', r'\1', text)


def changes_tsv(data, edits, prose=False):
    records = {row['loc'] if prose else row['key']: row for row in data['records']}
    lines = [f'# format\t{prose_editor.FORMAT if prose else workbench.FORMAT}',
             f'# revision\t{data["revision"]}', f'# rules\t{data["rulesRevision"]}']
    lines.extend(f'# base\t{key}\t{records[key]["base"]}' for key in edits)
    lines.extend(f'{key}\t{value}' for key, value in edits.items())
    return '\n'.join(lines) + '\n'


def prepare_import(path):
    proposals = read_proposals(path, script_dump.dump_rows())
    if not proposals:
        return {}, {}
    prose = prose_editor.catalogue()
    work = workbench.catalogue()
    prose_rows = {row['loc']: row for row in prose['records'] if row['editable']}
    work_rows = {row['loc']: row for row in work['records']}
    native = prose_editor.read_manifest()
    prose_edits, work_edits = {}, {}
    for loc, text in proposals.items():
        row = prose_rows.get(loc) or work_rows.get(loc)
        if row is None or not row['editable']:
            raise ValueError(f'{loc}: fixed/extraction reference cannot be imported; '
                             + (row.get('reason', '') if row else 'no editable text contract'))
        try:
            if loc in prose_rows:
                prose_edits[loc] = prose_draft(
                    authored_text(text, bytes.fromhex(native[loc]['hex'])), row)
            else:
                work_edits[row['key']] = text if row['subject'] == 'cinematic' else authored_text(
                    text, bytes.fromhex(native[loc]['hex']))
        except ValueError as exc:
            raise ValueError(f'{loc}: {exc}') from exc
    prose_tsv = changes_tsv(prose, prose_edits, prose=True) if prose_edits else None
    if work_edits:
        # Joint import is essential for a name change with matching prose changes:
        # glossary lint must see both halves, not reject either half in isolation.
        changes, outputs = workbench.prepare_import(changes_tsv(work, work_edits), prose_tsv)
    else:
        changes, outputs = prose_editor.prepare_import(prose_tsv, prose)
        # Prose's importer checks wrapping, controls and complete glossary lint.
        # Also run the same full font audit used by the workbench importer.
        with tempfile.TemporaryDirectory(prefix='shiren-script-insert-') as directory:
            candidate = Path(directory) / 'en.tsv'
            candidate.write_text(outputs[ROOT / 'script/en.tsv'][1], encoding='utf-8')
            result = subprocess.run([sys.executable, str(ROOT / 'tools/fontaudit.py'),
                                     '--en', str(candidate)], cwd=ROOT, capture_output=True, text=True)
            if result.returncode:
                raise ValueError(result.stdout + result.stderr)
    return changes, {path: pair for path, pair in outputs.items() if pair[0] != pair[1]}


def apply_and_build(outputs, root=ROOT):
    """Restore imported sources and release outputs if any build gate fails."""
    artifacts = {root / 'build' / name: None for name in ARTIFACTS}
    for path in artifacts:
        if path.exists():
            artifacts[path] = path.read_bytes()
    prose_editor.apply_import(outputs)
    try:
        subprocess.run(['sh', 'build.sh'], cwd=root, check=True)
        for name in ARTIFACTS[:3]:
            if not (root / 'build' / name).is_file():
                raise ValueError(f'Build did not produce {name}')
    except BaseException as exc:
        failures = []
        try:
            prose_editor.apply_import({path: (after, before) for path, (before, after) in outputs.items()})
        except (OSError, ValueError) as restore_error:
            failures.append(f'translation rollback: {restore_error}')
        for path, payload in artifacts.items():
            try:
                if payload is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(payload)
            except OSError as restore_error:
                failures.append(f'{path}: {restore_error}')
        if failures:
            raise RuntimeError('Build failed and restoration was incomplete: ' + '; '.join(failures)) from exc
        if isinstance(exc, KeyboardInterrupt):
            print('Previous translation files and ROM/IPS/map/save outputs restored.', file=sys.stderr)
            raise
        raise RuntimeError(f'Build failed: {exc}. Previous translation files and ROM/IPS/map/save '
                           'outputs restored; build diagnostics retained.') from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tsv', type=Path, help='full six-column spreadsheet, including edited_en')
    parser.add_argument('--apply', action='store_true', help='import validated changes and run sh build.sh')
    args = parser.parse_args()
    try:
        changes, outputs = prepare_import(args.tsv)
        for path, (before, after) in outputs.items():
            name = str(path.relative_to(ROOT))
            print(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                             'a/' + name, 'b/' + name)), end='')
        print(f'Validated {len(changes)} changed entries in {len(outputs)} project files.', flush=True)
        if args.apply:
            print('Applying changes and running the complete build gate…', flush=True)
            apply_and_build(outputs)
            print('Build passed: build/shiren_en.gb and build/shiren_en.ips. '
                  'Review the changed text in-game before accepting it.')
        else:
            print('Validation only: no project files or ROMs changed. Add --apply to import and build.')
    except KeyboardInterrupt:
        parser.exit(130, 'script_insert: interrupted.\n')
    except (OSError, ValueError, RuntimeError, csv.Error) as exc:
        parser.exit(1, f'script_insert: {exc}\n')


if __name__ == '__main__':
    main()
