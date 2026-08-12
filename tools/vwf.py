#!/usr/bin/env python3
"""A variable-width font for the composer: 18 characters a line become 24.

WHAT THIS IS, AND WHAT IT IS NOT. The font is drawn 5px wide inside an 8px cell, so the
whole of the gain here is dropping the three dead columns: the pen advances **6px, the
same for every glyph**. That is not a proportional font -- `i` gets the same 6px as `M` --
and it is a deliberate choice, not a shortcut. A per-glyph width table buys ONE more
character a line (25 against 24, mean advance 5.73px) and costs three things a uniform
pen keeps:

  * 72 divides by both 6 and 8. A line is drawn in two halves of 9 tiles, and 9 tiles is
    72px; at a uniform 6px that boundary lands on a glyph edge AND a tile edge, so the
    second half starts clean and `13:$439F` stays a plain "skip 9 characters" (now 12).
    With variable widths the second half starts mid-glyph and has to be handed a pen.
  * The cell budget at `13:$40D6` stays a CHARACTER count, so `dte_emit` needs no change
    at all. The DTE collision `HANDOFF_VWF.md` describes -- if `b` becomes pixels the
    expander has to charge pixels too, from a table it cannot reach -- is closed, not
    solved.
  * The `$CF38` line-buffer bound still holds: 24 characters against 49 bytes.

HOW THE COMPOSER DRAWS A LINE, measured 2026-08-03 by tracing a village dialogue. This is
the part it is worth not re-deriving; the full trace is in `HANDOFF_VWF.md`.

  `$C006` is a VRAM transfer queue -- `dw destination` then a payload -- consumed by two
  stack-pointer blitters in bank 0 that disagree about the payload size (`0:$10A0` reads
  22-byte slots and pushes tilemap rows, `0:$11C5` reads 66-byte slots and pushes tile
  data; 3 x 22 = 66, which is why the slot bases agree). `$C0CC` is referenced nowhere,
  so the queue is exactly three 66-byte slots = 12 tiles.

  A line owns 18 consecutive VRAM tiles at `$8A80` / `$8BA0` / `$8CC0` (table `13:$4412`,
  picked by `[$CF06] & 3`) and the tilemap row is 18 counting indices (`13:$4523`). 18
  tiles is 288 bytes and the queue holds 192, so the line is drawn in TWO HALVES of nine:
  `13:$43B8` fills the three payloads 4 + 4 + 1 and `13:$43E2` adds `$90` -- nine tiles --
  to the destination for the second half.

  ~~**The tilemap side therefore needs no change whatever.** A line owns 18 tiles however
  they are filled.~~ **WRONG, and it shipped the column-19 spill** -- see THE TYPEWRITER
  below. It is true of every routine that writes a whole row, and there are five of them
  (`13:$4523`'s callers), all of which do write a fixed 18. It is false of the SIXTH
  writer, which puts one cell on screen per frame as the text types and had to be found
  by watching VRAM rather than by reading the row drawers.

THE TYPEWRITER REVEALS ONE CELL A FRAME, AND IT COUNTED CHARACTERS. `13:$6ABC` walks the
composed line with the tile index in `b` and the tilemap address in `de`, queues a
one-cell write through `13:$6B85` (`[$C000]` = destination, `[$C002]` = tile), and then
does `inc b` / `inc de`. At a fixed-width pen character N *is* tile N and that is exactly
right. At a 6px pen character N lives in tile `(PEN * N) >> 3`, so past character 17 the
unmapped version walks off the end of an 18-tile row: entry 19 is the next line's first
tile, drawn at column 19, which is on screen at `WX = 7`. Joey found it in play on
2026-08-05, on `Tagura: Mister, where` with a fragment of ` did` hanging off the right.

`install` therefore maps the pair on its way to the queue, into the bytes the scanner and
the one-tile blitter leave dead once their last caller is gone. **`b` and `de` go on
counting CHARACTERS**: the dakuten overlay reads `de - 33`, the cell above the *previous*
character, and a `de` that counted cells would move that mark for Japanese lines that
render correctly today. So nothing in the loop changes except the two numbers handed to
the queue, and `tools/boxspill.py` is the check that says so.

The tile to reveal is the one the character ENDS in, not the one it starts in, and the
map clamps -- `cell_of` and `_cellmap_src` say why, and both answers cost a real bug if
taken the other way.

THE RENDERER IS PRE-SHIFTED, WHICH IS WHY IT IS SHORT. Shifting a glyph by the pen at
runtime needs a 16-bit rotate loop and one more register than the LR35902 has spare here,
so the four shifts a 6px pen ever produces (0, 2, 4, 6) are baked into the ROM instead:
`FONT_CODES` codes x 4 shifts x 16 bytes, each entry being 8 "this tile" bytes followed by
8 "spilled into the next tile" bytes. The inner loop is then an unrolled OR-copy with no
arithmetic in it at all, and the spill pass is the SAME routine called a second time --
for shifts 0 and 2 the spill bytes are all zero, so it runs unconditionally and writes
back what it read.

WHY THE GLYPHS COME OFF THE STACK BACKWARDS. Twelve codes have to be collected before any
can be drawn (the scanner walks the source and only it knows where the control codes are),
and there is no free WRAM to collect them into -- `$CF38` must stay zero because the
composer reads it as end-of-line, and `$C0CC` upward is live. So pass 1 pushes the codes
and pass 2 pops them, which hands them back in reverse; the glyphs are independent, so
the pen table is simply generated in reverse to match.

THE SCANNER IS COPIED, NOT REWRITTEN. `13:$4418` decides how many bytes each control code
eats, and this project has already been bitten once by a second copy of that knowledge
(`codec.ARITY` against the two dispatch tables). So the bytes are copied verbatim out of
the ROM at build time and asserted first -- the block is position-independent (`jr` only)
and if bank 13's scanner ever changes, the copy changes with it or the build fails.

usage: vwf.py <rom> [--selftest]
"""
import os
import sys
from math import gcd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbasm
from latinfont import EN_CODES, FONT_BASE, GLYPH_BYTES, ink_columns

BANKSZ = 0x4000

# ---------------------------------------------------------------------- the geometry
PEN = 6                     # pixels per character, every character
CELLS = 18                  # tiles a line owns -- unchanged, this is VRAM geometry
CHARS = CELLS * 8 // PEN    # 24 characters a line
HALF = CHARS // 2           # 12 -- the half-line the queue can hold in one go

OLD_LINE_CHARS = 0x12       # `13:$40D6 ld b,$12`
OLD_HALF_CHARS = 0x09       # `13:$43A3` and `13:$6BE6`

# The queue: three slots of `dw dest` + 64-byte payload, so tile t of the nine lives at
# $C008 + 16t + 2*(t >> 2) -- the +2 steps over each slot's own destination field.
QUEUE = 0xC006
def tile_addr(t):
    return 0xC008 + 16 * t + 2 * (t >> 2)


ZERO_RUNS = ((0xC008, 0x40), (0xC04A, 0x40), (0xC08C, 0x10))

# ---------------------------------------------------------------------- bank 13 sites
COMPOSER_BUDGET = 0x40D6            # ld b,$12  -- characters into the line buffer
HALF_SKIP = (0x43A3, 0x6BE6)        # ld b,$09  -- advance the source to the second half
RENDER_AT = 0x43B8                  # the glyph renderer's entry
RENDER_TAIL = 0x43D0                # where the destination computation begins
RENDER_LIMIT = RENDER_TAIL          # everything between is ours to replace
SCANNER_AT = 0x4418                 # "next glyph code" -- copied, see the docstring
SCANNER_END = 0x4464                # where it falls into the old one-tile blitter

# The typewriter, and the bytes the scanner and the one-tile blitter leave behind once
# the far-call stub at RENDER_AT has taken their last caller away. CELLMAP_AT is inside
# bank 13, so the reveal's `call` is repointed at it without spending a far call --
# but only AFTER `install` has copied the scanner out to FAR_BANK, which it does first.
REVEAL_CALL = 0x6B5B                # the `call $6B85` inside 13:$6B59
REVEAL_QUEUE = 0x6B85               # queues [$C000] = de, [$C002] = b
CELLMAP_AT = SCANNER_AT
CELLMAP_END = 0x4484
COLUMN_MASK = 0x1F                  # $9C40/$9C80/$9CC0: the column is de's low five bits

# The dead one-tile blitter, asserted whole. It is 32 bytes of code nothing calls any
# more, and asserting all of it is what proves nothing else has claimed the space.
OLD_BLITTER = bytes.fromhex('06 00 cb 21 cb 10 cb 21 cb 10 cb 21 cb 10 e5 21 80 76'
                            '09 06 08 2a 12 13 12 13 05 20 f8 e1 c1 c9')

# ---------------------------------------------------------------------- bank 32
FAR_BANK = 0x20             # the DTE table's bank: table $4100-$42FF, name6 at $4300
FAR_INDEX = 0x05            # entry ($4004,$4005); name6 holds $03
DATA_ORG = 0x4400           # the pre-shifted font
FONT_CODES = 0xB3           # codes $00-$B2 -- the whole English page, punctuation included
SHIFTS = (0, 2, 4, 6)
SHIFT_STRIDE = FONT_CODES * 16
CODE_ORG = DATA_ORG + SHIFT_STRIDE * len(SHIFTS)
BANK_END = 0x8000


def _off(bank, addr):
    return bank * BANKSZ + (addr - BANKSZ)


class Patcher(object):
    """Every write asserts the byte it replaces, so a moved address fails the build."""

    def __init__(self, buf):
        self.buf = buf
        self.n = 0

    def _expect(self, bank, addr, want, what):
        got = self.buf[_off(bank, addr)]
        if got != want:
            raise SystemExit('vwf: %d:$%04X is $%02X, expected $%02X (%s)'
                             % (bank, addr, got, want, what))

    def imm8(self, bank, addr, op, old, new, what):
        self._expect(bank, addr, op, what)
        self._expect(bank, addr + 1, old, what)
        self.buf[_off(bank, addr) + 1] = new
        self.n += 1

    def blob(self, bank, addr, data):
        o = _off(bank, addr)
        self.buf[o:o + len(data)] = data
        self.n += 1


# ------------------------------------------------------------------ the pre-shifted font
def preshift(rom):
    """-> bytes: FONT_CODES codes x 4 shifts x (8 'this tile' + 8 'next tile') bytes.

    Column c of a glyph is bit 7-c, so shifting the pen right by s moves column c to
    column c+s; whatever passes column 7 is the spill, which is `v << (8 - s)`.
    """
    out = bytearray()
    for s in SHIFTS:
        for code in range(FONT_CODES):
            g = rom[FONT_BASE + code * GLYPH_BYTES:FONT_BASE + (code + 1) * GLYPH_BYTES]
            out += bytes((b >> s) & 0xFF for b in g)
            out += bytes((b << (8 - s)) & 0xFF if s else 0 for b in g)
    assert len(out) == SHIFT_STRIDE * len(SHIFTS)
    return bytes(out)


def pentable():
    """-> bytes: 12 entries of `dw fontbase, dw dst0, dw dst1`, LAST GLYPH FIRST.

    Reversed because pass 2 pops the codes off the stack, which hands them back in the
    order they were pushed reversed. Glyphs are independent, so the order is free.
    """
    rows = []
    for i in range(HALF):
        pen = i * PEN
        tile, shift = pen >> 3, pen & 7
        base = DATA_ORG + SHIFTS.index(shift) * SHIFT_STRIDE
        dst0 = tile_addr(tile)
        # The last glyph of a half sits at shift 2, whose spill bytes are all zero, so
        # aiming its spill back at its own tile is a write of the value already there.
        dst1 = tile_addr(tile + 1) if tile + 1 < CELLS // 2 else dst0
        if dst1 == dst0:
            assert shift in (0, 2), 'glyph %d spills but has nowhere to spill to' % i
        rows.append((base, dst0, dst1))
    out = bytearray()
    for base, dst0, dst1 in reversed(rows):
        for v in (base, dst0, dst1):
            out += bytes((v & 0xFF, v >> 8))
    return bytes(out)


def cell_of(n):
    """-> the tile character `n` ENDS in: the last one it puts ink in.

    **The tile it STARTS in is the wrong answer and looks like a different bug.** It is
    `(PEN * n) >> 3`, it is what the arithmetic reaches for first, and because a 6px
    character straddles two tiles three times in four it leaves the tail of the last
    character on a line permanently unrevealed -- `...Are You all` typed out as
    `...Are You al`. Truncation is not an improvement on the spill. So the reveal has to
    cover every tile the character inks, and the last of those is this.

    The cost is that where a character ends a tile, the next character shares that tile
    and comes up with it -- the typewriter runs a character ahead once every four and
    then holds for a frame. The rate is unchanged (one character a frame either way) and
    it is the only choice that both finishes the line and never leaves the row.
    """
    return (PEN * n + PEN - 1) >> 3


def _cell_src():
    """-> the instructions turning `a` = character index into `a` = `cell_of(a)`.

    `(PEN * n + PEN - 1) >> 3` reduced by `gcd(PEN, 8)` so the multiply stays inside a
    byte: at a 6px pen it is `(3n + 2) >> 2`, where 3 x 23 + 2 is 71 and the unreduced
    6 x 23 + 5 would be 143, one doubling from wrapping. The reduction is asserted
    against the honest formula below rather than argued for. `l` is the scratch; `h` is
    not, because the caller is holding the character index there.
    """
    g = gcd(PEN, 8)
    num, shift, bias = PEN // g, (8 // g).bit_length() - 1, (PEN - 1) // g
    for n in range(CHARS):
        if (num * n + bias) >> shift != cell_of(n):
            raise SystemExit('vwf: the reduced cell formula ((%d*n+%d)>>%d) disagrees '
                             'with (%d*n+%d)>>3 at n=%d -- a %dpx pen needs its own'
                             % (num, bias, shift, PEN, PEN - 1, n, PEN))
    chains = {1: [], 3: ['ld l,a', 'add a,a', 'add a,l'],
              5: ['ld l,a', 'add a,a', 'add a,a', 'add a,l'],
              7: ['ld l,a', 'add a,a', 'add a,a', 'add a,a', 'sub l']}
    if num not in chains:
        raise SystemExit('vwf: no multiply chain for a %dpx pen (x%d); add one to '
                         '_cell_src' % (PEN, num))
    return chains[num] + (['add a,$%02X' % bias] if bias else []) + ['srl a'] * shift


def _cellmap_src():
    """The typewriter's per-character reveal, mapped to the cell the character is in.

    Entered in place of `call $6B85` with `b` = the tile index the caller is counting and
    `de` = the tilemap address it is counting alongside it. The character's ordinal comes
    out of `de` itself -- the three row addresses are `$9C40` / `$9C80` / `$9CC0` and the
    first character goes in column 1, so N is `(e & $1F) - 1` and no state has to be kept
    anywhere. `cell - N` is then added to both, which is a subtraction: it is never
    positive, and over 24 characters it bottoms out at -6.

    IT CLAMPS, and that is not belt and braces. **The composer this typewriter belongs to
    has no cell budget at all** -- `13:$687B` copies until `$FF` and the only bound is
    dte_rom's byte guard at `$CF38`, 49 bytes -- so nothing in the ROM stops a line at 24
    the way `13:$40D6 ld b,$18` stops the other composer's. A line over 24 characters has
    no pixels past the 24th either way (the renderer draws two halves of twelve and
    stops), but unclamped it would go on writing tilemap entries, which is the spill
    again. Clamped, the worst case repeats the last cell. `dialogue_preview --check` is
    still what keeps lines at 24; this is what makes `boxspill.py`'s invariant a property
    of the ROM rather than of the script that happens to be in it.

    Past 30 characters `de` has itself left the row and `and $1F` wraps, so the mapping
    is meaningless -- but so is everything else about that line, and the byte guard is
    the thing that bounds it.
    """
    return '\n'.join(
        ['push bc', 'push de', 'push hl',
         'ld a,e', 'and $%02X' % COLUMN_MASK, 'dec a',       # a = N
         'ld h,a']
        + _cell_src()                                        # a = the tile N ends in
        + ['cp $%02X' % CELLS, 'jr c,keep',                  # a line cannot leave its row
           'ld a,$%02X' % (CELLS - 1),
           'keep:   sub h', 'ld l,a',                        # l = cell - N, never > 0
           'ld a,b', 'add a,l', 'ld b,a',                    # the tile the pen is in
           'ld a,e', 'add a,l', 'ld e,a',                    # and that tile's column
           'call $%04X' % REVEAL_QUEUE,
           'pop hl', 'pop de', 'pop bc', 'ret'])


def _renderer_src(pentab_at, pentab_end, scan_at):
    return """
entry:  push bc
        push de
        push hl
        call zero
        pop hl
        ld c,$%02X
scan:   call $%04X
        push af
        dec c
        jr nz,scan
        ld de,$%04X
glyph:  pop af
        ld l,a
        ld h,$00
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,[de]
        inc de
        ld c,a
        ld a,[de]
        inc de
        ld b,a
        add hl,bc
        ld b,h
        ld c,l
        ld a,[de]
        inc de
        ld l,a
        ld a,[de]
        inc de
        ld h,a
        call blit
        ld a,[de]
        inc de
        ld l,a
        ld a,[de]
        inc de
        ld h,a
        call blit
        ld a,e
        cp $%02X
        jr nz,glyph
done:
        pop de
        pop bc
        ret
zero:   ld hl,$%04X
        ld b,$%02X
        call zrun
        ld hl,$%04X
        ld b,$%02X
        call zrun
        ld hl,$%04X
        ld b,$%02X
zrun:   xor a
zr1:    ld [hl+],a
        dec b
        jr nz,zr1
        ret
blit:   %s
        ret
""" % (HALF, scan_at, pentab_at, pentab_end & 0xFF,
       ZERO_RUNS[0][0], ZERO_RUNS[0][1],
       ZERO_RUNS[1][0], ZERO_RUNS[1][1],
       ZERO_RUNS[2][0], ZERO_RUNS[2][1],
       '\n        '.join(['ld a,[bc]', 'inc bc', 'or [hl]', 'ld [hl+],a', 'ld [hl+],a'] * 8))


def install(buf, notes=None):
    """Patch a 1 MiB ROM image in place. Returns the note lines."""
    p = Patcher(buf)
    out = []

    # ---- every glyph an English string can contain must fit the pen
    bad = [(ch, code) for ch, code in EN_CODES.items()
           for span in [ink_columns(buf[FONT_BASE + code * GLYPH_BYTES:
                                        FONT_BASE + (code + 1) * GLYPH_BYTES])]
           if span and span[1] > PEN - 2]
    if bad:
        raise SystemExit(
            'vwf: %d glyph(s) ink past column %d and a %dpx pen would clip them: %s. '
            'Draw them in latinfont.py rather than narrowing the pen.'
            % (len(bad), PEN - 2, PEN,
               ', '.join('%r $%02X' % (c, k) for c, k in sorted(bad, key=lambda x: x[1]))))

    # ---- the scanner, copied verbatim out of bank 13
    #
    # Position-independent by inspection AND by assertion: every branch in the block is a
    # `jr`, so the copy needs no relocation, and anything that is not a `jr` here would be
    # an absolute address that the copy would carry to the wrong bank.
    o = _off(13, SCANNER_AT)
    scanner = bytes(buf[o:o + (SCANNER_END - SCANNER_AT)])
    if scanner[0] != 0xC5 or scanner[1:3] != b'\x0e\xff':
        raise SystemExit('vwf: 13:$%04X does not begin `push bc / ld c,$FF` -- the '
                         'scanner is not where this expects it' % SCANNER_AT)
    addr = SCANNER_AT
    while addr < SCANNER_END:
        _, n = gbasm.gbdis.decode(buf, _off(13, addr), addr)
        op = buf[_off(13, addr)]
        if n == 3 and op in (0xC3, 0xCD, 0xC2, 0xCA, 0x21, 0x11, 0x01, 0xFA, 0xEA):
            raise SystemExit('vwf: 13:$%04X in the scanner holds an absolute address; the '
                             'copy in bank %d would follow it into the wrong bank'
                             % (addr, FAR_BANK))
        addr += n

    # ---- lay out bank 32: pre-shifted font, scanner copy, pen table, renderer
    font = preshift(buf)
    scan_at = CODE_ORG
    tail = bytes((0xC1, 0xC9))                      # pop bc / ret -- return the code in a
    pentab_at = CODE_ORG + len(scanner) + len(tail)
    pentab = pentable()
    pentab_end = pentab_at + len(pentab)
    if (pentab_at >> 8) != ((pentab_end - 1) >> 8):
        raise SystemExit('vwf: the pen table straddles a page boundary, so the renderer '
                         'cannot end its loop on `ld a,e / cp`')
    render_at = pentab_end
    code, _ = gbasm.assemble(_renderer_src(pentab_at, pentab_end, scan_at), render_at)

    blob = font + scanner + tail + pentab + code
    if DATA_ORG + len(blob) > BANK_END:
        raise SystemExit('vwf: bank %d needs %d bytes from $%04X and only %d are left'
                         % (FAR_BANK, len(blob), DATA_ORG, BANK_END - DATA_ORG))
    o = _off(FAR_BANK, DATA_ORG)
    if any(b != 0xFF for b in buf[o:o + len(blob)]):
        raise SystemExit('vwf: bank %d is not free at $%04X -- something else claimed it'
                         % (FAR_BANK, DATA_ORG))
    p.blob(FAR_BANK, DATA_ORG, blob)

    ix = _off(FAR_BANK, 0x4000) + FAR_INDEX - 1
    if buf[ix] != 0xFF or buf[ix + 1] != 0xFF:
        raise SystemExit('vwf: bank %d far index $%02X is already in use'
                         % (FAR_BANK, FAR_INDEX))
    buf[ix] = render_at & 0xFF
    buf[ix + 1] = render_at >> 8

    # ---- bank 13: the renderer entry becomes a far call
    #
    # `$43B8`'s three pushes stay, because `$43D0` -- the destination computation, which is
    # unchanged -- pops them. Everything between is the old nine-calls-of-one-tile loop.
    p._expect(13, RENDER_AT, 0xC5, 'the glyph renderer entry (push bc)')
    p._expect(13, RENDER_AT + 1, 0xD5, 'the glyph renderer entry (push de)')
    p._expect(13, RENDER_AT + 2, 0xE5, 'the glyph renderer entry (push hl)')
    p._expect(13, RENDER_AT + 3, 0x11, 'the old ld de,$C008')
    stub = bytes((0xC5, 0xD5, 0xE5, 0xD7, FAR_INDEX, FAR_BANK,
                  0xC3, RENDER_TAIL & 0xFF, RENDER_TAIL >> 8))
    p.blob(13, RENDER_AT, stub + b'\xFF' * (RENDER_LIMIT - RENDER_AT - len(stub)))

    # ---- the two character counts
    p.imm8(13, COMPOSER_BUDGET, 0x06, OLD_LINE_CHARS, CHARS,
           'the composer line budget, in characters')
    for at in HALF_SKIP:
        p.imm8(13, at, 0x06, OLD_HALF_CHARS, HALF, 'the half-line source skip')

    # ---- the typewriter reveals the cell the character is IN, not the Nth cell
    #
    # Into the scanner and one-tile blitter's dead bytes -- same bank as the reveal, so
    # it keeps a plain `call`. **This must come after the scanner has been copied out
    # to the far bank, and it does.** The blitter is asserted whole: it is unreachable, so
    # nothing else would notice if something had already taken the space, and the
    # scanner's own assertions above cover the other half of the region.
    o = _off(13, 0x4464)
    if bytes(buf[o:o + len(OLD_BLITTER)]) != OLD_BLITTER:
        raise SystemExit('vwf: 13:$4464 does not hold the one-tile blitter, so 13:$%04X'
                         '..$%04X is not free for the cell map'
                         % (CELLMAP_AT, CELLMAP_END - 1))
    cellmap, _ = gbasm.assemble(_cellmap_src(), CELLMAP_AT)
    if CELLMAP_AT + len(cellmap) > CELLMAP_END:
        raise SystemExit('vwf: the cell map is %d bytes and only %d are free at 13:$%04X'
                         % (len(cellmap), CELLMAP_END - CELLMAP_AT, CELLMAP_AT))
    p.blob(13, CELLMAP_AT,
           cellmap + b'\xFF' * (CELLMAP_END - CELLMAP_AT - len(cellmap)))
    p._expect(13, REVEAL_CALL, 0xCD, 'the typewriter reveal (call)')
    p._expect(13, REVEAL_CALL + 1, REVEAL_QUEUE & 0xFF, 'the typewriter reveal (target)')
    p._expect(13, REVEAL_CALL + 2, REVEAL_QUEUE >> 8, 'the typewriter reveal (target)')
    # The cell map clobbers hl to afford its multiply. These two are why that is safe:
    # the caller saves hl one instruction before the call and reloads it three after.
    p._expect(13, REVEAL_CALL - 1, 0xE5, 'the reveal saving hl before the call')
    p._expect(13, REVEAL_CALL + 5, 0x21, 'the reveal reloading hl after the call')
    p.blob(13, REVEAL_CALL, bytes((0xCD, CELLMAP_AT & 0xFF, CELLMAP_AT >> 8)))

    out.append('vwf: %d px pen -- a line holds %d characters in the same %d tiles '
               '(was %d)' % (PEN, CHARS, CELLS, OLD_LINE_CHARS))
    out.append('vwf: pre-shifted font %d bytes + renderer %d bytes -> bank %d $%04X, '
               'far index $%02X; %d bytes left in the bank'
               % (len(font), len(blob) - len(font), FAR_BANK, DATA_ORG, FAR_INDEX,
                  BANK_END - DATA_ORG - len(blob)))
    out.append('vwf: typewriter reveals the tile character N ENDS in, (%d*N+%d)>>3, not '
               'N -- 24 characters now land in cells 0..%d, %d bytes at 13:$%04X from '
               'the reveal at 13:$%04X' % (PEN, PEN - 1, cell_of(CHARS - 1),
                                           len(cellmap), CELLMAP_AT, REVEAL_CALL))
    out.append('vwf: 13:$%04X..$%04X freed (%d bytes) -- the one-tile blitter has no '
               'caller left; 13:$%04X..$%04X of it now holds the cell map'
               % (SCANNER_AT, CELLMAP_END - 1, CELLMAP_END - SCANNER_AT,
                  CELLMAP_AT, CELLMAP_AT + len(cellmap) - 1))
    if notes is not None:
        notes.extend(out)
    return out


def cellmap_selftest():
    """RUN the assembled cell map, for every character of every line. -> check count.

    Interpreted rather than re-derived, because a Python model of the arithmetic would
    agree with the Python that generated the arithmetic whatever either of them said.
    `13:$6B85` is stubbed with the three stores it really makes, so what comes back is
    the destination and the tile the queue would have been handed.
    """
    import gbemu

    code, _ = gbasm.assemble(_cellmap_src(), CELLMAP_AT)
    stub, _ = gbasm.assemble('ld a,e\nld [$C000],a\nld a,d\nld [$C001],a\n'
                             'ld a,b\nld [$C002],a\nret', REVEAL_QUEUE)
    bank = bytearray(b'\x00' * BANKSZ)
    bank[CELLMAP_AT - BANKSZ:CELLMAP_AT - BANKSZ + len(code)] = code
    bank[REVEAL_QUEUE - BANKSZ:REVEAL_QUEUE - BANKSZ + len(stub)] = stub

    # Past CHARS is the clamp's territory: the composer at 13:$687B has no cell budget,
    # so this is the only thing between a long line and the spill coming back.
    checks = 0
    for row, base in ((0x9C40, 0xA8), (0x9C80, 0xBA), (0x9CC0, 0xCC)):
        for n in range(COLUMN_MASK - 1):
            cpu = gbemu.Cpu({0: b'\x00' * BANKSZ, 13: bytes(bank)}, bank=13)
            cpu.b, cpu.c = base + n, 0x5A          # c is the caller's loop flag
            cpu.de = row + 1 + n
            cpu.call(CELLMAP_AT)

            cell = min(cell_of(n), CELLS - 1)
            got_dst = cpu.ram[0xC000 - 0x8000] | (cpu.ram[0xC001 - 0x8000] << 8)
            assert got_dst == row + 1 + cell, (row, n, hex(got_dst))
            assert cpu.ram[0xC002 - 0x8000] == base + cell, (row, n)
            # ...and the caller's own counters come back untouched, or the `inc b` /
            # `inc de` that follows would count cells and the mapping would compound.
            assert (cpu.b, cpu.c) == (base + n, 0x5A), (row, n, cpu.b, cpu.c)
            assert cpu.de == row + 1 + n, (row, n, hex(cpu.de))
            checks += 4

    # The two properties the bug was a violation of, at both ends: the last character
    # reaches the last tile (or the line loses its tail) and no character reaches past
    # it (or the row spills into the next line, which is what Joey photographed).
    assert cell_of(CHARS - 1) == CELLS - 1, 'the last character misses the last tile'
    assert all(0 <= cell_of(n) < CELLS for n in range(CHARS))
    assert all(cell_of(n) <= cell_of(n + 1) for n in range(CHARS - 1)), 'not monotonic'
    checks += 3
    return checks


# ---------------------------------------------------------------------------- selftest
def selftest():
    checks = 0

    # the pen table's geometry, derived twice
    tab = pentable()
    assert len(tab) == HALF * 6, len(tab)
    rows = [tab[i:i + 6] for i in range(0, len(tab), 6)]
    rows.reverse()
    for i, r in enumerate(rows):
        base = r[0] | (r[1] << 8)
        dst0 = r[2] | (r[3] << 8)
        pen = i * PEN
        assert base == DATA_ORG + SHIFTS.index(pen & 7) * SHIFT_STRIDE
        assert dst0 == tile_addr(pen >> 3), (i, hex(dst0))
        checks += 2
    # nine tiles, and only nine: the last glyph must not reach past tile 8
    assert tile_addr(8) + 15 == 0xC09B, hex(tile_addr(8))
    assert (HALF - 1) * PEN + 5 < CELLS // 2 * 8, 'a glyph runs past the half'
    checks += 2

    # the spill really is empty wherever the table sends it back to itself
    for i in range(HALF):
        pen = i * PEN
        if tile_addr((pen >> 3) + 1) == tile_addr(pen >> 3):
            assert pen & 7 in (0, 2)
        checks += 1

    # a pre-shifted entry reproduces a shift done in Python
    rom = bytearray(b'\x00' * (FONT_BASE + FONT_CODES * GLYPH_BYTES))
    rom[FONT_BASE + 0x0B * GLYPH_BYTES:FONT_BASE + 0x0B * GLYPH_BYTES + 8] = \
        bytes([0x70, 0x88, 0x88, 0xF8, 0x88, 0x88, 0x88, 0x00])     # 'A'
    ps = preshift(rom)
    for si, s in enumerate(SHIFTS):
        e = si * SHIFT_STRIDE + 0x0B * 16
        hi, lo = ps[e:e + 8], ps[e + 8:e + 16]
        assert hi[3] == (0xF8 >> s) & 0xFF, (s, hi[3])
        assert lo[3] == ((0xF8 << (8 - s)) & 0xFF if s else 0), (s, lo[3])
        # nothing is lost: the two halves recombine into the original
        assert ((hi[3] << 8) | lo[3]) >> (8 - s) if s else True
        checks += 2

    # the geometry the whole design rests on
    assert CELLS * 8 % PEN == 0, 'a line is not a whole number of characters'
    assert (CELLS // 2) * 8 % PEN == 0, 'a HALF line is not a whole number of characters'
    checks += 2

    checks += cellmap_selftest()

    print('vwf --selftest: %d checks OK (%d px pen, %d chars a line, %d a half)'
          % (checks, PEN, CHARS, HALF))


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        gbasm.selftest()
        selftest()
    else:
        rom = bytearray(open(sys.argv[1], 'rb').read())
        for line in install(rom):
            print(' ', line)
        if len(sys.argv) > 2 and not sys.argv[2].startswith('-'):
            open(sys.argv[2], 'wb').write(bytes(rom))
            print('wrote', sys.argv[2])
