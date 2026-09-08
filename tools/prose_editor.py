#!/usr/bin/env python3
"""Generate the static prose catalogue, serve a local preview, and validate/import edits.

The published catalogue contains English and source contracts, never Japanese prose.
The localhost preview supplies the ignored extraction through a read-only endpoint.
"""
import argparse
import difflib
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sys
import tempfile

import build
import codec
import dialogue_preview as dialogue
import dotfont
import dte_rom
import latinfont
import lint_en
import textlayout
import wrap_en

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site' / 'prose'
CATALOG = SITE / 'catalog.json'
FORMAT = 'shiren-prose-edits-v1'
RULE_FILES = ('tools/prose_editor.py', 'tools/wrap_en.py', 'tools/textlayout.py',
              'tools/dialogue_preview.py', 'tools/lint_en.py', 'tools/codec.py',
              'tools/latinfont.py', 'tools/dotfont.py', 'tools/dte_rom.py',
              'assets/fonts/thin_pixel_7_compact.json',
              'assets/fonts/thin_pixel_7_compact_glyphs.json',
              'site/prose/rules.js')


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def read_manifest():
    path = ROOT / 'script/script.json'
    if not path.exists():
        raise ValueError('Extract your ROM first: python3 tools/extract.py build/base.gb')
    return {r['loc']: r for r in json.loads(path.read_text())['strings']}


def sequence(text):
    """Preserve reviewed effect/raw bytes and the order of significant substitutions."""
    return [m.group(0) for m in codec.TOKEN_RE.finditer(text)
            if m.group(1).split(':')[0] not in lint_en.FREE]


def catalogue():
    manifest = read_manifest()
    current = lint_en.load_en(str(ROOT / 'script/en.tsv'))
    font = dotfont.load_approved()
    events, records = [], []
    group = None
    for line in (ROOT / 'script/prose_draft.tsv').read_text().splitlines():
        heading = re.match(r'^#\s*(?:=+|-+)\s*bank (\d+)\s*(?:—|:)\s*(.*?)\s*(?:=+|-+)\s*$', line)
        if heading:
            bank, name = heading.groups()
            name = re.sub(r' \(preserve reviewed.*\)$', '', name)
            slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
            group = {'id': f'{bank}-{slug}', 'name': name[0].upper() + name[1:], 'locs': []}
            # Repeated companion headings represent different sections of the draft.
            if any(e['id'] == group['id'] for e in events):
                group['id'] += f'-{len(events)}'
            events.append(group)
        if not line.strip() or line.startswith('#'):
            continue
        loc, draft = line.split('\t', 1)
        r = manifest[loc]
        # These are clear-condition/menu labels, not prose, even though drafted here.
        if loc == '11:$537F' or (r['bank'] == 14 and 0x7C78 <= r['offset'] % 0x4000 + 0x4000 <= 0x7EE6):
            continue
        if r['bank'] not in (11, 14) or dialogue.geometry_for(r)[:2] != (30, 3):
            raise ValueError(f'{loc}: unexpected prose renderer')
        if group is None:
            raise ValueError(f'{loc}: missing event heading')
        draft = draft.strip()
        terminal = re.search(r'<end>((?:<[^>]+>)*)$', r['jp'])
        compiled = current[loc]
        speaker = re.match(r"^([A-Za-z][A-Za-z '\-]{0,24}):", draft.lstrip('='))
        record = {
            'loc': loc, 'bank': r['bank'], 'event': group['id'],
            'speaker': speaker.group(1) if speaker else '',
            'draft': draft, 'current': compiled,
            'editable': not draft.startswith('='),
            'base': digest(json.dumps([draft, r['jp'], compiled], ensure_ascii=False)),
            'sourceHash': digest(r['jp']),
            'sourceIndent': textlayout.source_indent(bytes.fromhex(r['hex'])),
            'sourceHasEnd': bool(lint_en.ends(r['jp'])),
            'sourceTrailingEnd': r['jp'].rstrip().endswith('<end>'),
            'terminalSuffix': terminal.group(1) if terminal and terminal.group(1) else '',
            'significant': dict(lint_en.significant(r['jp'])),
            'sequence': sequence(draft),
        }
        records.append(record)
        group['locs'].append(loc)
    rules_hash = hashlib.sha256()
    for name in RULE_FILES:
        rules_hash.update(name.encode() + b'\0' + (ROOT / name).read_bytes() + b'\0')
    glyphs = {}
    for ch, rows in font.glyphs.items():
        span = dotfont.ink_span(rows)
        glyphs[ch] = {'code': latinfont.EN_CODES[ch], 'advance': font.advances[ch],
                      'ink': span[1] + 1 if span else 0, 'rows': list(rows)}
    data = {
        'format': 1, 'rulesRevision': rules_hash.hexdigest(),
        'font': {'name': font.name, 'glyphs': glyphs,
                 'credit': 'Thin Pixel-7 by Sizenko Alexander (Style-7), adapted for Shiren GB.'},
        'rules': {'glyphLimit': dialogue.WIDTH, 'pixelLimit': dialogue.LINE_PX,
                  'linesPerBox': dialogue.LINES_PER_BOX, 'bufferLimit': dialogue.BUF_LOOP2,
                  'controls': codec.REV_CONTROL, 'arity': codec.arity_for(14),
                  'sourceCosts': dialogue.production_widths(),
                  'pixelCosts': dialogue.dot_production_widths(font),
                  'combining': list(codec.COMBINING), 'dteCodes': list(dte_rom.DTE_CODES)},
        'events': [e for e in events if e['locs']], 'records': records,
    }
    data['revision'] = digest(json.dumps(data, ensure_ascii=False, sort_keys=True))
    return data


def compile_draft(record, draft, native, data):
    """The importer uses the existing Python wrapper and validators, not the JS port."""
    if not record['editable']:
        raise ValueError('Structured dialogue is read-only in this proof of concept')
    if len(draft) > 40000:
        raise ValueError('This entry exceeds the editor\'s 40,000-character limit')
    if not draft.strip() or draft != draft.strip() or any(c in draft for c in '\t\r\n'):
        raise ValueError('Use one nonempty TSV field without outer whitespace or literal tabs/newlines')
    if draft.startswith('='):
        raise ValueError('Ordinary prose cannot become a verbatim row')
    # Existing reviewed raw bytes may survive; a new raw escape cannot hide a control.
    if sequence(draft) != record['sequence']:
        raise ValueError('Required controls, arguments and raw bytes must retain their order')
    if '<end>' in draft:
        raise ValueError('Use <brk> in prose; the wrapper places <end>')
    font = dotfont.load_approved()
    pixels = dialogue.dot_production_widths(font)

    def measure(text):
        return dialogue.dot_metrics(build.encode_en(text, native['bank']), font,
                                    native['bank'], pixels)[:2]

    if draft == record['draft']:
        compiled, notes = record['current'], []
    else:
        compiled, notes = wrap_en.wrap(
            draft, terminal_end=record['terminalSuffix'], measure=measure,
            pixel_limit=dialogue.LINE_PX, first_indent=record['sourceIndent'])
    encoded = build.encode_en(textlayout.renderer_text(compiled, bytes.fromhex(native['hex'])), native['bank'])
    errors = lint_en.check_one(native['jp'], compiled, native['bank'])
    if record['sequence'] and record['sequence'][0].startswith('<cEC:') and not compiled.startswith(record['sequence'][0]):
        errors.append(('ec_prefix_moved', 'Keep the source dialogue prefix first'))
    errors += dialogue.check(encoded, buf=dialogue.BUF_LOOP2, bank=native['bank'],
                             font=font, pixel_widths=pixels)
    if set(encoded) & set(dte_rom.DTE_CODES):
        errors.append(('escape_is_dte_code', 'Raw byte collides with compression codes'))
    if errors:
        raise ValueError('; '.join(f'{kind}: {detail}' for kind, detail in errors))
    return compiled, notes


def parse_edits(text):
    if len(text.encode('utf-8')) > 2_000_000:
        raise ValueError('TSV is larger than 2 MB')
    metadata, bases, edits = {}, {}, {}
    for number, line in enumerate(text.lstrip('\ufeff').splitlines(), 1):
        if not line:
            continue
        if line.startswith('# '):
            fields = line[2:].split('\t')
            if fields[0] == 'base' and len(fields) == 3:
                if fields[1] in bases:
                    raise ValueError(f'Line {number}: duplicate base address')
                bases[fields[1]] = fields[2]
            elif fields[0] in ('format', 'revision', 'rules') and len(fields) == 2:
                if fields[0] in metadata:
                    raise ValueError(f'Line {number}: duplicate metadata')
                metadata[fields[0]] = fields[1]
            continue
        if line.startswith('#'):
            continue
        fields = line.split('\t')
        if len(fields) != 2 or not re.fullmatch(r'\d+:\$[0-9A-F]{4}', fields[0]):
            raise ValueError(f'Line {number}: expected loc<TAB>prose')
        loc, value = fields
        if loc in edits:
            raise ValueError(f'Line {number}: duplicate address {loc}')
        edits[loc] = value
    if metadata.get('format') != FORMAT or not edits or set(bases) != set(edits):
        raise ValueError('Expected a nonempty Prose Studio changes TSV with matching base hashes')
    return metadata, bases, edits


def replace_rows(text, replacements):
    remaining = dict(replacements)
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith('#') or '\t' not in line:
            continue
        loc = line.split('\t', 1)[0]
        if loc in remaining:
            lines[index] = loc + '\t' + remaining.pop(loc) + '\n'
    if remaining:
        raise ValueError('Missing target rows: ' + ', '.join(remaining))
    return ''.join(lines)


def prepare_import(text, data=None):
    data = catalogue() if data is None else data
    metadata, bases, edits = parse_edits(text)
    if metadata.get('rules') != data['rulesRevision']:
        raise ValueError('The editor rules changed; reopen the current editor and review your edits')
    # Whole-catalogue revisions may differ when unrelated rows changed. Each edited
    # address must still match its precise draft baseline, avoiding silent overwrites.
    by_loc = {r['loc']: r for r in data['records']}
    native = read_manifest()
    compiled, actual = {}, {}
    for loc, draft in edits.items():
        if loc not in by_loc or bases[loc] != by_loc[loc]['base']:
            raise ValueError(f'{loc}: unknown address or the project draft changed since export')
        try:
            value, _ = compile_draft(by_loc[loc], draft, native[loc], data)
        except ValueError as exc:
            raise ValueError(f'{loc}: {exc}') from exc
        if draft != by_loc[loc]['draft']:
            actual[loc], compiled[loc] = draft, value
    original_en = (ROOT / 'script/en.tsv').read_text()
    new_en = replace_rows(original_en, compiled)
    # Glossary lint is English-specific and runs here against the complete merged file.
    with tempfile.TemporaryDirectory(prefix='shiren-prose-import-') as directory:
        proposed = Path(directory) / 'en.tsv'
        proposed.write_text(new_en)
        import subprocess
        result = subprocess.run([sys.executable, str(ROOT / 'tools/lint_en.py'), '--en', str(proposed)],
                                cwd=ROOT, text=True, capture_output=True)
        if result.returncode:
            raise ValueError(result.stdout + result.stderr)
    original_draft = (ROOT / 'script/prose_draft.tsv').read_text()
    return actual, {
        ROOT / 'script/prose_draft.tsv': (original_draft, replace_rows(original_draft, actual)),
        ROOT / 'script/en.tsv': (original_en, new_en),
    }


def apply_import(outputs):
    # Prepare both complete files before replacing either. Roll back on a failed replace.
    staged, replaced = [], []
    try:
        for path, (before, after) in outputs.items():
            if path.read_text() != before:
                raise ValueError(f'{path}: changed while the import was being checked')
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                             prefix='.prose-import-', delete=False) as handle:
                handle.write(after)
                staged.append((path, Path(handle.name)))
                Path(handle.name).chmod(path.stat().st_mode & 0o777)
        for path in outputs:
            if path.read_text() != outputs[path][0]:
                raise ValueError(f'{path}: changed while the import was being staged')
        for path, temporary in staged:
            temporary.replace(path)
            replaced.append(path)
    except Exception:
        for path in replaced:
            path.write_text(outputs[path][0])
        raise
    finally:
        for _, temporary in staged:
            temporary.unlink(missing_ok=True)


def serve(port, testing=False):
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            route = self.path.split('?', 1)[0]
            special = {'/local-source.tsv': ROOT / 'script/script.tsv'}
            if testing:
                special['/test-oracle.json'] = ROOT / 'build/prose-editor-oracle.json'
            path = special.get(route)
            if path is not None:
                if not path.exists():
                    self.send_error(404)
                    return
                payload = path.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json' if path.suffix == '.json' else 'text/plain; charset=utf-8')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            super().do_GET()

    handler = functools.partial(Handler, directory=str(SITE))
    server = ThreadingHTTPServer(('127.0.0.1', port), handler)
    print(f'Prose Studio: http://127.0.0.1:{port}/', flush=True)
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    export = sub.add_parser('export', help='regenerate the public, Japanese-free catalogue')
    export.add_argument('--check', action='store_true', help='fail if the checked-in catalogue is stale')
    preview = sub.add_parser('serve', help='serve the static editor and local Japanese extraction')
    preview.add_argument('--port', type=int, default=8765)
    preview.add_argument('--test', action='store_true', help=argparse.SUPPRESS)
    incoming = sub.add_parser('import', help='validate and preview a downloaded changes TSV')
    incoming.add_argument('tsv', type=Path)
    incoming.add_argument('--apply', action='store_true', help='update only changed draft/en rows after validation')
    args = parser.parse_args()
    try:
        if args.command == 'export':
            data = catalogue()
            output = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
            if args.check:
                if not CATALOG.exists() or CATALOG.read_text() != output:
                    raise ValueError('Catalogue is stale; run python3 tools/prose_editor.py export')
            else:
                CATALOG.parent.mkdir(parents=True, exist_ok=True)
                CATALOG.write_text(output)
            print(f'{len(data["records"])} prose records in {len(data["events"])} event groups; '
                  f'{sum(r["editable"] for r in data["records"])} editable; Japanese text excluded.')
        elif args.command == 'serve':
            serve(args.port, args.test)
        else:
            changes, outputs = prepare_import(args.tsv.read_text(encoding='utf-8-sig'))
            for path, (before, after) in outputs.items():
                relative = str(path.relative_to(ROOT))
                print(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                                 'a/' + relative, 'b/' + relative)), end='')
            if args.apply and changes:
                apply_import(outputs)
            print(f'{len(changes)} changed row(s): ' + ('applied; run sh build.sh before using the ROM.'
                  if args.apply else 'validated, no project files changed. Add --apply to import.'))
    except (ValueError, OSError, KeyError) as exc:
        print(f'prose_editor: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
