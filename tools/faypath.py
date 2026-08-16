#!/usr/bin/env python3
"""Give Fay's dungeon a status-only Path label that fits its ten-cell field.

The status screen's absolute Path writer at ``4:$4FAE`` selects string index 7 when
``$C9E6 == 0``.  Index 7 is deliberately shared with the title-menu entry
``Fay's Puzzles``.  The status writer starts at shadow column 9 and has only ten cells
before the column-19 border, so copying that thirteen-character title exposes
``Fay's Puz`` and overwrites the border.

Keep the shared title string intact.  Replace only the writer's far call with a wrapper:
ordinary difficulty indices delegate to the original bank-11 copier. Index 7 writes
three spaces plus ``Puzzle`` after its existing one-cell prefix. Index $27 writes two
spaces plus ``Expert`` after its existing two-cell prefix. The resulting ten-cell values
occupy columns 9..18 exactly and leave the border alone; this also strips the trailing
fixed-cell padding carried by the shared ``Expert`` record.
"""
import gbasm
from latinfont import EN_CODES


BANKSZ = 0x4000
CALL_BANK = 4
CALL_AT = 0x4FD4
CALL_OLD = bytes((0xD7, 0x07, 0x0B))       # rst $10 / db index 7, bank 11

FAR_BANK = 0x34                            # bank 52; pool reader ends at $4059
FAR_INDEX = 0x05
CODE_AT = 0x405A
CODE_LIMIT = 0x4100                        # redirected text starts here

FAY_INDEX = 0x07
EXPERT_INDEX = 0x27
FAY_TEXT = '   Puzzle'                     # writer already emitted the fourth space
EXPERT_TEXT = '  Expert'                   # writer already emitted two spaces
FAY_BYTES = bytes(EN_CODES[ch] for ch in FAY_TEXT) + bytes((0xFF,))
EXPERT_BYTES = bytes(EN_CODES[ch] for ch in EXPERT_TEXT) + bytes((0xFF,))


def _off(bank, addr):
    return bank * BANKSZ + addr - (0x4000 if bank else 0)


def _helper():
    fay = ','.join('$%02X' % value for value in FAY_BYTES)
    expert = ','.join('$%02X' % value for value in EXPERT_BYTES)
    source = f"""
        cp ${FAY_INDEX:02X}
        jr z,.fay
        cp ${EXPERT_INDEX:02X}
        jr z,.expert
        rst $10
        db $07,$0B
        ret
    .fay:
        ld hl,.faytext
        jr .copy
    .expert:
        ld hl,.experttext
    .copy:
        ld a,[hl+]
        ld [de],a
        inc de
        cp $FF
        jr nz,.copy
        ret
    .faytext:
        db {fay}
    .experttext:
        db {expert}
    """
    return gbasm.assemble(source, CODE_AT)


def install(buf, notes):
    helper, _labels = _helper()
    if CODE_AT + len(helper) > CODE_LIMIT:
        raise SystemExit('faypath: %d-byte helper overruns bank %d prefix' %
                         (len(helper), FAR_BANK))

    call = _off(CALL_BANK, CALL_AT)
    found = bytes(buf[call:call + len(CALL_OLD)])
    if found != CALL_OLD:
        raise SystemExit('faypath: status Path far call at 4:$%04X changed: %s' %
                         (CALL_AT, found.hex(' ')))

    helper_at = _off(FAR_BANK, CODE_AT)
    if any(value != 0xFF for value in buf[helper_at:helper_at + len(helper)]):
        raise SystemExit('faypath: helper site %d:$%04X is occupied' %
                         (FAR_BANK, CODE_AT))
    entry = _off(FAR_BANK, 0x4000) + FAR_INDEX - 1
    if bytes(buf[entry:entry + 2]) != bytes((0xFF, 0xFF)):
        raise SystemExit('faypath: far entry $%02X in bank %d is occupied' %
                         (FAR_INDEX, FAR_BANK))

    buf[helper_at:helper_at + len(helper)] = helper
    # Entering the helper directly must preserve the source index test. Point the far
    # entry at the wrapper start, not at the Fay branch label.
    buf[entry:entry + 2] = bytes((CODE_AT & 0xFF, CODE_AT >> 8))
    buf[call:call + len(CALL_OLD)] = bytes((0xD7, FAR_INDEX, FAR_BANK))
    notes.append("status Path modes 0/4: shared padded sources -> right-aligned "
                 "`Puzzle`/`Expert` in columns 9..18; title-menu string unchanged")
