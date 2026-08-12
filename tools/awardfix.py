#!/usr/bin/env python3
"""Replace the Awards screen's native four-kana code with an English heading.

The small box below ``Log N`` is populated by ``4:$796F``.  The native routine derives
four kana from the selected log's 12-byte record through the 32-entry table at
``4:$79C4``.  Once the Japanese font is replaced those unchanged codes appear as strings
such as ``TtfD``; they are data, so the ordinary translation extractor cannot reach them.

For this translation the screen is reached through Rank/Pass. Replace that private
producer with ``Pass`` plus its terminator. It occupies the native four-character field,
so the box geometry and source-character limit remain unchanged.
"""
import gbasm
from latinfont import EN_CODES


BANKSZ = 0x4000
ROUTINE_AT = 0x796F
ROUTINE_BYTES = 0x3C
TEXT_AT = 0x79AB
TITLE = 'Pass'
TITLE_BYTES = bytes(EN_CODES[ch] for ch in TITLE) + bytes([0xFF])

NATIVE_ROUTINE = bytes.fromhex(
    'f5 c5 d5 e5 e8 db f8 00 54 5d fa ab c6 cb 27 c6 '
    'ab 6f 3e 00 ce 79 67 2a 66 6f d5 0e 0c 2a 12 13 '
    '0d 20 fa d1 d7 71 0f f8 0e 11 16 c6 0e 04 2a cd '
    'b1 79 0d 20 f9 e8 25 e1 d1 c1 f1 c9')
NATIVE_TEXT_SLOT = bytes.fromhex('79 c5 89 c5 99 c5 f5')
assert len(NATIVE_ROUTINE) == ROUTINE_BYTES
assert len(TITLE_BYTES) <= len(NATIVE_TEXT_SLOT)


def _off(bank, addr):
    return bank * BANKSZ + addr - 0x4000


def _routine():
    code, _labels = gbasm.assemble(f"""
        push af
        push bc
        push de
        push hl
        ld hl,${TEXT_AT:04X}
        ld de,$C616
        ld b,${len(TITLE_BYTES):02X}
    .copy:
        ld a,[hl+]
        ld [de],a
        inc de
        dec b
        jr nz,.copy
        pop hl
        pop de
        pop bc
        pop af
        ret
    """, ROUTINE_AT)
    if len(code) > ROUTINE_BYTES:
        raise AssertionError('awardfix: replacement routine does not fit native slot')
    return code


def install(buf, notes):
    routine_at = _off(4, ROUTINE_AT)
    text_at = _off(4, TEXT_AT)
    found = bytes(buf[routine_at:routine_at + ROUTINE_BYTES])
    if found != NATIVE_ROUTINE:
        raise SystemExit('awardfix: native 4:$796F producer changed: %s' %
                         found.hex(' '))
    found = bytes(buf[text_at:text_at + len(NATIVE_TEXT_SLOT)])
    if found != NATIVE_TEXT_SLOT:
        raise SystemExit('awardfix: native 4:$79AB table slot changed: %s' %
                         found.hex(' '))
    code = _routine()
    buf[routine_at:routine_at + len(code)] = code
    # Stop immediately.  The unused tail remains native data and is unreachable.
    buf[text_at:text_at + len(TITLE_BYTES)] = TITLE_BYTES
    notes.append('Awards heading: dynamic four-kana code at 4:$796F -> `%s` '
                 'in the native four-character box' % TITLE)
