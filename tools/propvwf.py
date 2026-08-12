#!/usr/bin/env python3
"""Proportional composer for the approved compact 8x8 font.

This remains separate from ``vwf.py`` so that omitting ``--dot-font`` produces the
measured uniform-6px control.  ``build.sh`` selects this approved path by default.  It
stages up to 30 source glyphs while assigning each glyph its approved advance in pixels.
The 30-glyph count is a source/reveal ceiling, not the visual line width: composition is
still clipped at the measured 144px edge.

The game's transfer queue only holds one 72px half-line.  A proportional glyph can cross
that boundary, so the first pass parks its spill tile, cumulative pen, character count,
and source pointer.  The second copies that spill into tile zero and resumes at the saved
pointer.  The first 28 entries of the typewriter's character-to-tile map live in the
measured-free run ``$C0E2-$C0FD``; entries 29 and 30 use measured-free post-composition
scratch at ``$C0D6`` and ``$C0DD``.  This split deliberately avoids live game bytes
``$C0FE-$C0FF``.  The map is generated at the end of the second composition pass.  The
optimized one-plane blitter,
literal scanner, and split proportional/native loops keep that whole pass inside its
original scheduler slot.

All eight shift residues are precomputed for the approved English glyphs plus the native
dialogue bullet.  A small code-to-slot table keeps that to 9.8 KiB instead of the 22.4
KiB a dense 179-code table would cost.  Translated composer lines are required to use
that approved page.
Untranslated lines optimistically compose proportionally and restart from a clean queue at native
8px spacing when a non-English code occurs.  The build proves every such fallback is
detectable before the first 72px half ends; it rejects a line that would switch too late.

usage:
    python3 tools/propvwf.py --selftest
    python3 tools/propvwf.py in.gb out.gb
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dotfont
import gbasm
import codec
from latinfont import EN_CODES, FONT_BASE, GLYPH_BYTES


BANKSZ = 0x4000

# ---------------------------------------------------------------------- geometry
CELLS = 18
CHARS = 30
HALF_PX = CELLS * 8 // 2
LINE_PX = CELLS * 8
OLD_LINE_CHARS = 0x12

QUEUE_PAYLOAD = 0xC008
ZERO_RUNS = ((0xC008, 0x40), (0xC04A, 0x40), (0xC08C, 0x10))
DUMMY_TILE = 0xC12C

# Shared, proven-free scratch.  $C0CC-$C0DD is also menuvwf's ephemeral row state;
# the proportional composer keeps that hook disabled.  The reveal map deliberately starts at
# $C0E2 because menuvwf retains $C0E0/$C0E1 for its raw border/marker cells.
S_PEN = 0xC0CC
S_COUNT = 0xC0CD
S_HALF = 0xC0CE
S_CODE = 0xC0CF
S_WIDTH = 0xC0D0
S_SHIFT = 0xC0D1
S_DST0 = 0xC0D2
S_DST1 = 0xC0D4
# S_ROWS was never consumed by the renderer.  Once pass 2 reaches buildmap, both this
# byte and $C0DD are available to hold the two reveal ordinals beyond the contiguous,
# trace-proven-safe $C0E2-$C0FD run.  Do not extend that run into live $C0FE/$C0FF.
REVEAL_TAIL0 = 0xC0D6
S_LOCAL = 0xC0D7
S_TILE = 0xC0D8
S_MODE = 0xC0D9
S_SRC = 0xC0DA
S_INDEX = 0xC0DC
REVEAL_TAIL1 = 0xC0DD
REVEAL_MAP = 0xC0E2
REVEAL_MAIN_COUNT = 28
REVEAL_MAP_END = REVEAL_MAP + REVEAL_MAIN_COUNT
REVEAL_TAIL = (REVEAL_TAIL0, REVEAL_TAIL1)
assert REVEAL_MAIN_COUNT + len(REVEAL_TAIL) == CHARS

# ---------------------------------------------------------------------- bank 13
COMPOSER_BUDGET = 0x40D6
RENDER_AT = 0x43B8
RENDER_TAIL = 0x43D0
RENDER_LIMIT = RENDER_TAIL
SCANNER_AT = 0x4418
SCANNER_END = 0x4464

REVEAL_CALL = 0x6B5B
REVEAL_QUEUE = 0x6B85
CELLMAP_AT = SCANNER_AT
CELLMAP_END = 0x4484
COLUMN_MASK = 0x1F

OLD_BLITTER = bytes.fromhex('06 00 cb 21 cb 10 cb 21 cb 10 cb 21 cb 10 e5 21 80 76'
                            '09 06 08 2a 12 13 12 13 05 20 f8 e1 c1 c9')
OLD_SCANNER = bytes.fromhex(
    'c5 0e ff 7e fe 79 20 03 23 18 3c fe 7a 20 03 23 18 35 '
    'fe e0 20 04 23 23 18 2d fe ed 20 03 23 18 26 fe eb 20 04 23 23 18 1e '
    'fe e8 20 03 23 18 17 fe ef 20 03 23 18 10 fe ee 20 03 23 18 09 '
    'fe ff 20 03 23 18 02 23 4f 79 fe ff 28 b7')

# ---------------------------------------------------------------------- bank 32
FAR_BANK = 0x20
FAR_INDEX = 0x05
# Bank 32 is byte-packed against menuvwf.  The spill-tile carry helper needs no glyph
# tables, so it lives after the mandatory reader and before text in pool bank 38.
CARRY_BANK = 0x26
CARRY_INDEX = 0x05
CARRY_ORG = 0x405A
CARRY_LIMIT = 0x4100
DATA_ORG = 0x4400
FONT_CODES = 0xB3
# Native dialogue cursor/bullet, unidentified-equipment mark, and plating star are
# retained at 8px.  `$88` is not decorative padding: carried equipment whose modifier
# has not yet been identified appends it twice, and the same pair reaches the item-detail
# name row and dialogue substitutions.  If it is absent from this table one unsupported
# suffix makes the *whole* containing line restart at native fixed width.
#
# Bank 32 remains tightly packed, so these status glyphs use the pre-shift slots that the
# menu renderer's compact painted-extent calculation makes room for. `~` stays omitted:
# no shipped string or name-entry cell can produce it, and unsupported_codes() keeps that
# fact measurable.
EXTRA_PROP_CODES = (0x81, 0x88, 0x8A)
OMITTED_PROP_CODES = (EN_CODES['~'],)
DOT_CODES = tuple(sorted((set(EN_CODES.values()) - set(OMITTED_PROP_CODES))
                         | set(EXTRA_PROP_CODES)))
DOT_SLOTS = len(DOT_CODES)
SHIFTS = tuple(range(8))
DOT_GLYPH_STRIDE = len(SHIFTS) * 16
GLYPH_ORG = DATA_ORG
NATIVE_ORG = GLYPH_ORG + DOT_SLOTS * DOT_GLYPH_STRIDE
META_ORG = NATIVE_ORG + FONT_CODES * GLYPH_BYTES
# This table used to be page-aligned so core-code lookup could load only H.  Adding the
# genuine unidentified-equipment star crossed the next page and would have turned 130
# bytes into padding.  Keep the table packed instead.  It still fits wholly inside one
# page, so the three lookup sites bias the code by its low byte and retain a fast direct
# H:L read while recovering enough bank-32 space for the distinct `$88` art.
CORE_WIDTH_ORG = META_ORG + FONT_CODES * 2
CORE_CODES = 0x43                    # $00-$42 are contiguous English slots
assert (CORE_WIDTH_ORG & 0xFF) + CORE_CODES <= 0x100
SCAN_ORG = CORE_WIDTH_ORG + CORE_CODES
BANK_END = 0x8000


def _off(bank, addr):
    return bank * BANKSZ + (addr - BANKSZ)


def tile_addr(tile):
    """Address of one tile's 16-byte payload inside the three queue slots."""
    return QUEUE_PAYLOAD + 16 * tile + 2 * (tile >> 2)


class Patcher(object):
    def __init__(self, buf):
        self.buf = buf

    def expect(self, bank, addr, want, what):
        got = self.buf[_off(bank, addr)]
        if got != want:
            raise SystemExit('propvwf: %d:$%04X is $%02X, expected $%02X (%s)'
                             % (bank, addr, got, want, what))

    def imm8(self, bank, addr, op, old, new, what):
        self.expect(bank, addr, op, what)
        self.expect(bank, addr + 1, old, what)
        self.buf[_off(bank, addr) + 1] = new

    def blob(self, bank, addr, data):
        at = _off(bank, addr)
        self.buf[at:at + len(data)] = data


def metadata(font):
    slots = {code: slot for slot, code in enumerate(DOT_CODES)}
    out = bytearray()
    for code in range(FONT_CODES):
        out += bytes((slots.get(code, 0xFF), font.advance_code(code, unknown=8)))
    return bytes(out)


def native_table(buf):
    return bytes(buf[FONT_BASE:FONT_BASE + FONT_CODES * GLYPH_BYTES])


def preshift(font, buf):
    """Eight shifts of approved English glyphs plus declared native dialogue symbols."""
    code_to_char = {code: ch for ch, code in EN_CODES.items()}
    out = bytearray()
    for code in DOT_CODES:
        for shift in SHIFTS:
            if code in code_to_char:
                glyph = font.glyphs[code_to_char[code]]
                width = font.advance_code(code)
            else:
                at = FONT_BASE + code * GLYPH_BYTES
                glyph = bytes(buf[at:at + GLYPH_BYTES])
                width = 8
            # propblit skips the spill OR when shift + advance <= 8.  That is exact only
            # when no ink extends beyond the declared advance, so make it a build-time
            # property of every glyph admitted to the proportional table.
            spill_mask = (1 << (8 - width)) - 1 if width < 8 else 0
            if any(row & spill_mask for row in glyph):
                raise SystemExit('propvwf: code $%02X inks outside its %dpx advance'
                                 % (code, width))
            out += bytes(value >> shift for value in glyph)
            out += bytes(((value << (8 - shift)) & 0xFF) if shift else 0
                         for value in glyph)
    assert len(out) == DOT_SLOTS * DOT_GLYPH_STRIDE
    return bytes(out)


def width_table(font):
    # Eight pixels is the safe native fallback.  It preserves untranslated Japanese
    # tiles rather than making a proportional-font decision for glyphs we did not select.
    return bytes(font.advance_code(code, unknown=8) for code in range(FONT_CODES))


def unsupported_codes(data, bank):
    """Literal glyph codes a proportional composer line cannot render.

    Called on the uncompressed build input.  Control arguments and combining marks do
    not reach the glyph renderer, matching the scanner copied into bank 32.
    """
    allowed = set(DOT_CODES)
    arity = dict(codec.arity_for(bank))
    # The copied renderer scanner at 13:$4439 advances over one pause byte after $EB.
    # codec deliberately models insertion syntax instead, where that byte is written as
    # a raw token (`<mode1><$C8>`), so this renderer-facing check needs the measured arity.
    arity[0xEB] = 1
    bad = set()
    i = 0
    while i < len(data):
        code = data[i]
        if codec.CONTROL_MIN <= code <= codec.CONTROL_MAX:
            i += arity.get(code, 0)
        elif code not in codec.COMBINING and code not in allowed:
            bad.add(code)
        i += 1
    return bad


def renderer_codes(data, bank, limit=CHARS):
    """Glyph codes the copied scanner returns, excluding controls and their arguments."""
    arity = dict(codec.arity_for(bank))
    arity[0xEB] = 1
    out = []
    i = 0
    while i < len(data) and len(out) < limit:
        code = data[i]
        if codec.CONTROL_MIN <= code <= codec.CONTROL_MAX:
            i += arity.get(code, 0)
        elif code not in codec.COMBINING:
            out.append(code)
        i += 1
    return out


def fallback_point(data, bank, font):
    """First unsupported glyph as ``(ordinal, pen_px)``, or ``None`` within 30 glyphs."""
    pen = 0
    for ordinal, code in enumerate(renderer_codes(data, bank)):
        if code not in DOT_CODES:
            return ordinal, pen
        pen += font.advance_code(code, unknown=8)
    return None


def _cellmap_src():
    """Map the typewriter's character ordinal through the prepared reveal table."""
    return """
entry:  push bc
        push de
        push hl
        ld a,e
        and $%02X
        dec a
        cp $%02X
        jr c,nkeep
        ld a,$%02X
nkeep:  ld c,a
        cp $%02X
        jr nc,tail
        add a,$%02X
        ld l,a
        ld h,$%02X
        ld a,[hl]
        jr mapped
tail:   sub $%02X
        jr nz,tail1
        ld a,[$%04X]
        jr mapped
tail1:  ld a,[$%04X]
mapped:
        sub c
        ld l,a
        ld a,b
        add a,l
        ld b,a
        ld a,e
        add a,l
        ld e,a
        call $%04X
        pop hl
        pop de
        pop bc
        ret
""" % (COLUMN_MASK, CHARS, CHARS - 1, REVEAL_MAIN_COUNT,
       REVEAL_MAP & 0xFF, REVEAL_MAP >> 8, REVEAL_MAIN_COUNT,
       REVEAL_TAIL0, REVEAL_TAIL1, REVEAL_QUEUE)


def _carry_src():
    expand8 = '\n'.join('        ld a,[hl+]\n        ld [hl+],a'
                        for _ in range(0x08))
    return f"""
carry:
        ld hl,${DUMMY_TILE:04X}
{expand8}
        ld hl,${DUMMY_TILE:04X}
        ld de,${QUEUE_PAYLOAD:04X}
        ld b,$10
pfcopy:
        ld a,[hl+]
        ld [de],a
        inc de
        dec b
        jr nz,pfcopy
        ret
"""


def _renderer_src(scan_at):
    clear64 = '\n'.join('        ld [hl+],a' for _ in range(0x40))
    clear16 = '\n'.join('        ld [hl+],a' for _ in range(0x10))
    expand32 = '\n'.join('        ld a,[hl+]\n        ld [hl+],a'
                         for _ in range(0x20))
    expand8 = '\n'.join('        ld a,[hl+]\n        ld [hl+],a'
                        for _ in range(0x08))
    or_rows = '\n'.join('        ld a,[hl+]\n        ld c,a\n'
                        '        ld a,[de]\n        or c\n        ld [de],a\n'
                        '        inc de\n        inc de' for _ in range(0x08))
    payloads = ','.join('$%02X,$%02X' % (tile_addr(tile) & 0xFF,
                                          tile_addr(tile) >> 8)
                        for tile in range(CELLS // 2))
    return f"""
entry:  push bc
        push de
        push hl
        ld a,[$CF06]
        and $30
        cp $10
        jr nz,first
        ld a,$01
        ld [${S_HALF:04X}],a
        call zeroqueue
        rst $10
        db ${CARRY_INDEX:02X},${CARRY_BANK:02X}
        ld a,[${S_SRC:04X}]
        ld l,a
        ld a,[${S_SRC + 1:04X}]
        ld h,a
        ld a,[${S_MODE:04X}]
        and a
        jp z,nativeloopcheck
        jp loopcheck
first:  xor a
        ld [${S_HALF:04X}],a
        ld [${S_PEN:04X}],a
        ld [${S_COUNT:04X}],a
        call zeroall
        ld a,$01
        ld [${S_MODE:04X}],a
        ld hl,$CF07
        ld a,[${S_MODE:04X}]
        and a
        jp z,nativeloopcheck
        jp loopcheck

loopcheck:
        ld a,[${S_COUNT:04X}]
        cp ${CHARS:02X}
        jp nc,passdone
        ld a,[${S_PEN:04X}]
        ld b,a
        ld a,[${S_HALF:04X}]
        and a
        ld a,b
        jr z,localcheck
        sub ${HALF_PX:02X}
localcheck:
        cp ${HALF_PX:02X}
        jp nc,passdone

scan:   call nextglyph
        ld e,a
        push hl
        ld a,e
        cp ${CORE_CODES:02X}
        jr nc,sparsewidth
        ld [${S_INDEX:04X}],a
        add a,${CORE_WIDTH_ORG & 0xFF:02X}
        ld l,a
        ld h,${CORE_WIDTH_ORG >> 8:02X}
        ld a,[hl]
        jr widthdone
sparsewidth:
        ld a,e
        ld c,a
        ld b,$00
        sla c
        rl b
        ld hl,${META_ORG:04X}
        add hl,bc
        ld a,[hl+]
        cp $FF
        jr z,unknown
        ld [${S_INDEX:04X}],a
        ld a,[hl]
        jr widthdone
unknown:
        pop hl
        ld a,[${S_HALF:04X}]
        and a
        jp z,fallback
        xor a
        ld [${S_INDEX:04X}],a
        ld a,$08
        jr widthready
widthdone:
        pop hl
widthready:
        ld [${S_WIDTH:04X}],a
        push hl
        call place
        jr nc,nodraw
        call propblit
nodraw: pop hl
        ld a,[${S_WIDTH:04X}]
        ld b,a
        ld a,[${S_PEN:04X}]
        add a,b
        ld [${S_PEN:04X}],a
        ld a,[${S_COUNT:04X}]
        inc a
        ld [${S_COUNT:04X}],a
        jp loopcheck

nativeloopcheck:
        ld a,[${S_COUNT:04X}]
        cp ${CHARS:02X}
        jp nc,passdone
        ld a,[${S_PEN:04X}]
        ld b,a
        ld a,[${S_HALF:04X}]
        and a
        ld a,b
        jr z,nativelocal
        sub ${HALF_PX:02X}
nativelocal:
        cp ${HALF_PX:02X}
        jp nc,passdone
        call nextglyph
        ld [${S_CODE:04X}],a
        push hl
        ld a,$08
        ld [${S_WIDTH:04X}],a
        call place
        jr nc,nativenodraw
        call nativeblit
nativenodraw:
        pop hl
        ld a,[${S_PEN:04X}]
        add a,$08
        ld [${S_PEN:04X}],a
        ld a,[${S_COUNT:04X}]
        inc a
        ld [${S_COUNT:04X}],a
        jp nativeloopcheck

passdone:
        ld a,[${S_HALF:04X}]
        and a
        jr z,savesrc
        call buildmap
        jr nosavesrc
savesrc:
        ld a,l
        ld [${S_SRC:04X}],a
        ld a,h
        ld [${S_SRC + 1:04X}],a
nosavesrc:
        call expandqueue
done:
        pop hl
        pop de
        pop bc
        ret

fallback:
        xor a
        ld [${S_MODE:04X}],a
        ld [${S_PEN:04X}],a
        ld [${S_COUNT:04X}],a
        call zeroall
        ld hl,$CF07
        jp nativeloopcheck

nextglyph:
        ld a,[hl+]
        cp $79
        jr z,ngslow
        cp $7A
        jr z,ngslow
        cp $E0
        ret c
        cp $ED
        jr z,nglineend
        cp $EE
        jr z,nglineend
        cp $EF
        jr z,nglineend
ngslow:
        dec hl
        jp ${scan_at:04X}
nglineend:
        pop de
        jp passdone

buildmap:
        push bc
        push de
        push hl
        ld hl,$CF07
        ld b,$00
        ld c,$00
bmcheck:
        ld a,c
        cp ${CHARS:02X}
        jr nc,bmfill
        ld a,b
        cp ${LINE_PX:02X}
        jr nc,bmfill
        ld a,[hl]
        cp $ED
        jr z,bmfill
        cp $EE
        jr z,bmfill
        cp $EF
        jr z,bmfill
        call nextglyph
        push hl
        ld e,a
        ld a,[${S_MODE:04X}]
        and a
        jr z,bmnative
        ld a,e
        cp ${CORE_CODES:02X}
        jr nc,bmsparse
        add a,${CORE_WIDTH_ORG & 0xFF:02X}
        ld l,a
        ld h,${CORE_WIDTH_ORG >> 8:02X}
        ld a,[hl]
        jr bmwidth
bmsparse:
        ld d,$00
        sla e
        rl d
        ld hl,${META_ORG:04X}
        add hl,de
        inc hl
        ld a,[hl]
        jr bmwidth
bmnative:
        ld a,$08
bmwidth:
        ld [${S_WIDTH:04X}],a
        dec a
        add a,b
        srl a
        srl a
        srl a
        cp ${CELLS:02X}
        jr c,bmkeep
        ld a,${CELLS - 1:02X}
bmkeep:
        ld e,a
        call bmstore
        pop hl
        ld a,[${S_WIDTH:04X}]
        add a,b
        ld b,a
        inc c
        jr bmcheck
bmfill:
        ld a,c
        cp ${CHARS:02X}
        jr nc,bmdone
        ld e,${CELLS - 1:02X}
bmfillloop:
        call bmstore
        inc c
        ld a,c
        cp ${CHARS:02X}
        jr c,bmfillloop
bmdone:
        pop hl
        pop de
        pop bc
        ret

; Store reveal cell E for ordinal C.  The last two entries use measured-safe scratch;
; a contiguous 30-byte run would overwrite live game state at $C0FE/$C0FF.
bmstore:
        ld a,c
        cp ${REVEAL_MAIN_COUNT:02X}
        jr nc,bmstoretail
        add a,${REVEAL_MAP & 0xFF:02X}
        ld l,a
        ld h,${REVEAL_MAP >> 8:02X}
        ld a,e
        ld [hl],a
        ret
bmstoretail:
        sub ${REVEAL_MAIN_COUNT:02X}
        jr nz,bmstoretail1
        ld a,e
        ld [${REVEAL_TAIL0:04X}],a
        ret
bmstoretail1:
        ld a,e
        ld [${REVEAL_TAIL1:04X}],a
        ret

place:  ld a,[${S_PEN:04X}]
        ld b,a
        ld a,[${S_HALF:04X}]
        and a
        ld a,b
        jr z,normal
        sub ${HALF_PX:02X}
normal: ld [${S_LOCAL:04X}],a
        and $07
        ld [${S_SHIFT:04X}],a
        ld a,[${S_LOCAL:04X}]
        srl a
        srl a
        srl a
        ld [${S_TILE:04X}],a
        call payload
        ld a,e
        ld [${S_DST0:04X}],a
        ld a,d
        ld [${S_DST0 + 1:04X}],a
        ld a,[${S_TILE:04X}]
        inc a
        cp $09
        jr nc,nospill
        call payload
        ld a,e
        ld [${S_DST1:04X}],a
        ld a,d
        ld [${S_DST1 + 1:04X}],a
        scf
        ret
nospill:
        ld a,${DUMMY_TILE & 0xFF:02X}
        ld [${S_DST1:04X}],a
        ld a,${DUMMY_TILE >> 8:02X}
        ld [${S_DST1 + 1:04X}],a
        scf
        ret

payload:
        add a,a
        ld l,a
        ld h,$00
        ld bc,payloadtab
        add hl,bc
        ld a,[hl+]
        ld e,a
        ld d,[hl]
        ret

propblit:
        ld a,[${S_INDEX:04X}]
        srl a
        ld h,a
        ld l,$00
        jr nc,sloteven
        ld l,$80
sloteven:
        ld a,[${S_SHIFT:04X}]
        swap a
        add a,l
        ld l,a
        jr nc,slotready
        inc h
slotready:
        ld bc,${GLYPH_ORG:04X}
        add hl,bc
        ld a,[${S_DST0:04X}]
        ld e,a
        ld a,[${S_DST0 + 1:04X}]
        ld d,a
        call orblock
        ld a,[${S_SHIFT:04X}]
        ld b,a
        ld a,[${S_WIDTH:04X}]
        add a,b
        cp $09
        ret c
        ld a,[${S_DST1:04X}]
        ld e,a
        ld a,[${S_DST1 + 1:04X}]
        ld d,a
        call orblock
        ret

nativeblit:
        ld a,[${S_CODE:04X}]
        ld l,a
        ld h,$00
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,${NATIVE_ORG:04X}
        add hl,bc
        ld a,[${S_DST0:04X}]
        ld e,a
        ld a,[${S_DST0 + 1:04X}]
        ld d,a
        call orblock
        ret

orblock:
{or_rows}
        ret

expandqueue:
        ld hl,${ZERO_RUNS[0][0]:04X}
{expand32}
        ld hl,${ZERO_RUNS[1][0]:04X}
{expand32}
        ld hl,${ZERO_RUNS[2][0]:04X}
{expand8}
        ret

zeroall:
        call zeroqueue
        ld hl,${DUMMY_TILE:04X}
        xor a
{clear16}
        ret

zeroqueue:
        ld hl,${ZERO_RUNS[0][0]:04X}
        xor a
{clear64}
        ld hl,${ZERO_RUNS[1][0]:04X}
{clear64}
        ld hl,${ZERO_RUNS[2][0]:04X}
{clear16}
        ret

payloadtab:
        db {payloads}
"""


def _scanner(buf):
    at = _off(13, SCANNER_AT)
    scanner = bytes(buf[at:at + SCANNER_END - SCANNER_AT])
    if scanner != OLD_SCANNER:
        raise SystemExit('propvwf: scanner changed at 13:$%04X; the proportional fast '
                         'literal path must be re-audited' % SCANNER_AT)
    addr = SCANNER_AT
    while addr < SCANNER_END:
        _, size = gbasm.gbdis.decode(buf, _off(13, addr), addr)
        op = buf[_off(13, addr)]
        if size == 3 and op in (0xC3, 0xCD, 0xC2, 0xCA, 0x21, 0x11, 0x01,
                               0xFA, 0xEA):
            raise SystemExit('propvwf: scanner has an absolute address at 13:$%04X'
                             % addr)
        addr += size
    return scanner


def install(buf, font=None, notes=None):
    """Install the proportional composer into an approved-font-patched 1 MiB ROM."""
    font = font or dotfont.load_approved()
    p = Patcher(buf)

    for ch, code in EN_CODES.items():
        at = FONT_BASE + code * GLYPH_BYTES
        if bytes(buf[at:at + GLYPH_BYTES]) != font.glyphs[ch]:
            raise SystemExit('propvwf: ROM glyph %r is not the approved %s data; '
                             'apply dotfont.patch first' % (ch, font.name))

    scanner = _scanner(buf)
    scan_tail = bytes((0xC1, 0xC9))             # pop bc / ret, code remains in a
    carry_code, carry_labels = gbasm.assemble(_carry_src(), CARRY_ORG)
    if CARRY_ORG + len(carry_code) > CARRY_LIMIT:
        raise SystemExit('propvwf: bank-%d carry helper needs %d bytes, only %d available'
                         % (CARRY_BANK, len(carry_code), CARRY_LIMIT - CARRY_ORG))
    carry_bank = _off(CARRY_BANK, 0x4000)
    if buf[carry_bank] != CARRY_BANK:
        raise SystemExit('propvwf: pool bank %d is not installed' % CARRY_BANK)
    carry_off = _off(CARRY_BANK, CARRY_ORG)
    if any(value != 0xFF for value in buf[carry_off:carry_off + len(carry_code)]):
        raise SystemExit('propvwf: bank %d carry region at $%04X is not free'
                         % (CARRY_BANK, CARRY_ORG))
    at = _off(CARRY_BANK, 0x4000) + CARRY_INDEX - 1
    if bytes(buf[at:at + 2]) != b'\xff\xff':
        raise SystemExit('propvwf: far index $%02X in bank %d is already used'
                         % (CARRY_INDEX, CARRY_BANK))
    buf[at] = carry_labels['carry'] & 0xFF
    buf[at + 1] = carry_labels['carry'] >> 8
    p.blob(CARRY_BANK, CARRY_ORG, carry_code)

    render_at = SCAN_ORG + len(scanner) + len(scan_tail)
    code, labels = gbasm.assemble(_renderer_src(SCAN_ORG), render_at)
    glyphs = preshift(font, buf)
    native = native_table(buf)
    meta = metadata(font)
    core_widths = bytes(font.advance_code(code) for code in range(CORE_CODES))
    pad = b'\xff' * (CORE_WIDTH_ORG - (META_ORG + len(meta)))
    blob = glyphs + native + meta + pad + core_widths + scanner + scan_tail + code
    if DATA_ORG + len(blob) > BANK_END:
        raise SystemExit('propvwf: bank %d overflow (%d bytes from $%04X)'
                         % (FAR_BANK, len(blob), DATA_ORG))
    at = _off(FAR_BANK, DATA_ORG)
    if any(value != 0xFF for value in buf[at:at + len(blob)]):
        raise SystemExit('propvwf: bank %d is not free at $%04X' % (FAR_BANK, DATA_ORG))
    p.blob(FAR_BANK, DATA_ORG, blob)

    index = _off(FAR_BANK, 0x4000) + FAR_INDEX - 1
    if buf[index:index + 2] != b'\xff\xff':
        raise SystemExit('propvwf: far index $%02X in bank %d is already used'
                         % (FAR_INDEX, FAR_BANK))
    buf[index] = labels['entry'] & 0xFF
    buf[index + 1] = labels['entry'] >> 8

    p.expect(13, RENDER_AT, 0xC5, 'renderer push bc')
    p.expect(13, RENDER_AT + 1, 0xD5, 'renderer push de')
    p.expect(13, RENDER_AT + 2, 0xE5, 'renderer push hl')
    p.expect(13, RENDER_AT + 3, 0x11, 'old renderer body')
    stub = bytes((0xC5, 0xD5, 0xE5, 0xD7, FAR_INDEX, FAR_BANK,
                  0xC3, RENDER_TAIL & 0xFF, RENDER_TAIL >> 8))
    p.blob(13, RENDER_AT, stub + b'\xff' * (RENDER_LIMIT - RENDER_AT - len(stub)))
    p.imm8(13, COMPOSER_BUDGET, 0x06, OLD_LINE_CHARS, CHARS,
           'composer character budget')

    old = _off(13, 0x4464)
    if bytes(buf[old:old + len(OLD_BLITTER)]) != OLD_BLITTER:
        raise SystemExit('propvwf: dead one-tile blitter changed at 13:$4464')
    cellmap, _ = gbasm.assemble(_cellmap_src(), CELLMAP_AT)
    if CELLMAP_AT + len(cellmap) > CELLMAP_END:
        raise SystemExit('propvwf: reveal map code needs %d bytes, only %d available'
                         % (len(cellmap), CELLMAP_END - CELLMAP_AT))
    p.blob(13, CELLMAP_AT,
           cellmap + b'\xff' * (CELLMAP_END - CELLMAP_AT - len(cellmap)))
    p.expect(13, REVEAL_CALL, 0xCD, 'typewriter reveal call')
    p.expect(13, REVEAL_CALL + 1, REVEAL_QUEUE & 0xFF, 'typewriter target low')
    p.expect(13, REVEAL_CALL + 2, REVEAL_QUEUE >> 8, 'typewriter target high')
    p.blob(13, REVEAL_CALL, bytes((0xCD, CELLMAP_AT & 0xFF, CELLMAP_AT >> 8)))

    out = [
        'propvwf: %s proportional composer; 30 staged characters, '
        '144px clipped line' % font.name,
        'propvwf: %d-byte 8-shift font table + %d-byte native fallback + %d-byte '
        'metadata + %d-byte core-width page + %d-byte code blob at %d:$%04X; '
        '%d bytes left' %
        (len(glyphs), len(native), len(meta), len(core_widths),
         len(blob) - len(glyphs) - len(native) - len(meta) - len(core_widths),
         FAR_BANK, DATA_ORG, BANK_END - DATA_ORG - len(blob)),
        'propvwf: typewriter reveal map $%04X-$%04X + $%04X/$%04X (%d entries)'
        % (REVEAL_MAP, REVEAL_MAP_END - 1, REVEAL_TAIL0, REVEAL_TAIL1, CHARS),
        'propvwf: %d-byte carry helper at %d:$%04X'
        % (len(carry_code), CARRY_BANK, CARRY_ORG),
        'propvwf: reveal map prepared at the end of the second composition pass',
    ]
    if notes is not None:
        notes.extend(out)
    return labels


def _model(buf, widths, codes):
    rows = [bytearray(CELLS) for _ in range(8)]
    reveal = []
    pen = 0
    proportional = all(code in DOT_CODES for code in codes)
    for code in codes:
        width = widths[code] if proportional else 8
        reveal.append(min((pen + width - 1) >> 3, CELLS - 1))
        glyph = buf[FONT_BASE + code * GLYPH_BYTES:
                    FONT_BASE + (code + 1) * GLYPH_BYTES]
        for y, bits in enumerate(glyph):
            for x in range(8):
                px = pen + x
                if px < LINE_PX and bits & (0x80 >> x):
                    rows[y][px >> 3] |= 0x80 >> (px & 7)
        pen += width
    tiles = []
    for tile in range(CELLS):
        data = bytearray()
        for y in range(8):
            data += bytes((rows[y][tile], rows[y][tile]))
        tiles.append(bytes(data))
    return tiles, reveal


def _queue_tiles(cpu):
    return [bytes(cpu.ram[tile_addr(tile) - 0x8000:
                          tile_addr(tile) - 0x8000 + 16]) for tile in range(CELLS // 2)]


def _read_reveal(cpu):
    main = cpu.ram[REVEAL_MAP - 0x8000:REVEAL_MAP_END - 0x8000]
    tail = (cpu.ram[address - 0x8000] for address in REVEAL_TAIL)
    return bytes(main) + bytes(tail)


def _write_reveal(cpu, values):
    assert len(values) == CHARS
    start = REVEAL_MAP - 0x8000
    cpu.ram[start:start + REVEAL_MAIN_COUNT] = bytes(values[:REVEAL_MAIN_COUNT])
    for address, value in zip(REVEAL_TAIL, values[REVEAL_MAIN_COUNT:]):
        cpu.ram[address - 0x8000] = value


def _run_line(bank, carry_bank, render_at, codes):
    import gbemu

    cpu = gbemu.Cpu({0: bytes(BANKSZ), FAR_BANK: bank,
                     CARRY_BANK: carry_bank}, bank=FAR_BANK)
    src = 0xCF07 - 0x8000
    cpu.ram[src:src + CHARS] = bytes(codes)
    cpu.ram[0xCF06 - 0x8000] = 0x20
    cpu.call(render_at, limit=2000000)
    first = _queue_tiles(cpu)
    cpu.ram[0xCF06 - 0x8000] = 0x10
    cpu.call(render_at, limit=2000000)
    reveal = _read_reveal(cpu)
    return first + _queue_tiles(cpu), reveal, cpu.steps


def selftest():
    base_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                             'build', '_base_expanded.gb')
    base = bytearray(open(base_path, 'rb').read())
    font = dotfont.load_approved()
    base[:] = font.patch(base)
    # Production gets this header and reader reservation from pool.install().  The unit
    # ROM deliberately isolates propvwf, so provide the one ownership marker it asserts.
    base[CARRY_BANK * BANKSZ] = CARRY_BANK
    labels = install(base, font)
    bank = bytes(base[FAR_BANK * BANKSZ:(FAR_BANK + 1) * BANKSZ])
    carry_bank = bytes(base[CARRY_BANK * BANKSZ:(CARRY_BANK + 1) * BANKSZ])
    widths = width_table(font)

    def codes_for(text):
        values = [EN_CODES[ch] for ch in text]
        if len(values) > CHARS:
            raise AssertionError(text)
        return values + [EN_CODES[' ']] * (CHARS - len(values))

    tests = [
        codes_for('Weakening Pot[12]'),
        codes_for('Remove/Toss/Drop/Info'),
        # Exact hostile suffix edge: the compact four-column 7 makes the final painted
        # pixel x=143 even though the trailing pen lands at 145px.
        codes_for('Stepped on True Rapier-77'),
        codes_for('WWW iii...'),
        codes_for('Tagura: Mister, where'),
        list(range(CHARS)),
        [0x81] + [EN_CODES[' ']] * (CHARS - 1),
        list(range(0x43, 0x43 + CHARS)),
    ]

    # Exercise every approved glyph at every attainable shift, especially as it crosses
    # the 72px queue boundary.  A tiny exact-width search constructs prefixes ending at
    # pixels 64..71; the renderer result is compared plane-for-plane with Python.
    chars = sorted(EN_CODES)
    paths = {0: ''}
    for target in range(1, HALF_PX):
        candidates = [(paths[target - font.advances[ch]] + ch)
                      for ch in chars if target - font.advances[ch] in paths]
        if candidates:
            paths[target] = min(candidates, key=lambda value: (len(value), value))
    for target in range(HALF_PX - 8, HALF_PX):
        if target not in paths:
            continue
        for ch in chars:
            if len(paths[target]) + 1 <= CHARS:
                tests.append(codes_for(paths[target] + ch))

    # Exhaust the actual admitted renderer alphabet, including native `$81`, the two
    # distinct equipment stars `$88`/`$8A`, and every punctuation slot, at every shift
    # residue as it crosses the 72px half-line boundary.  The earlier loop covered only
    # EN_CODES and therefore could not catch a missing native-status slot.
    space = EN_CODES[' ']
    for shift in range(8):
        prefix = paths[HALF_PX - 8 + shift]
        prefix_codes = [EN_CODES[ch] for ch in prefix]
        for code in DOT_CODES:
            values = prefix_codes + [code]
            tests.append(values + [space] * (CHARS - len(values)))

    checks = steps = 0
    for codes in tests:
        got, reveal, used = _run_line(bank, carry_bank, labels['entry'], codes)
        want, want_reveal = _model(base, widths, codes)
        assert got == want, ('tile mismatch', codes)
        assert reveal == bytes(want_reveal), ('reveal mismatch', codes,
                                               reveal, want_reveal)
        checks += len(got) + len(reveal)
        steps += used

    # $ED/$EE/$EF terminate the staged line. The original fixed renderer scanned past
    # them and drew zero-filled padding as spaces; the queue is already blank, so the
    # proportional path exits there to keep short end-of-message lines inside the same CPU slot.
    visible = [EN_CODES[ch] for ch in ' the shrine...']
    ended = visible + [0xED, 0xEE] + [EN_CODES[' ']] * (CHARS - len(visible) - 2)
    got, reveal, used = _run_line(bank, carry_bank, labels['entry'], ended)
    want, want_reveal = _model(base, widths, visible)
    want_reveal += [CELLS - 1] * (CHARS - len(want_reveal))
    assert got == want, ('line-end tile mismatch', ended)
    assert reveal == bytes(want_reveal), ('line-end reveal mismatch', reveal, want_reveal)
    checks += len(got) + len(reveal)
    steps += used

    # Run the assembled typewriter map itself for every character and verify both values
    # handed to the game's one-cell queue, while the caller's counters return untouched.
    import gbemu
    cellcode, _ = gbasm.assemble(_cellmap_src(), CELLMAP_AT)
    queue_stub, _ = gbasm.assemble(
        'ld a,e\nld [$C000],a\nld a,d\nld [$C001],a\n'
        'ld a,b\nld [$C002],a\nret', REVEAL_QUEUE)
    b13 = bytearray(BANKSZ)
    b13[CELLMAP_AT - BANKSZ:CELLMAP_AT - BANKSZ + len(cellcode)] = cellcode
    b13[REVEAL_QUEUE - BANKSZ:REVEAL_QUEUE - BANKSZ + len(queue_stub)] = queue_stub
    sample = codes_for('Weakening Pot[12]')
    _, wanted = _model(base, widths, sample)
    for n, cell in enumerate(wanted):
        cpu = gbemu.Cpu({0: bytes(BANKSZ), 13: bytes(b13)}, bank=13)
        _write_reveal(cpu, wanted)
        cpu.b, cpu.c = 0xA8 + n, 0x5A
        cpu.de = 0x9C41 + n
        cpu.call(CELLMAP_AT)
        dst = cpu.ram[0xC000 - 0x8000] | (cpu.ram[0xC001 - 0x8000] << 8)
        assert dst == 0x9C41 + cell, (n, cell, hex(dst))
        assert cpu.ram[0xC002 - 0x8000] == 0xA8 + cell, (n, cell)
        assert (cpu.b, cpu.c, cpu.de) == (0xA8 + n, 0x5A, 0x9C41 + n)
        checks += 3

    print('propvwf --selftest: %d line cases, %d checks OK; %d interpreted steps'
          % (len(tests) + 1, checks, steps))


def main():
    if '--selftest' in sys.argv:
        gbasm.selftest()
        selftest()
        return
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    font = dotfont.load_approved()
    rom = bytearray(font.patch(open(sys.argv[1], 'rb').read()))
    notes = []
    install(rom, font, notes)
    open(sys.argv[2], 'wb').write(rom)
    for note in notes:
        print(' ', note)
    print('wrote', sys.argv[2])


if __name__ == '__main__':
    main()
