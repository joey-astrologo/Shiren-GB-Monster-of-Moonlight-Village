#!/usr/bin/env python3
"""Render a native-pixel font comparison and measure the menu-VWF tile peak.

This is deliberately a project-text preview, not an alphabet-sheet beauty contest.  It
compares the current hand-drawn 6px font with a candidate TTF at its native 8px strike,
then with conservative ROM-fit spacing: preserve the candidate's advances except where
the raster has needless trailing whitespace, keep one blank pixel after ink, and give a
space four pixels.  The glyph pixels themselves are never altered.

    python3 tools/fontbakeoff.py "font candidates/Lanky Git Variable.ttf" \
        --output build/font_bakeoff_lanky.png

An approved JSON spec is compared directly with its declared width reference. For a TTF
or OTF, Pillow must rasterize the candidate to binary pixels at 8px. If it produces
antialiasing, the file is not a native 8px pixel strike and this tool refuses to make a
misleading sheet.
"""
import argparse
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from latinfont import G  # noqa: E402
import dotfont            # noqa: E402


LONG_ROWS = (
    'True Rapier-99',
    'Stopgap Staff[77]',
    'Weakening Pot[77]',
    'Sorcery Staff[77]',
    'Unlucky Staff[77]',
)
MAIN_ROWS = ('Item', 'Floor', 'Map', 'Quit')
# Remove is the widest live first action (Joey's equipment page), while the synthetic
# herb flow happens to show Drink.  A candidate has to survive the hostile combination.
ACTION_ROWS = ('Remove', 'Toss', 'Drop', 'Info')
RUNS = (57, 11, 4, 1)


def capneed(tiles):
    if tiles <= 4:
        return 4
    if tiles <= 8:
        return 8
    return tiles


def packable(caps, runs=RUNS):
    caps = sorted(caps, reverse=True)
    free = sorted(runs, reverse=True)

    def place(i):
        if i == len(caps):
            return True
        cap = caps[i]
        tried = set()
        for j, room in enumerate(free):
            if room < cap or room in tried:
                continue
            tried.add(room)
            free[j] -= cap
            if place(i + 1):
                return True
            free[j] += cap
        return False

    return place(0)


def current_glyph(ch):
    image = Image.new('1', (8, 8), 0)
    if ch == ' ':
        return image
    rows = G.get(ch)
    if rows is None:
        raise SystemExit('current font has no glyph for %r' % ch)
    for y, row in enumerate(rows):
        for x, pixel in enumerate(row):
            if pixel == '#':
                image.putpixel((x, y), 1)
    return image


def candidate_glyph(font, ch):
    image = Image.new('L', (8, 8), 0)
    ImageDraw.Draw(image).text((0, 0), ch, font=font, fill=255)
    levels = set(image.getdata())
    if not levels <= {0, 255}:
        raise SystemExit(
            'candidate antialiases at 8px (%r has levels %s); '
            'it is not a native 8px pixel strike' % (ch, sorted(levels)))
    return image.convert('1')


def gb_studio_glyph(sheet, ch):
    """Extract one ASCII glyph and its magenta-coded advance from a GB Studio sheet."""
    index = ord(ch) - 32
    if not 0 <= index < 224:
        raise SystemExit('GB Studio sheet cannot map %r through default ASCII' % ch)
    left = index % 16 * 8
    top = index // 16 * 8
    cell = sheet.crop((left, top, left + 8, top + 8)).convert('RGB')
    background = (224, 248, 207)
    ink = (7, 24, 33)
    trim = (255, 0, 255)
    colors = set(cell.getdata())
    unsupported = colors - {background, ink, trim}
    if unsupported:
        raise SystemExit('GB Studio glyph %r uses unsupported extra shades: %s' %
                         (ch, sorted(unsupported)))
    trim_columns = [x for x in range(8)
                    if any(cell.getpixel((x, y)) == trim for y in range(8))]
    advance = min(trim_columns) if trim_columns else 8
    if any(cell.getpixel((x, y)) != trim
           for x in range(advance, 8) for y in range(8)):
        raise SystemExit('GB Studio glyph %r has irregular magenta width metadata' % ch)
    glyph = Image.new('1', (8, 8), 0)
    for y in range(8):
        for x in range(advance):
            if cell.getpixel((x, y)) == ink:
                glyph.putpixel((x, y), 1)
    return glyph, advance


def seven_row(glyph, mode):
    """Keep the glyph's pixels but ensure row 7 is blank.

    Short glyphs merely move up one row.  Full-height glyphs lose one interior row:
    `middle` always removes row 4, while `smart` removes the row most similar to one of
    its neighbours.  The two treatments make the aesthetic choice visible before anyone
    redraws individual letters by hand.
    """
    bbox = glyph.getbbox()
    if bbox is None or bbox[3] <= 7:
        return glyph.copy()
    out = Image.new('1', (8, 8), 0)
    height = bbox[3] - bbox[1]
    if height <= 7:
        out.paste(glyph.crop((0, 1, 8, 8)), (0, 0))
        return out

    rows = [sum((1 << (7 - x)) for x in range(8) if glyph.getpixel((x, y)))
            for y in range(8)]
    if mode == 'middle':
        drop = 4
    elif mode == 'smart':
        def distance(a, b):
            return bin(a ^ b).count('1')

        drop = min(range(1, 7),
                   key=lambda y: (min(distance(rows[y], rows[y - 1]),
                                      distance(rows[y], rows[y + 1])),
                                  abs(y - 4)))
    else:
        raise ValueError(mode)
    for dst_y, src_y in enumerate(y for y in range(8) if y != drop):
        for x in range(8):
            if glyph.getpixel((x, src_y)):
                out.putpixel((x, dst_y), 1)
    return out


def dot_e_variant(glyphs, clear=False):
    """Return Dot Gothic glyphs with the proposed five-pixel-advance lowercase e."""
    out = {ch: image.copy() for ch, image in glyphs.items()}
    # Source e row 5 is `#...#`: the far-right pixel alone makes an otherwise
    # four-column glyph five columns wide.  Clear also extends the middle bar from
    # `###` to `####`, producing a conventional bitmap e.
    assert out['e'].getpixel((4, 5))
    assert not out['e'].getpixel((3, 4))
    out['e'].putpixel((4, 5), 0)
    if clear:
        out['e'].putpixel((3, 4), 1)
    return out


def image_from_rows(rows):
    image = Image.new('1', (8, 8), 0)
    for y, row in enumerate(rows):
        for x in range(8):
            if row & (0x80 >> x):
                image.putpixel((x, y), 1)
    return image


def text_width(text, glyph, advance):
    """Pixel extent, excluding the final glyph's invisible trailing spacing."""
    if not text:
        return 0
    tail = glyph(text[-1]).getbbox()
    tail_width = tail[2] if tail else advance(text[-1])
    return sum(advance(ch) for ch in text[:-1]) + tail_width


def row_cap(text, glyph, advance):
    return capneed((text_width(text, glyph, advance) + 7) // 8)


def profile(glyph, advance):
    items = tuple(row_cap(row, glyph, advance) for row in LONG_ROWS)
    main = tuple(row_cap(row, glyph, advance) for row in MAIN_ROWS)
    action = tuple(row_cap(row, glyph, advance) for row in ACTION_ROWS)
    action_peak = sum(items) + sum(action)
    redraw_peak = sum(items) + sum(main)
    peak = max(action_peak, redraw_peak)
    candidates = (items + action, items + main)
    return {
        'items': items,
        'main': main,
        'action': action,
        'peak': peak,
        'packable': all(packable(caps) for caps in candidates),
    }


def draw_text(screen, x, y, text, glyph, advance):
    for ch in text:
        tile = glyph(ch)
        screen.paste(0, (x, y), tile)
        x += advance(ch)


def panel(title, glyph, advance, stats, e_review=False, spacing_review=False,
          suffix_review=False, digit_review=False):
    panel_image = Image.new('1', (176, 184), 1)
    label = ImageDraw.Draw(panel_image)
    label.text((8, 2), title, fill=0)

    screen = Image.new('1', (160, 144), 1)
    draw = ImageDraw.Draw(screen)
    draw.rectangle((0, 0, 159, 143), outline=0)

    if digit_review:
        samples = (
            (4, 4, '444 447 474 477'),
            (4, 12, '744 747 774 777'),
            (4, 20, 'True Rapier+44'),
            (4, 28, 'True Rapier+77'),
            (4, 36, '+44 +47 +74 +77'),
            (4, 44, '-44 -47 -74 -77'),
        )
    elif suffix_review:
        samples = (
            (4, 4, 'True Rapier+99'),
            (4, 12, 'True Rapier+44'),
            (4, 20, 'True Rapier+77'),
            (4, 32, '+99 +44 +47 +74 +77'),
            (4, 40, '-99 -44 -47 -74 -77'),
        )
    elif spacing_review:
        samples = (
            (4, 4, 'Innkeeper: Ah, you woke'),
            (4, 12, 'up at last!'),
            (4, 20, 'You were crying out so'),
            (4, 32, 'DAD DOD Drop 1/2'),
            (4, 40, 'tt test Staff HP/Max'),
        )
    else:
        samples = (
            (4, 4, 'Innkeeper: Ah, you woke'),
            (4, 12, 'up at last!'),
            (4, 20, 'You were crying out so'),
            (4, 32, 'aceo gypq bdhl'),
            (4, 40, 'eerie evergreen eee' if e_review else 'minimum willow Ill'),
        )
    for x, y, text in samples:
        draw_text(screen, x, y, text, glyph, advance)
    for i, text in enumerate(LONG_ROWS):
        draw_text(screen, 4, 52 + 8 * i, text, glyph, advance)
    draw_text(screen, 4, 96, 'Remove Toss Drop Info', glyph, advance)
    draw_text(screen, 4, 108, 'ABCDEFGHIJKLM', glyph, advance)
    draw_text(screen, 4, 116, 'NOPQRSTUVWXYZ', glyph, advance)
    draw_text(screen, 4, 128, '0123456789 []!?', glyph, advance)

    panel_image.paste(screen, (8, 16))
    verdict = 'PASS' if stats['peak'] <= 73 and stats['packable'] else 'FAIL'
    label.text((8, 162), 'peak %d/73  runs %s' % (stats['peak'], verdict), fill=0)
    label.text((8, 170), 'item caps ' + '/'.join(map(str, stats['items'])), fill=0)
    return panel_image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('font', help='candidate TTF/OTF/PNG or approved font spec JSON')
    parser.add_argument('--output', default=os.path.join(ROOT, 'build',
                                                         'font_bakeoff.png'))
    parser.add_argument('--zoom', type=int, default=4)
    parser.add_argument('--dot-e-review', action='store_true',
                        help='compare two proposed lowercase-e edits; GB Studio PNG only')
    parser.add_argument('--dot-spacing-review', action='store_true',
                        help='compare proposed D/t/slash advances after e-clear approval')
    parser.add_argument('--approved-dot', action='store_true',
                        help='verify and render assets/fonts/dot_gothic_shiren.json')
    parser.add_argument('--suffix-review', action='store_true',
                        help='show signed item-modifier samples (use with --approved-dot)')
    parser.add_argument('--digit-review', action='store_true',
                        help='show digit-focused source/approved 4 and 7 samples '
                             '(use with --approved-dot)')
    args = parser.parse_args()

    font_path = os.path.abspath(args.font)
    font_name = os.path.splitext(os.path.basename(font_path))[0]
    chars = set(''.join(LONG_ROWS + MAIN_ROWS + ACTION_ROWS))
    chars.update('Innkeeper: Ah, you wokeup at last!You were crying out so')
    chars.update('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789[]!?/+-')

    source_kind = os.path.splitext(font_path)[1].lower()
    if source_kind in ('.ttf', '.otf'):
        if font_name.endswith(' Variable'):
            font_name = font_name[:-len(' Variable')]
        font = ImageFont.truetype(font_path, 8)
        glyphs = {ch: candidate_glyph(font, ch) for ch in chars if ch != ' '}
        native_widths = {ch: max(1, round(font.getlength(ch))) for ch in chars}
    elif source_kind == '.png':
        sheet = Image.open(font_path)
        if sheet.size != (128, 112):
            raise SystemExit('GB Studio font sheet must be 128x112, got %s' %
                             (sheet.size,))
        json_path = os.path.splitext(font_path)[0] + '.json'
        if os.path.exists(json_path):
            with open(json_path, encoding='utf-8') as src:
                font_name = json.load(src).get('name', font_name)
        extracted = {ch: gb_studio_glyph(sheet, ch) for ch in chars}
        glyphs = {ch: pair[0] for ch, pair in extracted.items() if ch != ' '}
        native_widths = {ch: pair[1] for ch, pair in extracted.items()}
    elif source_kind == '.json':
        loaded_candidate = dotfont.load_approved(font_path)
        font_name = loaded_candidate.name
        glyphs = {ch: image_from_rows(loaded_candidate.glyphs[ch])
                  for ch in chars if ch != ' '}
        native_widths = {ch: loaded_candidate.advances[ch] for ch in chars}
    else:
        raise SystemExit('candidate must be a TTF, OTF, GB Studio PNG or approved JSON')

    def candidate(ch):
        return Image.new('1', (8, 8), 0) if ch == ' ' else glyphs[ch]

    def native_advance(ch):
        return native_widths[ch]

    def romfit_advance(ch):
        if ch == ' ':
            return 4
        bbox = glyphs[ch].getbbox()
        if bbox is None:
            return native_advance(ch)
        # bbox right is exclusive.  Add one blank pixel after the rightmost ink, while
        # never making the candidate wider than its own embedded advance.
        return min(native_advance(ch), bbox[2] + 1)

    if sum((args.dot_e_review, args.dot_spacing_review, args.approved_dot)) > 1:
        raise SystemExit('choose only one Dot Gothic review mode')
    if (args.suffix_review or args.digit_review) and not args.approved_dot:
        raise SystemExit('--suffix-review/--digit-review require --approved-dot')
    if args.suffix_review and args.digit_review:
        raise SystemExit('choose either --suffix-review or --digit-review')
    e_review = False
    spacing_review = False
    if source_kind == '.json':
        if args.dot_e_review or args.dot_spacing_review or args.approved_dot:
            raise SystemExit('Dot Gothic review modes do not apply to approved JSON')
        reference_path = (loaded_candidate.spec.get('width_reference') or
                          loaded_candidate.spec.get('comparison_reference'))
        if reference_path:
            reference = dotfont.load_approved(os.path.join(ROOT, reference_path))
            reference_glyphs = {ch: image_from_rows(reference.glyphs[ch])
                                for ch in chars if ch != ' '}

            def reference_glyph(ch):
                return (Image.new('1', (8, 8), 0) if ch == ' '
                        else reference_glyphs[ch])

            profiles = (
                (reference.name + ' / shipped', reference_glyph, reference.advance),
                (loaded_candidate.name + ' / proposed', candidate, native_advance),
            )
        else:
            profiles = ((loaded_candidate.name + ' / approved',
                         candidate, native_advance),)
    elif args.approved_dot:
        if source_kind != '.png' or 'Dot Gothic' not in font_name:
            raise SystemExit('--approved-dot requires the Dot Gothic GB Studio PNG')
        spec_path = os.path.join(ROOT, 'assets', 'fonts', 'dot_gothic_shiren.json')
        loaded = dotfont.load_approved(spec_path, font_path)
        spec = loaded.spec
        approved_glyphs = {ch: image_from_rows(loaded.glyphs[ch]) for ch in chars}
        approved_widths = {ch: loaded.advances[ch] for ch in chars}

        def approved(ch):
            return Image.new('1', (8, 8), 0) if ch == ' ' else approved_glyphs[ch]

        def approved_advance(ch):
            return approved_widths[ch]

        profiles = (
            (font_name + ' / original', candidate, native_advance),
            (spec['name'] + ' / approved', approved, approved_advance),
        )
    elif args.dot_e_review:
        if source_kind != '.png' or 'Dot Gothic' not in font_name:
            raise SystemExit('--dot-e-review requires the Dot Gothic GB Studio PNG')
        e_review = True
        minimal_glyphs = dot_e_variant(glyphs)
        clear_glyphs = dot_e_variant(glyphs, clear=True)
        review_widths = dict(native_widths)
        review_widths['e'] = 5

        def review_advance(ch):
            return review_widths[ch]

        def minimal(ch):
            return Image.new('1', (8, 8), 0) if ch == ' ' else minimal_glyphs[ch]

        def clear(ch):
            return Image.new('1', (8, 8), 0) if ch == ' ' else clear_glyphs[ch]

        profiles = (
            (font_name + ' / original', candidate, native_advance),
            (font_name + ' / e minimal', minimal, review_advance),
            (font_name + ' / e clear', clear, review_advance),
        )
    elif args.dot_spacing_review:
        if source_kind != '.png' or 'Dot Gothic' not in font_name:
            raise SystemExit('--dot-spacing-review requires the Dot Gothic GB Studio PNG')
        spacing_review = True
        clear_glyphs = dot_e_variant(glyphs, clear=True)
        clear_widths = dict(native_widths)
        clear_widths['e'] = 5
        tight_widths = dict(clear_widths)
        tight_widths.update({'D': 5, 't': 5, '/': 7})

        def clear(ch):
            return Image.new('1', (8, 8), 0) if ch == ' ' else clear_glyphs[ch]

        def clear_advance(ch):
            return clear_widths[ch]

        def tight_advance(ch):
            return tight_widths[ch]

        profiles = (
            (font_name + ' / e clear', clear, clear_advance),
            (font_name + ' / D,t,/ tightened', clear, tight_advance),
        )
    elif source_kind == '.png':
        profiles = (
            ('Current handmade / 6px', current_glyph, lambda _ch: 6),
            (font_name + ' / GB widths', candidate, native_advance),
            (font_name + ' / ROM-fit', candidate, romfit_advance),
        )
    else:
        middle_glyphs = {ch: seven_row(image, 'middle') for ch, image in glyphs.items()}
        smart_glyphs = {ch: seven_row(image, 'smart') for ch, image in glyphs.items()}

        def middle(ch):
            return Image.new('1', (8, 8), 0) if ch == ' ' else middle_glyphs[ch]

        def smart(ch):
            return Image.new('1', (8, 8), 0) if ch == ' ' else smart_glyphs[ch]

        profiles = (
            ('Current handmade / 6px', current_glyph, lambda _ch: 6),
            (font_name + ' / original ROM-fit', candidate, romfit_advance),
            (font_name + ' / 7px middle cut', middle, romfit_advance),
            (font_name + ' / 7px smart cut', smart, romfit_advance),
        )
    rendered = []
    for title, glyph, advance in profiles:
        stats = profile(glyph, advance)
        rendered.append(panel(title, glyph, advance, stats, e_review=e_review,
                              spacing_review=spacing_review,
                              suffix_review=args.suffix_review,
                              digit_review=args.digit_review))
        print('%s: peak %d, runs %s; item caps %s; main %s; action %s' % (
            title, stats['peak'], 'PASS' if stats['packable'] else 'FAIL',
            '/'.join(map(str, stats['items'])), '/'.join(map(str, stats['main'])),
            '/'.join(map(str, stats['action']))))

    sheet = Image.new('1', (176 * len(rendered), 184), 1)
    for i, image in enumerate(rendered):
        sheet.paste(image, (176 * i, 0))
    if args.zoom != 1:
        sheet = sheet.resize((sheet.width * args.zoom, sheet.height * args.zoom),
                             Image.Resampling.NEAREST)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    sheet.save(args.output)
    print('wrote %s' % args.output)


if __name__ == '__main__':
    main()
