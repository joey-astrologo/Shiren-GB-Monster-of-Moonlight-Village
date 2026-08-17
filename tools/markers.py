#!/usr/bin/env python3
"""Build and install the shared English town/dungeon arrival-card graphics.

The cards are not script text. Bank 31 maps tiles $80-$A7 across two BG rows, renders an
optional floor number, and constructs a Japanese place name from 16x16 glyphs. The name
selector at ``DE+2`` addresses eight records; ``DE+1`` is the displayed floor number.

This replacement uses Joey's approved native-resolution ``Titles.webp`` artwork. Every
location name, the Forest ``F``, and the supplied 0/1/2/5/9 numerals are exact source
pixels; the missing 3/4/6/7/8 are fixed hand-built masks in the same style. Static label
bases combine with a live four-tile F1-F50 field, while F1 Forest and F50 Moonlight Exit
retain exact full source cards. The existing three-row map and eight-batch VBlank
uploader are preserved.
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gbasm


BANKSZ = 0x4000
SOURCE_BANK = 31
# The larger three-row pack no longer fits behind the cinematic in bank 63. Bank 60 is an
# unused text-pool bank in the completed translation; every byte used here is guarded so
# future pool growth fails loudly instead of overlapping the graphics.
FAR_BANK = 0x3C
FAR_UPLOAD = 0x0B
DATA_ORG = 0x5000

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_PATH = os.path.join(ROOT, 'assets', 'graphics', 'arrival_cards_source.json')
ASSET_SHA256 = '65799690672b327a8d3f1e454fe80cfc60a07b09146de7048fa174b56eb9d518'
SOURCE_ARTWORK_PATH = os.path.join(ROOT, 'assets', 'graphics',
                                   'arrival_cards_source.webp')
MOONLIGHT_EXIT_SOURCE_PATH = os.path.join(
    ROOT, 'assets', 'graphics', 'arrival_card_f50_moonlight_exit.png')

TOWN_LABEL = 'Moonlight Village'
# Exact order of the eight-pointer native name table at 31:$6348 and the bank-11 place
# list.  These compact terms are already the project's measured UI spellings.
LABELS = (TOWN_LABEL, 'Shifting Forest', 'Koma Cave', "Avatar's Crag", 'Kuyo Pass',
          "Dragon's Maw", "Orochi's Den", 'Moonlight Exit')
FLOOR_LABELS = LABELS[1:]
MAX_FLOOR = 50

STRIP_WIDTH = 160
STRIP_HEIGHT = 24
STRIP_SCREEN_TOP = 64
NUMBER_COLUMNS = 4                 # complete padded 32px F# field
NUMBER_GAP = 8
NUMBER_REGION = NUMBER_COLUMNS * 8
TILE_BYTES = 16
VISIBLE_TILE_COUNT = 60
TILE_COUNT = 64                     # eight complete 128-byte VBlank batches
RASTER_BYTES = TILE_COUNT * TILE_BYTES
ONEBIT_BYTES = TILE_COUNT * 8
NUMBER_ONEBIT_BYTES = NUMBER_COLUMNS * 2 * 8
BATCH_COUNT = TILE_COUNT // 8
THIRD_ROW_TILE = 0xA8
BLANK_ROW_TILE = 0xBC

# Normal floor progression uses numberless cards only for the village, Dragon's Maw
# threshold and Moonlight Exit. The alternate $60CB path can show F50 Moonlight Exit, so
# retain that exact supplied card
# fourth form as well.  Every numbered card shares a fixed two-digit field.
# Bases the uploader can select. EVERY selector needs its numbered form compiled: the
# native floor/selector table is not exhaustive of what the game can display -- Moonlight
# Exit shows at F1 through F50, not only at the F50 its table lists. Dropping a numbered
# variant makes the table fall back to the CENTRED base and the uploader then paints the
# F## field straight through the name.
VARIANTS = (
    (0, False),
    (1, True), (2, True), (3, True), (4, True),
    (5, False), (5, True),
    (6, True),
    (7, False), (7, True),
)
# Forest's name no longer fits the generic layout, which always reserves a full 32px
# field whatever the digit's real width, so both of its floors get a bespoke card.
SPECIAL_CARDS = {
    (1, 1): 'F1 Shifting Forest',
    (1, 2): 'F2 Shifting Forest',
    (7, 50): 'F50 Moonlight Exit',
}

# intro.install() retires 31:$51C9-$51F7. Its live wrappers end at $51DF, leaving this
# asserted slot for the far-call trampoline.
STUB_AT = 0x51E0
STUB_LIMIT = 0x51F8
NAME_CALL_AT = 0x613A
NATIVE_NAME = 0x6241
CLEAR_TILE_AT = 0x6157              # immediate in `ld a,$80` background fill
NATIVE_CLEAR_TILE = 0x80

# Shared scratch proved free by tools/wramfree.py. Arrival cards cannot overlap the intro,
# dialogue or menu renderers that borrow the same small run.
S_BATCHES_LEFT = 0xC0CC
S_BATCH = 0xC0CD
S_SELECTOR = 0xC0CE
S_NUMBER = 0xC0CF
S_GROUP_COL = 0xC0D0
S_SPECIAL = 0xC0D1
S_DRAW_COL = 0xC0D2
S_NUMBER_TOP = 0xC0D3

# Primary-path card records read from the guarded native tables at 31:$6358/$6370.
# The alternate path can show a numbered Moonlight Exit; retain its F50 source form.
ACTIVE_NUMBERED_FLOORS = {
    1: (1, 2),
    2: (3, 4, 5, 6),
    3: (7, 8, 9, 10),
    4: (11, 12, 13, 14),
    5: (15, 16, 17, 18, 19, 20),
    6: (21,),
    7: (50,),
}
ACTIVE_NUMBERLESS = ((0, 0), (5, 0), (7, 0))
ACTIVE_CARD_CASES = ACTIVE_NUMBERLESS + tuple(
    (selector, floor)
    for selector, floors in ACTIVE_NUMBERED_FLOORS.items()
    for floor in floors
)
NATIVE_FLOOR_TABLE_AT = 0x6358
NATIVE_FLOOR_TABLE = bytes((
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 0,
    15, 16, 17, 18, 19, 20, 21, 0,
))
NATIVE_SELECTOR_TABLE_AT = 0x6370
NATIVE_SELECTOR_TABLE = bytes((
    0, 2, 2, 4, 4, 4, 4, 6, 6, 6, 6, 8, 8, 8, 8, 10,
    10, 10, 10, 10, 10, 10, 12, 14,
))

# group-left must be tile-aligned because the live F# field replaces four tile columns.
# name-left is the exact x coordinate in the approved source contact sheet.
NUMBERED_POSITIONS = {
    'Shifting Forest': (0, 40),
    'Koma Cave': (8, 52),
    "Avatar's Crag": (0, 42),
    'Kuyo Pass': (16, 59),
    "Dragon's Maw": (0, 43),
    "Orochi's Den": (8, 51),
    'Moonlight Exit': (0, 41),
}

_ASSET = None


def _off(bank, addr):
    return bank * BANKSZ + (addr - (BANKSZ if bank else 0))


def _asset():
    global _ASSET
    if _ASSET is None:
        with open(ASSET_PATH, 'rb') as src:
            raw = src.read()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != ASSET_SHA256:
            raise SystemExit('markers: arrival-card asset SHA-256 is %s, expected %s'
                             % (digest, ASSET_SHA256))
        _ASSET = json.loads(raw.decode('utf-8'))
        if _ASSET.get('format') != 'shiren-gb-source-arrival-cards-v2':
            raise SystemExit('markers: unsupported arrival-card asset format')
        if tuple(_ASSET['labels']) != LABELS:
            raise SystemExit('markers: arrival-card label order changed')
        if set(_ASSET['numbers']) != {str(value) for value in range(1, MAX_FLOOR + 1)}:
            raise SystemExit('markers: arrival-card number set is not 1-%d' % MAX_FLOOR)
        if set(_ASSET['number_groups']) != set(_ASSET['numbers']):
            raise SystemExit('markers: arrival-card number/group sets differ')
        if set(_ASSET['special_cards']) != set(SPECIAL_CARDS.values()) \
                or set(_ASSET['special_lefts']) != set(SPECIAL_CARDS.values()):
            raise SystemExit('markers: arrival-card special set changed')
        for label, (_group_left, name_left) in NUMBERED_POSITIONS.items():
            if _ASSET['label_lefts'][label] != name_left:
                raise SystemExit('markers: source x for %r changed' % label)
    return _ASSET


def _mask(record):
    """Decode one variable-width MSB-first mask record into rows of zero/one pixels."""
    width = record['width']
    height = record['height']
    if len(record['rows']) != height:
        raise SystemExit('markers: %dx%d asset has %d rows'
                         % (width, height, len(record['rows'])))
    rows = []
    for source in record['rows']:
        packed = bytes.fromhex(source)
        if len(packed) != (width + 7) // 8:
            raise SystemExit('markers: %dpx asset row has %d packed bytes'
                             % (width, len(packed)))
        rows.append([1 if packed[x // 8] & (0x80 >> (x & 7)) else 0
                     for x in range(width)])
    return rows


def _numbered_top(label):
    """Return the source-relative top of a numbered marker."""
    top = _asset()['number_tops'][label]
    if not 0 <= top <= STRIP_HEIGHT - 12:
        raise SystemExit('markers: invalid number top %d for %r' % (top, label))
    return top


def _paint_mask(pixels, record, left, top=None):
    rows = _mask(record)
    top = 0 if top is None else top
    if left < 0 or top < 0 or left + record['width'] > STRIP_WIDTH \
            or top + record['height'] > STRIP_HEIGHT:
        raise SystemExit('markers: %dx%d mask at (%d,%d) exceeds 160x24 strip'
                         % (record['width'], record['height'], left, top))
    for y, row in enumerate(rows):
        for x, value in enumerate(row):
            if value:
                pixels[top + y][left + x] = 1


def _number_bounds(number):
    points = [(x, y) for y, row in enumerate(_mask(_asset()['numbers'][str(number)]))
              for x, value in enumerate(row) if value]
    if not points:
        raise SystemExit('markers: floor %d has an empty marker field' % number)
    return min(x for x, _y in points), max(x for x, _y in points)


def _numbered_geometry(_font, label):
    """Return exact source positions and the widest live ink span for one label."""
    name_extent = _asset()['labels'][label]['width']
    group_left, name_left = NUMBERED_POSITIONS[label]
    if group_left & 7:
        raise SystemExit('markers: numbered %r group x=%d is not tile-aligned' %
                         (label, group_left))
    selector = LABELS.index(label)
    floors = ACTIVE_NUMBERED_FLOORS[selector]
    lefts = []
    rights = []
    for number in floors:
        if _asset()['number_groups'][str(number)] != group_left:
            raise SystemExit('markers: F%d field group disagrees with %r' %
                             (number, label))
        field_left, field_right = _number_bounds(number)
        number_left = group_left + field_left
        number_right = group_left + field_right
        gap = name_left - number_right - 1
        if gap < NUMBER_GAP:
            raise SystemExit('markers: %r F%d has only %dpx number/name gap' %
                             (label, number, gap))
        lefts.append(number_left)
        rights.append(name_left + name_extent - 1)
    total = max(rights) - min(lefts) + 1
    if max(rights) >= STRIP_WIDTH:
        raise SystemExit('markers: numbered %r exceeds the %dpx card' %
                         (label, STRIP_WIDTH))
    return group_left, name_left, total


def _base_pixels(_font, label, numbered):
    pixels = [[0] * STRIP_WIDTH for _ in range(STRIP_HEIGHT)]
    record = _asset()['labels'][label]
    extent = record['width']
    if numbered:
        group_left, name_left, _total = _numbered_geometry(None, label)
        top = 0
    else:
        group_left = 0
        name_left = (STRIP_WIDTH - extent) // 2
        top = None
    _paint_mask(pixels, record, name_left, top=top)
    return pixels, group_left // 8


def _paint_number(pixels, number, left, top=0):
    record = _asset()['numbers'][str(number)]
    if (record['width'], record['height']) != (NUMBER_REGION, 12):
        raise SystemExit('markers: floor %d field is %dx%d, expected %dx12' %
                         (number, record['width'], record['height'], NUMBER_REGION))
    _paint_mask(pixels, record, left, top=top)


def _special_pixels(selector, number):
    pixels = [[0] * STRIP_WIDTH for _ in range(STRIP_HEIGHT)]
    key = SPECIAL_CARDS[(selector, number)]
    record = _asset()['special_cards'][key]
    _paint_mask(pixels, record, _asset()['special_lefts'][key])
    return pixels


def _onebit(pixels):
    """Encode 160x24 pixels as 60 visible tiles plus four blank queue-pad tiles."""
    out = bytearray()
    for tile_x in range(STRIP_WIDTH // 8):
        for tile_y in (0, 8):
            for y in range(tile_y, tile_y + 8):
                mask = 0
                for x in range(8):
                    if pixels[y][tile_x * 8 + x]:
                        mask |= 0x80 >> x
                out.append(mask)
    for tile_x in range(STRIP_WIDTH // 8):
        for y in range(16, 24):
            mask = 0
            for x in range(8):
                if pixels[y][tile_x * 8 + x]:
                    mask |= 0x80 >> x
            out.append(mask)
    out += b'\x00' * ((TILE_COUNT - VISIBLE_TILE_COUNT) * 8)
    assert len(out) == ONEBIT_BYTES
    return bytes(out)


def _two_plane(onebit):
    out = bytearray()
    for value in onebit:
        out.extend((value, value))
    assert len(out) == RASTER_BYTES
    return bytes(out)


def render_card(font=None, selector=0, number=0):
    """Return the exact 1024-byte VRAM raster for one selector/floor combination."""
    if not 0 <= selector < len(LABELS):
        raise ValueError('marker selector %d is outside 0-7' % selector)
    if number:
        if not 0 < number <= MAX_FLOOR:
            raise ValueError('floor number %d is outside 1-%d' % (number, MAX_FLOOR))
    if (selector, number) in SPECIAL_CARDS:
        pixels = _special_pixels(selector, number)
    else:
        label = LABELS[selector]
        pixels, group_col = _base_pixels(font, label, bool(number))
        if number:
            _paint_number(pixels, number, group_col * 8, _numbered_top(label))
    return _two_plane(_onebit(pixels))


def card_metrics(selector, number):
    """Return visible bounds and component tops for a generated card."""
    if (selector, number) in SPECIAL_CARDS:
        pixels = _special_pixels(selector, number)
        number_top = 1 if (selector, number) == (7, 50) else 0
        name_top = 0
    else:
        label = LABELS[selector]
        pixels, group_col = _base_pixels(None, label, bool(number))
        number_top = None
        name_top = 0
        if number:
            number_top = _numbered_top(label)
            _paint_number(pixels, number, group_col * 8, number_top)
    points = [(x, y) for y, row in enumerate(pixels)
              for x, value in enumerate(row) if value]
    if not points:
        raise ValueError('marker card %d/%d has no ink' % (selector, number))
    bounds = (min(x for x, _y in points), min(y for _x, y in points),
              max(x for x, _y in points), max(y for _x, y in points))
    return {'bounds': bounds, 'number_top': number_top, 'name_top': name_top}


def render_strip(font=None, text=TOWN_LABEL):
    """Compatibility helper used by markerspill for the centered village card."""
    if text != TOWN_LABEL:
        pixels, _group = _base_pixels(font, text, False)
        return _two_plane(_onebit(pixels))
    return render_card(font, 0, 0)


def floor_style_budget(font):
    """Return ``(label, pixels)`` for each source-positioned numbered form."""
    return tuple((label, _numbered_geometry(font, label)[2]) for label in FLOOR_LABELS)


def _number_data(_font):
    """Fifty top-aligned 32x16 number fields, shifted per selector by the uploader."""
    out = bytearray()
    for number in range(1, MAX_FLOOR + 1):
        pixels = [[0] * STRIP_WIDTH for _ in range(STRIP_HEIGHT)]
        _paint_number(pixels, number, 0, top=0)
        full = _onebit(pixels)
        out += full[:NUMBER_ONEBIT_BYTES]
    assert len(out) == MAX_FLOOR * NUMBER_ONEBIT_BYTES
    return bytes(out)


def _stub():
    """Replace the native name renderer while preserving its register contract."""
    return gbasm.assemble(f"""
        rst $10
        db ${FAR_UPLOAD:02X},${FAR_BANK:02X}
        ret
    """, STUB_AT)[0]


def _uploader(code_org, pointer_org, group_org, top_org, numbers_org,
              special_forest_org, special_forest2_org, special_moon_org):
    """Compile selector dispatch, three-row upload and live number-field overlay."""
    source = f"""
upload:
        push af
        push bc
        push de
        push hl

        ld hl,$0002
        add hl,de
        ld a,[hl]
        and $0E
        srl a
        ld [${S_SELECTOR:04X}],a
        ld c,a
        ld b,$00
        ld hl,${group_org:04X}
        add hl,bc
        ld a,[hl]
        ld [${S_GROUP_COL:04X}],a
        ld hl,${top_org:04X}
        add hl,bc
        ld a,[hl]
        ld [${S_NUMBER_TOP:04X}],a

        ld hl,$0001
        add hl,de
        ld a,[hl]
        ld [${S_NUMBER:04X}],a
        xor a
        ld [${S_SPECIAL:04X}],a

        ld a,[${S_SELECTOR:04X}]
        cp $01
        jr nz,check_moon
        ld a,[${S_NUMBER:04X}]
        cp $01
        jr z,forest_one
        cp $02
        jr nz,check_moon
        ld a,$03
        ld [${S_SPECIAL:04X}],a
        jr choose
forest_one:
        ld a,$01
        ld [${S_SPECIAL:04X}],a
        jr choose

check_moon:
        ld a,[${S_SELECTOR:04X}]
        cp $07
        jr nz,choose
        ld a,[${S_NUMBER:04X}]
        cp $32
        jr nz,choose
        ld a,$02
        ld [${S_SPECIAL:04X}],a

choose:
        ld a,[${S_SPECIAL:04X}]
        and a
        jr z,ordinary
        cp $01
        jr z,special_forest
        cp $03
        jr nz,special_moon
        ld hl,${special_forest2_org:04X}
        jr selected
special_forest:
        ld hl,${special_forest_org:04X}
        jr selected
special_moon:
        ld hl,${special_moon_org:04X}
        jr selected
ordinary:
        ld a,[${S_SELECTOR:04X}]
        add a,a
        ld c,a
        ld a,[${S_NUMBER:04X}]
        and a
        jr z,variant
        inc c
variant:
        ld b,$00
        sla c
        rl b
        ld hl,${pointer_org:04X}
        add hl,bc
        ld a,[hl+]
        ld h,[hl]
        ld l,a
selected:
        call map_extra_rows

        ld bc,$8800
        ld a,${BATCH_COUNT:02X}
        ld [${S_BATCHES_LEFT:04X}],a
        xor a
        ld [${S_BATCH:04X}],a
batch:
        push hl
        ld a,$05
        call $0881
        pop hl
        ld a,c
        ld [$C006],a
        ld a,b
        ld [$C007],a
        push bc
        ld de,$C008
        ld b,$20
copy_first:
        ld a,[hl+]
        ld [de],a
        inc de
        ld [de],a
        inc de
        dec b
        jr nz,copy_first
        pop bc
        ld a,c
        add a,$40
        ld c,a
        jr nc,first_no_carry
        inc b
first_no_carry:
        ld a,c
        ld [$C048],a
        ld a,b
        ld [$C049],a
        push bc
        ld de,$C04A
        ld b,$20
copy_second:
        ld a,[hl+]
        ld [de],a
        inc de
        ld [de],a
        inc de
        dec b
        jr nz,copy_second
        pop bc
        ld a,c
        add a,$40
        ld c,a
        jr nc,second_no_carry
        inc b
second_no_carry:
        ld a,[${S_NUMBER:04X}]
        and a
        jr z,arm
        ld a,[${S_SPECIAL:04X}]
        and a
        jr nz,arm
        push bc
        xor a
        ld a,[${S_GROUP_COL:04X}]
        ld c,a
        xor a
        call draw_number_column
        ld a,[${S_GROUP_COL:04X}]
        inc a
        ld c,a
        ld a,$01
        call draw_number_column
        ld a,[${S_GROUP_COL:04X}]
        inc a
        inc a
        ld c,a
        ld a,$02
        call draw_number_column
        ld a,[${S_GROUP_COL:04X}]
        inc a
        inc a
        inc a
        ld c,a
        ld a,$03
        call draw_number_column
        pop bc
arm:
        ld a,$0A
        ld [$C11A],a
        push hl
        rst $18
        pop hl
        ld a,[${S_BATCH:04X}]
        inc a
        ld [${S_BATCH:04X}],a
        ld a,[${S_BATCHES_LEFT:04X}]
        dec a
        ld [${S_BATCHES_LEFT:04X}],a
        jp nz,batch
        pop hl
        pop de
        pop bc
        pop af
        ret

map_extra_rows:
        push af
        push bc
        push de
        push hl
        ld hl,$0008
        add hl,de
        ld a,[hl]
        ld de,$9940
        cp $01
        jr nz,map_destination
        ld de,$9900
map_destination:
        ld a,$04
        call $0881
        ld hl,$C006
        ld a,e
        ld [hl+],a
        ld a,d
        ld [hl+],a
        ld a,${THIRD_ROW_TILE:02X}
        ld c,$14
map_third:
        ld [hl+],a
        inc a
        dec c
        jr nz,map_third
        push hl
        ld hl,$0020
        add hl,de
        ld d,h
        ld e,l
        pop hl
        ld a,e
        ld [hl+],a
        ld a,d
        ld [hl+],a
        ld a,${BLANK_ROW_TILE:02X}
        ld c,$14
map_blank:
        ld [hl+],a
        dec c
        jr nz,map_blank
        ld a,$08
        ld [$C11A],a
        rst $18
        pop hl
        pop de
        pop bc
        pop af
        ret

draw_number_column:
        ld [${S_DRAW_COL:04X}],a
        push af
        push bc
        push de
        push hl
        ld a,c
        srl a
        srl a
        ld hl,${S_BATCH:04X}
        cp [hl]
        jr nz,number_done

        ld a,c
        and $03
        add a,a
        ld c,a
        ld b,$00
        ld hl,destinations
        add hl,bc
        ld a,[hl+]
        ld e,a
        ld d,[hl]

        ld a,[${S_NUMBER:04X}]
        dec a
        ld c,a
        ld b,$00
        sla c
        rl b
        sla c
        rl b
        sla c
        rl b
        sla c
        rl b
        sla c
        rl b
        sla c
        rl b
        ld a,[${S_DRAW_COL:04X}]
        swap a
        add a,c
        ld c,a
        jr nc,number_source
        inc b
number_source:
        ld hl,${numbers_org:04X}
        add hl,bc
        ld a,[${S_NUMBER_TOP:04X}]
        ld b,a
        and a
        jr z,number_rows
        xor a
number_pad:
        ld [de],a
        inc de
        ld [de],a
        inc de
        dec b
        jr nz,number_pad
number_rows:
        ld a,[${S_NUMBER_TOP:04X}]
        ld c,a
        ld a,$10
        sub c
        ld b,a
number_copy:
        ld a,[hl+]
        ld [de],a
        inc de
        ld [de],a
        inc de
        dec b
        jr nz,number_copy
number_done:
        pop hl
        pop de
        pop bc
        pop af
        ret

destinations:
        db $08,$C0,$28,$C0,$4A,$C0,$6A,$C0
"""
    return gbasm.assemble(source, code_org)


def _compile_data(font, data_org):
    bases = []
    addresses = {}
    group_cols = [0]                  # the village never carries a floor number
    number_tops = [0]
    for label in LABELS[1:]:
        # Read the group column from the geometry rather than by rendering: a label whose
        # floors are all bespoke has no drawable generic form to paint.
        group_left, _name_left, _total = _numbered_geometry(font, label)
        group_cols.append(group_left // 8)
        number_tops.append(_numbered_top(label))
    for selector, numbered in VARIANTS:
        pixels, _group = _base_pixels(font, LABELS[selector], numbered)
        address = data_org + sum(len(base) for base in bases)
        addresses[(selector, numbered)] = address
        bases.append(_onebit(pixels))
    special_orgs = {}
    for case in SPECIAL_CARDS:
        special_orgs[case] = data_org + sum(len(base) for base in bases)
        bases.append(_onebit(_special_pixels(*case)))

    variants = bytearray()
    for selector in range(len(LABELS)):
        for numbered in (False, True):
            key = (selector, numbered)
            if key not in addresses:
                fallback = (selector, True) if (selector, True) in addresses \
                    else (selector, False)
                key = fallback
            address = addresses[key]
            variants += bytes((address & 0xFF, address >> 8))
    return (b''.join(bases), bytes(variants), bytes(group_cols), bytes(number_tops),
            special_orgs)


def install(buf, font, intro_built, notes=None):
    """Install all eight English card labels after :func:`intro.install`."""
    if len(buf) < 0x100000:
        raise SystemExit('markers: requires the 1 MiB expanded ROM')
    if not intro_built or 'end_addr' not in intro_built:
        raise SystemExit('markers: requires intro.install() and its reserved bank 63')

    for address, expected, label in (
            (NATIVE_FLOOR_TABLE_AT, NATIVE_FLOOR_TABLE, 'floor'),
            (NATIVE_SELECTOR_TABLE_AT, NATIVE_SELECTOR_TABLE, 'selector')):
        at = _off(SOURCE_BANK, address)
        actual = bytes(buf[at:at + len(expected)])
        if actual != expected:
            raise SystemExit('markers: native %s table at 31:$%04X changed: %s' %
                             (label, address, actual.hex()))

    floor_budget = floor_style_budget(font)
    too_wide = [(label, width) for label, width in floor_budget if width > STRIP_WIDTH]
    if too_wide:
        raise SystemExit('markers: shared town/floor style exceeds 160px: %s' % too_wide)

    data_org = DATA_ORG
    bases, pointers, groups, number_tops, special_orgs = _compile_data(font, data_org)
    numbers_org = data_org + len(bases)
    numbers = _number_data(font)
    pointer_org = numbers_org + len(numbers)
    group_org = pointer_org + len(pointers)
    top_org = group_org + len(groups)
    code_org = (top_org + len(number_tops) + 0x0F) & ~0x0F
    code, labels = _uploader(code_org, pointer_org, group_org, top_org, numbers_org,
                             special_orgs[(1, 1)], special_orgs[(1, 2)],
                             special_orgs[(7, 50)])
    end_addr = code_org + len(code)
    if end_addr > 0x8000:
        raise SystemExit('markers: town/floor cards overrun reserved bank %d by %d bytes'
                         % (FAR_BANK, end_addr - 0x8000))

    bank = _off(FAR_BANK, 0x4000)
    pointer_at = bank + FAR_UPLOAD - 1
    if bytes(buf[pointer_at:pointer_at + 2]) != b'\xFF\xFF':
        raise SystemExit('markers: far entry $%02X in bank %d is already occupied'
                         % (FAR_UPLOAD, FAR_BANK))
    tail_at = bank + data_org - 0x4000
    tail_end = bank + end_addr - 0x4000
    if any(value != 0xFF for value in buf[tail_at:tail_end]):
        raise SystemExit('markers: pool-bank range $%04X-$%04X is not free'
                         % (data_org, end_addr - 1))

    stub = _stub()
    stub_at = _off(SOURCE_BANK, STUB_AT)
    if len(stub) > STUB_LIMIT - STUB_AT:
        raise SystemExit('markers: %d-byte local stub exceeds its %d-byte retired slot'
                         % (len(stub), STUB_LIMIT - STUB_AT))
    if bytes(buf[stub_at:stub_at + (STUB_LIMIT - STUB_AT)]) != \
            b'\xFF' * (STUB_LIMIT - STUB_AT):
        raise SystemExit('markers: retired reader tail 31:$%04X-$%04X is not free'
                         % (STUB_AT, STUB_LIMIT - 1))

    call_at = _off(SOURCE_BANK, NAME_CALL_AT)
    expected = bytes((0xCD, NATIVE_NAME & 0xFF, NATIVE_NAME >> 8))
    if bytes(buf[call_at:call_at + 3]) != expected:
        raise SystemExit('markers: name call at 31:$%04X changed (got %s, expected %s)'
                         % (NAME_CALL_AT, bytes(buf[call_at:call_at + 3]).hex(),
                            expected.hex()))

    clear_at = _off(SOURCE_BANK, CLEAR_TILE_AT)
    if buf[clear_at] != NATIVE_CLEAR_TILE:
        raise SystemExit('markers: background fill tile at 31:$%04X is $%02X, expected $%02X'
                         % (CLEAR_TILE_AT, buf[clear_at], NATIVE_CLEAR_TILE))

    upload = labels['upload']
    buf[pointer_at:pointer_at + 2] = bytes((upload & 0xFF, upload >> 8))
    for address, data in ((data_org, bases), (numbers_org, numbers),
                          (pointer_org, pointers), (group_org, groups),
                          (top_org, number_tops),
                          (code_org, code)):
        at = bank + address - 0x4000
        buf[at:at + len(data)] = data
    buf[stub_at:stub_at + len(stub)] = stub
    buf[call_at:call_at + 3] = bytes((0xCD, STUB_AT & 0xFF, STUB_AT >> 8))
    buf[clear_at] = BLANK_ROW_TILE

    widest = max(floor_budget, key=lambda pair: pair[1])
    out = [
        'markers: eight town/floor labels use Joey\'s source-raster card style; '
        'F1 Forest and all supplied label/marker shapes remain pixel-exact',
        'markers: three visible tile rows; widest numbered label is %r at %d/%dpx' %
        (widest[0], widest[1], STRIP_WIDTH),
        'markers: twelve one-bit card bases + live 1-%d fields/uploader at bank %d '
        '$%04X-$%04X'
        % (MAX_FLOOR, FAR_BANK, data_org, end_addr - 1),
        'markers: source-raster asset %s; native three-row map and later transitions '
        'preserved'
        % ASSET_SHA256[:12],
    ]
    if notes is not None:
        notes.extend(out)
    return {'raster': render_card(font, 0, 0), 'data_org': data_org,
            'code_org': code_org, 'end_addr': end_addr, 'labels': labels, 'stub': stub,
            'bases': bases, 'pointers': pointers, 'groups': groups,
            'number_tops': number_tops, 'numbers': numbers,
            'special_orgs': special_orgs}
