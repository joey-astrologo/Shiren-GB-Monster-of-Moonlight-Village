#!/usr/bin/env python3
"""Approved-font fragments whose canonical pixels must survive menu transitions.

Weapon/Shield remain source-stable four-tile fragments; statusvwf publishes their maps
alongside full Strength/Experience and the dynamic values. Box 30 keeps task-number cells
2-4 and star cells 13+ while composing No and Rating. The selectable name grid remains
one character per cell.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dotfont
import gbasm
from latinfont import EN_CODES, FONT_BASE, GLYPH_BYTES


BANKSZ = 0x4000
BOX_TABLE = (31, 0x45D5)
QUIZ_ROW_AT = 4 * BANKSZ + (0x704E - 0x4000)
QUIZ_ROW_CELLS = 18
DIVIDER = 0xB6
SPACE = EN_CODES[' ']
TERM = 0xFF

# Fay can be entered without the ordinary menu-font upload.  Rank/Pass paints `$9A-$9D`,
# erase confirmation paints `$8A`, and ordinary one-row messages paint through `$C4`.
# They are all mutually exclusive with the quiz, but their VRAM pixels outlive their
# tilemaps.  Restore every Fay tile that any VWF pool is allowed to borrow at the one
# authoritative screen-entry boundary instead of depending on each incoming route.
FEI_RESTORE_BANK = 38
FEI_RESTORE_INDEX = 0x07
FEI_RESTORE_AT = 0x407C       # immediately after propvwf's bank-38 carry helper
FEI_RESTORE_LIMIT = 0x4200
FEI_ENTRY_PATCH = (4, 0x6E95)
FEI_ENTRY_OLD = bytes.fromhex('78eaf9c63e11cd2848')
FEI_RESTORE_TILES = (0x8A, 0x94, 0x95, 0x9A, 0x9B, 0x9C, 0x9D,
                     0xA4, 0xAF, 0xC4)

FEI_RESTORE_SRC = """
feirestore:
  ; Preserve the original entry's aggregate quiz-availability result.
  ld a,b
  ld [$C6F9],a
  push bc
  push de
  push hl
  ; Screen 17 is a composite: keep it dark while native graphics, task cells and
  ; proportional prompts are restored. menuvwf's box-32 finalizer publishes it.
  ld a,$13
  ld [$C1B3],a
  call frready
  ldh a,[$FF40]
  res 7,a
  ldh [$FF40],a
  ; `$8A` (stars) and `$94-$95` (No): three tiles in one VBlank.
  ld hl,frdata
  ld de,$88A0
  ld b,$01
  call frcopy
  ld de,$8940
  ld b,$02
  call frcopy
  ; `$9A-$9D` (Rating): the Pass row used to survive here.
  call frready
  ld de,$89A0
  ld b,$04
  call frcopy
  ; Empty/completed boxes and separators: three non-contiguous native tiles.
  call frready
  ld de,$8A40
  ld b,$01
  call frcopy
  ld de,$8AF0
  ld b,$01
  call frcopy
  ld de,$8C40
  ld b,$01
  call frcopy
  pop hl
  pop de
  pop bc
  ld a,$11
  ret
frready:
  ldh a,[$FF40]
  bit 7,a
  ret z
  ldh a,[$FF44]
  cp $90
  jr c,frwaitblank
frwaitvisible:
  ldh a,[$FF44]
  cp $90
  jr nc,frwaitvisible
frwaitblank:
  ldh a,[$FF44]
  cp $90
  jr c,frwaitblank
  ret
frcopy:
  ld c,$10
frbyte:
  ld a,[hl+]
  ld [de],a
  inc de
  dec c
  jr nz,frbyte
  dec b
  jr nz,frcopy
  ret
frdata:
  db %s
"""

# The status row remains visible behind the item list, so none of its persistent fragments
# may occupy a live item-allocator tile. Weapon and Shield use eight source-stable IDs
# that are neither English punctuation nor allocator capacity.
BOX2_TILES = {
    'Weapon': (0xA5, 0xA6, 0xA7, 0xA8),
    'Shield': (0xAA, 0xAD, 0xAE, 0xA9),
}

# Fay is entered through a menu transition which restores these six allocator tiles from
# ROM before drawing its header.  Keeping every Fay fragment in that context-local set
# leaves $9E/$9F/$A0/$B2 available for their real English punctuation.  In particular,
# $A0 is the colon after a Log/ranking number; claiming it made that colon look like
# the first "Ra" fragment of Rating.
QUIZ_TILES = {
    'No': (0x94, 0x95),
    'Rating': (0x9A, 0x9B, 0x9C, 0x9D),
}


def _off(bank, addr):
    return bank * BANKSZ + (addr - (0x4000 if bank else 0))


def _encode(text):
    return bytes(EN_CODES[ch] for ch in text)


def _render(text, font):
    """Return the minimum sequence of 8-byte 1bpp tiles for one Dot fragment."""
    extent = font.text_extent(text)
    count = max(1, (extent + 7) // 8)
    tiles = [bytearray(8) for _ in range(count)]
    pen = 0
    for ch in text:
        glyph = font.glyphs[ch]
        for y, row in enumerate(glyph):
            for x in range(8):
                if not row & (0x80 >> x):
                    continue
                pixel = pen + x
                if pixel >= count * 8:
                    raise SystemExit('structvwf: %r paints beyond its measured extent' % text)
                tiles[pixel // 8][y] |= 0x80 >> (pixel & 7)
        pen += font.advance(ch)
    return tuple(bytes(tile) for tile in tiles)


def _two_plane(one_plane):
    return b''.join(bytes((row, row)) for row in one_plane)


def _descriptor(buf, box):
    table = _off(*BOX_TABLE)
    addr = buf[table + 2 * box] | (buf[table + 2 * box + 1] << 8)
    at = _off(31, addr)
    return at, tuple(buf[at:at + 5]), buf[at + 5] | (buf[at + 6] << 8)


def _rows(buf, box):
    _desc_at, (_x, _y, count, width, _flags), source = _descriptor(buf, box)
    at = _off(31, source)
    out = []
    for _row in range(count):
        start = at
        for _cell in range(width):
            if buf[at] == TERM:
                break
            at += 1
        if buf[at] != TERM:
            raise SystemExit('structvwf: box %d row has no terminator within %d cells'
                             % (box, width))
        out.append((start, bytes(buf[start:at])))
        at += 1
    return out


def install(buf, notes=None, font=None):
    if font is None:
        font = dotfont.load_approved()

    custom = {}
    for text, ids in tuple(BOX2_TILES.items()) + tuple(QUIZ_TILES.items()):
        raster = _render(text, font)
        if len(raster) != len(ids):
            raise SystemExit('structvwf: %r renders to %d tiles, allocation has %d'
                             % (text, len(raster), len(ids)))
        for tile_id, tile in zip(ids, raster):
            if tile_id in custom:
                raise AssertionError('structvwf: duplicate custom tile $%02X' % tile_id)
            custom[tile_id] = tile

    for tile_id, tile in custom.items():
        at = FONT_BASE + tile_id * GLYPH_BYTES
        buf[at:at + GLYPH_BYTES] = tile

    # Build the restore payload from the final canonical ROM data. `$00-$C3` are stored
    # as 1bpp source rows and doubled by the native uploader; `$C4` begins the raw 2bpp
    # graphics block. Keeping the payload derived makes it impossible for a later font
    # adjustment to leave Fay's entry restore stale.
    restore_planes = bytearray()
    for tile_id in FEI_RESTORE_TILES:
        at = FONT_BASE + tile_id * GLYPH_BYTES
        if tile_id == 0xC4:
            restore_planes += buf[at:at + 16]
        else:
            restore_planes += _two_plane(buf[at:at + GLYPH_BYTES])
    restore_src = FEI_RESTORE_SRC % ','.join('$%02X' % value
                                             for value in restore_planes)
    restore, restore_labels = gbasm.assemble(restore_src, FEI_RESTORE_AT)
    if FEI_RESTORE_AT + len(restore) > FEI_RESTORE_LIMIT:
        raise SystemExit('structvwf: Fay restore needs %d bytes, only %d available'
                         % (len(restore), FEI_RESTORE_LIMIT - FEI_RESTORE_AT))
    bank_at = FEI_RESTORE_BANK * BANKSZ
    if buf[bank_at] != FEI_RESTORE_BANK:
        raise SystemExit('structvwf: bank %d far-call table is not installed' %
                         FEI_RESTORE_BANK)
    index_at = bank_at + FEI_RESTORE_INDEX - 1
    if bytes(buf[index_at:index_at + 2]) != b'\xFF\xFF':
        raise SystemExit('structvwf: far index $%02X in bank %d is already used'
                         % (FEI_RESTORE_INDEX, FEI_RESTORE_BANK))
    code_at = bank_at + FEI_RESTORE_AT - 0x4000
    if any(value != 0xFF for value in buf[code_at:code_at + len(restore)]):
        raise SystemExit('structvwf: Fay restore region %d:$%04X is not free'
                         % (FEI_RESTORE_BANK, FEI_RESTORE_AT))
    buf[code_at:code_at + len(restore)] = restore
    buf[index_at] = restore_labels['feirestore'] & 0xFF
    buf[index_at + 1] = restore_labels['feirestore'] >> 8

    entry_bank, entry_addr = FEI_ENTRY_PATCH
    entry_at = entry_bank * BANKSZ + entry_addr - 0x4000
    if bytes(buf[entry_at:entry_at + len(FEI_ENTRY_OLD)]) != FEI_ENTRY_OLD:
        raise SystemExit('structvwf: Fay entry patch at %d:$%04X changed'
                         % FEI_ENTRY_PATCH)
    entry = bytes((0xD7, FEI_RESTORE_INDEX, FEI_RESTORE_BANK,
                   0xCD, 0x28, 0x48, 0x00, 0x00, 0x00))
    buf[entry_at:entry_at + len(entry)] = entry

    box2_at, box2_desc, _box2_source = _descriptor(buf, 2)
    # build.py may DTE-pack these ROM rows before this installer runs. statusvwf owns
    # their final shadow map, so structvwf only needs the stable geometry and the base
    # native flags; it no longer rewrites variable-length packed source bytes in place.
    if box2_desc[:4] != (0, 10, 2, 18) or box2_desc[4] & 0x7F != 0x04:
        raise SystemExit('structvwf: box 2 descriptor at 31:$%04X is %s, expected '
                         '(0,10,2,18,$04|DTE)' %
                         (0x4000 + box2_at - 31 * BANKSZ, box2_desc))

    box30_at, box30_desc, _box30_source = _descriptor(buf, 30)
    if box30_desc != (0, 0, 1, 18, 0x00):
        raise SystemExit('structvwf: box 30 descriptor at 31:$%04X is %s, expected '
                         '(0,0,1,18,$00)' %
                         (0x4000 + box30_at - 31 * BANKSZ, box30_desc))
    box30 = _rows(buf, 30)
    expected_quiz = _encode('No     Rating')
    if len(box30) != 1 or box30[0][1] != expected_quiz:
        raise SystemExit('structvwf: box 30 wording/layout changed: %s'
                         % ([data.hex(' ') for _at, data in box30],))
    quiz_row = (bytes(QUIZ_TILES['No']) + bytes((SPACE,)) * 5
                + bytes(QUIZ_TILES['Rating']))
    quiz_row += bytes((SPACE,)) * (len(expected_quiz) - len(quiz_row))
    quiz_at = box30[0][0]
    buf[quiz_at:quiz_at + len(quiz_row)] = quiz_row

    mirrored = expected_quiz + bytes((SPACE,)) * (QUIZ_ROW_CELLS - len(expected_quiz))
    if bytes(buf[QUIZ_ROW_AT:QUIZ_ROW_AT + QUIZ_ROW_CELLS]) != mirrored:
        raise SystemExit('structvwf: Fay mirror at 4:$704E no longer matches box 30')
    fixed_mirror = quiz_row + bytes((SPACE,)) * (QUIZ_ROW_CELLS - len(quiz_row))
    buf[QUIZ_ROW_AT:QUIZ_ROW_AT + QUIZ_ROW_CELLS] = fixed_mirror

    if notes is not None:
        notes.append('structvwf: box 2 Weapon/Shield and Fay header install fixed-position '
                     'font fragments; statusvwf owns the completed box-2 shadow map')
        notes.append('structvwf: Fay entry restores %d borrowed VWF/native tiles inside '
                     'one atomic screen transaction via %d:$%04X (%d bytes)'
                     % (len(FEI_RESTORE_TILES), FEI_RESTORE_BANK, FEI_RESTORE_AT,
                        len(restore)))


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: structvwf.py <rom-in> <rom-out>')
    buf = bytearray(open(sys.argv[1], 'rb').read())
    install(buf)
    open(sys.argv[2], 'wb').write(buf)


if __name__ == '__main__':
    main()
