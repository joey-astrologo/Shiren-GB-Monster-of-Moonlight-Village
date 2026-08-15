#!/usr/bin/env python3
"""Build the one-bit arrival-card asset from Joey's approved source contact sheet.

``Titles.webp`` contains eight native-resolution 160x144 cards.  Its location names,
the Forest ``F``, and every supplied numeral are authoritative pixels; no system font or
TTF participates in this generator.  The missing 3/4/6/7/8 numerals are the approved
hand-built additions, derived from the supplied digits' stroke grammar.  Together they
produce fifty fixed 32x12 ``F#`` fields for the game's existing dynamic uploader.

The generated JSON is the build input.  Regenerating it additionally proves the contact
sheet hash, dimensions, palette, crop geometry, all known markers, and the F1-F50 bounds.

usage: floorcardgen.py --source Titles.webp --moon-exit MOCK.png [--output FILE]
"""
import argparse
import hashlib
import json

from PIL import Image


SOURCE_SHA256 = 'd2d6540b2ca617975d06d83dadaaf40c807218d363864c27f7ac1b3459f172ff'
MOONLIGHT_EXIT_SHA256 = 'f7173df64c389728ac244f58044c26815efd03c22f973b1a07f8d1892e6dc42a'
SOURCE_SIZE = (640, 288)
MOONLIGHT_EXIT_SIZE = (322, 290)
CARD_SIZE = (160, 144)
FIELD_WIDTH = 32
FIELD_HEIGHT = 12
LABELS = ('Moonlight Village', 'Forest', 'Koma Cave', 'Crags', 'Kuyo Pass',
          "Dragon's Maw", 'Orochi', 'Moonlight Exit')

# Crop rectangles are local to their 160x144 contact-sheet cells.  Right/bottom are
# exclusive.  These are the exact occupied bounds in Joey's source raster.
LABEL_CROPS = {
    'Moonlight Village': (0, (10, 63, 150, 80)),
    'Forest': (1, (68, 64, 121, 76)),
    'Koma Cave': (2, (57, 64, 144, 76)),
    'Crags': (3, (81, 64, 128, 80)),
    'Kuyo Pass': (4, (59, 64, 140, 82)),
    "Dragon's Maw": (5, (43, 64, 155, 80)),
    'Orochi': (6, (74, 63, 127, 76)),
}
MARKER_CROPS = {
    1: (1, (38, 64, 56, 76)),
    5: (2, (27, 64, 45, 76)),
    10: (3, (42, 64, 70, 76)),
    12: (4, (20, 64, 48, 76)),
    19: (5, (5, 64, 31, 76)),
    21: (6, (33, 64, 62, 76)),
    50: (7, (17, 64, 46, 76)),
}
DIGIT_CROPS = {
    '0': (7, (37, 64, 46, 76)),
    '1': (6, (55, 64, 62, 76)),
    '2': (6, (45, 64, 54, 76)),
    '5': (7, (29, 64, 36, 76)),
    '9': (5, (24, 64, 31, 76)),
}
FOREST_F_CROP = (1, (68, 64, 78, 76))

# Only these five glyphs were absent from the supplied contact sheet.  They are stored as
# literal one-bit rows so the approved audition is stable on every host.
MISSING_DIGITS = {
    '3': (
        '..#####.', '.#######', '.....###', '.....###', '...####.', '...#####',
        '.....###', '......##', '......##', '.....###', '.######.', '#####...',
    ),
    '4': (
        '....##.', '...###.', '..####.', '.##.##.', '##..##.', '##..##.',
        '#######', '.######', '....##.', '....##.', '...####', '..#####',
    ),
    '6': (
        '...###.', '..####.', '.##....', '##.....', '#####..', '######.',
        '##...##', '##...##', '##...##', '.##.##.', '.#####.', '..###..',
    ),
    '7': (
        '########', '########', '.....##.', '....##..', '....##..', '...##...',
        '...##...', '..##....', '..##....', '.##.....', '.##.....', '##......',
    ),
    '8': (
        '..#####..', '.###.###.', '.##...##.', '.##...##.', '..#####..', '.#######.',
        '##....##.', '##....##.', '##....##.', '.##..###.', '.######..', '..####...',
    ),
}

# Each dynamic field is four tiles wide.  The ink is right-aligned to the same position
# as the reviewed marker from that native floor group; the source label remains at its
# original pixel x.  This reproduces all seven numbered source cards exactly.
FIELD_LAYOUTS = (
    (range(1, 3), 24, 31),
    (range(3, 7), 16, 28),
    (range(7, 11), 40, 29),
    (range(11, 15), 16, 31),
    (range(15, 21), 0, 30),
    (range(21, 22), 32, 29),
    (range(22, 51), 0, 31),
)
LABEL_LEFTS = {
    'Moonlight Village': 10,
    'Forest': 68,
    'Koma Cave': 57,
    'Crags': 81,
    'Kuyo Pass': 59,
    "Dragon's Maw": 43,
    'Orochi': 74,
    'Moonlight Exit': 41,
}


def _sha(path):
    with open(path, 'rb') as src:
        return hashlib.sha256(src.read()).hexdigest()


def _load_source(path):
    digest = _sha(path)
    if digest != SOURCE_SHA256:
        raise SystemExit('floorcardgen: source SHA-256 is %s, expected %s' %
                         (digest, SOURCE_SHA256))
    image = Image.open(path).convert('RGB')
    if image.size != SOURCE_SIZE:
        raise SystemExit('floorcardgen: source is %s, expected %s' %
                         (image.size, SOURCE_SIZE))
    colors = set(image.getdata())
    if colors != {(0, 0, 0), (255, 255, 255)}:
        raise SystemExit('floorcardgen: source colors changed: %s' % sorted(colors))
    return image.convert('L').point(lambda value: 255 if value == 0 else 0, mode='1')


def _load_moonlight_exit(path):
    digest = _sha(path)
    if digest != MOONLIGHT_EXIT_SHA256:
        raise SystemExit('floorcardgen: Moonlight Exit SHA-256 is %s, expected %s' %
                         (digest, MOONLIGHT_EXIT_SHA256))
    image = Image.open(path).convert('L')
    if image.size != MOONLIGHT_EXIT_SIZE:
        raise SystemExit('floorcardgen: Moonlight Exit mock is %s, expected %s' %
                         (image.size, MOONLIGHT_EXIT_SIZE))
    # The capture is an exact 2x raster within a one-pixel top/bottom and two-pixel right
    # border. Thresholding at 50% yields uniform 2x2 blocks despite its grayscale PNG.
    doubled = image.crop((0, 1, 320, 289)).point(
        lambda value: 255 if value < 128 else 0, mode='1')
    for y in range(CARD_SIZE[1]):
        for x in range(CARD_SIZE[0]):
            values = {doubled.getpixel((x * 2 + dx, y * 2 + dy))
                      for dy in range(2) for dx in range(2)}
            if len(values) != 1:
                raise SystemExit('floorcardgen: Moonlight Exit block %d,%d is not exact 2x'
                                 % (x, y))
    native = doubled.resize(CARD_SIZE, Image.Resampling.NEAREST)
    if native.getbbox() != (4, 63, 157, 80):
        raise SystemExit('floorcardgen: Moonlight Exit native bbox is %s' %
                         (native.getbbox(),))
    return native


def _cell_crop(source, spec, tight=True):
    cell, box = spec
    left = (cell % 4) * CARD_SIZE[0]
    top = (cell // 4) * CARD_SIZE[1]
    x0, y0, x1, y1 = box
    mask = source.crop((left + x0, top + y0, left + x1, top + y1))
    if tight and mask.getbbox() != (0, 0, mask.width, mask.height):
        raise SystemExit('floorcardgen: crop %s is not tight' % (spec,))
    return mask


def _rows_mask(rows):
    widths = {len(row) for row in rows}
    if len(rows) != FIELD_HEIGHT or len(widths) != 1:
        raise SystemExit('floorcardgen: malformed hand-built digit')
    mask = Image.new('1', (widths.pop(), len(rows)), 0)
    pixels = mask.load()
    for y, row in enumerate(rows):
        for x, value in enumerate(row):
            if value == '#':
                pixels[x, y] = 1
            elif value != '.':
                raise SystemExit('floorcardgen: unknown digit pixel %r' % value)
    return mask


def _record(mask):
    """Encode variable-width one-bit rows as MSB-first hex strings."""
    pixels = mask.load()
    rows = []
    for y in range(mask.height):
        row = bytearray((mask.width + 7) // 8)
        for x in range(mask.width):
            if pixels[x, y]:
                row[x // 8] |= 0x80 >> (x & 7)
        rows.append(row.hex())
    return {'width': mask.width, 'height': mask.height, 'rows': rows}


def _compose_marker(f_mask, digits, number):
    components = [f_mask] + [digits[ch] for ch in str(number)]
    width = sum(mask.width for mask in components) + len(components) - 1
    marker = Image.new('1', (width, FIELD_HEIGHT), 0)
    left = 0
    for mask in components:
        marker.paste(mask, (left, 0))
        left += mask.width + 1
    return marker


def _layout(number):
    matches = [(group, right) for floors, group, right in FIELD_LAYOUTS
               if number in floors]
    if len(matches) != 1:
        raise SystemExit('floorcardgen: floor %d has %d layouts' %
                         (number, len(matches)))
    return matches[0]


def _number_field(markers, f_mask, digits, number):
    marker = markers.get(number) or _compose_marker(f_mask, digits, number)
    group_left, right = _layout(number)
    left = right + 1 - marker.width
    if left < 0 or left + marker.width > FIELD_WIDTH:
        raise SystemExit('floorcardgen: F%d is %dpx and does not fit its field at %d' %
                         (number, marker.width, left))
    field = Image.new('1', (FIELD_WIDTH, FIELD_HEIGHT), 0)
    field.paste(marker, (left, 0))
    return field, group_left


def build(source_path, moon_exit_path):
    source = _load_source(source_path)
    moon_exit = _load_moonlight_exit(moon_exit_path)
    labels = {label: _cell_crop(source, LABEL_CROPS[label]) for label in LABELS[:-1]}
    labels['Moonlight Exit'] = moon_exit.crop((41, 63, 157, 80))
    if labels['Moonlight Exit'].getbbox() != (0, 0, 116, 17):
        raise SystemExit('floorcardgen: Moonlight Exit name crop changed')
    markers = {number: _cell_crop(source, spec)
               for number, spec in MARKER_CROPS.items()}
    # The source F uses an 11px ink height inside the shared 12px marker line box.
    f_mask = _cell_crop(source, FOREST_F_CROP, tight=False)
    digits = {digit: _cell_crop(source, spec)
              for digit, spec in DIGIT_CROPS.items()}
    digits.update({digit: _rows_mask(rows)
                   for digit, rows in MISSING_DIGITS.items()})
    if set(digits) != set('0123456789'):
        raise SystemExit('floorcardgen: incomplete digit alphabet')

    numbers = {}
    groups = {}
    for number in range(1, 51):
        field, group_left = _number_field(markers, f_mask, digits, number)
        numbers[str(number)] = _record(field)
        groups[str(number)] = group_left

    # Prove that the dynamic composition reproduces every supplied floor marker at its
    # exact x position and that the shared labels retain their exact source x positions.
    for number, (cell, box) in MARKER_CROPS.items():
        field, group_left = _number_field(markers, f_mask, digits, number)
        x0, _y0, x1, _y1 = box
        actual_box = field.getbbox()
        actual = field.crop(actual_box)
        if actual.tobytes() != markers[number].tobytes():
            raise SystemExit('floorcardgen: F%d no longer matches its source shape' %
                             number)
        if number != 50 and actual_box[0] + group_left != x0:
            raise SystemExit('floorcardgen: F%d source x changed' % number)

    forest_card = source.crop((160 + 38, 64, 160 + 121, 76))
    moonlight_exit_card = moon_exit.crop((4, 63, 157, 80))
    return {
        'format': 'shiren-gb-source-arrival-cards-v2',
        'name': 'Source Raster Arrival Cards',
        'source': {
            'artwork': 'Titles.webp supplied by Joey',
            'artwork_sha256': SOURCE_SHA256,
            'moonlight_exit_mock_sha256': MOONLIGHT_EXIT_SHA256,
            'generator': 'tools/floorcardgen.py',
            'font_renderer': None,
            'source_card_size': list(CARD_SIZE),
            'strip_screen_top': 64,
            'note': ('Moonlight Village begins at source y63 and is shifted down one '
                     'pixel by the game\'s fixed y64 tile strip.'),
        },
        'labels': {label: _record(labels[label]) for label in LABELS},
        'label_lefts': LABEL_LEFTS,
        'number_tops': {label: (1 if label in ('Orochi', 'Moonlight Exit') else 0)
                        for label in LABELS},
        'number_groups': groups,
        'numbers': numbers,
        'special_cards': {
            'F1 Forest': _record(forest_card),
            'F50 Moonlight Exit': _record(moonlight_exit_card),
        },
        'special_lefts': {'F1 Forest': 38, 'F50 Moonlight Exit': 4},
        'digit_sources': {
            'source': sorted(DIGIT_CROPS),
            'hand_built': sorted(MISSING_DIGITS),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--moon-exit', required=True)
    parser.add_argument('--output', default='-')
    args = parser.parse_args()
    result = json.dumps(build(args.source, args.moon_exit), indent=2,
                        ensure_ascii=False) + '\n'
    if args.output == '-':
        print(result, end='')
    else:
        with open(args.output, 'w', encoding='utf-8') as dst:
            dst.write(result)


if __name__ == '__main__':
    main()
