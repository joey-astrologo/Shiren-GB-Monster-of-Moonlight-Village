#!/usr/bin/env python3
"""Right-align the save-summary ``Normal`` difficulty inside its thirteen-cell field.

The Adventure log summary draws difficulty on row 2 through the writer at ``4:$69D8``:

    dec c                                  ; difficulty 1..4 -> 0..3
    ld hl,$69F2 / add hl,bc / ld l,[hl]    ; COLUMN OFFSET, added to the destination
    ld h,$00 / add hl,de / ld d,h / ld e,l
    ld hl,$69F6 / add hl,bc / ld a,[hl]    ; bank-11 string index
    rst $10 / db $07,$0B                   ; far copier, runs to the terminator

The copier is length-agnostic, so the geometry lives entirely in the offset table. Those
four offsets right-align the JAPANESE labels in the thirteen-cell field:

    index  japanese      kana  offset  english   cells
    0      やさしい          4     $09   Easy      9..12
    1      ふつう            3     $0A   Normal    10..15   <-- clipped to `Nor`
    2      むずかしい        5     $09   Hard      9..12
    3      もっとむずかしい   8     $06   Expert    6..14

`Normal` is the only difficulty whose English is LONGER than its Japanese, which is why
it is the only one that clips, and why the status-screen fix in `faypath.py` did not
reach it -- that patches a different consumer, the absolute Path writer at `4:$4FAE`.

Offset $07 puts `Normal` in cells 7..12, ending on the same right edge as the shipping
`Easy`/`Hard` rows and producing an identically sized thirteen-cell row. It is also the
conservative choice on overrun: `Normal` is relocated rather than padded, so it carries
no trailing spaces and writes exactly six cells, whereas the untouched `Expert` record
keeps three cells of fixed-width padding and already writes through cell 14.

Only the one offset byte changes. The dispatcher and both tables are asserted first, so a
shifted routine fails the build instead of being patched blind.
"""

BANKSZ = 0x4000
BANK = 4

# `dec c` through the far call, asserted so a moved writer cannot be patched blind.
SETUP_AT = 0x69D9
SETUP_OLD = bytes.fromhex('0d 06 00 21 f2 69 09 6e 26 00 19 54 5d 21 f6 69 09 7e d7 07 0b')

OFFSETS_AT = 0x69F2
OFFSETS_OLD = bytes((0x09, 0x0A, 0x09, 0x06))     # Easy, Normal, Hard, Expert
INDICES_AT = 0x69F6
INDICES_OLD = bytes((0x0B, 0x0C, 0x0D, 0x27))     # bank-11 string-table indices

NORMAL_SLOT = 1
NORMAL_OLD = 0x0A
NORMAL_NEW = 0x07


def _off(bank, addr):
    return bank * BANKSZ + addr - (0x4000 if bank else 0)


def install(buf, notes):
    for at, want, what in ((SETUP_AT, SETUP_OLD, 'difficulty writer'),
                           (OFFSETS_AT, OFFSETS_OLD, 'column-offset table'),
                           (INDICES_AT, INDICES_OLD, 'string-index table')):
        off = _off(BANK, at)
        found = bytes(buf[off:off + len(want)])
        if found != want:
            raise SystemExit(
                'summarydifficulty: save-summary %s at %d:$%04X changed: %s -- the '
                'address moved, and patching blind would corrupt code'
                % (what, BANK, at, found.hex(' ')))

    slot = _off(BANK, OFFSETS_AT) + NORMAL_SLOT
    assert buf[slot] == NORMAL_OLD
    buf[slot] = NORMAL_NEW
    notes.append('save-summary Normal difficulty: column offset $%02X -> $%02X, so the '
                 'six-cell English name occupies cells %d..12 instead of clipping to '
                 '`Nor`' % (NORMAL_OLD, NORMAL_NEW, NORMAL_NEW))
