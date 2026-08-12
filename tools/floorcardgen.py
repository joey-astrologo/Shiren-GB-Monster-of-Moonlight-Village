#!/usr/bin/env python3
"""Generate the compact one-bit source asset for the arrival-card renderer.

This is the repository version of Joey's supplied ``floorcard.py`` and
``make_floor_card.py`` proof of concept.  It intentionally implements the approved clean
render only: Poppins Medium at a 12px cap height, rendered at 8x, searched over every
subpixel phase, box-filtered and hard-thresholded to one bit.  The optional hand-drawn
SciPy displacement was not used by the approved mock-ups and is therefore omitted.

The two supplied 6x references are authoritative.  Their native 160x144 rasters replace
the generated Moonlight Village block, Forest block, digit 1 and complete ``1 Forest``
special card so those two examples remain pixel-exact across Pillow/FreeType versions.
Every other label and number is baked into the JSON; the ROM build never needs Pillow or
the source TTF.

The expected source font is Google Fonts' OFL Poppins Medium v4.004:

    SHA-256 90373e7d838d32468438fc3e152dca0bdb12edcab99ea639f158790b1ba1fd05

usage: floorcardgen.py --font Poppins-Medium.ttf --village REF.png --forest REF.png
                       [--output FILE]
"""
import argparse
import hashlib
import json
import os

from PIL import Image, ImageDraw, ImageFont


SCALE = 8
CAP = 12
BAND = (65, 80)
BG = (240, 240, 240)
FONT_SHA256 = '90373e7d838d32468438fc3e152dca0bdb12edcab99ea639f158790b1ba1fd05'
LABELS = ('Moonlight Village', 'Forest', 'Koma Cave', 'Crags', 'Kuyo Pass',
          "Dragon's Maw", 'Orochi', 'Moon Exit')


def _sha(path):
    with open(path, 'rb') as src:
        return hashlib.sha256(src.read()).hexdigest()


def _font_size(font_path, cap=CAP):
    best = None
    distance = 1 << 30
    for size in range(6, 300):
        font = ImageFont.truetype(font_path, size)
        box = font.getbbox('H')
        error = abs((box[3] - box[1]) - cap * SCALE)
        if error < distance:
            best, distance = size, error
    return best


def _trim(mask):
    pixels = mask.load()
    xs = []
    ys = []
    for y in range(mask.height):
        for x in range(mask.width):
            if pixels[x, y]:
                xs.append(x)
                ys.append(y)
    if not xs:
        raise ValueError('cannot trim an empty mask')
    return mask.crop((min(xs), min(ys), max(xs) + 1, max(ys) + 1))


def render(font_path, text, cap=CAP):
    """Reproduce the supplied clean supersample/phase-search renderer."""
    font = ImageFont.truetype(font_path, _font_size(font_path, cap))
    best = None
    for dy in range(SCALE):
        for dx in range(SCALE):
            high = Image.new('L', (4000, 700), 0)
            draw = ImageDraw.Draw(high)
            x = float(200 + dx)
            for ch in text:
                draw.text((x, 200 + dy), ch, 255, font=font)
                x += font.getlength(ch)
            box = high.getbbox()
            high = high.crop((box[0] - 4 * SCALE, box[1] - 4 * SCALE,
                              box[2] + 4 * SCALE, box[3] + 4 * SCALE))
            box = high.getbbox()
            left = (box[0] // SCALE) * SCALE
            top = (box[1] // SCALE) * SCALE
            right = ((box[2] + SCALE - 1) // SCALE) * SCALE
            bottom = ((box[3] + SCALE - 1) // SCALE) * SCALE
            high = high.crop((left, top, right, bottom))
            low = high.resize((high.width // SCALE, high.height // SCALE),
                              Image.Resampling.BOX)
            score = sum(min(value, 255 - value) for value in low.getdata())
            if best is None or score < best[0]:
                best = score, low
    mask = best[1].point(lambda value: 255 if value >= 128 else 0, mode='1')
    return _trim(mask)


def _native_reference(path):
    image = Image.open(path).convert('RGB')
    if image.size != (960, 864):
        raise SystemExit('floorcardgen: %s is %s, expected an exact 960x864 6x reference'
                         % (path, image.size))
    native = image.resize((160, 144), Image.Resampling.NEAREST)
    if native.resize(image.size, Image.Resampling.NEAREST).tobytes() != image.tobytes():
        raise SystemExit('floorcardgen: %s is not an exact 6x nearest-neighbour raster'
                         % path)
    colors = set(native.getdata())
    if colors != {BG, (0, 0, 0)}:
        raise SystemExit('floorcardgen: %s colors are %s, expected only %s and black'
                         % (path, sorted(colors), BG))
    return native.convert('L').point(lambda value: 255 if value == 0 else 0, mode='1')


def _bbox_block(screen):
    box = screen.getbbox()
    if not box:
        raise SystemExit('floorcardgen: reference has no ink')
    return screen.crop(box), box


def _split_forest(block):
    """Split the authoritative ``1`` and ``Forest`` around its exact 10px gap."""
    occupied = []
    px = block.load()
    for x in range(block.width):
        occupied.append(any(px[x, y] for y in range(block.height)))
    for start in range(1, block.width - 10):
        if occupied[start - 1] and not any(occupied[start:start + 10]) \
                and occupied[start + 10]:
            one = _trim(block.crop((0, 0, start, block.height)))
            forest = _trim(block.crop((start + 10, 0, block.width, block.height)))
            return one, forest
    raise SystemExit('floorcardgen: Forest reference has no exact 10px number gap')


def _record(mask):
    """Encode variable-width one-bit rows as MSB-first hex strings."""
    px = mask.load()
    rows = []
    for y in range(mask.height):
        row = bytearray((mask.width + 7) // 8)
        for x in range(mask.width):
            if px[x, y]:
                row[x // 8] |= 0x80 >> (x & 7)
        rows.append(row.hex())
    return {'width': mask.width, 'height': mask.height, 'rows': rows}


def build(font_path, village_path, forest_path):
    font_sha = _sha(font_path)
    if font_sha != FONT_SHA256:
        raise SystemExit('floorcardgen: Poppins SHA-256 is %s, expected %s'
                         % (font_sha, FONT_SHA256))

    village_screen = _native_reference(village_path)
    forest_screen = _native_reference(forest_path)
    village, village_box = _bbox_block(village_screen)
    forest_card, forest_box = _bbox_block(forest_screen)
    one, forest = _split_forest(forest_card)

    labels = {label: _record(render(font_path, label)) for label in LABELS}
    labels['Moonlight Village'] = _record(village)
    labels['Forest'] = _record(forest)
    numbers = {str(number): _record(render(font_path, str(number)))
               for number in range(1, 51)}
    numbers['1'] = _record(one)

    return {
        'format': 'shiren-gb-poppins-arrival-cards-v1',
        'name': 'Poppins Medium Arrival Cards',
        'source': {
            'font': 'Poppins Medium v4.004 (Google Fonts)',
            'font_sha256': font_sha,
            'license': 'SIL Open Font License 1.1; see licenses/OFL-1.1-Poppins.txt',
            'generator': 'tools/floorcardgen.py',
            'supersample': SCALE,
            'cap_height': CAP,
            'threshold': 0.5,
            'handdrawn': False,
            'band': list(BAND),
            'village_reference_sha256': _sha(village_path),
            'forest_reference_sha256': _sha(forest_path),
        },
        'reference_boxes': {
            'Moonlight Village': list(village_box),
            '1 Forest': list(forest_box),
        },
        'labels': labels,
        'numbers': numbers,
        'special_cards': {'1 Forest': _record(forest_card)},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--font', required=True)
    parser.add_argument('--village', required=True)
    parser.add_argument('--forest', required=True)
    parser.add_argument('--output', default='-')
    args = parser.parse_args()
    result = json.dumps(build(args.font, args.village, args.forest), indent=2,
                        ensure_ascii=False) + '\n'
    if args.output == '-':
        print(result, end='')
    else:
        with open(args.output, 'w', encoding='utf-8') as dst:
            dst.write(result)


if __name__ == '__main__':
    main()
