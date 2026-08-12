#!/usr/bin/env python3
"""Audit the translated corpus against the approved proportional-font advances.

The production build uses the approved proportional font loaded by ``dotfont.py``.
This tool independently measures its painted pixels while preserving ROM-derived geometry:

* composer dialogue owns 18 tiles = 144px per line;
* extracted bank-31 rows own ``box.width * 8`` pixels (including a raw cursor cell);
* item descriptions, equipment seals, and clear-condition rows use the proportional menu
  drawer's measured 18-tile / 144px no-cursor shape;
* legacy glossary substitution reservations remain labelled historical warnings, not
  physical limits or reasons to shorten English;
* current item variants enumerate every signed equipment value from -99 through +99 and
  every two-digit staff/pot count, then measure the widest suffix against the 128px item
  payload and convert it to its painted allocator footprint.

Strings without measured per-screen geometry are never called safe.  They are listed as
``UNPROVEN`` even when their standalone pixel width is small.
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import codec                                                        # noqa: E402
import dialogue_preview as dialogue                                  # noqa: E402
import dotfont                                                       # noqa: E402
import lint_en                                                       # noqa: E402
import menuvwf                                                       # noqa: E402
from latinfont import EN_CODES                                       # noqa: E402


COMPOSER_PX = 18 * 8
OLD_PEN_PX = 6
LEGACY_SUBST_RESERVATION_PX = {
    0xE2: dialogue.NAME_CAP * OLD_PEN_PX,
    0xE3: dialogue.ITEM_CAP * OLD_PEN_PX,
    0xEA: dialogue.PLAYER_NAME * OLD_PEN_PX,
    0xE4: dialogue.DIGITS[0xE4] * OLD_PEN_PX,
    0xE5: dialogue.DIGITS[0xE5] * OLD_PEN_PX,
    0xE6: dialogue.DIGITS[0xE6] * OLD_PEN_PX,
}

# The measured item-list row staged for menu VWF has two raw cells before the name:
# equipment marker/border state and cursor cell.  The descriptor is 18 cells wide.
ITEM_PREFIX_CELLS = 2
ITEM_TEXT_PX = (18 - ITEM_PREFIX_CELLS) * 8

MAIN_MENU_LOCS = {
    '11:$53FA', '11:$5401', '11:$5407', '11:$540B', '11:$5412',
    '11:$5418', '11:$541E', '11:$5425', '11:$542A', '11:$542F',
    '11:$5435', '11:$543A', '11:$5440', '11:$5444', '11:$544C',
}
ACTION_MENU_LOCS = {
    '30:$7EC3', '30:$7EC6', '30:$7EC9', '30:$7ECC', '30:$7ECF',
    '30:$7ED4', '30:$7ED9', '30:$7EDD', '30:$7EE0', '30:$7EE5',
    '30:$7EE8', '30:$7EEB', '30:$7EF0', '30:$7EF3', '30:$7EF7',
    '30:$7EFE', '30:$7F02', '30:$7F08',
}
TITLE_MENU_LOCS = {
    '11:$5330', '11:$533B', '11:$5344', '11:$534D', '11:$5355',
    '11:$535E', '11:$536E', '11:$5374', '11:$5387', '11:$5398',
}
# Measured by menuresidency.prefix_for from the live bank-31 drawer.  The descriptor
# width includes the one raw cursor cell, so the proportional text owns the remainder.
RUNTIME_MENU_PX = {
    **{loc: (4 * 8, 'main x0 y0 w5, one raw cell') for loc in MAIN_MENU_LOCS},
    **{loc: (4 * 8, 'action x13 w5, one raw cell') for loc in ACTION_MENU_LOCS},
    **{loc: (10 * 8, 'title/file x0 y1 w11, one raw cell')
       for loc in TITLE_MENU_LOCS},
    # Box 45 is a two-row popup at x3 with descriptor width 6. Its row-1 Pass label
    # uses the proportional cells after the raw cursor column; startspill verifies
    # its exact static pool and the settled two-plane result.
    '11:$544C': (5 * 8, 'Rank/Pass popup x3 w6, one raw cell'),
    # 4:$4FAE copies these at absolute shadow $C3C9 (row 6, column 9). The build patches
    # 4:$4FE6-$4FE8 to 6/4/6 leading cells, right-aligning Easy/Normal/Hard at column 18.
    # The listed spans extend to the screen edge; pathspill separately asserts the exact
    # fixed-cell destination and preserved column-19 box border.
    '11:$53A1': (5 * 8, 'absolute status label: 6-cell prefix at column 9'),
    '11:$53A6': (7 * 8, 'absolute status label: 4-cell prefix at column 9'),
    '11:$53AA': (5 * 8, 'absolute status label: 6-cell prefix at column 9'),
    '11:$5459': (9 * 8, 'absolute status label: 2-cell prefix at column 9'),
    # 4:$4AE0 copies this label to shadow $C4A1 (row 13, column 1), leaving 19 cells.
    '4:$4AFE': (19 * 8, 'absolute status label at shadow $C4A1'),
    # Save-summary box 26 (x4,y4,w14) is built by 4:$68A3.  Once its 16-source-character
    # Log/name header is consumed as one VWF row, the third logical row contains the
    # place name selected by 4:$6941-$698B from table entries $0E-$15.  The proportional
    # summary allocator gives that row its measured final eight-tile slice.
    **{loc: (8 * 8, 'save-summary box 26 row 2; staged at $C62D, 8-tile slice')
       for loc in ('11:$53B1', '11:$53B9', '11:$53C1', '11:$53CB',
                   '11:$53D4', '11:$53DC', '11:$53E5', '11:$53ED')},
}
LOG_PREFIX_LOC = '11:$537F'
# V3 composes the words on both sides while deliberately retaining box 2's divider tile.
# No other non-Dot code is admitted by this exception.
STRUCTURED_BOX_RAW = {2: {0xB6}}
CONDITION_SOURCE_CAP = dialogue.HELP_WIDTH
CONDITION_POOL_RUNS = (57, 11, 4)
EQUIP_MESSAGE_LOC = '13:$465E'
HERB_MESSAGE_LOC = '13:$46AC'
HERB_ITEM_RANGE = (0x4232, 0x42E3)
HERB_APPEARANCE_RANGE = (0x472C, 0x47EE)


def _cost(value, arg):
    if isinstance(value, dict):
        return value.get(arg[0], 0) if arg else 0
    return value


def pixels(data, font, bank=None, controls=None):
    """Return ``(painted extent, unknown codes)`` for encoded renderer input."""
    _advance, extent, unknown = dialogue.dot_metrics(data, font, bank, controls)
    return extent, unknown


def uniform_pixels(data, bank=None, controls=None):
    """The installed renderer's 6px measurement, for before/after warning context."""
    controls = controls or {}
    arity = codec.arity_for(bank)
    total, i = 0, 0
    while i < len(data):
        code = data[i]
        if codec.CONTROL_MIN <= code <= codec.CONTROL_MAX:
            n = arity.get(code, 0)
            total += _cost(controls.get(code, 0), data[i + 1:i + 1 + n])
            i += n
        elif code not in codec.COMBINING:
            total += OLD_PEN_PX
        i += 1
    return total


def load_translations(manifest, en_path, glossary_path):
    """Mirror build.py's glossary-first, en-last translation precedence."""
    by_loc = {r['loc']: r for r in manifest['strings']}
    translated, source, unknown = {}, {}, []

    def read(path, columns, label):
        for number, raw in enumerate(open(path, encoding='utf-8'), 1):
            line = lint_en.spreadsheet_line(raw)
            if not line or line.startswith('#'):
                continue
            fields = line.split('\t', columns - 1)
            if len(fields) < columns:
                continue
            loc, text = fields[0].strip(), fields[-1]
            if not text.strip():
                continue
            row = by_loc.get(loc)
            if row is None:
                unknown.append((path, number, loc))
                continue
            translated[row['id']] = text
            source[row['id']] = label

    if glossary_path and os.path.exists(glossary_path):
        read(glossary_path, 4, 'glossary')
    read(en_path, 2, 'en')
    return translated, source, unknown


def encoded_translations(strings, translated):
    """Encode with the same leading-space preservation rule as build.py."""
    import build

    encoded, errors = {}, []
    for row in strings:
        if row['id'] not in translated:
            continue
        original = bytes.fromhex(row['hex'])
        lead = original[:1] == bytes([EN_CODES[' ']])
        try:
            encoded[row['id']] = build.encode_en(
                (' ' if lead else '') + translated[row['id']], row['bank'])
        except ValueError as exc:
            errors.append((row, str(exc)))
    return encoded, errors


def box_widths(path):
    widths = {}
    if not os.path.exists(path):
        return widths
    for raw in open(path, encoding='utf-8'):
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        widths[int(fields[0], 0)] = int(fields[3], 0)
    return widths


def display_text(text, limit=68):
    text = text.replace('\n', ' ')
    return repr(text if len(text) <= limit else text[:limit - 3] + '...')


def print_ranked(title, rows, limit, formatter):
    print('%s: %d' % (title, len(rows)))
    for row in rows[:limit]:
        print('  ' + formatter(row))
    if len(rows) > limit:
        print('  ... %d more' % (len(rows) - limit))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--script', default=os.path.join(ROOT, 'script', 'script.json'))
    parser.add_argument('--en', default=os.path.join(ROOT, 'script', 'en.tsv'))
    parser.add_argument('--glossary', default=os.path.join(ROOT, 'script', 'glossary.tsv'))
    parser.add_argument('--geometry',
                        default=os.path.join(ROOT, 'script', 'box_geometry.tsv'))
    parser.add_argument('--font-spec',
                        help='review an alternate font spec without changing production')
    parser.add_argument('--details', type=int, default=12,
                        help='maximum rows shown in each detailed section')
    parser.add_argument('--strict-unproven', action='store_true',
                        help='also fail when translated strings lack measured geometry')
    args = parser.parse_args()

    font = (dotfont.load_approved(args.font_spec) if args.font_spec
            else dotfont.load_approved())
    manifest = json.load(open(args.script, encoding='utf-8'))
    strings = manifest['strings']
    by_id = {row['id']: row for row in strings}
    translated, sources, unknown_locs = load_translations(
        manifest, args.en, args.glossary)
    encoded, encode_errors = encoded_translations(strings, translated)
    overrides = box_widths(args.geometry)

    glossary = lint_en.load_glossary(args.glossary)
    glossary_by_loc = {entry['loc']: entry for entry in glossary}
    glossary_ids = {row['id'] for row in strings if row['loc'] in glossary_by_loc}

    # Unknown producers use their narrowest approved glyph for the "cannot fit under any
    # value" failure class. The player-name producer is settled and instead uses its real
    # six-character maximum. Declared legacy caps remain a separate warning class.
    letter_floor = min(font.advances[ch] for ch in EN_CODES if ch.isalpha())
    digit_floor = min(font.advances[str(n)] for n in range(10))
    subst_floor = {code: (digit_floor if code in dialogue.DIGITS else letter_floor)
                   for code in dialogue.SUBST_DOC}
    subst_floor[0xEA] = dialogue.dot_player_name_width(font)

    # The 13 fixed <cF0:xx> fragments are real inline text on the help path.
    cf0_pixels = {}
    for index, loc in enumerate(dialogue.CF0_LOCS):
        row = next((r for r in strings if r['loc'] == loc), None)
        if row and row['id'] in encoded:
            cf0_pixels[index] = dialogue.dot_metrics(
                encoded[row['id']], font, row['bank'])[:2]

    composer_lines = []
    composer_over = []
    composer_cap = []
    help_lines = []
    help_over = []
    box_rows = []
    box_over = []
    box_raw = []
    structured_box_rows = []
    runtime_menu = []
    runtime_menu_over = []
    runtime_menu_source_over = []
    runtime_menu_raw = []
    condition_rows = []
    old_cap_warnings = set()
    classified = set()

    for ident, data in encoded.items():
        row = by_id[ident]
        if dialogue.is_dialogue(row):
            classified.add(ident)
            help_path = dialogue.is_help(row)
            floor_controls = dict(subst_floor)
            cap_controls = dict(LEGACY_SUBST_RESERVATION_PX)
            cap_controls[0xEA] = dialogue.dot_player_name_width(font)
            if help_path:
                floor_controls[0xF0] = cf0_pixels
                cap_controls[0xF0] = cf0_pixels
            for line in dialogue.split_lines(data, row['bank']):
                floor_px, raw_codes = pixels(line.data, font, row['bank'], floor_controls)
                cap_px, _ = pixels(line.data, font, row['bank'], cap_controls)
                record = (floor_px, cap_px, row, line, raw_codes)
                if help_path:
                    help_lines.append(record)
                    if floor_px > COMPOSER_PX:
                        help_over.append(record)
                else:
                    composer_lines.append(record)
                    key = (row['id'], line.box, line.row)
                    old_floor_px = uniform_pixels(
                        line.data, row['bank'],
                        {code: OLD_PEN_PX for code in dialogue.SUBST_DOC})
                    old_cap_px = uniform_pixels(
                        line.data, row['bank'], LEGACY_SUBST_RESERVATION_PX)
                    if old_floor_px <= COMPOSER_PX < old_cap_px:
                        old_cap_warnings.add(key)
                    if floor_px > COMPOSER_PX:
                        composer_over.append(record)
                    elif cap_px > COMPOSER_PX:
                        composer_cap.append(record)
            continue

        if row.get('box'):
            classified.add(ident)
            width = overrides.get(row['box']['id'], row['box']['width'])
            budget = width * 8
            # A leading source-space is a cursor slot. Boxes 8/14/17 also preserve their
            # measured nonzero first cell raw because the live cursor overwrites it after
            # the row draw. Either kind consumes a full tile rather than a Dot advance.
            raw_prefix = bool(data and (data[0] == EN_CODES[' '] or
                                        row['box']['id'] in menuvwf.ROM_RAW_PREFIX_BOXES))
            body = data[1:] if raw_prefix else data
            used, raw_codes = pixels(body, font, row['bank'])
            structured = raw_codes & STRUCTURED_BOX_RAW.get(row['box']['id'], set())
            raw_codes -= structured
            used += 8 if raw_prefix else 0
            record = (used, budget, row, raw_codes, raw_prefix)
            box_rows.append(record)
            if structured:
                structured_box_rows.append(record)
            if raw_codes:
                box_raw.append(record)
            elif used > budget:
                box_over.append(record)

    for ident, data in encoded.items():
        row = by_id[ident]
        geometry = RUNTIME_MENU_PX.get(row['loc'])
        if dialogue.is_clear_condition(row):
            geometry = (18 * 8, 'proportional clear-condition box 44 w18; five rows at 4:$79E4')
        elif row['loc'] == LOG_PREFIX_LOC:
            geometry = (14 * 8, 'file-log detail x4 y4 w14; digit + label + player name')
        if geometry is None:
            continue
        used, raw_codes = pixels(data, font, row['bank'])
        budget, evidence = geometry
        if row['loc'] == LOG_PREFIX_LOC:
            used += max(font.advances[str(n)] for n in range(10))
            used += LEGACY_SUBST_RESERVATION_PX[0xEA]
        source = dialogue.Line(data, 'end', 0, 0, row['bank']).cells(
            dialogue.floor_widths())
        if row['loc'] == LOG_PREFIX_LOC:
            source += 1 + dialogue.PLAYER_NAME       # selected log digit + live name
        record = (used, budget, row, raw_codes, evidence)
        runtime_menu.append(record)
        classified.add(ident)
        if used > budget:
            runtime_menu_over.append(record)
        # Box 44 shares the no-prefix 21-glyph proportional scanner with help/seals.
        # Ordinary menu/item rows retain their independently measured 18-glyph scanner.
        source_cap = (CONDITION_SOURCE_CAP if dialogue.is_clear_condition(row)
                      else lint_en.ITEM_ROW_CELLS)
        if source > source_cap:
            runtime_menu_source_over.append((source, source_cap, row,
                                              translated[row['id']], evidence))
        if raw_codes:
            runtime_menu_raw.append(record)
        if dialogue.is_clear_condition(row):
            condition_rows.append(((used + 7) // 8, source, row,
                                   translated[row['id']]))

    # Shared help fragments have no standalone screen geometry, but every use was
    # measured inline above through <cF0:xx>.  Do not count them as unproven twice.
    cf0_ids = {row['id'] for row in strings if row['loc'] in dialogue.CF0_LOCS}
    classified.update(cf0_ids)

    # Glossary names are runtime substitutions and item-list rows rather than standalone
    # composer strings, so they get their own reports. `name_over` compares only with the
    # legacy reservation and is therefore a review warning. `item_variants` is physical:
    # it adds the actual worst ordinary suffix for each item-table class and measures the
    # painted extent accepted by the menu allocator.
    name_rows, name_over, counter_over = [], [], []
    widest_digit = max(font.advances[str(n)] for n in range(10))
    counter_px = font.advances['['] + 2 * widest_digit + font.advances[']']
    for entry in glossary:
        row = next((r for r in strings if r['loc'] == entry['loc']), None)
        if row is None or row['id'] not in translated:
            continue
        text = translated[row['id']]
        try:
            used = font.text_width(text)
        except KeyError:
            # Encoding already reports this, so do not create a misleading second width.
            continue
        cap = (dialogue.ITEM_CAP if entry['cls'] in ('item', 'appearance')
               else dialogue.NAME_CAP) * OLD_PEN_PX
        record = (used, cap, row, entry, text)
        name_rows.append(record)
        if used > cap:
            name_over.append(record)
        if lint_en.carries_counter(text) and used + counter_px > ITEM_TEXT_PX:
            counter_over.append((used + counter_px, ITEM_TEXT_PX, row, entry, text))

    item_variants, item_variant_over, item_source_over = [], [], []
    item_entries = [entry for entry in glossary if entry['cls'] == 'item']
    if len(item_entries) != 145:
        raise SystemExit('fontaudit: expected the 145-entry item-name table, found %d; '
                         'the enhancement/counter class boundaries must be re-censused'
                         % len(item_entries))
    enhancement_suffixes = [sign + str(value)
                            for sign in ('+', '-') for value in range(1, 100)]
    counter_suffixes = ['[%d]' % value for value in range(1, 100)]
    def suffix_score(suffix):
        return font.text_extent(suffix), font.text_width(suffix)

    enhancement_peak = max(map(suffix_score, enhancement_suffixes))
    counter_peak = max(map(suffix_score, counter_suffixes))
    widest_enhancements = [suffix for suffix in enhancement_suffixes
                            if suffix_score(suffix) == enhancement_peak]
    widest_counters = [suffix for suffix in counter_suffixes
                       if suffix_score(suffix) == counter_peak]
    # Keep one deterministic representative for fixtures while reporting the tie count.
    widest_enhancement = max(widest_enhancements)
    widest_counter = max(widest_counters)
    for index, entry in enumerate(item_entries):
        row = next((r for r in strings if r['loc'] == entry['loc']), None)
        if row is None or row['id'] not in translated:
            continue
        bare = translated[row['id']]
        suffix = (widest_enhancement if index < 34 else
                  widest_counter if lint_en.carries_counter(bare) else '')
        variant = bare + suffix
        try:
            advance = font.text_width(variant)
            extent = font.text_extent(variant)
        except KeyError:
            continue
        tiles = (extent + 7) // 8
        record = (extent, advance, tiles, len(variant), row, entry, variant)
        item_variants.append(record)
        if extent > ITEM_TEXT_PX:
            item_variant_over.append(record)
        # This is the current item-row scanner contract, distinct from pixel fit.
        if len(variant) > lint_en.ITEM_ROW_CELLS:
            item_source_over.append(record)

    # The weapon/shield result message can receive an item name with its live signed
    # enhancement.  Measure every current worst-case item-row variant, plus every
    # unidentified appearance name, against the dialogue composer's real limits.
    equip_message_row = next((row for row in strings
                              if row['loc'] == EQUIP_MESSAGE_LOC), None)
    equip_results = []
    equip_result_over = []
    if equip_message_row and equip_message_row['id'] in translated:
        template = translated[equip_message_row['id']]
        selector = '<cE0:46>'
        if not template.startswith(selector):
            raise SystemExit('fontaudit: %s must retain its %s selector, found %r'
                             % (EQUIP_MESSAGE_LOC, selector, template))
        template = template[len(selector):]
        if template.count('<cE3>') != 1:
            raise SystemExit('fontaudit: %s must contain exactly one <cE3>, found %r'
                             % (EQUIP_MESSAGE_LOC, template))
        equip_names = [(record[6], record[4], record[5]) for record in item_variants]
        for entry in (entry for entry in glossary if entry['cls'] == 'appearance'):
            row = next((candidate for candidate in strings
                        if candidate['loc'] == entry['loc']), None)
            if row is not None and row['id'] in translated:
                equip_names.append((translated[row['id']], row, entry))
        for item_name, row, entry in equip_names:
            expanded = template.replace('<cE3>', item_name)
            try:
                extent = font.text_extent(expanded)
            except KeyError:
                continue
            record = (extent, len(expanded), row, entry, expanded)
            equip_results.append(record)
            if extent > COMPOSER_PX or len(expanded) > dialogue.WIDTH:
                equip_result_over.append(record)

    # The herb action stages a generic <cE3>, but that producer can only supply a herb
    # or seed name (identified item table) or a colour-based herb appearance
    # (unidentified item table).  Measure the real reachable domain so wording such as
    # `Consumed the <cE3>` cannot fit with one herb and silently clip with another.  Do
    # not charge arbitrary equipment variants: those cannot enter this action path.
    herb_message_row = next((row for row in strings
                             if row['loc'] == HERB_MESSAGE_LOC), None)
    herb_consumption = []
    herb_consumption_over = []
    if herb_message_row and herb_message_row['id'] in translated:
        template = translated[herb_message_row['id']]
        if template.count('<cE3>') != 1:
            raise SystemExit('fontaudit: %s must contain exactly one <cE3>, found %r'
                             % (HERB_MESSAGE_LOC, template))
        for entry in glossary:
            address = int(entry['loc'].split('$', 1)[1], 16)
            reachable = ((entry['cls'] == 'item' and
                          HERB_ITEM_RANGE[0] <= address <= HERB_ITEM_RANGE[1]) or
                         (entry['cls'] == 'appearance' and
                          HERB_APPEARANCE_RANGE[0] <= address <= HERB_APPEARANCE_RANGE[1]))
            if not reachable:
                continue
            row = next((candidate for candidate in strings
                        if candidate['loc'] == entry['loc']), None)
            if row is None or row['id'] not in translated:
                continue
            expanded = template.replace('<cE3>', translated[row['id']])
            try:
                extent = font.text_extent(expanded)
            except KeyError:
                continue
            record = (extent, len(expanded), row, entry, expanded)
            herb_consumption.append(record)
            if extent > COMPOSER_PX or len(expanded) > dialogue.WIDTH:
                herb_consumption_over.append(record)

    classified.update(glossary_ids)
    unproven = []
    for ident, data in encoded.items():
        if ident in classified:
            continue
        row = by_id[ident]
        used, raw_codes = pixels(data, font, row['bank'])
        unproven.append((used, row, translated[ident], raw_codes, sources[ident]))
    unproven.sort(key=lambda item: (-item[0], item[1]['loc']))

    composer_lines.sort(key=lambda item: (-item[0], item[2]['loc']))
    composer_over.sort(key=lambda item: (-item[0], item[2]['loc']))
    composer_cap.sort(key=lambda item: (-item[1], item[2]['loc']))
    help_lines.sort(key=lambda item: (-item[0], item[2]['loc']))
    help_over.sort(key=lambda item: (-item[0], item[2]['loc']))
    box_rows.sort(key=lambda item: (-item[0] / item[1], item[2]['loc']))
    box_over.sort(key=lambda item: (-item[0] + item[1], item[2]['loc']))
    runtime_menu.sort(key=lambda item: (-item[0] / item[1], item[2]['loc']))
    runtime_menu_over.sort(key=lambda item: (-item[0] + item[1], item[2]['loc']))
    runtime_menu_source_over.sort(key=lambda item: (-item[0], item[2]['loc']))
    name_rows.sort(key=lambda item: (-item[0], item[2]['loc']))
    name_over.sort(key=lambda item: (-item[0] + item[1], item[2]['loc']))
    item_variants.sort(key=lambda item: (-item[0], item[4]['loc']))
    item_variant_over.sort(key=lambda item: (-item[0], item[4]['loc']))
    item_source_over.sort(key=lambda item: (-item[3], -item[0], item[4]['loc']))
    equip_results.sort(key=lambda item: (-item[0], -item[1], item[2]['loc']))
    equip_result_over.sort(key=lambda item: (-item[0], -item[1], item[2]['loc']))
    herb_consumption.sort(key=lambda item: (-item[0], -item[1], item[2]['loc']))
    herb_consumption_over.sort(key=lambda item: (-item[0], -item[1], item[2]['loc']))

    # Box 44 displays five condition rows.  Its current top-five footprints total 56
    # tiles, so every possible five-row page fits wholly in the 57-tile primary run;
    # this is stronger than assuming a particular page grouping.  Fail if translator
    # edits invalidate that order-independent proof.  The 11- and 4-tile extension runs
    # remain available to the renderer but are not needed for today's corpus.
    condition_rows.sort(key=lambda item: (-item[0], item[2]['loc']))
    condition_top = condition_rows[:5]
    condition_primary_need = sum(item[0] for item in condition_top)
    condition_allocator_over = []
    if len(condition_top) == 5 and condition_primary_need > CONDITION_POOL_RUNS[0]:
        condition_allocator_over.append((condition_primary_need, condition_top))

    print('%s pixel audit' % font.name)
    print('  source SHA-256 verified: %s' % font.spec['source']['sha256'])
    print('  translations: %d encoded (%d glossary entries); %d unknown loc; %d encode error'
          % (len(encoded), len(glossary), len(unknown_locs), len(encode_errors)))
    print('  legacy substitution reservations (warnings, not font limits): '
          'name %dpx, item/count %dpx, player %dpx'
          % (LEGACY_SUBST_RESERVATION_PX[0xE2],
             LEGACY_SUBST_RESERVATION_PX[0xE3],
             LEGACY_SUBST_RESERVATION_PX[0xEA]))
    print()

    print('PROVEN PHYSICAL GEOMETRY')
    print('  composer: %d strings, %d lines, widest enforced-value line %d/%dpx'
          % (len({r[2]['id'] for r in composer_lines}), len(composer_lines),
             composer_lines[0][0] if composer_lines else 0, COMPOSER_PX))
    print('  proportional help/seals: %d strings, %d lines, widest %d/%dpx'
          % (len({r[2]['id'] for r in help_lines}), len(help_lines),
             help_lines[0][0] if help_lines else 0, COMPOSER_PX))
    print('  extracted box rows: %d rows; %d retain non-font raw tile code(s)'
          % (len(box_rows), len(box_raw)))
    print('  structured fixed-cell proportional rows: %d (box-2 divider retained)'
          % len(structured_box_rows))
    print('  measured runtime menu/list labels: %d; widest occupancy %.0f%%'
          % (len(runtime_menu),
             max((100 * row[0] / row[1] for row in runtime_menu), default=0)))
    print('  clear-condition rows: %d proportional; worst any-five %d/%d primary tiles'
          % (len(condition_rows), condition_primary_need, CONDITION_POOL_RUNS[0]))
    print('  shared help fragments: %d measured inline through <cF0:xx>' % len(cf0_ids))
    print('  glossary runtime names: %d; widest %dpx; two-digit counter costs %dpx'
          % (len(name_rows), name_rows[0][0] if name_rows else 0, counter_px))
    if item_variants:
        top_five = sum(row[2] for row in item_variants[:5])
        widest = item_variants[0]
        print('  current item variants: %d; widest signed/count representatives '
              '%s (%d tied) / %s (%d tied); '
              'widest painted %d/%dpx, %d tiles, '
              '%d source chars (%s)'
              % (len(item_variants), widest_enhancement, len(widest_enhancements),
                 widest_counter, len(widest_counters),
                 widest[0], ITEM_TEXT_PX, widest[2], widest[3], widest[6]))
        allocator_tiles = ((menuvwf.POOL_END - menuvwf.POOL_BASE) + 11 + 4)
        print('  five widest current item variants: %d allocator tiles; + four '
              '4-tile verbs = %d/%d'
              % (top_five, top_five + 16, allocator_tiles))
    if equip_results:
        widest_equip = equip_results[0]
        print('  equipment-result substitutions: %d representative names; widest '
              '%d/%dpx, %d/%d source glyphs (%s)'
              % (len(equip_results), widest_equip[0], COMPOSER_PX,
                 widest_equip[1], dialogue.WIDTH, widest_equip[4]))
    if herb_consumption:
        widest_herb = herb_consumption[0]
        print('  herb-consumption substitutions: %d reachable names; widest '
              '%d/%dpx, %d/%d source glyphs (%s)'
              % (len(herb_consumption), widest_herb[0], COMPOSER_PX,
                 widest_herb[1], dialogue.WIDTH, widest_herb[4]))
    print()

    def line_fmt(item, use_cap=False):
        floor_px, cap_px, row, line, raw_codes = item
        value = cap_px if use_cap else floor_px
        suffix = (' raw=' + ','.join('$%02X' % code for code in sorted(raw_codes))
                  if raw_codes else '')
        return '%-11s box %d line %d  %3d/%dpx  %s%s' % (
            row['loc'], line.box + 1, line.row + 1, value, COMPOSER_PX,
            display_text(line.text()), suffix)

    print_ranked('DEFINITE composer overflow (enforced runtime values)', composer_over,
                 args.details, line_fmt)
    print_ranked('LEGACY RESERVATION warning (minimum fits; runtime value may not)',
                 composer_cap, args.details, lambda item: line_fmt(item, True))
    approved_cap_keys = {(item[2]['id'], item[3].box, item[3].row)
                         for item in composer_cap}
    print('  comparison: approved %s %d warning(s), installed uniform-6px %d; %d new'
          % (font.name, len(approved_cap_keys), len(old_cap_warnings),
             len(approved_cap_keys - old_cap_warnings)))
    print_ranked('Proportional help/seal overflow', help_over, args.details,
                 line_fmt)
    print_ranked('Extracted box-row overflow', box_over, args.details,
                 lambda item: '%-11s box %d row %d  %d/%dpx  %s' % (
                     item[2]['loc'], item[2]['box']['id'], item[2]['box']['row'],
                     item[0], item[1], display_text(translated[item[2]['id']])))
    print_ranked('Measured dynamic main/action overflow', runtime_menu_over, args.details,
                 lambda item: '%-11s %3d/%dpx  %s  (%s)' % (
                     item[2]['loc'], item[0], item[1],
                     display_text(translated[item[2]['id']]), item[4]))
    print_ranked('Measured dynamic menu SOURCE-GUARD overflow',
                 runtime_menu_source_over, args.details,
                 lambda item: '%-11s %2d/%d glyphs  %s  (%s)' % (
                     item[2]['loc'], item[0], item[1], display_text(item[3]), item[4]))
    print_ranked('Clear-condition five-row ALLOCATOR overflow',
                 condition_allocator_over, args.details,
                 lambda item: '%d/%d primary tiles: %s' % (
                     item[0], CONDITION_POOL_RUNS[0],
                     ', '.join('%s=%d' % (row[2]['loc'], row[0])
                               for row in item[1])))
    print_ranked('Glossary legacy-reservation review', name_over, args.details,
                 lambda item: '%-11s %-10s %3d/%dpx  %s' % (
                     item[2]['loc'], item[3]['cls'], item[0], item[1],
                     display_text(item[4])))
    print_ranked('Counted item-row overflow (two-digit [NN])', counter_over, args.details,
                 lambda item: '%-11s %3d/%dpx  %s' % (
                     item[2]['loc'], item[0], item[1], display_text(item[4])))
    print_ranked('Current item-variant PHYSICAL overflow (all signed values / [NN])',
                 item_variant_over, args.details,
                 lambda item: '%-11s %3d/%dpx %2d tiles %2d chars  %s' % (
                     item[4]['loc'], item[0], ITEM_TEXT_PX, item[2], item[3],
                     display_text(item[6])))
    print_ranked('Current item-variant SOURCE-GUARD overflow', item_source_over,
                 args.details,
                 lambda item: '%-11s %2d/%d chars %3dpx %2d tiles  %s' % (
                     item[4]['loc'], item[3], lint_en.ITEM_ROW_CELLS,
                     item[0], item[2], display_text(item[6])))
    print_ranked('Equipment-result substitution overflow', equip_result_over,
                 args.details,
                 lambda item: '%-11s %3d/%dpx %2d/%d glyphs  %s' % (
                     item[2]['loc'], item[0], COMPOSER_PX,
                     item[1], dialogue.WIDTH, display_text(item[4])))
    print_ranked('Herb-consumption substitution overflow', herb_consumption_over,
                 args.details,
                 lambda item: '%-11s %3d/%dpx %2d/%d glyphs  %s' % (
                     item[2]['loc'], item[0], COMPOSER_PX,
                     item[1], dialogue.WIDTH, display_text(item[4])))
    print()

    print_ranked('UNPROVEN runtime geometry', unproven, args.details,
                 lambda item: '%-11s bank %-2d standalone=%3dpx source=%-8s %s%s' % (
                     item[1]['loc'], item[1]['bank'], item[0], item[4],
                     display_text(item[2]),
                     (' raw=' + ','.join('$%02X' % code for code in sorted(item[3])))
                     if item[3] else ''))
    if box_raw:
        print()
        print_ranked('RAW-FALLBACK extracted rows (physical fit not proportional approval)',
                     box_raw, args.details,
                     lambda item: '%-11s box %d  %d/%dpx raw=%s  %s' % (
                         item[2]['loc'], item[2]['box']['id'], item[0], item[1],
                         ','.join('$%02X' % code for code in sorted(item[3])),
                         display_text(translated[item[2]['id']])))
    if runtime_menu_raw:
        print()
        print_ranked('RAW-FALLBACK measured runtime rows', runtime_menu_raw, args.details,
                     lambda item: '%-11s %d/%dpx raw=%s  %s' % (
                         item[2]['loc'], item[0], item[1],
                         ','.join('$%02X' % code for code in sorted(item[3])),
                         display_text(translated[item[2]['id']])))

    for path, number, loc in unknown_locs[:args.details]:
        print('UNKNOWN LOC %s:%d %s' % (os.path.relpath(path, ROOT), number, loc))
    for row, error in encode_errors[:args.details]:
        print('ENCODE ERROR %-11s %s' % (row['loc'], error))

    definite = (len(composer_over) + len(help_over) + len(box_over)
                + len(runtime_menu_over) + len(runtime_menu_source_over) + len(counter_over)
                + len(condition_allocator_over)
                + len(item_variant_over) + len(item_source_over)
                + len(equip_result_over)
                + len(herb_consumption_over)
                + len(encode_errors) + len(unknown_locs))
    print()
    print('VERDICT: %d definite physical/source failure(s), %d legacy line-reservation '
          'warning(s), %d legacy glossary review(s), %d translated string(s) still '
          'require runtime geometry measurement.'
          % (definite, len(composer_cap), len(name_over), len(unproven)))
    if definite:
        print('FAIL: do not install the proportional renderer until definite failures are '
              'resolved or proven to stay on a fixed-width path.')
    elif unproven:
        print('BOUNDED PASS: proven classes fit; unproven classes are not approved.')
    else:
        print('PASS: every translated class represented by this manifest fits.')
    return 1 if definite or (args.strict_unproven and unproven) else 0


if __name__ == '__main__':
    sys.exit(main())
