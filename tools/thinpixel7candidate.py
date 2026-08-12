#!/usr/bin/env python3
"""Build a non-production 8x8 audition spec from Thin Pixel-7's native strike.

Thin Pixel-7 is a 5x7 bitmap design embedded in a TTF whose exact, non-antialiased strike
appears at 20 ppem. The font's bundled EULA permits use in freeware software with credit.
This tool does not install the font and does not copy the TTF into the repository; it
creates review-only JSON files under ``build/`` from a user-supplied copy.

Most glyphs fit the Game Boy cell by taking source rows 8..15. For g/p/q/y, rows 8..12 and
14..16 keep the lowercase body on the same baseline as a/e/o and preserve the complete
two-row descender; only a repeated vertical row in the bowl/stem is omitted. Lowercase j
is the other nine-row glyph; one of its five identical stem rows is removed, preserving
its dot, cap, descender, and all distinct pixel shapes. Horizontal pixels are copied
exactly. Advances use the native strike, with only redundant trailing whitespace trimmed
to one blank column and space set to 4px.
"""
import argparse
import hashlib
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from latinfont import EN_CODES  # noqa: E402


PPEM = 20
SOURCE_TOP = 8
ALIGNED_DESCENDERS = set('gpqy')
FORMAT = 'shiren-gb-8x8-rows-v1'

TABULAR_DIGITS = {
    '0': ('.##.....', '#..#....', '#..#....', '#..#....',
          '#..#....', '#..#....', '.##.....', '........'),
    '1': ('..#.....', '.##.....', '#.#.....', '..#.....',
          '..#.....', '..#.....', '####....', '........'),
    '2': ('.##.....', '#..#....', '...#....', '.##.....',
          '#.......', '#.......', '####....', '........'),
    '3': ('.##.....', '#..#....', '...#....', '..#.....',
          '...#....', '#..#....', '.##.....', '........'),
    '4': ('...#....', '..##....', '.#.#....', '#..#....',
          '####....', '...#....', '...#....', '........'),
    '5': ('####....', '#.......', '###.....', '...#....',
          '...#....', '#..#....', '.##.....', '........'),
    '6': ('.##.....', '#..#....', '#.......', '###.....',
          '#..#....', '#..#....', '.##.....', '........'),
    '7': ('####....', '...#....', '...#....', '..#.....',
          '.#......', '.#......', '.#......', '........'),
    '8': ('.##.....', '#..#....', '#..#....', '.##.....',
          '#..#....', '#..#....', '.##.....', '........'),
    '9': ('.##.....', '#..#....', '#..#....', '.###....',
          '...#....', '#..#....', '.##.....', '........'),
}

REVIEWED_SYMBOLS = {
    ',': ('........', '........', '........', '........',
          '........', '........', '.#......', '#.......'),
    '?': ('.###....', '#...#...', '....#...', '...#....',
          '..#.....', '........', '..#.....', '........'),
    ':': ('........', '........', '#.......', '........',
          '........', '........', '#.......', '........'),
    '-': ('........', '........', '........', '.###....',
          '........', '........', '........', '........'),
    '+': ('........', '........', '..#.....', '.###....',
          '..#.....', '........', '........', '........'),
}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as src:
        for block in iter(lambda: src.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def raster(font, ch):
    if ch == ' ':
        return ['........'] * 8, 4

    canvas = Image.new('L', (16, 24), 0)
    ImageDraw.Draw(canvas).text((0, 0), ch, font=font, fill=255)
    levels = set(canvas.getdata())
    if not levels <= {0, 255}:
        raise SystemExit('Thin Pixel-7 %r is antialiased at %d ppem: %s' %
                         (ch, PPEM, sorted(levels)))

    if ch == 'j':
        source_rows = list(range(8, 17))
        # Five equal stem rows sit between the cap and descender. Removing the fourth
        # retains the intended shape while making the only 9px-tall glyph fit 8 rows.
        del source_rows[6]
    elif ch in ALIGNED_DESCENDERS:
        # Preserve the ordinary lowercase top plus the complete two-row descender.
        # Source row 13 repeats a vertical bowl/stem row, so it is the lossless-looking
        # place to compress these otherwise 9px-tall glyphs into the Game Boy cell.
        source_rows = list(range(8, 13)) + list(range(14, 17))
    else:
        top = SOURCE_TOP + (1 if ch == ',' else 0)
        source_rows = list(range(top, top + 8))

    rows = []
    for y in source_rows:
        rows.append(''.join('#' if canvas.getpixel((x, y)) else '.'
                            for x in range(8)))

    ink_columns = [x for x in range(8)
                   if any(row[x] == '#' for row in rows)]
    if not ink_columns:
        raise SystemExit('Thin Pixel-7 %r became blank during 8x8 fitting' % ch)
    ink_width = max(ink_columns) + 1
    native = max(1, round(font.getlength(ch)))
    advance = min(native, ink_width + 1)
    if ink_width >= advance:
        raise SystemExit('Thin Pixel-7 %r inks %dpx but advances %dpx' %
                         (ch, ink_width, advance))
    return rows, advance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('ttf', help='Thin Pixel-7 TTF from the author/DaFont archive')
    parser.add_argument('--glyphs',
                        default=os.path.join(ROOT, 'build',
                                             'thin_pixel_7_candidate_glyphs.json'))
    parser.add_argument('--spec',
                        default=os.path.join(ROOT, 'build',
                                             'thin_pixel_7_candidate.json'))
    parser.add_argument('--compact-digits', action='store_true',
                        help='use the project-reviewed tabular numerals and symbols')
    args = parser.parse_args()

    font = ImageFont.truetype(args.ttf, PPEM)
    glyphs, advances = {}, {}
    for ch in EN_CODES:
        glyphs[ch], advances[ch] = raster(font, ch)
    if args.compact_digits:
        glyphs.update(TABULAR_DIGITS)
        glyphs.update(REVIEWED_SYMBOLS)
        for ch in TABULAR_DIGITS:
            advances[ch] = 5
        advances['-'] = 5
        advances['+'] = 5

    os.makedirs(os.path.dirname(os.path.abspath(args.glyphs)), exist_ok=True)
    with open(args.glyphs, 'w', encoding='utf-8') as out:
        json.dump({'format': FORMAT, 'glyphs': glyphs}, out, ensure_ascii=False,
                  indent=2)
        out.write('\n')

    glyph_digest = sha256(args.glyphs)
    glyph_rel = os.path.relpath(os.path.abspath(args.glyphs), ROOT)
    candidate_name = ('Thin Pixel-7 / compact-digit GB audition'
                      if args.compact_digits else 'Thin Pixel-7 / GB audition')
    fit_note = ('Thin Pixel-7 20ppem binary letters and unmodified punctuation; g/p/q/y '
                'bodies retain the normal lowercase baseline and complete two-row tails '
                'while one repeated bowl/stem row is omitted; one repeated lowercase-j '
                'stem row is removed to fit 8px.')
    if args.compact_digits:
        fit_note += (' Numerals use playtest-reviewed compact drawings with uniform 5px '
                     'tabular advances; comma, question mark, colon, plus and minus use '
                     'the matching reviewed refinements.')
    spec = {
        'name': candidate_name,
        'status': 'review-only third-party candidate; not installed in the English ROM',
        'design': {
            'source': 'Thin Pixel-7 version 1.0 by Sizenko Alexander / Style-7',
            'fit': fit_note,
            'license': ('Bundled EULA permits use in freeware software with credit; '
                        'commercial/business use requires a separate license.'),
            'upstream_ttf_sha256': sha256(args.ttf),
        },
        'source': {
            'name': 'Thin Pixel-7 Game Boy audition rows',
            'file': glyph_rel,
            'format': FORMAT,
            'sha256': glyph_digest,
            'provenance': ('Generated from a locally supplied Thin Pixel-7 TTF plus the '
                           'declared project-reviewed digit/symbol adaptations; the TTF '
                           'is not copied into this repository.'),
        },
        # Comparison only: unlike width_reference, this does not claim that every glyph
        # is no wider than Moonlit Sans. fontaudit.py judges the real text corpus.
        'comparison_reference': 'assets/fonts/moonlit_sans.json',
        'advances': advances,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.spec)), exist_ok=True)
    with open(args.spec, 'w', encoding='utf-8') as out:
        json.dump(spec, out, ensure_ascii=False, indent=2)
        out.write('\n')

    print('%s: %d glyphs; TTF %s' %
          (candidate_name, len(glyphs), spec['design']['upstream_ttf_sha256']))
    print('  glyphs %s' % os.path.relpath(args.glyphs, ROOT))
    print('  spec   %s' % os.path.relpath(args.spec, ROOT))


if __name__ == '__main__':
    main()
