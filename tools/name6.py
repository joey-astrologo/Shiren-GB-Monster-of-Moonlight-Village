#!/usr/bin/env python3
"""The player name goes from 4 characters to 6.

This is not a cap patch. The four-character limit is ONE nibble (`4:$5E91 ld a,$40`, the
high nibble of `$C6E2`), and patching that alone gives a field that types and draws six
characters and SAVES FOUR -- which is worse than not doing it. The name is threaded
through five structures that are each sized exactly four, and the work is making all five
agree.

  packed buffer     $D100, 4 bytes, and $D104 starts a live 120-byte block (-> SRAM
                    $A6DC in bank 3, `15:$5B2D`). It cannot grow forward, so it is
                    rehomed BACKWARD to $D0FD..$D102, with $D103 as the slot the
                    default-name literal's $FF terminator spills into.

  save record       79 bytes at SRAM $A700, gathered and scattered ONE BYTE AT A TIME
                    through a pointer table (`15:$59E3`, one 16-bit WRAM/SRAM address per
                    record byte) with a class table (`15:$592F`) saying which of the three
                    scatter passes owns each byte. The name is entries 2-5 and needs 6, so
                    the record grows to 81 and takes $A74F/$A750, which no code in the ROM
                    names and a save written by the unpatched build leaves at $FF.

                    It grows FORWARD, and that is the one thing here worth not re-deriving.
                    Growing backward to $A6FE looks better -- every existing field keeps
                    its SRAM address, so the seven routines that write record bytes by
                    absolute address need no patch -- and it is WRONG: `$A680..$A6FF` is a
                    live 128-byte block that `15:$5AC1`/`$5ADC` mirror to SRAM bank 0
                    `$A806`, and `15:$4E67` re-clears it to $FF right after the new-game
                    template is written. It was tried; the record came back with $FF in
                    its first two bytes and the log list read `65535回目` for `1回目`.
                    The evidence that $A74F is free, by contrast, is a save the ROM wrote:
                    the `51 A4 EE DB` there in a real cartridge .srm is uninitialised SRAM,
                    not data -- a fresh save from the unpatched build has $FF.

  file-select       one status byte plus the record's first 33 bytes, stride 34, three
  summary           slots in a 107-byte stack buffer built by `15:$4F90` for `4:$666D`.
                    33 -> 35 and 34 -> 36, so the buffer is 113 and TWENTY-FIVE
                    `ld hl,sp+n` operands move, by +2/+4/+6 depending on the slot.

  message payload   `4:$6D43`'s 12-byte stack payload carries the name at sp+2..sp+5 for
                    `15:$5183`, the normal New Log save path. sp+2..sp+7 is free.

  default name      two 4-byte literals, `4:$6EC4` (packed) and `4:$6B89` (display). One
                    shared 7-byte literal `Shiren`+$FF replaces both.

THE WIDTH LIVES IN THREE PLACES, which is the part that shipped broken twice. The nibble at
`4:$5E91` is only one of them: `4:$4B10` names the BOX to draw and `4:$5EE8` picks the
CURSOR's base column, and neither follows the nibble. Both were wrong for a whole build --
the field held six characters and drew four, with the underline under the second one -- and
both healed on the first keypress, because `4:$6150` (the cursor REDRAW) does derive box and
column from the width. Only the INITIAL draw was wrong, so a screenshot taken after typing
looked right. Joey found them by playing. If a fourth copy turns up, it will be in the same
shape: an immediate next to a `call` into `$5Exx`.

WHERE THE SPACE CAME FROM, because it is the part with no slack.

The record's three tables all grow: class 79->81, template 79->81, pointers 158->162, and
the 22-byte scatter helper at `15:$597E` sits between them. Rewritten minimally the helper
is 15 bytes, which is 7 back against 8 needed -- bank 15 is ONE BYTE short, and it has no
$FF anywhere and no slack byte adjacent to the region. The two candidate holes (`15:$7F27`
and `4:$7F21`) are runs of $00 inside the sparse tail blob each bank ends with, not free
space: nothing in the ROM names them, but nothing proves they are dead either, and zeros
in a bit table are DATA.

So the 81-byte new-game template moves to bank 32 with a 25-byte copier, reached by the
ROM's own far call (`rst $10 / db index,bank`) in the 14 bytes its copy loop used to
occupy. It is read exactly once, by `15:$4E0E`, at new game -- the one consumer in the set
that is not in a per-byte loop. Bank 15's table region then holds class + helper +
pointers with 80 bytes to spare.

The default-name literal buys its own three bytes the same way, out of `4:$6EA2`:
`ld a,$00` -> `xor a`, a redundant `xor a` dropped, and `ld a,$FF` -> `dec a`.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbasm
from latinfont import EN_CODES, FONT_BASE, GLYPH_BYTES

gbdis = gbasm.gbdis          # dis.py loaded by path, not the stdlib module of that name

BANKSZ = 0x4000

# ---------------------------------------------------------------------------- the sizes
OLD_LEN = 4
NEW_LEN = 6
OLD_RECORD = 79
NEW_RECORD = OLD_RECORD + (NEW_LEN - OLD_LEN)           # 81
NAME_AT = 2                                             # record offset of the name

BUF_OLD = 0xD100                                        # packed name buffer
BUF_NEW = 0xD0FD                                        # 6 bytes + a terminator slot
BLOCK = 0xD104                                          # first byte that must NOT move

SLOT = 0xA700               # SRAM record base, slot 0 -- unchanged: the record grows FORWARD
SLOT_STRIDE = 0x780
SLOT_LIMIT = 0xA75C         # the next structure in the slot (`15:$4E5A`, 20 bytes)

# Record bytes written by absolute SRAM address rather than through the pointer table.
# Everything at record offset >= NAME_AT + OLD_LEN moves up by the two bytes the name
# gained, so each of these is +2. `15:$519E`'s $A702 is the name itself and does not move.
DIRECT_WRITES = ((0x50DD, 0xEA), (0x5157, 0xEA),        # $A720, record offset 32
                 (0x51E2, 0x01), (0x51F8, 0x01),        # $A723 / $A727, four bytes each
                 (0x5252, 0xEA), (0x5255, 0xEA))        # $A71D / $A71E

DEFAULT_NAME = 'Shiren'

# ---------------------------------------------------------------------------- bank 15
CLASS_AT = 0x592F           # class table, stays put and grows into the helper's old home
HELPER_AT = CLASS_AT + NEW_RECORD                       # $5980
PTRS_AT = HELPER_AT + 15                                # $598F
REGION_END = 0x5A81         # first byte after the region -- `15:$5A81` is a routine
OLD_CLASS_AT, OLD_HELPER_AT = 0x592F, 0x597E
OLD_TMPL_AT, OLD_PTRS_AT = 0x5994, 0x59E3

# ---------------------------------------------------------------------------- bank 32
FAR_BANK = 0x20             # the DTE table bank: its table is $4100-$42FF, this is past it
FAR_INDEX = 0x03            # entry ($4002,$4003), unused; the far call reads it from there
FAR_ORG = 0x4300

# Start-menu VWF rows borrow these native tile IDs.  Erase confirmation uses $89 in its
# Log header and $9E-$A0 for `Erase this?`; the name screen later needs the same IDs for
# its field underline and fixed-cell `( ) :` keys.  Fresh entry happens before the
# collision and cannot prove this lifetime, so both name-screen callers go through a
# restore in the unused pre-text code area of pool bank 44.
NAME_RESTORE_TILES = (0x89, 0x9E, 0x9F, 0xA0)
NAME_RESTORE_BANK = 0x2C
NAME_RESTORE_INDEX = 0x05
NAME_RESTORE_AT = 0x405A
NAME_RESTORE_LIMIT = 0x4100
NAME_RESTORE_TRAMPOLINE = 0x5EFF

DEFAULT_LIT = 0x6EC1        # the shared literal, inside `4:$6EA2`'s own routine

# The two menu boxes the name field is drawn in. Box 10 is 4 cells wide, box 11 is 6 --
# both real descriptors in `script/build-inputs/box_geometry.tsv`, both already in the ROM, both drawing
# the same text at `$C6E3`. Widening the field means selecting the other one.
NARROW_BOX, WIDE_BOX = 0x0A, 0x0B


def _off(bank, addr):
    return bank * BANKSZ + (addr - 0x4000)


class Patcher(object):
    """Every write asserts the byte it is about to replace, so a moved address fails the
    build instead of corrupting code. This is the same rule build.py applies to the
    name-entry grid stride and the bank-13 message gate."""

    def __init__(self, buf):
        self.buf = buf
        self.notes = []

    def _expect(self, bank, addr, want, what):
        got = self.buf[_off(bank, addr)]
        if got != want:
            raise SystemExit(
                'name6: expected $%02X at %d:$%04X for %s, found $%02X -- the address '
                'moved, and patching blind would corrupt code' % (want, bank, addr, what, got))

    def imm8(self, bank, addr, opcode, old, new, what):
        """Patch the 1-byte operand of the instruction at `addr`."""
        self._expect(bank, addr, opcode, what + ' (opcode)')
        self._expect(bank, addr + 1, old, what)
        self.buf[_off(bank, addr + 1)] = new

    def imm16(self, bank, addr, opcode, old, new, what):
        """Patch the 2-byte operand of the instruction at `addr`."""
        self._expect(bank, addr, opcode, what + ' (opcode)')
        self._expect(bank, addr + 1, old & 0xFF, what + ' (lo)')
        self._expect(bank, addr + 2, old >> 8, what + ' (hi)')
        self.buf[_off(bank, addr + 1)] = new & 0xFF
        self.buf[_off(bank, addr + 2)] = new >> 8

    def blob(self, bank, addr, data):
        o = _off(bank, addr)
        self.buf[o:o + len(data)] = data

    def read(self, bank, addr, n):
        o = _off(bank, addr)
        return bytes(self.buf[o:o + n])


def _name_bytes(text, length):
    out = bytearray(EN_CODES[c] for c in text)
    if len(out) > length:
        raise SystemExit('name6: default name %r is longer than %d characters'
                         % (text, length))
    return bytes(out)


def _far_src(template):
    """Bank 32: copy the new-game template into the SRAM record. Registers are handed
    through by the far call in both directions, so this restores all of them."""
    return """
        push af
        push bc
        push de
        push hl
        rst $20
        db $02
        ld hl,tmpl
        ld bc,$%04X
        ld e,$%02X                  ; NEW_RECORD
copy:   ld a,[hl+]
        ld [bc],a
        inc bc
        dec e
        jr nz,copy
        pop hl
        pop de
        pop bc
        pop af
        ret
tmpl:   db %s
""" % (SLOT, NEW_RECORD, ','.join('$%02X' % b for b in template))


def _name_restore_src(planes):
    """Restore the native name cursor and punctuation in one LCD-off transaction."""
    return """
namerestore:
        push af
        push bc
        push de
        push hl
        call nrready
        ldh a,[$FF40]
        push af
        res 7,a
        ldh [$FF40],a
        ld hl,nrdata
        ld de,$8890
        ld b,$01
        call nrcopy
        ld de,$89E0
        ld b,$03
        call nrcopy
        pop af
        ldh [$FF40],a
        pop hl
        pop de
        pop bc
        pop af
        ret
nrready:
        ldh a,[$FF40]
        bit 7,a
        ret z
        ldh a,[$FF44]
        cp $90
        jr c,nrwaitblank
nrwaitvisible:
        ldh a,[$FF44]
        cp $90
        jr nc,nrwaitvisible
nrwaitblank:
        ldh a,[$FF44]
        cp $90
        jr c,nrwaitblank
        ret
nrcopy:
        ld c,$10
nrbyte:
        ld a,[hl+]
        ld [de],a
        inc de
        dec c
        jr nz,nrbyte
        dec b
        jr nz,nrcopy
        ret
nrdata:
        db %s
""" % ','.join('$%02X' % value for value in planes)


def _helper_src():
    """`15:$597E`, rewritten and rehomed. 15 bytes against the original's 22.

    Entered with bc = the record byte's SRAM address and de = its index (d is 0 at all
    three call sites, and e counts 0..80). `push af`/`pop af` go because the callers
    reload `a` from `e` before testing it; `push de`/`pop de` go because `add hl,de`
    twice replaces the original `sla e`, which is what needed de restored.
    """
    return """
        ld hl,$%04X
        add hl,de
        add hl,de
        ld a,[hl+]
        ld h,[hl]
        ld l,a
        rst $20
        db $02
        ld a,[bc]
        rst $20
        db $00
        ld [hl],a
        ret
""" % PTRS_AT


# `4:$6EA2` rewritten: three bytes cheaper, which is exactly what the 7-byte literal costs.
_DEFAULT_SRC = """
        push af
        push bc
        push hl
        ld bc,$%04X
        ld hl,lit
copy:   ld a,[hl+]
        ld [bc],a
        inc bc
        cp $FF
        jr nz,copy
        xor a
        ld [$C9DC],a
        ld [$C9E6],a
        dec a
        ld [$C6A3],a
        pop hl
        pop bc
        pop af
        ret
lit:    db %s
"""


def install(buf, notes=None):
    """Apply the whole change to a built ROM image. -> the number of sites patched."""
    p = Patcher(buf)
    notes = p.notes if notes is None else notes

    # ---- read the three tables out of the ROM rather than restating them here
    old_class = p.read(15, OLD_CLASS_AT, OLD_RECORD)
    old_tmpl = p.read(15, OLD_TMPL_AT, OLD_RECORD)
    old_ptrs = [p.read(15, OLD_PTRS_AT + 2 * i, 2) for i in range(OLD_RECORD)]
    old_ptrs = [b[0] | (b[1] << 8) for b in old_ptrs]

    want = [BUF_OLD + i for i in range(OLD_LEN)]
    if old_ptrs[NAME_AT:NAME_AT + OLD_LEN] != want:
        raise SystemExit('name6: record entries %d-%d name %s, not the packed name buffer '
                         '-- the pointer table moved'
                         % (NAME_AT, NAME_AT + OLD_LEN - 1,
                            ' '.join('$%04X' % a for a in old_ptrs[NAME_AT:NAME_AT + OLD_LEN])))
    if BUF_NEW + NEW_LEN > BLOCK - 1:
        raise SystemExit('name6: the packed buffer would run into the $D104 block')
    if SLOT + NEW_RECORD > SLOT_LIMIT:
        raise SystemExit('name6: the %d-byte record would reach $%04X, past the next '
                         'structure in the slot at $%04X'
                         % (NEW_RECORD, SLOT + NEW_RECORD - 1, SLOT_LIMIT))

    name = _name_bytes(DEFAULT_NAME, NEW_LEN)
    pad = NEW_LEN - len(name)

    # The name's six bytes are class 2, which is what the four it replaces already are.
    new_class = old_class[:NAME_AT] + b'\x02' * (NEW_LEN - OLD_LEN) + old_class[NAME_AT:]
    new_tmpl = (old_tmpl[:NAME_AT] + name + b'\xFF' * pad
                + old_tmpl[NAME_AT + OLD_LEN:])
    new_ptrs = (old_ptrs[:NAME_AT]
                + [BUF_NEW + i for i in range(NEW_LEN)]
                + old_ptrs[NAME_AT + OLD_LEN:])
    for tbl, n, what in ((new_class, NEW_RECORD, 'class'), (new_tmpl, NEW_RECORD, 'template'),
                         (new_ptrs, NEW_RECORD, 'pointer')):
        if len(tbl) != n:
            raise SystemExit('name6: the %s table came out %d bytes, not %d'
                             % (what, len(tbl), n))

    # ---------------------------------------------------------------- bank 32: the template
    far, _ = gbasm.assemble(_far_src(new_tmpl), FAR_ORG)
    o = _off(FAR_BANK, FAR_ORG)
    if any(b != 0xFF for b in buf[o:o + len(far)]):
        raise SystemExit('name6: bank %d is not free at $%04X for the template copier'
                         % (FAR_BANK, FAR_ORG))
    buf[o:o + len(far)] = far
    ix = _off(FAR_BANK, 0x4000) + FAR_INDEX - 1
    if buf[ix] != 0xFF or buf[ix + 1] != 0xFF:
        raise SystemExit('name6: bank %d index entry $%02X is already in use'
                         % (FAR_BANK, FAR_INDEX))
    buf[ix] = FAR_ORG & 0xFF
    buf[ix + 1] = FAR_ORG >> 8
    notes.append('name6: new-game template (%d bytes) + copier -> bank %d $%04X, far index $%02X'
                 % (NEW_RECORD, FAR_BANK, FAR_ORG, len(far) and FAR_INDEX))

    # Restore the four native tiles that the start-menu VWF may have borrowed before
    # either name-entry path. They all live in the 1bpp source page and are doubled into
    # the two runtime planes by the normal font uploader. Deriving the payload from the
    # already-patched ROM keeps it synchronized with latinfont automatically.
    restore_planes = bytearray()
    for tile in NAME_RESTORE_TILES:
        at = FONT_BASE + tile * GLYPH_BYTES
        glyph = buf[at:at + GLYPH_BYTES]
        restore_planes += b''.join(bytes((row, row)) for row in glyph)
    restore_src = _name_restore_src(restore_planes)
    restore, restore_labels = gbasm.assemble(restore_src, NAME_RESTORE_AT)
    if NAME_RESTORE_AT + len(restore) > NAME_RESTORE_LIMIT:
        raise SystemExit('name6: name-entry restore needs %d bytes, only %d available'
                         % (len(restore), NAME_RESTORE_LIMIT - NAME_RESTORE_AT))
    bank_at = _off(NAME_RESTORE_BANK, 0x4000)
    if buf[bank_at] != NAME_RESTORE_BANK:
        raise SystemExit('name6: bank %d pool reader is not installed' %
                         NAME_RESTORE_BANK)
    restore_at = _off(NAME_RESTORE_BANK, NAME_RESTORE_AT)
    if any(value != 0xFF for value in buf[restore_at:restore_at + len(restore)]):
        raise SystemExit('name6: bank %d is not free at $%04X for the name-entry restore'
                         % (NAME_RESTORE_BANK, NAME_RESTORE_AT))
    restore_ix = _off(NAME_RESTORE_BANK, 0x4000) + NAME_RESTORE_INDEX - 1
    if bytes(buf[restore_ix:restore_ix + 2]) != b'\xFF\xFF':
        raise SystemExit('name6: bank %d index entry $%02X is already in use'
                         % (NAME_RESTORE_BANK, NAME_RESTORE_INDEX))
    buf[restore_at:restore_at + len(restore)] = restore
    buf[restore_ix] = restore_labels['namerestore'] & 0xFF
    buf[restore_ix + 1] = restore_labels['namerestore'] >> 8
    notes.append('name6: name entry restores native $89/$9E-$A0 via bank %d $%04X '
                 '(%d bytes)' % (NAME_RESTORE_BANK, NAME_RESTORE_AT, len(restore)))

    # `15:$4E0E..$4E1B`: `ld hl,$5994 / ld bc,$A700 / ld e,$4F / <copy loop>` -> one far
    # call. The `rst $20 / db $02` at $4E0C that selected SRAM bank 2 is left alone; the
    # far routine selects it again, and `15:$4E1C call $4E43` selects it for itself.
    p._expect(15, 0x4E0E, 0x21, 'the template copy loop')
    p._expect(15, 0x4E1A, 0x20, 'the template copy loop (jr nz)')
    p.blob(15, 0x4E0E, bytes([0xD7, FAR_INDEX, FAR_BANK]) + b'\x00' * 11)

    # ---------------------------------------------------------------- bank 15: the tables
    if PTRS_AT + 2 * NEW_RECORD > REGION_END:
        raise SystemExit('name6: the three tables overrun $%04X' % REGION_END)
    p.blob(15, CLASS_AT, new_class)
    helper, _ = gbasm.assemble(_helper_src(), HELPER_AT)
    if len(helper) != PTRS_AT - HELPER_AT:
        raise SystemExit('name6: the scatter helper is %d bytes, the layout reserves %d'
                         % (len(helper), PTRS_AT - HELPER_AT))
    p.blob(15, HELPER_AT, helper)
    ptr_blob = bytearray()
    for a in new_ptrs:
        ptr_blob += bytes([a & 0xFF, a >> 8])
    p.blob(15, PTRS_AT, bytes(ptr_blob))
    free = REGION_END - (PTRS_AT + len(ptr_blob))
    p.blob(15, PTRS_AT + len(ptr_blob), b'\xFF' * free)
    notes.append('name6: bank 15 record tables rebuilt for %d entries (class $%04X, helper '
                 '$%04X, pointers $%04X, %d bytes free at $%04X)'
                 % (NEW_RECORD, CLASS_AT, HELPER_AT, PTRS_AT, free,
                    PTRS_AT + len(ptr_blob)))

    # ---------------------------------------------------------------- bank 15: consumers
    for addr in (0x58C6, 0x58EA, 0x590E):
        p.imm16(15, addr, 0xCD, OLD_HELPER_AT, HELPER_AT, 'call the scatter helper')
    p.imm16(15, 0x4F53, 0x21, OLD_PTRS_AT, PTRS_AT, 'the gather pointer table')
    p.imm8(15, 0x4F64, 0xFE, 2 * OLD_RECORD, 2 * NEW_RECORD, 'the gather bound')
    for addr in (0x58CC, 0x58F0, 0x5914):
        p.imm8(15, addr, 0xFE, OLD_RECORD, NEW_RECORD, 'a scatter bound')

    # The summary: one status byte plus the record's first 33 bytes becomes 35, so the
    # stride is 36 and `15:$4F90`'s three scratch words move from +102/+104/+105.
    old_sum, new_sum = 1 + 33, 1 + 33 + (NEW_LEN - OLD_LEN)
    p.imm8(15, 0x5011, 0x1E, 33, 33 + (NEW_LEN - OLD_LEN), 'the summary copy length')
    p.imm16(15, 0x4FBE, 0x01, old_sum, new_sum, 'the summary stride')
    shift = 3 * (new_sum - old_sum)
    for old_field, sites in ((0x0066, (0x4F99, 0x4FCB, 0x5006)),
                             (0x0068, (0x4FAB, 0x4FDD, 0x4FF7)),
                             (0x0069, (0x4FA4, 0x4FB9, 0x4FED))):
        for addr in sites:
            p.imm16(15, addr, 0x21, old_field, old_field + shift,
                    'a summary-builder scratch offset')

    # `15:$5183`, the New Log save path: the name is at record offset 2 either way, so
    # only its length changes.
    p._expect(15, 0x519F, (SLOT + NAME_AT) & 0xFF, 'the New Log save name address')
    p.imm8(15, 0x51A7, 0x1E, OLD_LEN, NEW_LEN, 'the name length in the New Log save')

    # Record bytes some routines write by absolute SRAM address instead of through the
    # pointer table. Each is past the name, so each moves up by the two bytes it gained.
    for addr, opcode in DIRECT_WRITES:
        old = buf[_off(15, addr + 1)] | (buf[_off(15, addr + 2)] << 8)
        if not SLOT + NAME_AT + OLD_LEN <= old < SLOT + OLD_RECORD:
            raise SystemExit('name6: %d:$%04X names $%04X, which is not a record byte past '
                             'the name' % (15, addr, old))
        p.imm16(15, addr, opcode, old, old + (NEW_LEN - OLD_LEN),
                'a record byte written by address')

    # `15:$52DB`'s 10-byte $D60F record is full and stays at four characters -- it did not
    # fire on name confirm. Repointed so it reads the name's first four bytes, not garbage.
    p.imm16(15, 0x52DE, 0x01, BUF_OLD, BUF_NEW, 'the $D60F record name source')

    # ---------------------------------------------------------------- bank 4: the field
    p.imm8(4, 0x5E76, 0x16, 2 * OLD_LEN, 2 * NEW_LEN, 'the entry field blank fill')
    p.imm8(4, 0x5E85, 0x16, 2 * OLD_LEN, 2 * NEW_LEN, 'the entry field prefill')
    p.imm8(4, 0x5E91, 0x3E, OLD_LEN << 4, NEW_LEN << 4, 'the field width nibble of $C6E2')

    # The second alphabet page was deliberately retired and box 13 aliases box 12, but
    # the stock initializer still selected header action 0 -- the now-blank page toggle.
    # Start on A instead.  $C6F3 no longer needs an explicit reset: its page bit selects
    # two aliased tables and its action bits are recomputed when the cursor enters the
    # header.  Preserve explicit zeroes for both horizontal cursor variables.
    init_at = 0x5E53
    old_init = bytes.fromhex('af ea f3 c6 ea f4 c6 ea f5 c6 ea f0 c6')
    new_init, _ = gbasm.assemble(
        'xor a\nld [$C6F4],a\nld [$C6F0],a\ninc a\nld [$C6F5],a\nxor a\nnop',
        init_at)
    if len(new_init) != len(old_init):
        raise AssertionError('name6: name cursor initializer changed size')
    if p.read(4, init_at, len(old_init)) != old_init:
        raise SystemExit('name6: name cursor initializer moved at 4:$%04X' % init_at)
    p.blob(4, init_at, new_init)

    # Moving Up from the left-hand letter cells formerly mapped back to action 0.  Route
    # those columns to Fwd (action 1), the first live header command, so normal vertical
    # navigation cannot re-enter the retired blank toggle.
    header_map = 0x6543
    if p.read(4, header_map, 5) != b'\x00' * 5:
        raise SystemExit('name6: header action map moved at 4:$%04X' % header_map)
    p.blob(4, header_map, b'\x01' * 5)

    # $5EDD draws two independent cursors on entry: the name-field underline and then a
    # hardcoded four-tile header underline.  Changing only $C6F5 would move the logical
    # selection to A while leaving that long header graphic under the blank toggle.  The
    # normal row cursor is the one-cell native $CA tile at shadow $C3E1.
    selector_at = 0x5EF8
    old_selector = bytes.fromhex(
        '21 a1 c3 3e c7 22 3e c8 22 3e c8 22 3e c9 22')
    new_selector, _ = gbasm.assemble('ld hl,$C3E1\nld [hl],$CA', selector_at)
    if p.read(4, selector_at, len(old_selector)) != old_selector:
        raise SystemExit('name6: initial header cursor moved at 4:$%04X' % selector_at)
    p.blob(4, selector_at,
           new_selector + b'\x00' * (len(old_selector) - len(new_selector)))
    notes.append('name6: name picker starts on A with native $CA cursor; retired '
                 'page-toggle columns map to Fwd')

    # The shorter one-cell selector above freed ten bytes at $5EFD-$5F06. Keep the
    # selector's normal fallthrough by jumping directly to its register pops, and use the
    # remaining bytes as a local far-call trampoline. Both New Log and Rename call the
    # same initializer, so both must restore the native tiles before it runs.
    freed_at = selector_at + len(new_selector)
    freed_len = len(old_selector) - len(new_selector)
    if (freed_at, freed_len) != (0x5EFD, 10):
        raise AssertionError('name6: selector saving moved from $5EFD/10')
    if p.read(4, freed_at, freed_len) != b'\x00' * freed_len:
        raise SystemExit('name6: name-entry restore trampoline space is not blank')
    selector_skip, _ = gbasm.assemble('jr $5F07', freed_at)
    trampoline, _ = gbasm.assemble(
        'rst $10\ndb $%02X,$%02X\njp $5E50' %
        (NAME_RESTORE_INDEX, NAME_RESTORE_BANK), NAME_RESTORE_TRAMPOLINE)
    bridge = selector_skip + trampoline
    if len(bridge) > freed_len:
        raise AssertionError('name6: name-entry restore trampoline is too large')
    p.blob(4, freed_at, bridge + b'\x00' * (freed_len - len(bridge)))
    for caller in (0x4B04, 0x4B22):
        p.imm16(4, caller, 0xCD, 0x5E50, NAME_RESTORE_TRAMPOLINE,
                'a name-entry initializer/restore call')
    notes.append('name6: New Log and Rename restore native name-screen tiles before '
                 'initializing the field')

    # THE BOX INDEX IS DUPLICATED, and the width nibble alone does not move it. `4:$4B02`
    # builds the player-name screen as `call $5E6E` (which sets the width) followed by a
    # HARDCODED `ld a,$0A` -- box 10, four cells wide. Its twin at `4:$4B20` is the same
    # screen at six: `call $5E9A` (width 6) plus a hardcoded box 11.
    #
    # Missing this ships a field that holds six characters and DRAWS four: the box clipped
    # `Shiren` to `Shir` until the first keypress, because `4:$6150` -- which does pick the
    # box from the width -- only runs on the cursor redraw, not on the initial draw. Joey
    # caught it by playing. Third instance of a renderer's geometry duplicated somewhere a
    # reference cannot follow; see the picker stride at GRID_STRIDE_AT.
    p.imm8(4, 0x4B10, 0x3E, NARROW_BOX, WIDE_BOX, 'the name-entry screen box index')

    # ...and so is the CURSOR's base column, a third copy of the same geometry. `4:$5EDD`
    # draws the underline at `$C347 + cursor` or at a flat `$C348` depending on bit 1 of
    # `$C6F7` -- which is not a cursor flag, it is which of the two name screens is up:
    # box 11 sits at x=6 and box 10 at x=7, so the two bases are the two boxes' first text
    # cells. It has exactly two callers, `4:$4B1A` and `4:$4B38`, and now that both draw
    # box 11 the narrow arm is wrong for both: it put the underline under the SECOND
    # character until the first redraw. Make the test unconditional rather than invert it,
    # so the two callers cannot drift apart again.
    p.imm8(4, 0x5EE8, 0x20, 0x03, 0x03, 'the cursor-column branch')     # asserts the shape
    p._expect(4, 0x5EEA, 0x23, 'the narrow arm of the cursor-column branch')
    buf[_off(4, 0x5EE8)] = 0x18                                         # `jr nz,` -> `jr `
    notes.append('name6: cursor column 4:$5EE8 now unconditional -- both name screens draw '
                 'box %d, so the $C348 arm is dead' % WIDE_BOX)

    # ---------------------------------------------------------------- bank 4: the buffer
    for addr, opcode, what in ((0x675A, 0x01, 'the summary name renderer'),
                               (0x761C, 0x01, 'display -> packed'),
                               (0x7637, 0x01, 'packed -> display'),
                               (0x6D8C, 0x11, 'the message payload')):
        p.imm16(4, addr, opcode, BUF_OLD, BUF_NEW, what + ' packed buffer')
    p.imm8(4, 0x675D, 0x16, OLD_LEN, NEW_LEN, 'the summary name renderer length')
    p.imm8(4, 0x7622, 0x16, OLD_LEN, NEW_LEN, 'the display -> packed length')
    p.imm8(4, 0x7647, 0x16, OLD_LEN, NEW_LEN, 'the packed -> display length')
    p.imm8(4, 0x6D8F, 0x06, OLD_LEN, NEW_LEN, 'the message payload name length')

    # ---------------------------------------------------------------- bank 4: the summary
    #
    # A field at record offset `i` of slot `s` sits at 1 + 34s + i today. The record grows
    # by two AT OFFSET 6, and every slot's entry grows by two, so the field moves by
    # 2*s if it is at or before the name and 2*(s+1) if it is past it. The name itself
    # stays at sp+3, which is why it is the one operand that does not move.
    #
    # The operands are found by DECODING forward from the routine's first byte, not by
    # scanning for $F8: an $F8 can also be the low half of some other instruction's
    # immediate, and rewriting one of those would be a silent corruption.
    grow = NEW_LEN - OLD_LEN
    moved = seen = 0
    addr = 0x666D
    while addr < 0x673D:
        _, size = gbdis.decode(buf, _off(4, addr), addr)
        if buf[_off(4, addr)] == 0xD7:          # `rst $10` carries two inline argument bytes
            size += 2
        elif buf[_off(4, addr)] == 0xE7:        # `rst $20` carries one
            size += 1
        elif buf[_off(4, addr)] == 0xF8:        # `ld hl,sp+n`
            n = buf[_off(4, addr + 1)]
            seen += 1
            if n >= 0x80:
                raise SystemExit('name6: `ld hl,sp-%d` at 4:$%04X is not a summary field'
                                 % (0x100 - n, addr))
            slot, within = divmod(n, old_sum)
            if slot >= 3:
                raise SystemExit('name6: sp+%d at 4:$%04X is past the three summaries'
                                 % (n, addr))
            # `within` is 0 for the slot's status byte and 1+i for its record byte i, so a
            # field is past the name -- and shifts one slot-worth extra -- from within 7.
            new = n + grow * (slot + (1 if within > NAME_AT + OLD_LEN else 0))
            if new != n:
                buf[_off(4, addr + 1)] = new
                moved += 1
        addr += size
    if (seen, moved) != (25, 21):
        raise SystemExit('name6: found %d `ld hl,sp+n` in 4:$666D and moved %d, '
                         'expected 25 and 21' % (seen, moved))
    p.imm8(4, 0x6671, 0xE8, (-3 * old_sum - 5) & 0xFF, (-3 * new_sum - 5) & 0xFF,
           'the summary stack frame')
    p.imm8(4, 0x673D, 0xE8, 3 * old_sum + 5, 3 * new_sum + 5, 'the summary stack frame')
    notes.append('name6: summary buffer %d -> %d bytes, %d `ld hl,sp+n` operands moved'
                 % (3 * old_sum + 5, 3 * new_sum + 5, moved))

    # The save-summary builder inserts two Japanese-only fixed fields after its dynamic
    # values.  $B4 is the native floor `F`; $AB/$AC are 回目 (attempt ordinal).  They sit
    # outside the translation tables, so use the installed English glyph codes directly.
    p.imm8(4, 0x69B4, 0x3E, 0xB4, EN_CODES['F'], 'the save-summary floor suffix')
    p.imm8(4, 0x6A27, 0x3E, 0xAB, EN_CODES['x'], 'the save-summary attempt suffix')
    p.imm8(4, 0x6A2B, 0x3E, 0xAC, EN_CODES[' '], 'the save-summary attempt padding')
    notes.append('name6: save summary uses English floor `F` and a numeric `x` attempt '
                 'suffix instead of native $B4/$AB/$AC tiles')

    # ---------------------------------------------------------------- bank 4: the default
    lit = ','.join('$%02X' % b for b in name + b'\xFF')
    src = _DEFAULT_SRC % (BUF_NEW, lit)
    code, labels = gbasm.assemble(src, 0x6EA2)
    if labels['lit'] != DEFAULT_LIT or len(code) != 0x6EC8 - 0x6EA2:
        raise SystemExit('name6: the rewritten default-name routine is %d bytes and puts '
                         'its literal at $%04X; it must be %d and $%04X'
                         % (len(code), labels['lit'], 0x6EC8 - 0x6EA2, DEFAULT_LIT))
    p._expect(4, 0x6EA2, 0xF5, 'the default-name routine')
    p._expect(4, 0x6EC8, 0xC5, 'the routine after the default-name literal')
    p.blob(4, 0x6EA2, code)
    # The display-form copy takes the same literal: for Latin the two forms are identical,
    # and its own 4-byte literal had no room to grow either.
    p.imm16(4, 0x6B7B, 0x21, 0x6B89, DEFAULT_LIT, 'the display-form default name')
    p.blob(4, 0x6B89, b'\x00' * 4)
    notes.append('name6: default name %r; one shared literal at 4:$%04X'
                 % (DEFAULT_NAME, DEFAULT_LIT))

    notes.append('name6: player name %d -> %d characters (record %d -> %d at SRAM $%04X, '
                 'packed buffer $%04X)'
                 % (OLD_LEN, NEW_LEN, OLD_RECORD, NEW_RECORD, SLOT, BUF_NEW))
    return notes


def selftest():
    """Assemble both routines and check the sizes the layout depends on."""
    gbasm.selftest()
    helper, _ = gbasm.assemble(_helper_src(), HELPER_AT)
    assert len(helper) == 15, len(helper)
    far, _ = gbasm.assemble(_far_src(b'\x00' * NEW_RECORD), FAR_ORG)
    assert len(far) == 25 + NEW_RECORD, len(far)
    restore, labels = gbasm.assemble(
        _name_restore_src(b'\x00' * (16 * len(NAME_RESTORE_TILES))), NAME_RESTORE_AT)
    assert labels['namerestore'] == NAME_RESTORE_AT, hex(labels['namerestore'])
    assert len(restore) == 141, len(restore)
    assert NAME_RESTORE_AT + len(restore) <= NAME_RESTORE_LIMIT
    selector_skip, _ = gbasm.assemble('jr $5F07', 0x5EFD)
    trampoline, _ = gbasm.assemble(
        'rst $10\ndb $%02X,$%02X\njp $5E50' %
        (NAME_RESTORE_INDEX, NAME_RESTORE_BANK), NAME_RESTORE_TRAMPOLINE)
    assert len(selector_skip + trampoline) <= 10
    code, labels = gbasm.assemble(
        _DEFAULT_SRC % (BUF_NEW, ','.join('$%02X' % b for b in b'\x01' * 7)), 0x6EA2)
    assert labels['lit'] == DEFAULT_LIT, hex(labels['lit'])
    assert len(code) == 0x6EC8 - 0x6EA2, len(code)
    print('name6 selftest: helper %d bytes at $%04X, pointers $%04X-$%04X, '
          'far routine %d bytes, name restore %d bytes, default literal at 4:$%04X -- OK'
          % (len(helper), HELPER_AT, PTRS_AT, PTRS_AT + 2 * NEW_RECORD - 1,
             len(far), len(restore), DEFAULT_LIT))


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        selftest()
    else:
        rom = bytearray(open(sys.argv[1], 'rb').read())
        for n in install(rom):
            print(' ', n)
        if len(sys.argv) > 2 and not sys.argv[2].startswith('-'):
            open(sys.argv[2], 'wb').write(bytes(rom))
            print('wrote', sys.argv[2])
