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
import hashlib
import json
import math
import zlib
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw

from floorcardgen import FONT_SHA256, render


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


def _paste_mask(screen, mask, xy, color):
    solid = Image.new('RGB', mask.size, color)
    screen.paste(solid, xy, mask)


def make_card(base, font_path, role, name, colors):
    black, green, white = colors
    screen = base.copy()
    ImageDraw.Draw(screen).rectangle((0, CREDIT_BAND_TOP, 159, 143), fill=black)

    role_mask = _fitting_mask(font_path, role, cap=7)
    name_mask = _fitting_mask(font_path, name, cap=10)
    role_xy = ((160 - role_mask.width) // 2, 94)
    name_xy = ((160 - name_mask.width) // 2, 112)

    # Match the approved title card's crisp white lettering and green lower-right
    # shadow at native Game Boy resolution.
    _paste_mask(screen, role_mask, (role_xy[0] + 1, role_xy[1] + 1), green)
    _paste_mask(screen, role_mask, role_xy, white)
    _paste_mask(screen, name_mask, (name_xy[0] + 1, name_xy[1] + 1), green)
    _paste_mask(screen, name_mask, name_xy, white)
    return screen


def build_audition(font_path, reference_path, frame_path):
    font_sha = _sha(font_path)
    if font_sha != FONT_SHA256:
        raise SystemExit('endingcreditsaudition: Poppins SHA-256 is %s, expected %s'
                         % (font_sha, FONT_SHA256))
    colors = _title_colors(reference_path) if reference_path else \
        ((0, 0, 0), TITLE_GREEN, TITLE_WHITE)
    base = _nearest_native(frame_path, SCREEN_SCALE, 'ending frame')
    return [make_card(base, font_path, role, name, colors) for role, name in CARDS]


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


def frozen_asset(cards, font_path):
    pack = b''.join(_pack_strip(card, ROLE_Y) +
                    _pack_strip(card, NAME_TILE_Y) for card in cards)
    return {
        'format': ASSET_FORMAT,
        'name': 'Poppins Medium Ending Credits',
        'source': {
            'font': 'Poppins Medium v4.004 (Google Fonts)',
            'font_sha256': _sha(font_path),
            'license': 'SIL Open Font License 1.1; see licenses/OFL-1.1-Poppins.txt',
            'generator': 'tools/endingcreditsaudition.py',
            'card_count': len(CREDITS),
            'role_screen_y': ROLE_Y,
            'name_tile_screen_y': NAME_TILE_Y,
            'native_end_mark': 'preserved',
        },
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--font', required=True)
    parser.add_argument('--copyright-reference')
    parser.add_argument('--frame', required=True)
    parser.add_argument('--output', default='build/ending_credits_audition.png')
    parser.add_argument('--screen-output',
                        default='build/ending_credits_audition_director.png')
    parser.add_argument('--asset-output')
    args = parser.parse_args()

    cards = build_audition(args.font, args.copyright_reference, args.frame)
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
    if args.asset_output:
        asset_output = Path(args.asset_output)
        asset_output.parent.mkdir(parents=True, exist_ok=True)
        asset_output.write_text(json.dumps(frozen_asset(cards, args.font), indent=2,
                                          ensure_ascii=False) + '\n',
                                encoding='utf-8')
        print('Wrote %s' % asset_output)


if __name__ == '__main__':
    main()
