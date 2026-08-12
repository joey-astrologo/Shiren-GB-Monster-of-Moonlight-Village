#!/usr/bin/env python3
"""The rankings board shows 6 name characters instead of 4.

Joey reported `Shiren` -> `Shirn`, `Poopin` -> `Poopn`, `Abcdef` -> `Abcdn`. The third
sample is what settles the diagnosis: the fifth glyph is the same `n` every time, so the
row is not "showing 5 of 6" -- it is drawing the four stored name bytes and then running
one byte too far into the next field, which holds 50 (`$32`, drawn as `n` by the Latin
font). `シレン` is `4D 6B 6F FF` and terminates inside its own four bytes, which is why the
original game never showed this.

THE RENDERER WAS NEVER THE PROBLEM, and that is the finding this patch is built on. The
old brief listed "the renderer's cell cap for the name field" as unestablished and warned
that "if it draws a fixed 5 cells, neither approach shows six on its own". Measured:

    31:$46BC -> 31:$4A4B far-calls bank 4 (`rst $08 / db $29,$04`), which copies SIX bytes
    from the record into a scratch buffer at $C6E3 and appends $FF; 31:$4A5F then copies to
    the tilemap until $FF with NO length cap.

Proved on screen rather than argued: a record crafted as ten distinct letters drew exactly
`ABCDEF`, and byte 6 (`G`) appeared in the score column instead. The name field is already
six cells wide end to end. So this is purely a storage problem and it is worth exactly two
bytes per record.

WHAT THE RECORD IS, measured from Joey's .srm and confirmed against the drawer:

    0-3   name          4-6  score, 24-bit LE      7  floor (low 6 bits, drawn +1)
    8-9   count, 16-bit LE

All ten bytes are live, so the name cannot grow in place. Joey chose to grow the record
rather than rehome the names into a parallel array, because the measurements made growing
the cheaper of the two: the 32-byte gap that follows table 1 means a 12-byte record fits
19 entries in the space 20 ten-byte ones used, and the insert keeps a SINGLE record-moving
primitive instead of having to shift two arrays at different strides.

    new record   0-5 name    6-8 score    9 floor    10-11 count      stride 12
    table 1      $A010 .. $A0F3   19 x 12 = 228   (232 available before table 2)
    table 2      $A0F8 .. $A1DB   19 x 12 = 228   (232 available before the live $A1E0)
    WRAM stage   $D61B .. $D6FE   228 bytes

WHERE IT LIVES, because none of it was in the handoff. SRAM **bank 3**: a 496-byte master
block at `$BE00`, copied to a working copy at `$A000` (`15:$5553` / `15:$5575`, copier
`15:$4710`) and staged into WRAM `$D61B`. The block is 16-byte header, table 1, a 32-byte
gap, table 2, then a 48-byte tail whose `$A1E0` is a live 16-bit value.

THE TWO THINGS THAT COST THE MOST TO ESTABLISH, both of which are traps if you skip them:

1. **The WRAM staging grows past `$D6E2`, and that region is shared scratch.** Banks 2, 5,
   16, 19 and 26 all name addresses inside the existing 200-byte buffer, so a static scan
   cannot tell you whether the extra 28 bytes are safe. It was MEASURED instead: stamp
   `$D6E3-$D6FF` with a pattern once the board is up, drive it for 1,920 frames, and read
   back. Not one byte was overwritten. The staging is also re-loaded from SRAM every time
   the screen opens (`$54C4`) and written back (`$54EA`), so it never has to persist
   between visits -- the only requirement is that nothing else writes it WHILE the board
   is up, which is exactly what the stamp measures. `--selftest` re-checks the arithmetic;
   the stamp lives in the handoff as the thing to re-run if the entry count changes.

2. **The 10-byte payload at `$D60F` cannot grow, so the name is not sourced from it.**
   `$D60F..$D618` is the payload and `$D619` is a live flag (`15:$5283`, `$5294`, `$5343`)
   with the staging base `$D61B` right behind it -- there is no room for two more bytes and
   nowhere adjacent to move it to. So the struct builder at `15:$5382` is replaced by one
   that assembles the 12-byte record from TWO sources: six name bytes from the packed
   player-name buffer `$D0FD` (which name6.py established, and which is the current
   player's name by construction) and the remaining six from `$D613` (score, floor, count).
   `15:$52DB`'s existing 4-byte copy into `$D60F` is left ALONE -- `15:$4082`/`$4096`/
   `$409F`/`$40AD` still read that payload, and this patch has no business changing what
   they see.

   The replacement is 45 bytes and lives in the 80 free bytes at `15:$5A31` that name6.py
   left behind; its two callers (`15:$534D`, `15:$5375`) are repointed.

THE STRUCT OFFSETS ALL MOVE BY TWO, which is the bulk of the diff and the easiest place to
make a silent mistake. `15:$53C5` builds its working state on the stack directly behind the
record it is inserting (`add sp,-47`), so a 12-byte record collides with the cursor pointer
that used to sit at +$0B. Everything from +$0B up shifts +2; the record's score field moves
+$05 -> +$07. Two operands deliberately do NOT move and both are checked by `--selftest`:
`15:$5438`'s `$0002` is the score's high-byte offset, and `15:$5473`'s `$0004` is
count-minus-score, which is 4 in both layouts (8-4 and 10-6).

**This is a SAVE FORMAT CHANGE.** A board written by an older build is read at the wrong
stride and shows garbage; there is no migration and the ranks earned before it are lost.
That is the whole argument for doing it now rather than after the prose -- every ranking
earned before the fix stores four characters, and fixing it later does not repair them.

`build.py --no-rank6` is the bisect control. It is implied by `--no-name6`, because the
name source is `$D0FD`, which only exists at six bytes in a name6 build.

usage: rank6.py <rom> [--selftest]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbasm
from latinfont import EN_CODES

BANKSZ = 0x4000

OLD_STRIDE, NEW_STRIDE = 0x0A, 0x0C
OLD_COUNT, NEW_COUNT = 0x14, 0x13           # entries per table: 20 -> 19
STAGE = 0xD61B                              # WRAM staging base

# field offsets inside a record, old -> new
OLD_SCORE, NEW_SCORE = 4, 6
OLD_FLOOR, NEW_FLOOR = 7, 9
OLD_COUNTF, NEW_COUNTF = 8, 10

DIFFICULTY_AT = 0x47EB
OLD_DIFFICULTIES = bytes((
    0x00, 0x2E, 0x15, 0x16, 0x0C,       # やさしい
    0x00, 0x26, 0x1C, 0x0D, 0x00,       # ふつう
    0x2B, 0xA5, 0x10, 0x16, 0x0C,       # むずかしい
))
EN_DIFFICULTIES = b''.join(bytes(EN_CODES[ch] for ch in text)
                           for text in ('Easy ', 'Norm.', 'Hard '))

NAME_SRC = 0xD0FD                           # name6.py's packed player-name buffer, 6 bytes
REST_SRC = 0xD613                           # payload+4: score(3), floor(1), count(2)
TYPE_AT = 0xD60E

BUILDER_AT = 0x5A31                         # the 80 free bytes name6.py left in bank 15
BUILDER_LIMIT = 0x5A81
OLD_BUILDER = 0x5382
BUILDER_CALLERS = (0x534D, 0x5375)

# The last entry's score field, which is where the insert's backward walk starts.
OLD_CURSOR = STAGE + (OLD_COUNT - 1) * OLD_STRIDE + OLD_SCORE        # $D6DD
NEW_CURSOR = STAGE + (NEW_COUNT - 1) * NEW_STRIDE + NEW_SCORE        # $D6F9

OLD_BYTES, NEW_BYTES = OLD_COUNT * OLD_STRIDE, NEW_COUNT * NEW_STRIDE   # 200 -> 228

# SRAM, in the working copy's addresses. The master at $BE00 mirrors these.
TABLE1, TABLE2, TAIL_LIVE = 0xA010, 0xA0F8, 0xA1E0


def _off(bank, addr):
    return bank * BANKSZ + (addr - 0x4000)


class Patcher(object):
    """Every write asserts the byte it replaces, so a moved address fails the build instead
    of corrupting code -- the same rule name6.py and the bank-13 message gate apply."""

    def __init__(self, buf):
        self.buf = buf
        self.n = 0

    def _expect(self, bank, addr, want, what):
        got = self.buf[_off(bank, addr)]
        if got != want:
            raise SystemExit(
                'rank6: expected $%02X at %d:$%04X for %s, found $%02X -- the address '
                'moved, and patching blind would corrupt code'
                % (want, bank, addr, what, got))

    def imm8(self, bank, addr, opcode, old, new, what):
        self._expect(bank, addr, opcode, what + ' (opcode)')
        self._expect(bank, addr + 1, old, what)
        self.buf[_off(bank, addr + 1)] = new
        self.n += 1

    def imm16(self, bank, addr, opcode, old, new, what):
        self._expect(bank, addr, opcode, what + ' (opcode)')
        self._expect(bank, addr + 1, old & 0xFF, what + ' (lo)')
        self._expect(bank, addr + 2, old >> 8, what + ' (hi)')
        self.buf[_off(bank, addr + 1)] = new & 0xFF
        self.buf[_off(bank, addr + 2)] = new >> 8
        self.n += 1

    def blob(self, bank, addr, data):
        o = _off(bank, addr)
        self.buf[o:o + len(data)] = data
        self.n += 1


# ---------------------------------------------------------------------------- bank 31
# The drawer. `31:$4662` walks five records a page; `31:$4640` counts the non-empty ones.
# The name is at record+0 in both layouts, so `31:$46BC` needs no change at all.
DRAWER = (
    (0x4641, 0x11, 0x0009, 0x000B, 'count scan: advance after the 2-byte read'),
    (0x4646, 0x21, STAGE + OLD_COUNTF, STAGE + NEW_COUNTF, 'count scan: first count field'),
    (0x46A1, 0x11, 0x000A, 0x000C, 'page loop: next record'),
    (0x46B3, 0x01, 0x0008, 0x000A, 'empty test: count offset'),
    (0x46E4, 0x11, 0x0004, 0x0006, 'score field offset'),
    (0x4745, 0x11, 0x0007, 0x0009, 'floor field offset'),
    (0x47AA, 0x11, 0x0009, 0x000B, 'count high byte: the two flag bits'),
    (0x47FE, 0x11, 0x0007, 0x0009, 'floor byte: the bit-7 flag'),
    (0x4833, 0x11, 0x0008, 0x000A, 'count field offset'),
)

# Every `ld de,$00nn` / `ld bc,$00nn` in `31:$4640-$4870` is either a record field offset or
# the count scan's advance, and all eight are in DRAWER. Sweeping the whole block for the
# pattern -- rather than following the seven calls the page loop makes -- is what caught
# `$47AA`, `$47FE` and `$4833`: the first draft patched only the fields it had read the
# code for, and the board drew the count as 1024 for 1.
DRAWER_SWEEP = (0x4640, 0x4870)

# Bank 15's half of the same discipline. Every operand in the insert block is either patched
# above or deliberately left alone, and `install` proves there is no third category.
RANGE_STRUCT = (0x53C5, 0x54C4)     # insert, compare, shift, record copy
RANGE_STACK = (0x533C, 0x5382)      # the two struct bases and the rank-index read

# Operands inside RANGE_STRUCT that must NOT move, with the reason each is safe.
KEEP_STRUCT = {
    0x53F0: 'cp $02 -- a comparison RESULT, not an offset',
    0x5438: 'ld bc,$0002 -- the score high byte, and the score is still 3 bytes',
    0x5450: 'ld e,$03 -- the score compare is still 3 bytes wide',
    0x545D: 'ld d,$02 -- a result value',
    0x5463: 'ld d,$00 -- a result value',
    0x546A: 'ld d,$01 -- a result value',
    0x5473: 'ld bc,$0004 -- count minus score, which is 4 in BOTH layouts (8-4 and 10-6)',
}
# Stack reads inside RANGE_STACK that must NOT move: the two struct BASES.
KEEP_STACK = {
    0x5349: 'ld hl,sp+0 -- $533C\'s struct base',
    0x5371: 'ld hl,sp+1 -- $536B\'s struct base',
}

# ---------------------------------------------------------------------------- bank 15
# The insert (`15:$53C5`) builds its state on the stack directly behind the 12-byte record,
# so every struct field from +$0B up shifts by two. Listed as (addr, opcode, old, new).
STRUCT = (
    (0x53C8, 0x21, 0x0005, 0x0007, 'new record: score field'),
    (0x53CE, 0x21, 0x000B, 0x000D, 'struct: cursor pointer'),
    (0x53D8, 0x21, 0x000D, 0x000F, 'struct: table pointer'),
    (0x53DF, 0x21, 0x0010, 0x0012, 'struct: table pointer 2'),
    (0x53EB, 0x21, 0x000F, 0x0011, 'struct: compare result'),
    (0x53F8, 0x21, 0x000D, 0x000F, 'struct: table pointer'),
    (0x53FF, 0x21, 0x0010, 0x0012, 'struct: table pointer 2'),
    (0x540C, 0x21, 0x000D, 0x000F, 'struct: table pointer'),
    (0x5417, 0x21, 0x0012, 0x0014, 'struct: final index'),
    (0x5421, 0x21, 0x0005, 0x0007, 'new record: score field'),
    (0x5427, 0x21, 0x000D, 0x000F, 'struct: table pointer'),
    (0x543B, 0x21, 0x000B, 0x000D, 'compare: cursor pointer'),
    (0x5444, 0x21, 0x000D, 0x000F, 'compare: table pointer'),
    (0x546E, 0x21, 0x000F, 0x0011, 'compare: result'),
    (0x5476, 0x21, 0x000D, 0x000F, 'compare: table pointer'),
    (0x5488, 0x21, 0x000F, 0x0011, 'compare: result'),
    (0x5495, 0x21, 0x000D, 0x000F, 'shift: source pointer'),
    (0x54A1, 0x21, 0x0010, 0x0012, 'shift: destination pointer'),
)

# The stride and the walk backwards over it.
STRIDES = (
    (0x53D5, 0x01, OLD_CURSOR, NEW_CURSOR, 'insert: last entry score field'),
    (0x5406, 0x21, 0x10000 - OLD_STRIDE, 0x10000 - NEW_STRIDE, 'insert: step back one record'),
    (0x549C, 0x01, 0x10000 - OLD_SCORE, 0x10000 - NEW_SCORE, 'shift: score field -> record base'),
)

# The length of a record move, and the one stack read of the struct outside `15:$53C5`.
#
# BOTH OF THESE WERE MISSED IN THE FIRST BUILD and Joey found them by playing. They are the
# reason RANGE_STRUCT/RANGE_STACK below are swept at build time rather than trusted to a
# list. `15:$54B7` kept copying TEN bytes of a twelve-byte record, which silently dropped
# the count -- the exact field `31:$46B1` reads to decide a slot is empty, so every entry
# was written and then treated as absent and the board drew nothing. `15:$535E` read the
# final rank index from the struct offset it lived at BEFORE the +2 shift, so the far call
# that shows the result screen on death got a pointer byte for a rank and did not draw.
COPYLEN = (
    (0x54B7, 0x1E, OLD_STRIDE, NEW_STRIDE, 'record copy length'),
)
STACKREAD = (
    (0x535E, 0xF8, 0x12, 0x14, 'result screen: the final rank index at struct+$14'),
)

# The staging copies and clears, 200 bytes -> 228. The copies count down in `e` (an 8-bit
# immediate); the clears carry the count in `bc` because their loop handles a 16-bit length.
SIZES = (
    (0x55D5, 0x1E, OLD_BYTES, NEW_BYTES, 'table 1 load'),
    (0x55EE, 0x1E, OLD_BYTES, NEW_BYTES, 'table 1 save'),
    (0x5607, 0x1E, OLD_BYTES, NEW_BYTES, 'table 2 load'),
    (0x5620, 0x1E, OLD_BYTES, NEW_BYTES, 'table 2 save'),
)
CLEARS = (
    (0x566C, 0x01, OLD_BYTES, NEW_BYTES, 'table 1 clear'),
    (0x5695, 0x01, OLD_BYTES, NEW_BYTES, 'table 2 clear'),
)

# The per-table entry counts.
COUNTS = (
    (31, 0x4649, 0x0E, 'count scan limit'),
    (15, 0x53E6, 0x0E, 'insert: slots to walk'),
    (15, 0x541D, 0xFE, 'insert: did it reach the end'),
)


def _builder_src():
    """Assemble the 12-byte record from the name buffer and the payload's tail.

    Same contract as the `15:$5382` it replaces: `de` is the struct base, `[$D60E]` is the
    type byte and a zero type means write only that byte, and every register is restored.
    """
    return """
        push af
        push bc
        push hl
        ld h,d
        ld l,e
        ld a,[$%04X]
        ld [hl],a
        cp $00
        jr z,done
        ld hl,$0001
        add hl,de
        push de
        ld bc,$%04X
        ld e,$%02X
name:   ld a,[bc]
        ld [hl+],a
        inc bc
        dec e
        jr nz,name
        ld bc,$%04X
        ld e,$%02X
rest:   ld a,[bc]
        ld [hl+],a
        inc bc
        dec e
        jr nz,rest
        pop de
done:   pop hl
        pop bc
        pop af
        ret
""" % (TYPE_AT, NAME_SRC, 6, REST_SRC, NEW_STRIDE - 6)


def _sweep(buf, bank, lo, hi, ops16=(0x01, 0x11), ops8=()):
    """-> [addr] for every small-immediate load in a range.

    Decoded linearly from an instruction boundary rather than by scanning for opcode bytes,
    so an operand byte that happens to equal $11 cannot masquerade as an instruction.
    """
    found = []
    addr = lo
    while addr < hi:
        off = _off(bank, addr)
        try:
            _, n = gbasm.gbdis.decode(buf, off, addr)
        except Exception:
            break
        op = buf[off]
        if n == 3 and op in ops16:
            if (buf[off + 1] | (buf[off + 2] << 8)) < 0x0100:
                found.append(addr)
        elif n == 2 and op in ops8:
            found.append(addr)
        addr += n
    return found


def _guard(buf, bank, lo, hi, patched, keep, what, **kw):
    stray = [a for a in _sweep(buf, bank, lo, hi, **kw)
             if a not in patched and a not in keep]
    if stray:
        raise SystemExit(
            'rank6: unclassified operand(s) in %s at %s -- every one has to be either '
            'patched or listed as deliberately unchanged before the stride moves. This '
            'guard exists because two were missed and shipped.'
            % (what, ', '.join('%d:$%04X' % (bank, a) for a in stray)))


def install(buf, notes=None):
    """Patch a 1 MiB ROM image in place. Returns the note lines."""
    p = Patcher(buf)
    out = []

    # Every operand in the drawer and in bank 15's insert block is either patched below or
    # listed as deliberately unchanged. These three guards prove there is no third category.
    # They are not belt-and-braces: `$47AA`/`$47FE`/`$4833` were nearly missed in the drawer,
    # and `$54B7`/`$535E` WERE missed in bank 15 and shipped a build where every rank entry
    # was stored and then treated as empty. Classify, do not enumerate from memory.
    _guard(buf, 31, DRAWER_SWEEP[0], DRAWER_SWEEP[1],
           set(a for a, _, _, _, _ in DRAWER), {}, 'the bank 31 drawer')
    _guard(buf, 15, RANGE_STRUCT[0], RANGE_STRUCT[1],
           set(a for a, _, _, _, _ in STRUCT + STRIDES + COPYLEN), KEEP_STRUCT,
           'the bank 15 insert block', ops16=(0x01, 0x11, 0x21), ops8=(0x1E, 0x16))
    _guard(buf, 15, RANGE_STACK[0], RANGE_STACK[1],
           set(a for a, _, _, _, _ in STACKREAD), KEEP_STACK,
           'the bank 15 struct stack reads', ops16=(), ops8=(0xF8,))

    for addr, op, old, new, what in DRAWER:
        p.imm16(31, addr, op, old, new, 'drawer: ' + what)
    p.imm8(31, 0x466C, 0x3E, OLD_STRIDE, NEW_STRIDE, 'drawer: page offset stride')
    # The native ordinal suffix at $4730 is tile $A0.  English also assigns $A0 to
    # colon, and the fixed rankings path does not reliably upload that high punctuation
    # tile.  A low-page period is both stable and idiomatic: "1.", "2.", ...
    p.imm8(31, 0x4730, 0x3E, 0xA0, EN_CODES['.'], 'drawer: rank ordinal punctuation')
    p.imm8(31, 0x4786, 0x3E, 0xB4, EN_CODES['F'], 'drawer: ranking floor suffix')
    p.imm8(31, 0x4855, 0x3E, 0xAB, EN_CODES['x'], 'drawer: ranking attempt suffix')
    for offset, want in enumerate(OLD_DIFFICULTIES):
        p._expect(31, DIFFICULTY_AT + offset, want, 'drawer: difficulty labels')
    p.blob(31, DIFFICULTY_AT, EN_DIFFICULTIES)

    for addr, op, old, new, what in STRUCT + STRIDES + CLEARS:
        p.imm16(15, addr, op, old, new, what)
    for addr, op, old, new, what in SIZES + COPYLEN + STACKREAD:
        p.imm8(15, addr, op, old, new, what)

    for bank, addr, op, what in COUNTS:
        p.imm8(bank, addr, op, OLD_COUNT, NEW_COUNT, what)

    code, _ = gbasm.assemble(_builder_src(), BUILDER_AT)
    if BUILDER_AT + len(code) > BUILDER_LIMIT:
        raise SystemExit('rank6: the struct builder is %d bytes and only %d are free at '
                         '15:$%04X' % (len(code), BUILDER_LIMIT - BUILDER_AT, BUILDER_AT))
    for addr in range(BUILDER_AT, BUILDER_AT + len(code)):
        p._expect(15, addr, 0xFF, 'struct builder region must be free')
    p.blob(15, BUILDER_AT, code)
    for addr in BUILDER_CALLERS:
        p.imm16(15, addr, 0xCD, OLD_BUILDER, BUILDER_AT, 'struct builder call')

    out.append('rank6: rankings record %d -> %d bytes, %d -> %d entries per table; the '
               'board now shows a 6-character name (SAVE FORMAT CHANGE)'
               % (OLD_STRIDE, NEW_STRIDE, OLD_COUNT, NEW_COUNT))
    out.append('rank6: ranking ordinals use a stable low-page period (1., 2., ...)')
    out.append('rank6: fixed ranking fields use English F and numeric x suffixes')
    out.append('rank6: fixed ranking difficulties use Easy / Norm. / Hard')
    out.append('rank6: struct builder at 15:$%04X, %d bytes, %d free after'
               % (BUILDER_AT, len(code), BUILDER_LIMIT - BUILDER_AT - len(code)))
    out.append('rank6: %d sites patched' % p.n)
    if notes is not None:
        notes.extend(out)
    return out


def selftest():
    """Check the arithmetic this layout depends on, and the two operands that must NOT move."""
    fail = []

    def ck(cond, msg):
        print('  %s  %s' % ('ok  ' if cond else 'FAIL', msg))
        if not cond:
            fail.append(msg)

    ck(NEW_BYTES <= TABLE2 - TABLE1,
       'table 1: %d bytes fits the %d before table 2' % (NEW_BYTES, TABLE2 - TABLE1))
    ck(NEW_BYTES <= TAIL_LIVE - TABLE2,
       'table 2: %d bytes fits the %d before the live $%04X'
       % (NEW_BYTES, TAIL_LIVE - TABLE2, TAIL_LIVE))
    ck(STAGE + NEW_BYTES - 1 == 0xD6FE,
       'WRAM staging ends at $%04X (stamp-measured clean to $D6FF)' % (STAGE + NEW_BYTES - 1))
    ck(NEW_CURSOR == STAGE + (NEW_COUNT - 1) * NEW_STRIDE + NEW_SCORE,
       'insert cursor starts at $%04X, the last entry score field' % NEW_CURSOR)
    ck(NEW_COUNTF - NEW_SCORE == OLD_COUNTF - OLD_SCORE,
       'count-minus-score is %d in both layouts, so 15:$5473 must NOT move'
       % (NEW_COUNTF - NEW_SCORE))
    ck(NEW_SCORE >= 6, 'the name has its 6 bytes before the score at +%d' % NEW_SCORE)
    ck(NEW_STRIDE - NEW_COUNTF == 2, 'the count is the last field, 2 bytes')

    code, _ = gbasm.assemble(_builder_src(), BUILDER_AT)
    ck(BUILDER_AT + len(code) <= BUILDER_LIMIT,
       'struct builder is %d bytes, %d free at 15:$%04X'
       % (len(code), BUILDER_LIMIT - BUILDER_AT, BUILDER_AT))
    return fail


# SRAM bank 3, master block. A .srm is the four 8 KiB banks end to end.
SRM_BANK, MASTER = 3, 0xBE00
MASTER_T1, MASTER_T2 = MASTER + 0x10, MASTER + 0xF8


def _srm_off(addr, bank=SRM_BANK):
    return bank * 0x2000 + (addr - 0xA000)


def upgrade_srm(data):
    """Rewrite a save's two rank tables from the 10-byte layout to the 12-byte one.

    There is no version marker in the block, so this cannot detect which format a save is
    already in -- run it exactly once, on a save written before the change. Names keep
    their four stored characters and gain an `$FF` terminator, so a converted board reads
    `Shir` rather than `Shirn`: the two characters were never stored and cannot be
    recovered. Everything else carries over, and a 20th entry (if any) is dropped.
    """
    out = bytearray(data)
    moved = 0
    for base in (MASTER_T1, MASTER_T2):
        old = bytes(data[_srm_off(base):_srm_off(base) + OLD_COUNT * OLD_STRIDE])
        new = bytearray()
        for i in range(NEW_COUNT):
            r = old[i * OLD_STRIDE:(i + 1) * OLD_STRIDE]
            name = bytearray(r[0:4])
            if 0xFF not in name:                 # terminate it inside its own six bytes
                name += b'\xFF\x00'
            else:
                name += b'\x00\x00'
            new += name[:6] + r[4:7] + r[7:8] + r[8:10]
            if any(r):
                moved += 1
        assert len(new) == NEW_COUNT * NEW_STRIDE
        out[_srm_off(base):_srm_off(base) + len(new)] = new
    return bytes(out), moved


def repair_srm(data):
    """Restore the count on records the 2026-08-03 first build damaged.

    That build patched the record stride everywhere except `15:$54B7`, so every record move
    copied 10 bytes of 12 and dropped the count. `31:$46B1` reads exactly that field to
    decide a slot is empty, so an affected board draws nothing from the first damaged slot
    on. The count itself is not recoverable; a record with a name but a zero count is set to
    1, which makes it visible again and reads `1回`.
    """
    out = bytearray(data)
    fixed = 0
    for base in (MASTER_T1, MASTER_T2):
        for i in range(NEW_COUNT):
            o = _srm_off(base) + i * NEW_STRIDE
            rec = data[o:o + NEW_STRIDE]
            named = any(b not in (0x00, 0xFF) for b in rec[0:6])
            if named and rec[10] == 0 and rec[11] == 0:
                out[o + 10] = 1
                fixed += 1
    return bytes(out), fixed


def main():
    a = sys.argv[1:]
    if '--repair' in a:
        rest = [x for x in a if x != '--repair']
        if len(rest) != 2:
            raise SystemExit('usage: rank6.py --repair <old.srm> <new.srm>')
        data = open(rest[0], 'rb').read()
        if len(data) != 0x8000:
            raise SystemExit('rank6: %s is %d bytes, expected a 32768-byte .srm'
                             % (rest[0], len(data)))
        if os.path.exists(rest[1]):
            raise SystemExit('rank6: %s exists -- refusing to overwrite a save' % rest[1])
        new, fixed = repair_srm(data)
        open(rest[1], 'wb').write(new)
        print('rank6: restored the count on %d damaged record(s)' % fixed)
        print('rank6: wrote %s (the input is untouched)' % rest[1])
        return 0
    if '--upgrade' in a:
        rest = [x for x in a if x != '--upgrade']
        if len(rest) != 2:
            raise SystemExit('usage: rank6.py --upgrade <old.srm> <new.srm>')
        data = open(rest[0], 'rb').read()
        if len(data) != 0x8000:
            raise SystemExit('rank6: %s is %d bytes, expected a 32768-byte .srm'
                             % (rest[0], len(data)))
        if os.path.exists(rest[1]):
            raise SystemExit('rank6: %s exists -- refusing to overwrite a save' % rest[1])
        new, moved = upgrade_srm(data)
        open(rest[1], 'wb').write(new)
        print('rank6: converted %d rank entr%s to the 12-byte layout'
              % (moved, 'y' if moved == 1 else 'ies'))
        print('rank6: wrote %s (the input is untouched)' % rest[1])
        return 0
    if '--selftest' in a:
        gbasm.selftest()
        fail = selftest()
        print('\nrank6 selftest: %s' % ('FAILED' if fail else 'all checks pass'))
        return 1 if fail else 0
    if not a:
        raise SystemExit(__doc__.strip().splitlines()[-1])
    buf = bytearray(open(a[0], 'rb').read())
    for line in install(buf):
        print(line)
    out = a[1] if len(a) > 1 else a[0]
    open(out, 'wb').write(bytes(buf))
    print('rank6: wrote %s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
