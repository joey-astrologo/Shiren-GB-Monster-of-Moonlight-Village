#!/usr/bin/env python3
"""Generate review-only reflows for dialogue containing the live player name.

The ordinary prose wrapper deliberately charges unknown runtime substitutions their
narrowest possible value.  That is appropriate for an unknown monster/item producer, but
the player name is a settled six-character input contract.  This tool gives that known
case its own audition without changing ``script/en.tsv``:

* find every current line that fails for the widest selectable six-character name;
* reflow the containing strings with the real six-glyph / Dot-pixel cost;
* validate the candidates with both ``Shiren`` and the widest name; and
* write a TSV overlay plus a human-readable Markdown review sheet under ``build/``.

Use the overlay with the normal previewer, for example::

    python3 tools/nameaudition.py
    python3 tools/dialogue_preview.py --en build/player_name_candidates.tsv \
        --player-text Shiren '14:$566D'
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import build as B                                                    # noqa: E402
import dialogue_preview as dialogue                                  # noqa: E402
import dotfont                                                       # noqa: E402
import fontaudit                                                     # noqa: E402
import wrap_en                                                       # noqa: E402


PLAYER_CODE = 0xEA
DEFAULT_NAME = 'Shiren'
WIDEST_NAME = 'MMMMMM'  # M, V and W all have the approved font's widest 8px advance.

# One mechanical reflow would turn the first page into two pages and leave "I'm so
# happy..." on a third.  This keeps the meaning and original two-page pacing while fitting
# the settled six-character player-name contract.  Every other candidate preserves its
# wording byte for byte and changes only <br>/<brk> layout.
CURATED_PAGE = {
    ('14:$5840', 0): ("Keyaki: Lately, the<br> villagers are starting to<br> accept "
                       "you, <name>.<end>"),
}


def _controls(font, name):
    cells = dialogue.floor_widths()
    cells[PLAYER_CODE] = len(name)
    pixels = dialogue.dot_floor_widths(font)
    pixels[PLAYER_CODE] = (font.text_width(name), font.text_extent(name))
    return cells, pixels


def _line_metrics(line, row, font, cells, pixels):
    _advance, extent, _raw = dialogue.dot_metrics(
        line.data, font, row['bank'], pixels)
    return line.cells(cells), extent


def _unsafe_lines(data, row, font, cells, pixels):
    out = []
    for line in dialogue.split_lines(data, row['bank']):
        if PLAYER_CODE not in line.data:
            continue
        source, extent = _line_metrics(line, row, font, cells, pixels)
        if source > dialogue.WIDTH or extent > dialogue.LINE_PX:
            out.append((line, source, extent))
    return out


def _candidate(text, row, font, cells, pixels, unsafe_boxes):
    """Reflow only boxes that actually fail; preserve every unrelated authored break."""

    def measure(value):
        data = B.encode_en(value, row['bank'])
        return dialogue.dot_metrics(data, font, row['bank'], pixels)[:2]

    pages = text.split('<brk>')
    out, notes = [], []
    for box, page in enumerate(pages):
        if box not in unsafe_boxes:
            out.append(page)
            continue
        draft = CURATED_PAGE.get((row['loc'], box), page.replace('<br>', ' '))
        lines = []
        for segment in draft.split('<br>'):
            segment = segment.strip()
            if not segment:
                continue
            first = box == 0 and not lines
            lines.extend(wrap_en.wrap_segment(
                segment, dialogue.WIDTH, first, cells, measure, dialogue.LINE_PX))
        if len(lines) > dialogue.LINES_PER_BOX:
            raise ValueError('%s box %d needs %d lines after reflow; limit is %d' %
                             (row['loc'], box + 1, len(lines),
                              dialogue.LINES_PER_BOX))
        laid_out = []
        for row_no, line in enumerate(lines):
            lead = '' if box == 0 and row_no == 0 else ' '
            laid_out.append(lead + line)
        out.append('<br>'.join(laid_out))
    return '<brk>'.join(out), notes


def _encode(text, row):
    lead = bytes.fromhex(row['hex'])[:1] == bytes([0xB4])
    return B.encode_en((' ' if lead else '') + text, row['bank'])


def _box_count(data, bank):
    return max((line.box for line in dialogue.split_lines(data, bank)), default=0) + 1


def _expanded_line(line, name):
    return line.text().replace('<name>', name)


def _candidate_boxes(data, row, font, default_controls, widest_controls, name,
                     show_all=False):
    lines = dialogue.split_lines(data, row['bank'])
    wanted = ({line.box for line in lines} if show_all else
              {line.box for line in lines if PLAYER_CODE in line.data})
    out = []
    for box in sorted(wanted):
        rendered = []
        for line in lines:
            if line.box != box:
                continue
            default_source, default_extent = _line_metrics(
                line, row, font, *default_controls)
            widest_source, widest_extent = _line_metrics(
                line, row, font, *widest_controls)
            rendered.append((line.row + 1, default_source, default_extent,
                             widest_source, widest_extent, _expanded_line(line, name)))
        out.append((box + 1, rendered))
    return out


def _write_tsv(path, candidates):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as out:
        out.write('# Generated by tools/nameaudition.py; review overlay, not production.\n')
        for loc, text in candidates:
            out.write('%s\t%s\n' % (loc, text))


def _write_report(path, current_counts, candidates, details, default_name, widest_name,
                  applied=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as out:
        out.write('# Player-name dialogue audition\n\n')
        out.write('Generated by `tools/nameaudition.py`. The validated candidates were %s'
                  ' production `script/en.tsv`.\n\n' %
                  ('applied to' if applied else 'not applied to'))
        out.write('- Current unsafe lines with `%s`: **%d**.\n' %
                  (default_name, current_counts[0]))
        out.write('- Current unsafe lines with widest legal `%s`: **%d** across **%d** '
                  'strings.\n' % (widest_name, current_counts[1], len(candidates)))
        out.write('- Candidate validation failures: **0** for both names.\n\n')
        out.write('Candidate text is shown with `%s`; every line also lists the widest '
                  '`%s` measurement. Both are measured against the 30-glyph / 144px '
                  'renderer.\n\n' % (default_name, widest_name))
        for detail in details:
            out.write('## `%s`\n\n' % detail['loc'])
            out.write('Current unsafe line%s:\n\n' %
                      ('' if len(detail['unsafe']) == 1 else 's'))
            for item in detail['unsafe']:
                box, row, dsource, dextent, wsource, wextent, text = item
                out.write('- Box %d, line %d — `%s`  '\
                          '\n  Shiren **%d/30, %d/144px**; widest **%d/30, %d/144px**.\n'
                          % (box, row, text.replace('`', '\\`'), dsource, dextent,
                             wsource, wextent))
            if detail['old_boxes'] != detail['new_boxes']:
                out.write('\nPacing note: candidate changes **%d box%s to %d**.\n' %
                          (detail['old_boxes'], '' if detail['old_boxes'] == 1 else 'es',
                           detail['new_boxes']))
            out.write('\nCandidate name-bearing box%s:\n\n' %
                      ('' if len(detail['boxes']) == 1 else 'es'))
            for box, lines in detail['boxes']:
                out.write('```text\nbox %d\n' % box)
                for item in lines:
                    row, dsource, dextent, wsource, wextent, text = item
                    out.write('  %d  [Shiren %2d/30, %3d/144px; widest %2d/30, '
                              '%3d/144px] %s\n' %
                              (row, dsource, dextent, wsource, wextent, text))
                out.write('```\n\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--en', default=os.path.join(ROOT, 'script', 'en.tsv'))
    ap.add_argument('--default-name', default=DEFAULT_NAME)
    ap.add_argument('--widest-name', default=WIDEST_NAME)
    ap.add_argument('--out-tsv',
                    default=os.path.join(ROOT, 'build', 'player_name_candidates.tsv'))
    ap.add_argument('--out-report',
                    default=os.path.join(ROOT, 'build', 'player_name_audition.md'))
    ap.add_argument('--apply', action='store_true',
                    help='merge the validated candidates into --en after writing review '
                         'artifacts')
    args = ap.parse_args()

    for label, name in (('default', args.default_name), ('widest', args.widest_name)):
        if not name or len(name) > dialogue.PLAYER_NAME:
            ap.error('%s name must contain 1-%d characters' %
                     (label, dialogue.PLAYER_NAME))
        try:
            B.encode_en(name)
        except ValueError as exc:
            ap.error('%s name is not encodable: %s' % (label, exc))

    font = dotfont.load_approved()
    manifest = json.load(open(os.path.join(ROOT, 'script', 'script.json'), encoding='utf-8'))
    strings = manifest['strings']
    by_id = {row['id']: row for row in strings}
    translated, _sources, _unknown = fontaudit.load_translations(
        manifest, args.en, os.path.join(ROOT, 'script', 'glossary.tsv'))
    encoded, errors = fontaudit.encoded_translations(strings, translated)
    if errors:
        raise SystemExit('cannot audition with %d translation encode error(s)' % len(errors))

    default_cells, default_pixels = _controls(font, args.default_name)
    widest_cells, widest_pixels = _controls(font, args.widest_name)
    current_default = []
    current_widest = []
    for ident, data in encoded.items():
        row = by_id[ident]
        if not dialogue.is_dialogue(row):
            continue
        current_default += [(row, item) for item in _unsafe_lines(
            data, row, font, default_cells, default_pixels)]
        current_widest += [(row, item) for item in _unsafe_lines(
            data, row, font, widest_cells, widest_pixels)]

    affected = sorted({row['id'] for row, _item in current_widest},
                      key=lambda ident: by_id[ident]['loc'])
    candidates = []
    details = []
    for ident in affected:
        row = by_id[ident]
        current = encoded[ident]
        current_unsafe = _unsafe_lines(
            current, row, font, widest_cells, widest_pixels)
        candidate, notes = _candidate(
            translated[ident], row, font, widest_cells, widest_pixels,
            {line.box for line, _source, _extent in current_unsafe})
        if any(kind == 'unwrappable' for kind, _detail in notes):
            raise SystemExit('%s produced an unwrappable candidate: %r' %
                             (row['loc'], notes))
        candidate_data = _encode(candidate, row)

        # Exact literal expansion makes the ordinary previewer's source and pixel checks
        # authoritative for both review names.
        for name in (args.default_name, args.widest_name):
            literal = _encode(candidate.replace('<name>', name), row)
            problems = dialogue.check(
                literal, width=dialogue.WIDTH, per_box=dialogue.LINES_PER_BOX,
                buf=dialogue.geometry_for(row)[2], bank=row['bank'], font=font)
            if problems:
                raise SystemExit('%s candidate fails for %s: %r' %
                                 (row['loc'], name, problems))

        unsafe = []
        for line, widest_source, widest_extent in current_unsafe:
            default_source, default_extent = _line_metrics(
                line, row, font, default_cells, default_pixels)
            unsafe.append((line.box + 1, line.row + 1,
                           default_source, default_extent, widest_source, widest_extent,
                           _expanded_line(line, args.default_name)))
        old_boxes = _box_count(current, row['bank'])
        new_boxes = _box_count(candidate_data, row['bank'])
        details.append({
            'loc': row['loc'],
            'unsafe': unsafe,
            'old_boxes': old_boxes,
            'new_boxes': new_boxes,
            'boxes': _candidate_boxes(
                candidate_data, row, font,
                (default_cells, default_pixels), (widest_cells, widest_pixels),
                args.default_name, show_all=old_boxes != new_boxes),
        })
        candidates.append((row['loc'], candidate))

    _write_tsv(args.out_tsv, candidates)
    _write_report(args.out_report,
                  (len(current_default), len(current_widest)), candidates, details,
                  args.default_name, args.widest_name, args.apply)
    if args.apply:
        wrap_en.merge(candidates, args.en)
    print('player-name audition: %d unsafe line(s) for %s; %d for %s across %d strings'
          % (len(current_default), args.default_name, len(current_widest),
             args.widest_name, len(candidates)))
    print('candidate overlay: %s' % os.path.relpath(args.out_tsv, ROOT))
    print('review sheet:     %s' % os.path.relpath(args.out_report, ROOT))
    if args.apply:
        print('applied:          %s' % os.path.relpath(args.en, ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
