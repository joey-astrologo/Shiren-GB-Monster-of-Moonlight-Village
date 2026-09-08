#!/usr/bin/env python3
"""Generate the complete translation workbench catalogue; validate/import edit TSVs.

Run from the repository root. Generation reads local extraction/build inputs; the
published site and its CI packager need only the checked-in public snapshots.
"""
import argparse
import csv
import hashlib
from html import escape
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import build
import codec
import dialogue_preview as dialogue
import dotfont
import fontaudit
import intro
import lint_en
import menuvwf
import menuromspill
import prose_editor
import textlayout

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'site/workbench/catalog.json'
FORMAT = 'shiren-workbench-edits-v1'
SUBJECTS = [
    ('prose', 'Prose', 'Dialogue grouped by the existing event sections.'),
    ('items', 'Items', 'Identified item names and unidentified appearance names, grouped by category.'),
    ('names', 'Monsters and characters', 'Monster tiers, character names and named objects.'),
    ('descriptions', 'Item descriptions', 'Help text grouped by item category; shared fragments have their own editor.'),
    ('seals', 'Equipment seals', 'One-line equipment abilities displayed below an item name.'),
    ('fragments', 'Shared help text', 'The thirteen fragments inserted into descriptions by <cF0:xx>.'),
    ('menus', 'Menus', 'Labels grouped by menu or box, using its actual text and tile limits.'),
    ('verbs', 'Item actions', 'Commands used by the inventory and floor-item submenus.'),
    ('messages', 'Gameplay messages', 'Combat, item, trap and system messages in script order.'),
    ('choices', 'Choices and structured dialogue', 'Event text whose explicit breaks, cursor cells and controls must be retained.'),
    ('conditions', 'Clear conditions', 'The forty condition rows displayed five at a time.'),
    ('cinematic', 'Opening cinematic', 'The twelve entries from intro.tsv, using the cinematic screen slots.'),
    ('reference', 'Fixed text and extraction references', 'Keyboard tables, fixed composite labels and extraction entries without an editable text contract.'),
]
BOX_NAMES = {
    1: 'Status summary', 2: 'Status: fixed fields', 8: 'Which item?', 9: 'Empty inventory',
    12: 'Name-entry keyboard', 13: 'Keyboard alias → box 12', 14: 'Inventory heading',
    16: 'Name limit', 17: 'Pot heading', 18: 'Floor heading', 20: 'Close / quit',
    21: 'Close / exit / quit (route unconfirmed)', 24: 'Continue / new game',
    28: 'Confirmation', 29: 'Difficulty', 30: "Fay's Puzzles: fixed fields",
    32: "Fay's Puzzles: prompt", 33: 'Debug items: consumables',
    34: 'Debug items: equipment', 37: 'Inventory full', 38: 'No awards',
    41: 'Rankings heading', 46: 'Easy explanation', 47: 'Ranking category',
    48: 'Normal explanation', 50: 'Hard explanation', 51: 'New game only',
}
# Category-specific action-table slots; common actions follow the table's order.
VERB_GROUPS = ['Herbs / seeds', 'Scrolls', 'Staffs', 'Bracers', 'Food', 'Equipment',
               'Pots', 'Pots', 'Shared actions', 'Shared actions', 'Shared actions',
               'Shared actions', 'Arrows', 'Shared actions', 'Shared actions',
               '', '', 'Pots / floor items', 'Equipment', '', 'Pots / floor items']
RULE_FILES = tuple(dict.fromkeys(prose_editor.RULE_FILES + (
    'tools/workbench.py', 'site/workbench/rules.js', 'tools/fontaudit.py',
    'tools/menuvwf.py', 'tools/menuromspill.py', 'tools/build.py', 'tools/intro.py',
    'script/build-inputs/box_geometry.tsv', 'script/build-inputs/box_alias.tsv')))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def headings(path):
    result, heading = {}, 'Other entries'
    for line in path.read_text().splitlines():
        match = re.match(r'^#\s*[-=]{3,}\s*(.+?)(?:\s*[-=]{3,})?$', line)
        if match:
            heading = match[1].strip().capitalize()
        elif line and not line.startswith('#'):
            result[line.split('\t')[0]] = heading
    return result


def native_suffix(row):
    """Runtime categories come from table slots, never the translated word Staff/Pot.

    The identified table is 11:$4537. The appearance table at 11:$4A6C starts
    with 24 herbs, 27 scrolls, 12 staffs and 14 pots. Placeholder slots retain
    their native category too, even when their English name ends in a digit.
    """
    for ref in row['refs']:
        if ref['kind'] != 'table': continue
        if ref['table'] == 11 * 0x4000 + 0x4537 - 0x4000:
            if ref['index'] < 34: return 'signed'
            if 112 <= ref['index'] < 138: return 'counter'
        if ref['table'] == 11 * 0x4000 + 0x4A6C - 0x4000 and 51 <= ref['index'] < 77:
            return 'counter'
    return ''


def geometry(row, subject, current, widths):
    """Export constraints from the same renderer census used by the project audit."""
    p = {'kind': subject, 'pixels': None, 'cells': None, 'rows': 1,
         'buffer': None, 'bufferScope': 'line', 'rawPrefix': False,
         'indent': textlayout.source_indent(bytes.fromhex(row['hex'])),
         'sourceCosts': 'production', 'fixed': False, 'tileCap': None}
    if subject in ('descriptions', 'seals', 'messages', 'choices'):
        p['cells'], p['rows'], p['buffer'] = dialogue.geometry_for(row)
        p['pixels'] = dialogue.LINE_PX
        if subject in ('descriptions', 'seals'):
            p['bufferScope'], p['sourceCosts'] = 'box', 'help'
    elif subject == 'conditions':
        p.update(pixels=144, cells=fontaudit.CONDITION_SOURCE_CAP, sourceCosts='floor')
    elif subject == 'verbs' or subject == 'menus':
        p['sourceCosts'] = 'floor'
        if row.get('box'):
            box = row['box']; bid = box['id']; width = widths.get(bid, box['width'])
            p.update(pixels=width * 8, cells=menuvwf.ROM_SOURCE_CAP if bid in menuvwf.ROM_LONG_SOURCE_BOXES else width,
                     rawPrefix=bool(p['indent'] or bid in menuvwf.ROM_RAW_PREFIX_BOXES), fixed=bid not in menuvwf.ROM_BOXES)
            if bid in menuvwf.ROM_BOXES:
                # The runtime slices are stricter than install()'s coarse preflight
                # caps. Use the same layout oracle as the emulator ownership audit.
                p['tileCap'] = menuromspill.rom_slice(box['rows'], box['row'], (bid,))[1]
        else:
            p.update(pixels=fontaudit.RUNTIME_MENU_PX.get(row['loc'], (112, ''))[0],
                     cells=18, rawPrefix=row['loc'] in fontaudit.RUNTIME_RAW_PREFIX_LOCS)
            if row['loc'] == fontaudit.LOG_PREFIX_LOC:
                p['log'] = True
            if row['loc'] in fontaudit.SUMMARY_PLACE_LOCS:
                p['floorPrefix'] = row['loc'] != fontaudit.SUMMARY_PLACE_LOCS[0]
                p['cells'] = menuvwf.SUMMARY_SOURCE_CAP
    return p


def catalogue():
    manifest = json.loads((ROOT / 'script/script.json').read_text())
    strings = manifest['strings']; by_loc = {r['loc']: r for r in strings}
    translated, origins, unknown = fontaudit.load_translations(manifest, str(ROOT / 'script/en.tsv'), str(ROOT / 'script/glossary.tsv'))
    if unknown: raise ValueError('Translation addresses missing from extraction')
    prose = json.loads((ROOT / 'site/prose/catalog.json').read_text())
    prose_rows = {r['loc']: r for r in prose['records']}
    events = {e['id']: e['name'] for e in prose['events']}
    gloss = lint_en.load_glossary(str(ROOT / 'script/glossary.tsv'))
    glossary = {r['loc']: r for r in gloss}
    en = lint_en.load_en(str(ROOT / 'script/en.tsv'))
    draft = lint_en.load_en(str(ROOT / 'script/prose_draft.tsv'))
    groups = headings(ROOT / 'script/en.tsv')
    name_groups = headings(ROOT / 'script/glossary.tsv')
    widths = fontaudit.box_widths(str(ROOT / 'script/build-inputs/box_geometry.tsv'))
    item_locs = [r['loc'] for r in gloss if r['cls'] == 'item']
    if len(item_locs) != 145: raise ValueError('Re-census item suffix categories before exporting')
    records, coverage = [], []
    for row in strings:
        loc = row['loc']; current = translated.get(row['id'], '')
        subject, reason = None, ''
        group = groups.get(loc, 'Other entries')
        if loc in prose_rows:
            subject = 'prose' if prose_rows[loc]['editable'] else 'choices'
            group = events[prose_rows[loc]['event']]
        elif loc in glossary:
            subject = 'items' if glossary[loc]['cls'] in ('item', 'appearance') else 'names'
            group = name_groups[loc]
        elif dialogue.is_seal(row): subject, group = 'seals', 'Equipment abilities'
        elif dialogue.is_help(row): subject = 'descriptions'
        elif dialogue.is_clear_condition(row): subject, group = 'conditions', 'Clear-condition table'
        elif loc in dialogue.CF0_LOCS: subject, group = 'fragments', 'Shared description fragments'
        elif loc in fontaudit.ACTION_MENU_LOCS:
            subject = 'verbs'
            index = next(r['index'] for r in row['refs'] if r['kind'] == 'table')
            group = VERB_GROUPS[index]
        elif row.get('box'):
            subject, group = 'menus', f"Box {row['box']['id']:02d} · {BOX_NAMES[row['box']['id']]}"
            bid = row['box']['id']
            if bid in (2, 12, 13, 30):
                reason = {2: 'The status renderer places separate fields and a divider at fixed coordinates; edit its renderer with these strings.',
                          12: 'Keyboard cells also define input positions and character mapping; changing only this text would break name entry.',
                          13: 'The build aliases this keyboard to box 12. This extracted copy is not rendered.',
                          30: "The Fay header is a composite renderer that requires the literal 'No     Rating'."}[bid]
        elif loc in fontaudit.RUNTIME_MENU_PX or loc == fontaudit.LOG_PREFIX_LOC: subject = 'menus'
        elif dialogue.is_dialogue(row): subject = 'messages'
        if not current and not reason:
            reason = 'No approved translation or established editable rendering contract. Retained for extraction coverage.'
        if loc == '4:$4AFE':
            reason = 'The shop renderer generates its price heading independently; changing this extracted label alone does not translate that heading.'
        if reason or not subject: subject = 'reference'
        coverage.append({'loc': loc, 'subject': subject})
        if subject == 'prose': continue
        profile = geometry(row, subject, current, widths)
        destination = 'glossary' if loc in glossary else 'en'
        if loc in prose_rows or loc in draft: destination = 'draft'
        record = {'key': loc, 'loc': loc, 'bank': row['bank'], 'subject': subject, 'group': group,
                  'current': current, 'jp': row['jp'], 'sourceHash': digest(row['jp']),
                  'editable': not bool(reason), 'reason': reason, 'profile': profile,
                  'destination': destination,
                  'controls': re.findall(r'<[^>]+>', current),
                  'spaces': [list((re.match(r'^ *', s)[0], re.search(r' *$', s)[0])) for s in re.split(r'<br>|<brk>', current)],
                  'sourceHasEnd': '<end>' in row['jp'], 'sourceTrailingEnd': row['jp'].rstrip().endswith('<end>'),
                  'refs': [f"{r['kind']} " + (f"{r['table'] // 0x4000}:${r['table'] % 0x4000 + 0x4000:04X} [{r['index']}]" if r['kind'] == 'table' else '') for r in row['refs']]}
        if loc in glossary:
            entry = glossary[loc]; record['nameClass'] = entry['cls']
            record['profile']['suffix'] = native_suffix(row)
            record['profile']['item'] = entry['cls'] in ('item', 'appearance')
            addr = int(loc.split('$')[1], 16)
            record['herb'] = ((entry['cls'] == 'item' and fontaudit.HERB_ITEM_RANGE[0] <= addr <= fontaudit.HERB_ITEM_RANGE[1]) or
                              (entry['cls'] == 'appearance' and fontaudit.HERB_APPEARANCE_RANGE[0] <= addr <= fontaudit.HERB_APPEARANCE_RANGE[1]))
        record['base'] = digest(json.dumps([row['jp'], current, destination, glossary.get(loc, {}).get('en'), en.get(loc), draft.get(loc)], ensure_ascii=False))
        records.append(record)
    intro_text = (ROOT / 'script/intro.tsv').read_text()
    intro_rows = csv.DictReader((l for l in intro_text.splitlines() if not l.startswith('#')), delimiter='\t')
    for row in intro_rows:
        event = next(e for e in intro.EVENTS if e['id'] == row['id'])
        records.append({'key': row['id'], 'loc': row['loc'], 'bank': 31, 'subject': 'cinematic',
                        'group': f"Clip {int(row['clip']) + 1}", 'current': row['english'], 'jp': row['japanese'],
                        'sourceHash': digest(row['japanese']), 'editable': True, 'reason': '',
                        'destination': 'intro', 'base': digest(json.dumps(row, ensure_ascii=False, sort_keys=True)),
                        'controls': [], 'spaces': [], 'refs': [row['source_ranges']],
                        'profile': {'kind': 'cinematic', 'pixels': intro.LINE_TEXT_PX, 'slots': [len(p) for p in event['pages']]}})
    if len(coverage) != len(by_loc) or len({r['loc'] for r in coverage}) != len(coverage):
        raise ValueError('Extraction coverage has duplicates or omissions')
    rules_hash = hashlib.sha256()
    for name in RULE_FILES: rules_hash.update(name.encode() + b'\0' + (ROOT / name).read_bytes() + b'\0')
    font = dotfont.load_approved()
    data = {'format': FORMAT, 'rulesRevision': rules_hash.hexdigest(), 'ruleSources': RULE_FILES, 'font': prose['font'],
            'rules': {'controls': codec.REV_CONTROL, 'banks': {b: codec.arity_for(b) for b in {r['bank'] for r in strings}},
                      'sourceCosts': {'production': dialogue.production_widths(), 'floor': dialogue.floor_widths()},
                      'pixelCosts': dialogue.dot_production_widths(font), 'combining': list(codec.COMBINING)},
            'subjects': [{'id': s, 'name': n, 'description': d, 'count': sum(r['subject'] == s for r in coverage) + (len(intro.EVENTS) if s == 'cinematic' else 0)} for s, n, d in SUBJECTS],
            'coverage': coverage, 'extractedCount': len(strings), 'cinematicCount': len(intro.EVENTS),
            'cf0': dialogue.CF0_LOCS, 'records': records,
            'evidence': ['docs/VWF_BUDGETS.md', 'docs/MENU_STRUCTURE.md', 'docs/ENGINEERING_RULES.md',
                         'tools/fontaudit.py', 'tools/dialogue_preview.py', 'tools/menuvwf.py', 'tools/intro.py']}
    # JSON object keys become strings; hash that public representation, including
    # the bank map, rather than Python's numeric-key sort order.
    data = json.loads(json.dumps(data, ensure_ascii=False))
    data['revision'] = digest(json.dumps(data, ensure_ascii=False, sort_keys=True))
    return data


def suffixes(record):
    kind = record['profile'].get('suffix')
    return ([''] + [s + str(n) for s in ('+', '-') for n in range(1, 100)] if kind == 'signed' else
            [''] + ['[%d]' % n for n in range(1, 100)] if kind == 'counter' else [''])


def write_navigation(data):
    """Keep public links and the coverage table in step with the generated census."""
    cards, table = [], []
    for subject in data['subjects']:
        sid, name = subject['id'], escape(subject['name'])
        url = 'prose/' if sid == 'prose' else 'workbench/?subject=' + sid
        cards.append(f'<article class="subject-card"><div class="subject-count">{subject["count"]} entries</div>'
                     f'<h3><a href="{url}">{name}</a></h3><p>{escape(subject["description"])}</p>'
                     f'<a class="subject-open" href="{url}">Open {"references" if sid == "reference" else "editor"} →</a></article>')
        table.append(f'<tr><th scope="row"><a href="{url}">{name}</a></th><td>{subject["count"]}</td>'
                     f'<td>{"Reference only" if sid == "reference" else "Editable"}</td></tr>')
    index = ROOT / 'site/index.html'
    start, end = '<!-- workbenches:start -->', '<!-- workbenches:end -->'
    before = index.read_text()
    if before.count(start) != 1 or before.count(end) != 1: raise ValueError('Home page lacks workbench markers')
    index.write_text(before.split(start)[0] + start + '\n<div class="subject-grid">\n' + '\n'.join(cards) + '\n</div>\n' + end + before.split(end)[1])
    reference = []
    for row in data['records']:
        if not row['editable']:
            reference.append(f'<li><a href="workbench/?subject=reference#{row["key"].replace("$", "%24").replace(":", "%3A")}">{row["key"]}</a>: {escape(row["reason"])}</li>')
    evidence = ''.join(f'<li><a href="https://github.com/joey-astrologo/Shiren-GB-Monster-of-Moonlight-Village/blob/main/{p}">{p}</a></li>' for p in data['evidence'])
    assets = [
        ('Arrival and floor cards', 'tools/floorcardgen.py', 'Raster artwork and card geometry; not extracted dialogue.'),
        ('Title artwork', 'tools/titlelogo.py', 'Illustrated title and its native layout variants.'),
        ('Copyright card', 'tools/titlecard.py', 'Approved full-screen tile artwork.'),
        ('Wait card', 'tools/waitcard.py', 'Fixed tile-map text replacement.'),
        ('Normal ending', 'tools/normalending.py', 'Two generated raster lines around the native ending mark.'),
        ('Ending credits', 'tools/endingcredits.py', 'Twenty-two raster credit cards with a separate font and timing contract.'),
    ]
    art = ''.join(f'<li><a href="https://github.com/joey-astrologo/Shiren-GB-Monster-of-Moonlight-Village/blob/main/{p}">{n}</a> — {d}</li>' for n, p, d in assets)
    (ROOT / 'site/coverage.html').write_text('''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Script coverage · Shiren GB</title><link rel="stylesheet" href="style.css"></head>
<body><header class="masthead"><div class="header-inner"><a class="brand" href="./">SHIREN GB<small>Translation tools</small></a><a href="./">All workbenches</a></div></header>
<main class="coverage"><h1>Script coverage</h1><p>Every one of the 1,424 extracted script entries has exactly one primary workbench. The 12 opening-cinematic entries are counted separately. The prose editor also retains 44 structured entries as linked references; they are counted under Choices below.</p>
<table><thead><tr><th scope="col">Workbench</th><th scope="col">Entries</th><th scope="col">Editing</th></tr></thead><tbody>''' + ''.join(table) + '''</tbody></table>
<p>Coverage is checked against the included Japanese TSVs when the site is packaged. Missing entries, duplicate ownership, stale rule snapshots or mismatched Japanese prevent publication.</p>
<h2>Reference entries</h2><p>These entries remain visible because their source exists in the extraction. Editing only a TSV would not safely change their current rendering.</p><ul>''' + ''.join(reference) + '''</ul>
<h2>Text stored as graphics or generated by code</h2><p>The extracted script is not a census of every word drawn by the game. These separate translation assets and renderers are linked here for project work; this website does not export artwork changes.</p><ul>''' + art + '''</ul>
<h2>Rule sources</h2><p>The browser checks the approved font, bank-specific codec, source scanners, staging buffers and measured layout. Item suffixes, floor prefixes, shared help expansions, known item-result messages, seal buffers and condition allocations are checked together. ROM placement, other runtime producer values and visual acceptance still require the project build and game checks.</p><ul>''' + evidence + '''</ul><p><a href="./">← Back to workbenches</a></p></main></body></html>
''')


def validate_row(record, text, data, edits=None):
    """Independent Python oracle: encode and measure with the actual build tools."""
    edits = edits or {}; errors, metrics = [], []
    p = record['profile']; font = dotfont.load_approved()
    if not record['editable']:
        return {'errors': ['This reference entry cannot be edited.'] if text != record['current'] else [], 'lines': []}
    try:
        if not text.strip() or len(text) > 40000 or re.search(r'[\t\r\n]', text):
            raise ValueError('Use nonempty text, at most 40,000 characters, without literal tabs or newlines.')
        if p['kind'] == 'cinematic':
            event = next(e for e in intro.EVENTS if e['id'] == record['key'])
            pages = intro._split_controls(text, event)
            for box, (page, slots) in enumerate(zip(pages, p['slots'])):
                wrapped = []
                for segment in page.split('<br>'): wrapped.extend(intro._wrap_segment(segment, font, event))
                if len(wrapped) != slots: errors.append('Fill exactly %d line(s) on page %d.' % (slots, box + 1))
                for row, line in enumerate(wrapped): metrics.append({'box': box, 'row': row, 'extent': font.text_extent(line), 'cells': len(line), 'buffer': len(line)})
            return {'errors': errors, 'lines': metrics}
        controls = re.findall(r'<[^>]+>', text)
        flexible = p['kind'] == 'descriptions'
        keep = lambda ts: [t for t in ts if not (flexible and t == '<br>')]
        if keep(controls) != keep(record['controls']):
            errors.append('Keep the required controls, arguments, raw bytes and their order. Only description line breaks may move.')
        prefix = re.match(r'^(?:<[^>]+>)+', record['current'])
        if prefix and not text.startswith(prefix[0]):
            errors.append('Keep the original leading controls before the text.')
        if not flexible:
            for before, after in zip(re.split(r'<br>|<brk>', record['current']), re.split(r'<br>|<brk>', text)):
                prefix = re.match(r'^ *(?:<[^>]+>)+', before)
                if prefix and not after.startswith(prefix[0]):
                    errors.append('Keep each line\'s leading controls and choice cursor before its label.')
        spaces = [list((re.match(r'^ *', s)[0], re.search(r' *$', s)[0])) for s in re.split(r'<br>|<brk>', text)]
        if (spaces != record['spaces'] if not flexible else text != text.strip()):
            errors.append('Preserve the structural leading and trailing spaces on each line.')
        errors.extend(detail for _, detail in lint_en.check_one(record['jp'], text, record['bank']))
        native = textlayout.renderer_text(text, bytes([0]) if p['indent'] else b'')
        encoded = build.encode_en(native, record['bank'])
        source_costs = dialogue.floor_widths() if p['sourceCosts'] == 'floor' else dialogue.production_widths()
        pixel_costs = dialogue.dot_production_widths(font)
        if p['sourceCosts'] == 'help':
            lookup = {r['key']: r for r in data['records']}
            fragments = {i: build.encode_en(edits.get(loc, lookup[loc]['current']), 11) for i, loc in enumerate(data['cf0'])}
            cells = {i: dialogue.Line(value, '', 0, 0, 11).cells(dialogue.production_widths()) for i, value in fragments.items()}
            source_costs = dialogue.help_widths(cf0=cells)
            pixel_costs = dialogue.dot_help_widths(font, fragments)
        for line in dialogue.split_lines(encoded, record['bank']):
            cells = line.cells(source_costs)
            body = line.data[1:] if p['rawPrefix'] else line.data
            extent = dialogue.dot_metrics(body, font, record['bank'], pixel_costs)[1]
            body_extent = extent
            # Runtime menu budgets exclude the external cursor; descriptor widths include it.
            if p['rawPrefix'] and record['loc'].startswith('31:'): extent += 8
            if p['fixed']: extent = len(line.data) * 8
            if p.get('log'):
                extent += max(font.advances[str(n)] for n in range(10)) + 36; cells += 7
            buffer = dialogue.buffer_bytes(line.data, widths=source_costs, bank=record['bank'])
            metrics.append({'box': line.box, 'row': line.row, 'extent': extent, 'cells': cells, 'buffer': buffer})
            if p['pixels'] is not None and extent > p['pixels']: errors.append('Line exceeds %d painted pixels.' % p['pixels'])
            if p['cells'] is not None and cells > p['cells']: errors.append('Line exceeds %d source glyphs.' % p['cells'])
            if line.row >= p['rows']: errors.append('Too many lines on a page.')
            if p['tileCap'] and (body_extent + 7) // 8 > p['tileCap']: errors.append('Line exceeds its %d-tile allocation.' % p['tileCap'])
        if p['buffer'] and dialogue.buffer_bytes(encoded, scope=p['bufferScope'], widths=source_costs, bank=record['bank']) >= p['buffer']:
            errors.append('Staged text exceeds the %d-byte cleared buffer.' % p['buffer'])
        if p.get('item'):
            for suffix in suffixes(record):
                if font.text_extent(native + suffix) > 128 or len(native + suffix) > 18:
                    errors.append('Item name with runtime suffix exceeds 128 pixels or 18 source glyphs.'); break
        if p.get('floorPrefix'):
            for n in range(1, 51):
                variant = '%2dF ' % n + native
                if font.text_extent(variant) > 88 or len(variant) > 19:
                    errors.append('Place name with floor prefix exceeds 88 pixels or 19 source glyphs.'); break
    except (ValueError, KeyError, SystemExit) as exc:
        errors.append(str(exc))
    return {'errors': list(dict.fromkeys(errors)), 'lines': metrics}


def validate_all(data, edits):
    records = {r['key']: r for r in data['records']}
    errors = {}
    # A changed fragment can invalidate an unchanged consumer, so check the merged catalogue.
    for key, row in records.items():
        result = validate_row(row, edits.get(key, row['current']), data, edits)
        if result['errors']: errors[key] = result['errors']
    font = dotfont.load_approved()
    def fail(keys, message):
        for key in keys: errors.setdefault(key, []).append(message)
    conditions, names, items, seals = [], [], [], []
    for key, row in records.items():
        value = edits.get(key, row['current'])
        if 'nameClass' in row: names.append((row, value))
        if row['subject'] == 'conditions':
            try: conditions.append(((font.text_extent(value) + 7) // 8, key))
            except KeyError: pass
        if row['profile'].get('item'):
            try:
                peak = max((font.text_extent(value + suffix), len(value + suffix), value + suffix) for suffix in suffixes(row))
                items.append((row, peak))
            except KeyError: pass
        if row['subject'] == 'seals':
            try: seals.append((len(build.encode_en(value, row['bank'])) + 1, key))
            except ValueError: pass
    top = sorted(conditions, reverse=True)[:5]
    if sum(n for n, _ in top) > 57: fail([k for _, k in top], 'The five widest condition rows exceed the 57-tile primary allocation.')
    for row, value in names:
        for other, other_value in names:
            if other['key'] >= row['key']: continue
            if row['jp'] == other['jp'] and value != other_value: fail([row['key'], other['key']], 'Duplicate Japanese names must have the same translation.')
            if row['jp'] != other['jp'] and value == other_value: fail([row['key'], other['key']], 'Different Japanese names must remain distinguishable.')
    for loc in (fontaudit.EQUIP_MESSAGE_LOC, fontaudit.HERB_MESSAGE_LOC):
        template = edits.get(loc, records[loc]['current']).removeprefix('<cE0:46>')
        for row, peak in items:
            if loc == fontaudit.HERB_MESSAGE_LOC and not row['herb']: continue
            value = edits.get(row['key'], row['current']) if loc == fontaudit.HERB_MESSAGE_LOC else peak[2]
            expanded = template.replace('<cE3>', value)
            try:
                if font.text_extent(expanded) > 144 or len(expanded) > 30:
                    fail([loc, row['key']], f"{loc}: expanded item message exceeds 144 pixels or 30 source glyphs.")
            except KeyError: pass
    if items and seals:
        top_seals = sorted(seals, reverse=True)[:4]
        largest_item = max(items, key=lambda item: item[1][1])
        if largest_item[1][1] + 1 + sum(n for n, _ in top_seals) >= 120:
            fail([largest_item[0]['key']] + [k for _, k in top_seals], 'Item name plus four seals exceeds the shared 120-byte buffer.')
    return errors


def parse_edits(text):
    if len(text.encode()) > 2_000_000: raise ValueError('TSV exceeds 2 MB')
    metadata, bases, edits = {}, {}, {}
    for n, line in enumerate(text.lstrip('\ufeff').splitlines(), 1):
        if not line: continue
        fields = line.split('\t')
        if line.startswith('# '):
            key = fields[0][2:]
            if key == 'key' and fields == ['# key', 'english']: continue
            if key == 'base' and len(fields) == 3 and fields[1] not in bases: bases[fields[1]] = fields[2]
            elif key in ('format', 'revision', 'rules') and len(fields) == 2 and key not in metadata: metadata[key] = fields[1]
            else: raise ValueError(f'Invalid/duplicate metadata on line {n}')
        elif len(fields) == 2 and fields[0] not in edits: edits[fields[0]] = fields[1]
        else: raise ValueError(f'Invalid/duplicate TSV row on line {n}')
    if metadata.get('format') != FORMAT or not metadata.get('revision') or not metadata.get('rules') or not edits or set(bases) != set(edits):
        raise ValueError('Missing or incompatible TSV metadata')
    return metadata, bases, edits


def replace_column(text, edits, column):
    found, result = set(), []
    for raw in text.splitlines(keepends=True):
        fields = raw.rstrip('\r\n').split('\t')
        if fields[0] in edits:
            if fields[0] in found or len(fields) <= column: raise ValueError('Duplicate or malformed project row')
            found.add(fields[0]); fields[column] = edits[fields[0]]
            result.append('\t'.join(fields) + ('\r\n' if raw.endswith('\r\n') else '\n'))
        else: result.append(raw)
    if found != set(edits): raise ValueError('Edited address missing from destination')
    return ''.join(result)


def prepare_import(text, prose_text=None):
    data = catalogue(); metadata, bases, edits = parse_edits(text)
    if metadata['rules'] != data['rulesRevision']: raise ValueError('Rules changed; review edits in the current site')
    records = {r['key']: r for r in data['records']}
    for key in edits:
        if key not in records or not records[key]['editable'] or bases[key] != records[key]['base']: raise ValueError(f'{key}: unknown/reference entry or changed project baseline')
    errors = validate_all(data, edits)
    if errors: raise ValueError(json.dumps(errors, indent=2))
    changes = {k: v for k, v in edits.items() if v != records[k]['current']}
    patches = {'en': {}, 'glossary': {}, 'prose_draft': {}, 'intro': {}}
    existing_en = lint_en.load_en(str(ROOT / 'script/en.tsv'))
    for key, value in changes.items():
        dest = records[key]['destination']
        if dest == 'draft': patches['prose_draft'][key] = '=' + value; patches['en'][key] = value
        else: patches[dest][key] = value.strip() if dest == 'glossary' else value
        if dest == 'glossary' and key in existing_en: patches['en'][key] = value
    if prose_text is not None:
        # A terminology rename may touch both a name and ordinary dialogue. Validate
        # the prose against its own wrapper/base, then lint the two downloads together.
        prose_data = prose_editor.catalogue()
        meta, prose_bases, prose_edits = prose_editor.parse_edits(prose_text)
        if meta.get('rules') != prose_data['rulesRevision']: raise ValueError('Prose rules changed; review the current prose editor')
        prose_rows = {r['loc']: r for r in prose_data['records']}
        native = prose_editor.read_manifest()
        for loc, value in prose_edits.items():
            row = prose_rows.get(loc)
            if not row or prose_bases[loc] != row['base']: raise ValueError(f'{loc}: prose baseline changed')
            compiled, _ = prose_editor.compile_draft(row, value, native[loc], prose_data)
            if value != row['draft']:
                if loc in patches['en']: raise ValueError(f'{loc}: downloads contain overlapping edits')
                patches['en'][loc] = compiled; patches['prose_draft'][loc] = value; changes[loc] = value
    outputs = {}
    for name, values in patches.items():
        if not values: continue
        path = ROOT / 'script' / (name + '.tsv'); before = path.read_text()
        outputs[path] = (before, replace_column(before, values, {'glossary': 3, 'intro': 7}.get(name, 1)))
    # English terminology and the complete merged source must agree before application.
    with tempfile.TemporaryDirectory(prefix='shiren-workbench-') as directory:
        directory = Path(directory)
        for name in ('en', 'glossary', 'intro'):
            path = ROOT / 'script' / (name + '.tsv')
            (directory / path.name).write_text(outputs.get(path, ('', path.read_text()))[1])
        for command in ([sys.executable, 'tools/lint_en.py', '--en', str(directory / 'en.tsv'), '--glossary', str(directory / 'glossary.tsv')],
                        [sys.executable, 'tools/fontaudit.py', '--en', str(directory / 'en.tsv'), '--glossary', str(directory / 'glossary.tsv')]):
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            if result.returncode: raise ValueError(result.stdout + result.stderr)
    return changes, outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('export')
    sub.add_parser('check')
    imp = sub.add_parser('import'); imp.add_argument('tsv', type=Path); imp.add_argument('--apply', action='store_true')
    imp.add_argument('--prose-edits', type=Path, help='validate/apply an ordinary-prose download in the same transaction, for coordinated terminology changes')
    args = parser.parse_args()
    if args.command == 'import':
        changes, outputs = prepare_import(args.tsv.read_text(), args.prose_edits.read_text() if args.prose_edits else None)
        if args.apply: prose_editor.apply_import(outputs)
        print(f"{'Applied' if args.apply else 'Validated'} {len(changes)} changes in {len(outputs)} files. Run the project build and game checks before release.")
    else:
        data = catalogue(); errors = validate_all(data, {})
        if errors: raise ValueError(json.dumps(errors, ensure_ascii=False, indent=2))
        if args.command == 'export':
            CATALOG.parent.mkdir(parents=True, exist_ok=True)
            CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
            (ROOT / 'site/data/intro.tsv').write_bytes((ROOT / 'script/intro.tsv').read_bytes())
            write_navigation(data)
        print(f"Covered {data['extractedCount']} extracted entries and {data['cinematicCount']} cinematic entries; {len(data['records'])} new workbench records.")


if __name__ == '__main__':
    main()
