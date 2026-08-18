#!/usr/bin/env python3
"""Install the complete 22-card English ending-credit roll.

The ending's forest, palette fades, music, all native credit positions, and post-credit
transition stay intact.  Bank 31's credit driver is replaced with a compact sequencer
which asks two unused expanded banks to upload two 160x16 strips per card.  The strips
are frozen from the approved Inter audition, so ordinary builds do not require the
source font or depend on a particular Pillow/FreeType version.

The native roll contains 22 actual cards.  Every one has a one-for-one English card in
``assets/graphics/ending_credits_inter.json``.  The Japanese end mark shown after the
roll is deliberately not intercepted and remains native.
"""
import base64
import hashlib
import json
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gbasm


BANKSZ = 0x4000
SOURCE_BANK = 31
FAR_BANKS = (0x3A, 0x3B)
FAR_UPLOAD = 0x05
CARDS_PER_BANK = 11
CODE_ORG = 0x4100
POINTERS_ORG = 0x4200
DATA_ORG = 0x4800

DRIVER_AT = 0x767E
DRIVER_LIMIT = 0x76D7
SEQUENCE_AT = DRIVER_AT
NATIVE_DRIVER_SHA256 = \
    '5cafa7df2ff1fa178fdfbd3122e344203a38770a2dabcf2db89c04f3cb8abd65'
MAP_CODE_AT = 0x7B40

ROLE_VRAM = 0x8800
NAME_VRAM = 0x8B00
STRIP_BYTES = 20 * 2 * 16
CARD_BYTES = STRIP_BYTES * 2
TILE_BYTES = 16
TILES_PER_ROW = 20
BATCHES_PER_STRIP = STRIP_BYTES // 128
S_CARD_INDEX = 0xC0CB
S_BATCHES = 0xC0CC
CREDIT_BAND_TOP = 84

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSET_PATH = os.path.join(ROOT, 'assets', 'graphics',
                          'ending_credits_inter.json')
ASSET_FORMAT = 'shiren-gb-poppins-ending-credits-v1'
def _asset():
    try:
        with open(ASSET_PATH, encoding='utf-8') as src:
            asset = json.load(src)
    except (OSError, ValueError) as exc:
        raise SystemExit('endingcredits: cannot read %s: %s' % (ASSET_PATH, exc))
    if asset.get('format') != ASSET_FORMAT:
        raise SystemExit('endingcredits: unsupported asset format %r' %
                         asset.get('format'))
    credits = asset.get('credits', ())
    if len(credits) != len(FAR_BANKS) * CARDS_PER_BANK:
        raise SystemExit('endingcredits: asset contains %d cards, expected 22' %
                         len(credits))
    record = asset.get('pack', {})
    if record.get('encoding') != 'zlib+base64':
        raise SystemExit('endingcredits: unsupported pack encoding %r' %
                         record.get('encoding'))
    try:
        pack = zlib.decompress(base64.b64decode(record['data']))
    except (KeyError, ValueError, zlib.error) as exc:
        raise SystemExit('endingcredits: malformed frozen pack: %s' % exc)
    expected_size = len(credits) * CARD_BYTES
    if len(pack) != expected_size or record.get('raw_bytes') != expected_size:
        raise SystemExit('endingcredits: frozen pack is %d bytes, expected %d' %
                         (len(pack), expected_size))
    digest = hashlib.sha256(pack).hexdigest()
    if digest != record.get('sha256'):
        raise SystemExit('endingcredits: frozen pack checksum changed: %s' % digest)
    return asset, tuple(credits), pack


ASSET, CARD_RECORDS, PACK = _asset()
CARDS = tuple((record['role'], record['name']) for record in CARD_RECORDS)
DURATIONS = tuple(record['duration'] for record in CARD_RECORDS)
CARD_COUNT = len(CARDS)
PACK_SHA256 = ASSET['pack']['sha256']


def _off(bank, addr):
    return bank * BANKSZ + (addr - (BANKSZ if bank else 0))


def source_graphics():
    """Return the approved semantic strips in row-major audition order."""
    return tuple(PACK[index * CARD_BYTES:(index + 1) * CARD_BYTES]
                 for index in range(CARD_COUNT))


def _native_strip(strip):
    """Convert row-major tiles to the native column-interleaved map order.

    The asset stores the complete top row followed by the bottom row. Native $7C88
    maps even tile IDs across the top and odd IDs across the bottom, so VRAM must hold
    top0,bottom0,top1,bottom1,... instead.
    """
    if len(strip) != STRIP_BYTES:
        raise AssertionError(len(strip))
    tiles = tuple(strip[at:at + TILE_BYTES]
                  for at in range(0, STRIP_BYTES, TILE_BYTES))
    top, bottom = tiles[:TILES_PER_ROW], tiles[TILES_PER_ROW:]
    return b''.join(tile for pair in zip(top, bottom) for tile in pair)


def graphics():
    """Return cards in the interleaved tile order required by the native map."""
    cards = []
    for card in source_graphics():
        cards.append(_native_strip(card[:STRIP_BYTES]) +
                     _native_strip(card[STRIP_BYTES:]))
    return tuple(cards)


NATIVE_PACK_SHA256 = hashlib.sha256(b''.join(graphics())).hexdigest()


def _strip_pixels(strip):
    """Decode one row-major 20x2 2bpp strip to 160x16 palette indices."""
    pixels = [[0] * 160 for _ in range(16)]
    for tile_y in range(2):
        for tile_x in range(TILES_PER_ROW):
            at = (tile_y * TILES_PER_ROW + tile_x) * TILE_BYTES
            for row in range(8):
                lo, hi = strip[at + row * 2:at + row * 2 + 2]
                for column in range(8):
                    bit = 7 - column
                    pixels[tile_y * 8 + row][tile_x * 8 + column] = \
                        ((hi >> bit) & 1) * 2 + ((lo >> bit) & 1)
    return pixels


def card_window(index):
    """Return the approved 160x32 live SGB raster for screen rows 96-127.

    The credit tilemap begins at BG row 12 but SCY is 8 during the native roll, so role
    tiles appear at screen y=96 and name tiles at y=112.
    """
    card = source_graphics()[index]
    rows = [[0] * 160 for _ in range(32)]
    for strip, top in ((card[:STRIP_BYTES], 0),
                       (card[STRIP_BYTES:], 16)):
        pixels = _strip_pixels(strip)
        for row, values in enumerate(pixels):
            if top + row < len(rows):
                rows[top + row] = values
    palette = ((0, 0, 0), (0, 99, 197), (123, 255, 49), (255, 255, 255))
    return bytes(channel for row in rows for value in row for channel in palette[value])


def _sequence():
    """Show all native cards in order, retaining their three original durations."""
    source = f"""
credits_en:
        push af
        push bc
        push de
        push hl
        ld a,$62
        ld [$C15E],a
        xor a
credit_loop:
        ld [${S_CARD_INDEX:04X}],a
        call show_card
        ld a,[${S_CARD_INDEX:04X}]
        inc a
        cp ${CARD_COUNT:02X}
        jr nz,credit_loop
        pop hl
        pop de
        pop bc
        pop af
        ret

show_card:
        cp ${CARDS_PER_BANK:02X}
        jr c,low_bank
        sub ${CARDS_PER_BANK:02X}
        rst $10
        db ${FAR_UPLOAD:02X},${FAR_BANKS[1]:02X}
        jr uploaded
low_bank:
        rst $10
        db ${FAR_UPLOAD:02X},${FAR_BANKS[0]:02X}
uploaded:
        call $7AB1
        ld a,[${S_CARD_INDEX:04X}]
        cp $14
        jr c,ordinary_duration
        jr z,producer_duration
        ld a,$60
        jr card_wait
producer_duration:
        ld a,$51
        jr card_wait
ordinary_duration:
        ld a,$47
card_wait:
        call $7C9D
        call $7C9D
        dec a
        jr nz,card_wait
        call $7AD9
        ret

clear_credit_row:
        push af
        ld a,$80
        ld b,$20
clear_credit_cell:
        ld [hl+],a
        dec b
        jr nz,clear_credit_cell
        pop af
        ret
"""
    return gbasm.assemble(source, DRIVER_AT)


def _uploader():
    source = f"""
upload:
        push af
        push bc
        push de
        push hl
        add a,a
        ld c,a
        ld b,$00
        ld hl,${POINTERS_ORG:04X}
        add hl,bc
        ld a,[hl+]
        ld h,[hl]
        ld l,a
        ld bc,${ROLE_VRAM:04X}
        ld a,${BATCHES_PER_STRIP:02X}
        call upload_strip
        ld bc,${NAME_VRAM:04X}
        ld a,${BATCHES_PER_STRIP:02X}
        call upload_strip
        pop hl
        pop de
        pop bc
        pop af
        ret

upload_strip:
        ld [${S_BATCHES:04X}],a
upload_batch:
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
        ld b,$40
copy_first:
        ld a,[hl+]
        ld [de],a
        inc de
        dec b
        jr nz,copy_first
        pop bc
        ld a,c
        add a,$40
        ld c,a
        jr nc,first_ok
        inc b
first_ok:
        ld a,c
        ld [$C048],a
        ld a,b
        ld [$C049],a
        push bc
        ld de,$C04A
        ld b,$40
copy_second:
        ld a,[hl+]
        ld [de],a
        inc de
        dec b
        jr nz,copy_second
        pop bc
        ld a,c
        add a,$40
        ld c,a
        jr nc,second_ok
        inc b
second_ok:
        ld a,$0A
        ld [$C11A],a
        push hl
        rst $18
        pop hl
        ld a,[${S_BATCHES:04X}]
        dec a
        ld [${S_BATCHES:04X}],a
        jr nz,upload_batch
        ret
"""
    return gbasm.assemble(source, CODE_ORG)


def _map_patch(clear_row):
    """Match the native rows: role 13/14, name 16/17, with blank separators."""
    return gbasm.assemble(f"""
        ld hl,$9980
        call ${clear_row:04X}
        ld a,$80
        call $7C88
        ld a,$B0
        call $7C88
        call ${clear_row:04X}
    """, MAP_CODE_AT)[0]


def install(buf, font=None, notes=None):
    del font
    if len(buf) < 0x100000:
        raise SystemExit('endingcredits: requires the 1 MiB expanded ROM')
    cards = graphics()

    sequence, sequence_labels = _sequence()
    if len(sequence) > DRIVER_LIMIT - DRIVER_AT:
        raise SystemExit('endingcredits: local sequence is %d bytes, native driver '
                         'replacement holds %d' %
                         (len(sequence), DRIVER_LIMIT - DRIVER_AT))

    code, labels = _uploader()
    if CODE_ORG + len(code) > POINTERS_ORG:
        raise SystemExit('endingcredits: uploader overlaps its pointer table')
    if POINTERS_ORG + CARDS_PER_BANK * 2 > DATA_ORG:
        raise SystemExit('endingcredits: pointer table overlaps frozen graphics')
    data_end = DATA_ORG + CARDS_PER_BANK * CARD_BYTES
    if data_end > 0x8000:
        raise SystemExit('endingcredits: frozen graphics exceed expanded bank tail')

    for group, bank_number in enumerate(FAR_BANKS):
        bank = _off(bank_number, 0x4000)
        pointer_at = bank + FAR_UPLOAD - 1
        if bytes(buf[pointer_at:pointer_at + 2]) != b'\xFF\xFF':
            raise SystemExit('endingcredits: far entry $%02X in bank %d is occupied' %
                             (FAR_UPLOAD, bank_number))
        occupied_at = bank + CODE_ORG - 0x4000
        occupied_end = bank + data_end - 0x4000
        if any(value != 0xFF for value in buf[occupied_at:occupied_end]):
            raise SystemExit('endingcredits: bank %d $%04X-$%04X is not free' %
                             (bank_number, CODE_ORG, data_end - 1))

        upload = labels['upload']
        buf[pointer_at:pointer_at + 2] = bytes((upload & 0xFF, upload >> 8))
        code_at = bank + CODE_ORG - 0x4000
        buf[code_at:code_at + len(code)] = code
        pointers = b''.join(bytes(((DATA_ORG + index * CARD_BYTES) & 0xFF,
                                   (DATA_ORG + index * CARD_BYTES) >> 8))
                            for index in range(CARDS_PER_BANK))
        pointers_at = bank + POINTERS_ORG - 0x4000
        buf[pointers_at:pointers_at + len(pointers)] = pointers
        first = group * CARDS_PER_BANK
        group_pack = b''.join(cards[first:first + CARDS_PER_BANK])
        data_at = bank + DATA_ORG - 0x4000
        buf[data_at:data_at + len(group_pack)] = group_pack

    driver_at = _off(SOURCE_BANK, DRIVER_AT)
    native_driver = bytes(buf[driver_at:driver_at + (DRIVER_LIMIT - DRIVER_AT)])
    driver_digest = hashlib.sha256(native_driver).hexdigest()
    if driver_digest != NATIVE_DRIVER_SHA256:
        raise SystemExit('endingcredits: native driver changed at 31:$%04X-$%04X: %s' %
                         (DRIVER_AT, DRIVER_LIMIT - 1, driver_digest))

    map_at = _off(SOURCE_BANK, MAP_CODE_AT)
    expected_map = bytes.fromhex('218099cd727c3e80cd887ccd727c3eb0cd887c')
    map_patch = _map_patch(sequence_labels['clear_credit_row'])
    if len(map_patch) != len(expected_map):
        raise SystemExit('endingcredits: map patch changed size (%d != %d)' %
                         (len(map_patch), len(expected_map)))
    if bytes(buf[map_at:map_at + len(expected_map)]) != expected_map:
        raise SystemExit('endingcredits: native credit map builder changed')

    buf[driver_at:driver_at + len(sequence)] = sequence
    buf[map_at:map_at + len(map_patch)] = map_patch

    out = [
        'endingcredits: all 22 native cards translated in approved Inter style; '
        'native forest, music, fades and Japanese End mark preserved',
        'endingcredits: cards split 11/11 across banks %d/%d $%04X-$%04X; '
        'pack SHA-256 %s' %
        (FAR_BANKS[0], FAR_BANKS[1], DATA_ORG, data_end - 1,
         NATIVE_PACK_SHA256[:12]),
        'endingcredits: sequencer replaces native credit driver at 31:$%04X-$%04X; '
        'enemy EXP tables remain untouched' %
        (DRIVER_AT, DRIVER_AT + len(sequence) - 1),
    ]
    if notes is not None:
        notes.extend(out)
    return {
        'cards': cards,
        'data_org': DATA_ORG,
        'data_end': data_end,
        'pointers_org': POINTERS_ORG,
        'code_org': CODE_ORG,
        'labels': labels,
        'sequence': sequence,
        'sequence_labels': sequence_labels,
        'map_patch': map_patch,
    }
