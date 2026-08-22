#!/usr/bin/env python3
"""Translate the Normal-clear teaser around the native green ``End`` mark.

The full Hard ending and its 22-card credit roll are separate.  Clearing Normal dispatches
bank-31 ending case 4; Hard eventually dispatches case 5, the plain green ``End`` screen.
The first implementation confused those cases and patched the Hard-only renderer, so its
test could pass while a real Normal clear stayed Japanese.  This patch replaces only case
4's one-shot far call with a wrapper that first invokes the original native producer and
then adds the English overlay.  All other cards retain their byte-for-byte native route.
The overlay keeps the mark and timing, clears the six Japanese text rows, and installs two
approved-font English raster rows.

The rasters are stored as one-bit tile rows in the otherwise unused last $100 bytes of
ending-credit bank 59.  They use the native card's polarity: set pixels are its black
background and cleared pixels form the white letters.  The tiny far helper expands each
byte to both Game Boy bitplanes while the LCD is briefly disabled during the already-black
transition.  Case 5 is outside the hook and remains byte-for-byte native apart from the
separately translated credits.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gbasm


BANKSZ = 0x4000
SOURCE_BANK = 31
FAR_BANK = 0x3B
FAR_INDEX = 0x07
CODE_ORG = 0x405A
CODE_LIMIT = 0x4100
DATA_ORG = 0x7F00
DATA_LIMIT = 0x8000

HOOK_AT = 0x79CB
# Case 4's one-shot native producer call, ``far 30:$7F0C``.
HOOK_OLD = bytes.fromhex('D7 0B 1E')

TILE_BASE = 0xA0
TILE_VRAM = 0x8A00                       # signed BG tile $A0
MAP_BASE = 0x9800
TOP_ROW = 4
BOTTOM_ROW = 14
TOP_TEXT = "That's all for now."
BOTTOM_TEXT = 'See the rest on Hard!'


def _off(bank, addr):
    return bank * BANKSZ + (addr - (BANKSZ if bank else 0))


def _raster_row(text, font):
    """Return native-polarity ``(map_x, 1bpp tiles)`` for a centered font row."""
    missing = sorted(set(text) - set(font.glyphs))
    if missing:
        raise SystemExit('normalending: approved font has no glyph(s) %r' % missing)
    width = font.text_extent(text)
    if width > 160:
        raise SystemExit('normalending: %r is %d pixels wide' % (text, width))
    left = (160 - width) // 2
    pixels = [0] * 8
    pen = left
    for char in text:
        glyph = font.glyphs[char]
        for y, row in enumerate(glyph):
            for x in range(8):
                if row & (0x80 >> x):
                    at = pen + x
                    if not 0 <= at < 160:
                        raise SystemExit('normalending: centered row crossed the screen')
                    pixels[y] |= 1 << (159 - at)
        pen += font.advance(char)

    first = left // 8
    last = (left + width - 1) // 8
    tiles = bytearray()
    for tile in range(first, last + 1):
        for y in range(8):
            # Native case 4 uses color 3 (both bits set) as black and color 0 as
            # white.  Store black around the glyph and cut the letter out in white.
            tiles.append(((pixels[y] >> (152 - tile * 8)) & 0xFF) ^ 0xFF)
    return first, bytes(tiles)


def graphics(font):
    """Return the two map records and their packed one-bit tile data."""
    top_x, top = _raster_row(TOP_TEXT, font)
    bottom_x, bottom = _raster_row(BOTTOM_TEXT, font)
    top_count = len(top) // 8
    bottom_count = len(bottom) // 8
    records = (
        (TOP_ROW, top_x, TILE_BASE, top_count),
        (BOTTOM_ROW, bottom_x, TILE_BASE + top_count, bottom_count),
    )
    pack = top + bottom
    if len(pack) > DATA_LIMIT - DATA_ORG:
        raise SystemExit('normalending: %d-byte raster exceeds $%04X-$%04X' %
                         (len(pack), DATA_ORG, DATA_LIMIT - 1))
    if TILE_BASE + top_count + bottom_count > 0xC0:
        raise SystemExit('normalending: English teaser exceeds private $A0-$BF tiles')
    return records, pack


def _helper(records, pack):
    top, bottom = records
    source = f"""
normal_end:
        rst $10
        db $0B,$1E
english:
        ldh a,[$FF40]
        bit 7,a
        jr z,lcd_ready
wait_vblank:
        ldh a,[$FF44]
        cp $90
        jr c,wait_vblank
lcd_ready:
        di
        ldh a,[$FF40]
        push af
        res 7,a
        ldh [$FF40],a
        push bc
        push de
        ld hl,${DATA_ORG:04X}
        ld de,${TILE_VRAM:04X}
        ld bc,${len(pack):04X}
tile_loop:
        ld a,[hl+]
        ld [de],a
        inc de
        ld [de],a
        inc de
        dec bc
        ld a,b
        or c
        jr nz,tile_loop
        ld hl,${MAP_BASE + 3 * 32:04X}
        call clear_pair
        ld hl,${MAP_BASE + 12 * 32:04X}
        call clear_pair
        ld hl,${MAP_BASE + 15 * 32:04X}
        call clear_pair
        ld hl,${MAP_BASE + top[0] * 32 + top[1]:04X}
        ld a,${top[2]:02X}
        ld b,${top[3]:02X}
top_map:
        ld [hl+],a
        inc a
        dec b
        jr nz,top_map
        ld hl,${MAP_BASE + bottom[0] * 32 + bottom[1]:04X}
        ld a,${bottom[2]:02X}
        ld b,${bottom[3]:02X}
bottom_map:
        ld [hl+],a
        inc a
        dec b
        jr nz,bottom_map
        pop de
        pop bc
        pop af
        ldh [$FF40],a
        ei
        ret
clear_pair:
        xor a
        ld b,$34
clear_loop:
        ld [hl+],a
        dec b
        jr nz,clear_loop
        ret
"""
    return gbasm.assemble(source, CODE_ORG)


def install(buf, font, notes=None):
    """Install the conditional Normal-clear card and return its build metadata."""
    if len(buf) < 0x100000:
        raise SystemExit('normalending: requires the 1 MiB expanded ROM')
    records, pack = graphics(font)
    code, labels = _helper(records, pack)
    if CODE_ORG + len(code) > CODE_LIMIT:
        raise SystemExit('normalending: helper is %d bytes; $%04X-$%04X holds %d' %
                         (len(code), CODE_ORG, CODE_LIMIT - 1,
                          CODE_LIMIT - CODE_ORG))

    bank = _off(FAR_BANK, 0x4000)
    pointer_at = bank + FAR_INDEX - 1
    if bytes(buf[pointer_at:pointer_at + 2]) != b'\xFF\xFF':
        raise SystemExit('normalending: far entry $%02X in bank %d is occupied' %
                         (FAR_INDEX, FAR_BANK))
    code_at = bank + CODE_ORG - 0x4000
    data_at = bank + DATA_ORG - 0x4000
    if any(value != 0xFF for value in buf[code_at:code_at + len(code)]):
        raise SystemExit('normalending: bank %d helper span is not free' % FAR_BANK)
    if any(value != 0xFF for value in buf[data_at:data_at + len(pack)]):
        raise SystemExit('normalending: bank %d raster tail is not free' % FAR_BANK)

    hook = _off(SOURCE_BANK, HOOK_AT)
    if bytes(buf[hook:hook + len(HOOK_OLD)]) != HOOK_OLD:
        raise SystemExit('normalending: native Normal-teaser hook changed at 31:$%04X' %
                         HOOK_AT)
    entry = labels['normal_end']
    buf[pointer_at:pointer_at + 2] = bytes((entry & 0xFF, entry >> 8))
    buf[code_at:code_at + len(code)] = code
    buf[data_at:data_at + len(pack)] = pack
    buf[hook:hook + len(HOOK_OLD)] = bytes((0xD7, FAR_INDEX, FAR_BANK))

    out = [
        'normalending: native case-4 Normal-clear teaser translated as %r / %r; '
        'green End, palette and timing retained; Hard case 5 untouched' %
        (TOP_TEXT, BOTTOM_TEXT),
        'normalending: %d approved-font tiles packed in native black-card polarity '
        'in bank %d '
        '$%04X-$%04X; helper %d/%d bytes' %
        (len(pack) // 8, FAR_BANK, DATA_ORG, DATA_ORG + len(pack) - 1,
         len(code), CODE_LIMIT - CODE_ORG),
    ]
    if notes is not None:
        notes.extend(out)
    return {'records': records, 'pack': pack, 'code': code, 'labels': labels}
