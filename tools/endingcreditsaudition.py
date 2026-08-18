#!/usr/bin/env python3
"""Render and freeze the complete English ending-credit roll.

The ending keeps the game's native forest scene and black credit band.  English text
uses the same Poppins Medium, white face, and one-pixel green shadow as the approved
copyright title card.  This is deliberately an audition tool: it writes PNG previews
and never edits a ROM.

The 22 entries below are a card-for-card transcription of the native Game Boy
roll.  The separate Japanese end mark which follows them is deliberately not
part of this asset and remains native.

usage: endingcreditsaudition.py --font Poppins-Medium.ttf \
           --frame frame_15060.png [--copyright-reference title_x6.png] \
           [--output build/ending_credits_audition.png] \
           [--asset-output assets/graphics/ending_credits_poppins.json]
"""
import argparse
import base64
import glob
import hashlib
import json
import math
import os
import zlib
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from poppins import AA_HIGH, AA_LOW, FONT_SHA256, render, render_levels


NATIVE_SIZE = (160, 144)
SCREEN_SCALE = 4
CREDIT_BAND_TOP = 84
CREDITS = (
    ('Shiren GB', 'Development Staff', '- 風来のシレン -', '開発陣', 0x47),
    ('Director', 'Seiichiro Nagahata', '監督', '長畑 成一郎', 0x47),
    ('Planning & Script', 'Shin-ichiro Tomie', '企画・脚本', '冨江 慎一郎', 0x47),
    ('Original Art', 'Kaoru Hasegawa', '原画', '長谷川 薫', 0x47),
    ('Music', 'Koichi Sugiyama', '音楽', 'すぎやま こういち', 0x47),
    ('Development Director', 'Masayoshi Saito', '開発監督', '斉藤 昌快', 0x47),
    ('Chief Programmer', 'Kazumi Ogawa', 'チーフプログラマー', '小川 一美', 0x47),
    ('Programming', 'Yasuo Nakajima', 'プログラム', '中島 康雄', 0x47),
    ('Programming', 'Masahiro Nii', 'プログラム', '二位 真裕', 0x47),
    ('Programming', 'Nobuhiro Yamada', 'プログラム', '山田 信洋', 0x47),
    ('Art Director', 'Shinji Tanaka', '美術監督', '田中 信二', 0x47),
    ('Art', 'E Sakurai', '美術', '桜井 絵', 0x47),
    ('Art', 'Kazuo Shimizu', '美術', '清水 一男', 0x47),
    ('Sound', 'Kojiro Nakashima', '音響', '中嶋 康二郎', 0x47),
    ("Fay's Puzzles", 'Yuichi Kanzawa', 'フェイの問題', '神澤 諭一', 0x47),
    ('Special Thanks', 'Shinichi Koike', '協力', '小池 慎一', 0x47),
    ('Special Thanks', 'Hitomi Saito', '協力', '斉藤 ひとみ', 0x47),
    ('Special Thanks', 'Haruaki Kurokawa', '協力', '黒川 春秋', 0x47),
    ('Special Thanks', 'Chiharu Tanigawa', '協力', '谷川 千春', 0x47),
    ('Developed by', 'Aquamarine', '開発', '（株）アクアマリン', 0x47),
    ('Producer', 'Koichi Nakamura', '製作', '中村 光一', 0x51),
    ('Production & Copyright', 'Chunsoft', '制作・著作', '（株）チュンソフト', 0x60),
)
CARDS = tuple((role, name) for role, name, _native_role, _native_name, _duration
              in CREDITS)
ASSET_FORMAT = 'shiren-gb-poppins-ending-credits-v1'
ROLE_Y = 94
NAME_TILE_Y = 110
STRIP_BYTES = 20 * 2 * 16
TITLE_GREEN = (131, 198, 86)
TITLE_WHITE = (240, 240, 240)

# `shadow` is the approved style: a crisp 1-bit face over a one-pixel offset shadow, taken
# from the copyright title card.  `aa` instead spends the same two ink colors the way the
# native Japanese roll does -- dim at partial coverage, bright at full, no shadow -- which
# is what the credit band's palette fade treats kindly.
DEFAULT_LICENSE = 'SIL Open Font License 1.1; see licenses/OFL-1.1-Inter.txt'
STYLE_SHADOW = 'shadow'
STYLE_AA = 'aa'
STYLES = (STYLE_SHADOW, STYLE_AA)
ROLE_CAP = 7
NAME_CAP = 10


def _sha(path):
    with open(path, 'rb') as src:
        return hashlib.sha256(src.read()).hexdigest()


def _nearest_native(path, scale, label):
    image = Image.open(path).convert('RGB')
    expected = (NATIVE_SIZE[0] * scale, NATIVE_SIZE[1] * scale)
    if image.size != expected:
        raise SystemExit('endingcreditsaudition: %s is %s, expected %s'
                         % (label, image.size, expected))
    native = image.resize(NATIVE_SIZE, Image.Resampling.NEAREST)
    if native.resize(expected, Image.Resampling.NEAREST).tobytes() != image.tobytes():
        raise SystemExit('endingcreditsaudition: %s is not an exact %dx raster'
                         % (label, scale))
    return native


def _title_colors(path):
    reference = _nearest_native(path, 6, 'copyright reference')
    colors = Counter(reference.getdata())
    if len(colors) != 3:
        raise SystemExit('endingcreditsaudition: copyright reference has %d colors, '
                         'expected exactly black, green, and white' % len(colors))
    ordered = sorted(colors, key=lambda color: sum(color))
    black, green, white = ordered
    if black != (0, 0, 0):
        raise SystemExit('endingcreditsaudition: darkest copyright color is %s, not black'
                         % (black,))
    return black, green, white


def _fitting_mask(font_path, text, cap, maximum_width=152):
    while cap >= 5:
        mask = render(font_path, text, cap=cap)
        if mask.width <= maximum_width:
            return mask
        cap -= 1
    raise SystemExit('endingcreditsaudition: cannot fit %r in the credit band' % text)


def _fitting_levels(font_path, text, cap, aa, maximum_width=152):
    """The `aa` counterpart of `_fitting_mask`.

    Anti-aliased text is a little wider than the same string thresholded at 50%, because
    the dim level keeps edge pixels the 1-bit mask drops, so the fit is measured again
    rather than assumed from the `shadow` cap.
    """
    while cap >= 5:
        partial, full = render_levels(font_path, text, cap=cap, low=aa[0], high=aa[1])
        if full.width <= maximum_width:
            return partial, full
        cap -= 1
    raise SystemExit('endingcreditsaudition: cannot fit %r in the credit band' % text)


def _paste_mask(screen, mask, xy, color):
    solid = Image.new('RGB', mask.size, color)
    screen.paste(solid, xy, mask)


def make_card(base, font_path, role, name, colors, style=STYLE_SHADOW,
              aa=(AA_LOW, AA_HIGH)):
    black, green, white = colors
    screen = base.copy()
    ImageDraw.Draw(screen).rectangle((0, CREDIT_BAND_TOP, 159, 143), fill=black)

    for text, cap, top in ((role, ROLE_CAP, ROLE_Y), (name, NAME_CAP, NAME_TILE_Y + 2)):
        if style == STYLE_SHADOW:
            mask = _fitting_mask(font_path, text, cap=cap)
            xy = ((160 - mask.width) // 2, top)
            # Match the approved title card's crisp white lettering and green
            # lower-right shadow at native Game Boy resolution.
            _paste_mask(screen, mask, (xy[0] + 1, xy[1] + 1), green)
            _paste_mask(screen, mask, xy, white)
        else:
            partial, full = _fitting_levels(font_path, text, cap=cap, aa=aa)
            xy = ((160 - full.width) // 2, top)
            _paste_mask(screen, partial, xy, green)
            _paste_mask(screen, full, xy, white)
    return screen


def build_audition(font_path, reference_path, frame_path, style=STYLE_SHADOW,
                   aa=(AA_LOW, AA_HIGH), strict_font=True):
    """Render all 22 cards.  `strict_font` is the promotion guard, not an audition one.

    Auditioning a replacement font is the whole point of this tool, so an unapproved font
    only has to match when the caller is freezing the asset the build installs.
    """
    font_sha = _sha(font_path)
    if font_sha != FONT_SHA256:
        if strict_font:
            raise SystemExit('endingcreditsaudition: Poppins SHA-256 is %s, expected %s'
                             % (font_sha, FONT_SHA256))
        print('endingcreditsaudition: auditioning unapproved font %s (SHA-256 %s)'
              % (os.path.basename(font_path), font_sha[:16]))
    colors = _title_colors(reference_path) if reference_path else \
        ((0, 0, 0), TITLE_GREEN, TITLE_WHITE)
    base = _nearest_native(frame_path, SCREEN_SCALE, 'ending frame')
    cards = [make_card(base, font_path, role, name, colors, style, aa)
             for role, name in CARDS]
    clipped = {index: sorted(rows) for index, card in enumerate(cards)
               if (rows := _uncovered_rows(card))}
    if clipped:
        print('endingcreditsaudition: %s %s: %d card(s) ink band rows no strip uploads, '
              'so the ROM clips them: %s'
              % (os.path.splitext(os.path.basename(font_path))[0], style, len(clipped),
                                          ', '.join('card %d row(s) %s' %
                                                    (index, rows) for index, rows
                                                    in sorted(clipped.items())[:4])))
    return cards


def _uncovered_rows(card):
    """Band rows this card inks which no strip uploads, so the ROM cannot show them.

    The approved shadow style already loses the last row of a cap-10 descender this way,
    so this reports rather than refuses -- but a style which clips more than the approved
    one is drawing a preview the ROM will not reproduce.
    """
    covered = set(range(ROLE_Y, ROLE_Y + 16)) | set(range(NAME_TILE_Y, NAME_TILE_Y + 16))
    pixels = card.convert('RGB').load()
    return {y for y in range(CREDIT_BAND_TOP, 144) if y not in covered
            and any(pixels[x, y] != (0, 0, 0) for x in range(160))}


def _pack_strip(screen, top):
    """Return the 20x2 Game Boy 2bpp tiles covering one 160x16 text strip."""
    # The mock-up's muted green and off-white are semantic palette colors.  The
    # Super Game Boy credit scene maps indices 2 and 3 to its brighter live green
    # and white, exactly as the already-approved four-card prototype did.
    palette = {(0, 0, 0): 0, TITLE_GREEN: 2, TITLE_WHITE: 3}
    pixels = screen.convert('RGB').load()
    packed = bytearray()
    for tile_y in range(2):
        for tile_x in range(20):
            for row in range(8):
                lo = hi = 0
                for column in range(8):
                    color = pixels[tile_x * 8 + column, top + tile_y * 8 + row]
                    if color not in palette:
                        raise SystemExit('endingcreditsaudition: unexpected credit color %s'
                                         % (color,))
                    value = palette[color]
                    bit = 7 - column
                    lo |= (value & 1) << bit
                    hi |= ((value >> 1) & 1) << bit
                packed.extend((lo, hi))
    if len(packed) != STRIP_BYTES:
        raise AssertionError(len(packed))
    return bytes(packed)


def _font_identity(font_path):
    """The font's own family and style, so a frozen asset cannot misname its source."""
    family, style = ImageFont.truetype(font_path, 24).getname()
    return ('%s %s' % (family, style)).strip()


def frozen_asset(cards, font_path, style=STYLE_SHADOW, aa=None, license_text=None):
    pack = b''.join(_pack_strip(card, ROLE_Y) +
                    _pack_strip(card, NAME_TILE_Y) for card in cards)
    identity = _font_identity(font_path)
    source = {
        'font': '%s (%s)' % (identity, os.path.basename(font_path)),
        'font_sha256': _sha(font_path),
        'license': license_text or DEFAULT_LICENSE,
        'generator': 'tools/endingcreditsaudition.py',
        'style': style,
        'card_count': len(CREDITS),
        'role_screen_y': ROLE_Y,
        'name_tile_screen_y': NAME_TILE_Y,
        'native_end_mark': 'preserved',
    }
    if style == STYLE_AA and aa:
        # Without the coverage cuts the pack cannot be regenerated from the font.
        source['aa_low'], source['aa_high'] = aa
    return {
        'format': ASSET_FORMAT,
        'name': '%s Ending Credits' % identity,
        'source': source,
        'credits': [
            {
                'role': role,
                'name': name,
                'native_role': native_role,
                'native_name': native_name,
                'duration': duration,
            }
            for role, name, native_role, native_name, duration in CREDITS
        ],
        'pack': {
            'encoding': 'zlib+base64',
            'raw_bytes': len(pack),
            'sha256': hashlib.sha256(pack).hexdigest(),
            'data': base64.b64encode(zlib.compress(pack, 9)).decode('ascii'),
        },
    }


# The two strips, and nothing else.  CREDIT_BAND_TOP is where the mock-up paints its
# black rectangle, but a capture of the real roll still has forest above y=96, so a
# comparison taken from 84 comes out measuring scenery.
STRIP_ROWS = (ROLE_Y, NAME_TILE_Y + 16)


def _band(card, scale):
    """The two text strips alone, which is all a style comparison is about."""
    top, bottom = STRIP_ROWS
    return card.crop((0, top, 160, bottom)).resize(
        (160 * scale, (bottom - top) * scale), Image.Resampling.NEAREST)


def comparison_sheet(columns, scale=4):
    """Lay labelled style columns side by side, one card per row."""
    labels = [label for label, _cards in columns]
    height = (STRIP_ROWS[1] - STRIP_ROWS[0]) * scale
    cell = 160 * scale
    rows = len(columns[0][1])
    sheet = Image.new('RGB', (len(columns) * cell, 16 + rows * (height + 4)), 'white')
    draw = ImageDraw.Draw(sheet)
    for index, label in enumerate(labels):
        draw.text((index * cell + 4, 4), label, fill='black')
    for row in range(rows):
        for index, (_label, cards) in enumerate(columns):
            sheet.paste(_band(cards[row], scale),
                        (index * cell, 16 + row * (height + 4)))
    return sheet


def japanese_reference(directory):
    """Load the native cards endingcreditscanjp.py captured, in roll order."""
    paths = sorted(glob.glob(os.path.join(directory, 'card_*.png')))
    if len(paths) != len(CREDITS):
        raise SystemExit('endingcreditsaudition: %s holds %d card PNG(s), expected %d '
                         '-- regenerate with endingcreditscanjp.py --cards-dir'
                         % (directory, len(paths), len(CREDITS)))
    cards = []
    for path in paths:
        image = Image.open(path).convert('RGB')
        scale = image.width // NATIVE_SIZE[0]
        if not scale or image.size != (NATIVE_SIZE[0] * scale, NATIVE_SIZE[1] * scale):
            raise SystemExit('endingcreditsaudition: %s is %s, not a whole-number '
                             'multiple of the Game Boy screen' % (path, image.size))
        cards.append(image.resize(NATIVE_SIZE, Image.Resampling.NEAREST))
    return cards


def ink_ratio(cards):
    """Dim ink per bright ink over the credit band -- the native roll sits near 0.85."""
    dim = bright = 0
    for card in cards:
        for color in card.crop((0, STRIP_ROWS[0], 160,
                                STRIP_ROWS[1])).convert('RGB').getdata():
            if color == (0, 0, 0):
                continue
            # Any capture of the real thing uses the live palette, not the mock-up's.
            if sum(color) >= 720:
                bright += 1
            else:
                dim += 1
    return dim / bright if bright else 0.0


def _style_spec(spec, default_aa):
    """Parse one --style entry: `shadow`, `aa`, or `aa:LOW:HIGH` for a tuning variant."""
    parts = spec.strip().split(':')
    style = parts[0]
    if style not in STYLES:
        raise SystemExit('endingcreditsaudition: unknown --style %r, expected %s'
                         % (style, ' or '.join(STYLES)))
    if len(parts) == 1:
        aa = default_aa
    elif len(parts) == 3 and style == STYLE_AA:
        aa = (int(parts[1]), int(parts[2]))
    else:
        raise SystemExit('endingcreditsaudition: %r is not a style; use `aa:LOW:HIGH` '
                         'to vary the coverage cuts' % spec)
    if not 0 <= aa[0] < aa[1] <= 255:
        raise SystemExit('endingcreditsaudition: %r needs 0 <= LOW < HIGH <= 255' % spec)
    label = style if style != STYLE_AA else 'aa %d/%d' % aa
    return label, style, aa


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--font', required=True,
                        help='comma-separated. Every font is rendered in every --style, '
                             'so fonts and styles compare in one sheet.')
    parser.add_argument('--copyright-reference')
    parser.add_argument('--frame', required=True)
    parser.add_argument('--output', default='build/ending_credits_audition.png')
    parser.add_argument('--screen-output',
                        default='build/ending_credits_audition_director.png')
    parser.add_argument('--asset-output')
    parser.add_argument('--style', default=STYLE_SHADOW,
                        help='comma-separated: %s. More than one writes a comparison '
                             'sheet instead of a contact sheet.' % ', '.join(STYLES))
    parser.add_argument('--aa-low', type=int, default=AA_LOW,
                        help='coverage at which a pixel takes the dim color (0-255)')
    parser.add_argument('--aa-high', type=int, default=AA_HIGH,
                        help='coverage at which a pixel takes the bright color (0-255)')
    parser.add_argument('--japanese',
                        help='a endingcreditscanjp.py --cards-dir, added as the '
                             'leftmost comparison column')
    parser.add_argument('--compare-output',
                        default='build/ending_credits_styles.png')
    parser.add_argument('--font-license',
                        help='licence line recorded in a frozen asset; required when '
                             'freezing a font other than the approved one')
    parser.add_argument('--allow-new-font', action='store_true',
                        help='permit --asset-output with a font other than the approved '
                             'Poppins Medium')
    args = parser.parse_args()

    if not 0 <= args.aa_low < args.aa_high <= 255:
        raise SystemExit('endingcreditsaudition: need 0 <= --aa-low < --aa-high <= 255')
    styles = [_style_spec(spec, (args.aa_low, args.aa_high))
              for spec in args.style.split(',') if spec.strip()]
    fonts = [font.strip() for font in args.font.split(',') if font.strip()]
    for font in fonts:
        if not os.path.exists(font):
            raise SystemExit('endingcreditsaudition: missing font %s' % font)
    if args.asset_output and (len(styles) != 1 or len(fonts) != 1):
        raise SystemExit('endingcreditsaudition: --asset-output freezes one font in one '
                         'style; pass a single --font and --style')

    strict = bool(args.asset_output) and not args.allow_new_font
    if args.asset_output and args.allow_new_font and not args.font_license:
        raise SystemExit('endingcreditsaudition: freezing a new font needs '
                         '--font-license, or the asset would record the wrong one')
    rendered = []
    for font in fonts:
        stem = os.path.splitext(os.path.basename(font))[0]
        for label, style, aa in styles:
            cards = build_audition(font, args.copyright_reference, args.frame,
                                   style, aa, strict_font=strict)
            rendered.append(('%s %s' % (stem, label) if len(fonts) > 1 else label,
                             style, cards))
    for label, _style, cards in rendered:
        print('endingcreditsaudition: %-24s dim/bright ink ratio %.2f'
              % (label, ink_ratio(cards)))

    cards = rendered[0][2]
    enlarged = [card.resize((640, 576), Image.Resampling.NEAREST) for card in cards]
    rows = math.ceil(len(enlarged) / 2)
    sheet = Image.new('RGB', (1280, rows * 576), (0, 0, 0))
    for index, card in enumerate(enlarged):
        sheet.paste(card, ((index % 2) * 640, (index // 2) * 576))

    output = Path(args.output)
    screen_output = Path(args.screen_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    screen_output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    enlarged[0].save(screen_output)
    print('Wrote %s' % output)
    print('Wrote %s' % screen_output)

    if len(rendered) > 1 or args.japanese:
        columns = []
        if args.japanese:
            native = japanese_reference(args.japanese)
            columns.append(('Japanese (native)', native))
            print('endingcreditsaudition: native dim/bright ink ratio %.2f'
                  % ink_ratio(native))
        columns.extend(('English (%s)' % label, cards)
                       for label, _style, cards in rendered)
        compare = Path(args.compare_output)
        compare.parent.mkdir(parents=True, exist_ok=True)
        comparison_sheet(columns).save(compare)
        print('Wrote %s' % compare)

    if args.asset_output:
        asset_output = Path(args.asset_output)
        asset_output.parent.mkdir(parents=True, exist_ok=True)
        asset_output.write_text(
            json.dumps(frozen_asset(cards, fonts[0], styles[0][1], styles[0][2],
                                    args.font_license), indent=2,
                       ensure_ascii=False) + '\n', encoding='utf-8')
        print('Wrote %s' % asset_output)


if __name__ == '__main__':
    main()
