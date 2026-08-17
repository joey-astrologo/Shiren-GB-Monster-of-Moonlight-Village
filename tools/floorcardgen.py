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
# The eight cards the game selects, in native table order. Three now carry a modifier the
# Japanese always had; SOURCE_LABELS keeps the contact-sheet names the crops are keyed on.
SOURCE_LABELS = ('Moonlight Village', 'Forest', 'Koma Cave', 'Crags', 'Kuyo Pass',
                 "Dragon's Maw", 'Orochi', 'Moonlight Exit')
LABELS = ('Moonlight Village', 'Shifting Forest', 'Koma Cave', "Avatar's Crag",
          'Kuyo Pass', "Dragon's Maw", "Orochi's Den", 'Moonlight Exit')

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

# ---- composed labels -------------------------------------------------------------
#
# Three place names gained a modifier that the Japanese always carried: `へんげのもり`
# is a forest of TRANSFORMATION, `けしんのいわば` the crags of an INCARNATION, and
# `オロチのまくつ` Orochi's DEN. The supplied contact sheet has no artwork for the longer
# names, so they are composed from its own letterforms, exactly as the missing digits are
# hand-built from the supplied digits' stroke grammar.
#
# Only three glyphs are absent from the sheet entirely. They are stored as literal rows,
# derived from the shapes they must sit beside: A is the supplied V reflected with a
# crossbar, f takes t's stem and crossbar with h's ascender, and S follows C's aperture
# and stroke weight.
HAND_BUILT_LETTERS = {
    'A': (-11, (
        '.....#....', '....##....', '...###....', '...##.#...', '...##.##..',
        '..##..##..', '..######..', '.########.', '.##....##.', '###....##.',
        '##.....###', '##......#.',
    )),
    'S': (-11, (
        '...######.', '.#########', '###.....##', '##........', '###.......',
        '.#####....', '..######..', '.....#####', '.......###', '##......##',
        '####...###', '.#######..',
    )),
    'f': (-12, (
        '...#####', '..######', '..##....', '..##....', '..##....', '########',
        '########', '..##....', '..##....', '..##....', '..##....', '..##....',
        '..##....',
    )),
}

# The sheet is hand-lettered PER CARD -- Moonlight Village's h is 8px with a flared stem,
# Orochi's is 7px and square. So a composed name takes every shared letter from the label
# it extends; anything else disagrees with the original card letter for letter.
COMPOSED_LABELS = {
    'Shifting Forest': 'Forest',
    "Avatar's Crag": 'Crags',
    "Orochi's Den": 'Orochi',
}
# Labels whose blank-column runs align 1:1 with their characters. Forest is excluded: its
# F is drawn with a detached stem, so the first run is the stem alone.
CLEAN_SEGMENTATION = ('Moonlight Village', 'Crags', 'Orochi')
# Explicit ink ranges where segmentation cannot be trusted. `rows` clips a glyph that
# shares its run with a neighbour.
GLYPH_RANGES = {
    'Forest': {'F': (0, 9), 'o': (11, 17), 'r': (20, 25),
               'e': (27, 34), 's': (37, 42), 't': (45, 52)},
    'Koma Cave': {'v': (70, 77)},
    # The apostrophe shares a blank-column run with the following s. Its ink is rows 1-5
    # of the label, measured: an earlier guess of rows 0-3 clipped the tail and left it
    # reading as a grave accent.
    "Dragon's Maw": {'D': (0, 12), "'": (60, 63, 1, 5)},
}
# A glyph that sits ON the baseline, for labels that do not segment 1:1.
BASELINE_ANCHORS = {'Forest': (11, 17), 'Koma Cave': (12, 19), "Dragon's Maw": (21, 28)}
# Cards keeping their source artwork keep their reviewed digit offset unchanged; only a
# composed label needs its baseline measured.
SOURCE_NUMBER_TOPS = {
    'Moonlight Village': 0, 'Forest': 0, 'Koma Cave': 0, 'Crags': 0,
    'Kuyo Pass': 0, "Dragon's Maw": 0, 'Orochi': 1, 'Moonlight Exit': 1,
}
LETTER_TRACKING = 1        # measured mode of the sheet's inter-letter gaps
WORD_SPACE = 7             # measured word gap
DIGIT_BASELINE = 11        # every F## field inks rows 0-11

# Each dynamic field is four tiles wide.  The ink is right-aligned to the same position
# as the reviewed marker from that native floor group; the source label remains at its
# original pixel x.  This reproduces all seven numbered source cards exactly.
# `group` places the 32px field on the strip; `right` is the ink's right edge INSIDE it,
# so the two are independent. The three renamed cards no longer fit at their source group
# -- Avatar's Crag needs group <= 9 where Crags sat at 40 -- and Koma Cave moves one tile
# purely to centre, which was the drift Joey noticed in play.
FIELD_LAYOUTS = (
    (range(1, 3), 0, 31),       # Forest: group 0 so its generic form also fits
    (range(3, 7), 8, 28),       # Koma Cave: was 16, recentred
    (range(7, 11), 0, 29),      # Avatar's Crag: was 40, the longer name needs the room
    (range(11, 15), 16, 31),    # Kuyo Pass: unchanged
    (range(15, 21), 0, 30),     # Dragon's Maw: unchanged
    (range(21, 22), 8, 29),     # Orochi's Den: was 32
    (range(22, 51), 0, 31),
)
# Name x on a numbered card. Recomputed from the measured label widths so each card's ink
# centres on the 160px strip, rather than inherited from the contact sheet's own x.
LABEL_LEFTS = {
    'Moonlight Village': 10,
    'Shifting Forest': 40,      # generic fallback form; F1/F2 use bespoke cards
    'Koma Cave': 52,
    "Avatar's Crag": 42,
    'Kuyo Pass': 59,
    "Dragon's Maw": 43,
    "Orochi's Den": 51,
    'Moonlight Exit': 41,       # unused: F50 is a bespoke card
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


def _ink_cols(mask):
    w, h = mask.size
    px = mask.load()
    return [any(px[x, y] for y in range(h)) for x in range(w)]


def _runs(mask):
    runs, start = [], None
    for x, on in enumerate(_ink_cols(mask)):
        if on and start is None:
            start = x
        elif not on and start is not None:
            runs.append((start, x - 1)); start = None
    if start is not None:
        runs.append((start, mask.size[0] - 1))
    return runs


def _baseline(label, mask):
    """Row the label's letters sit on, measured from a glyph known to touch it."""
    px = mask.load(); w, h = mask.size
    if label in CLEAN_SEGMENTATION:
        chars = label.replace(' ', '')
        runs = _runs(mask)
        if len(runs) != len(chars):
            raise SystemExit('floorcardgen: %r no longer segments 1:1' % label)
        best = 0
        for ch, (a, b) in zip(chars, runs):
            if ch in 'aceimnorsuvwxz':
                best = max(best, max(y for y in range(h)
                                     if any(px[x, y] for x in range(a, b + 1))))
        return best
    a, b = BASELINE_ANCHORS[label]
    return max(y for y in range(h) if any(px[x, y] for x in range(a, b + 1)))


def _glyphs(label, mask):
    """-> {char: (top relative to baseline, rows of '#'/'.')} for one source label."""
    px = mask.load(); w, h = mask.size
    base = _baseline(label, mask)
    if label in CLEAN_SEGMENTATION:
        ranges = dict(zip(label.replace(' ', ''), _runs(mask)))
    else:
        ranges = GLYPH_RANGES[label]
    out = {}
    for ch, spec in ranges.items():
        x0, x1 = spec[0], spec[1]
        ys = [y for y in range(h) if any(px[x, y] for x in range(x0, x1 + 1))]
        y0 = spec[2] if len(spec) > 2 else min(ys)
        y1 = spec[3] if len(spec) > 3 else max(ys)
        out[ch] = (y0 - base,
                   tuple(''.join('#' if px[x, y] else '.' for x in range(x0, x1 + 1))
                         for y in range(y0, y1 + 1)))
    return out


def _special_card(f_mask, digits, name_mask, name_baseline, number):
    """Compose a whole bespoke `F# Name` card, baselines aligned.

    Forest needs one for each of its two floors: its name no longer fits the generic
    layout, which always reserves a full 32px field whatever the digit's real width.
    """
    marker = _compose_marker(f_mask, digits, number)
    base = max(FIELD_HEIGHT - 1, name_baseline)
    below = max(0, name_mask.height - name_baseline)
    height = base + max(1, below)
    width = marker.width + WORD_SPACE + name_mask.width
    card = Image.new('1', (width, height), 0)
    card.paste(marker, (0, base - (FIELD_HEIGHT - 1)))
    card.paste(name_mask, (marker.width + WORD_SPACE, base - name_baseline))
    return card


def _alphabet(labels, donor):
    """Glyphs for one composed name: donor label first, then the rest, then hand-built."""
    lib = dict(_glyphs(donor, labels[donor]))
    for label in ('Moonlight Village', 'Crags', 'Orochi', 'Forest',
                  'Koma Cave', "Dragon's Maw"):
        for ch, glyph in _glyphs(label, labels[label]).items():
            lib.setdefault(ch, glyph)
    for ch, glyph in HAND_BUILT_LETTERS.items():
        lib.setdefault(ch, glyph)
    return lib


def _compose(text, lib):
    """-> (PIL mask, baseline row) for one composed label."""
    cells = [None if ch == ' ' else lib[ch] for ch in text]
    top = min(t for c in cells if c for t, _ in [c])
    bottom = max(t + len(r) for c in cells if c for t, r in [c])
    width = sum(WORD_SPACE if c is None else len(c[1][0]) + LETTER_TRACKING
                for c in cells) - LETTER_TRACKING
    mask = Image.new('1', (width, bottom - top), 0)
    px = mask.load()
    x = 0
    for cell in cells:
        if cell is None:
            x += WORD_SPACE; continue
        t, rows = cell
        for i, row in enumerate(rows):
            for j, ch in enumerate(row):
                if ch == '#':
                    px[x + j, t - top + i] = 1
        x += len(rows[0]) + LETTER_TRACKING
    return mask, -top


def build(source_path, moon_exit_path):
    source = _load_source(source_path)
    moon_exit = _load_moonlight_exit(moon_exit_path)
    labels = {label: _cell_crop(source, LABEL_CROPS[label])
              for label in SOURCE_LABELS[:-1]}
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
        # F50 was always exempt. F1/F5/F10/F21 belong to cards that were renamed or
        # recentred, so their group moved by intent; their SHAPE is still proved above.
        if number not in (1, 5, 10, 21, 50) and actual_box[0] + group_left != x0:
            raise SystemExit('floorcardgen: F%d source x changed' % number)

    # Compose the three longer names, then keep every card keyed on its final label.
    composed, baselines = {}, {}
    for name, donor in COMPOSED_LABELS.items():
        mask, base = _compose(name, _alphabet(labels, donor))
        composed[name] = mask
        baselines[name] = base
    final = {}
    for source_label, label in zip(SOURCE_LABELS, LABELS):
        if label in composed:
            final[label] = composed[label]
        else:
            final[label] = labels[source_label]
            baselines[label] = DIGIT_BASELINE + SOURCE_NUMBER_TOPS[source_label]

    # Forest's two floors both become bespoke cards; the old F1 crop had `Forest` baked
    # into it as a single raster, so it cannot survive the rename either.
    forest_specials = {}
    for number in (1, 2):
        card = _special_card(f_mask, digits, composed['Shifting Forest'],
                             baselines['Shifting Forest'], number)
        forest_specials['F%d Shifting Forest' % number] = card
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
        'labels': {label: _record(final[label]) for label in LABELS},
        'label_lefts': LABEL_LEFTS,
        # Derived, not chosen: the F## field always inks rows 0-11, so a label whose own
        # baseline is lower must push the digit down to meet it.
        'number_tops': {label: baselines[label] - DIGIT_BASELINE for label in LABELS},
        'number_groups': groups,
        'numbers': numbers,
        'special_cards': dict(
            [(key, _record(card)) for key, card in forest_specials.items()]
            + [('F50 Moonlight Exit', _record(moonlight_exit_card))]),
        # Bespoke cards are centred on the 160px strip; F50 keeps its reviewed x.
        'special_lefts': dict(
            [(key, (CARD_SIZE[0] - card.width) // 2)
             for key, card in forest_specials.items()]
            + [('F50 Moonlight Exit', 4)]),
        'digit_sources': {
            'source': sorted(DIGIT_CROPS),
            'hand_built': sorted(MISSING_DIGITS),
        },
        'label_sources': {
            'source': [l for l in LABELS if l not in COMPOSED_LABELS],
            'composed': {name: donor for name, donor in COMPOSED_LABELS.items()},
            'hand_built_glyphs': sorted(HAND_BUILT_LETTERS),
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
