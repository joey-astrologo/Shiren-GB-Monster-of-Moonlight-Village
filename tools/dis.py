#!/usr/bin/env python3
"""Minimal LR35902 (Game Boy) disassembler -- enough to read routines.

usage: dis.py <rom> <hex-offset> <count-bytes> [--bank N]

<hex-offset> is a raw FILE offset, unless --bank is given -- then it is a CPU address
($4000-$7FFF) inside that bank, which is what Mesen and every note in FINDINGS.md uses.
`--bank` was documented and silently ignored for a while; it works now.

Addresses are shown as bank:addr so they can be compared against Mesen directly.
"""
import sys

R = ['b', 'c', 'd', 'e', 'h', 'l', '[hl]', 'a']
ALU = ['add a,', 'adc a,', 'sub ', 'sbc a,', 'and ', 'xor ', 'or ', 'cp ']
CBOPS = ['rlc', 'rrc', 'rl', 'rr', 'sla', 'sra', 'swap', 'srl']

# 0x00-0x3F and 0xC0-0xFF are irregular; (mnemonic, extra-bytes)
LOW = {
    0x00: ('nop', 0), 0x01: ('ld bc,%(d16)s', 2), 0x02: ('ld [bc],a', 0), 0x03: ('inc bc', 0),
    0x04: ('inc b', 0), 0x05: ('dec b', 0), 0x06: ('ld b,%(d8)s', 1), 0x07: ('rlca', 0),
    0x08: ('ld [%(a16)s],sp', 2), 0x09: ('add hl,bc', 0), 0x0A: ('ld a,[bc]', 0),
    0x0B: ('dec bc', 0), 0x0C: ('inc c', 0), 0x0D: ('dec c', 0), 0x0E: ('ld c,%(d8)s', 1),
    0x0F: ('rrca', 0),
    0x10: ('stop', 1), 0x11: ('ld de,%(d16)s', 2), 0x12: ('ld [de],a', 0), 0x13: ('inc de', 0),
    0x14: ('inc d', 0), 0x15: ('dec d', 0), 0x16: ('ld d,%(d8)s', 1), 0x17: ('rla', 0),
    0x18: ('jr %(r8)s', 1), 0x19: ('add hl,de', 0), 0x1A: ('ld a,[de]', 0), 0x1B: ('dec de', 0),
    0x1C: ('inc e', 0), 0x1D: ('dec e', 0), 0x1E: ('ld e,%(d8)s', 1), 0x1F: ('rra', 0),
    0x20: ('jr nz,%(r8)s', 1), 0x21: ('ld hl,%(d16)s', 2), 0x22: ('ld [hl+],a', 0),
    0x23: ('inc hl', 0), 0x24: ('inc h', 0), 0x25: ('dec h', 0), 0x26: ('ld h,%(d8)s', 1),
    0x27: ('daa', 0), 0x28: ('jr z,%(r8)s', 1), 0x29: ('add hl,hl', 0), 0x2A: ('ld a,[hl+]', 0),
    0x2B: ('dec hl', 0), 0x2C: ('inc l', 0), 0x2D: ('dec l', 0), 0x2E: ('ld l,%(d8)s', 1),
    0x2F: ('cpl', 0),
    0x30: ('jr nc,%(r8)s', 1), 0x31: ('ld sp,%(d16)s', 2), 0x32: ('ld [hl-],a', 0),
    0x33: ('inc sp', 0), 0x34: ('inc [hl]', 0), 0x35: ('dec [hl]', 0),
    0x36: ('ld [hl],%(d8)s', 1), 0x37: ('scf', 0), 0x38: ('jr c,%(r8)s', 1),
    0x39: ('add hl,sp', 0), 0x3A: ('ld a,[hl-]', 0), 0x3B: ('dec sp', 0), 0x3C: ('inc a', 0),
    0x3D: ('dec a', 0), 0x3E: ('ld a,%(d8)s', 1), 0x3F: ('ccf', 0),
}
HIGH = {
    0xC0: ('ret nz', 0), 0xC1: ('pop bc', 0), 0xC2: ('jp nz,%(a16)s', 2), 0xC3: ('jp %(a16)s', 2),
    0xC4: ('call nz,%(a16)s', 2), 0xC5: ('push bc', 0), 0xC6: ('add a,%(d8)s', 1),
    0xC7: ('rst $00', 0), 0xC8: ('ret z', 0), 0xC9: ('ret', 0), 0xCA: ('jp z,%(a16)s', 2),
    0xCC: ('call z,%(a16)s', 2), 0xCD: ('call %(a16)s', 2), 0xCE: ('adc a,%(d8)s', 1),
    0xCF: ('rst $08', 0),
    0xD0: ('ret nc', 0), 0xD1: ('pop de', 0), 0xD2: ('jp nc,%(a16)s', 2),
    0xD4: ('call nc,%(a16)s', 2), 0xD5: ('push de', 0), 0xD6: ('sub %(d8)s', 1),
    0xD7: ('rst $10', 0), 0xD8: ('ret c', 0), 0xD9: ('reti', 0), 0xDA: ('jp c,%(a16)s', 2),
    0xDC: ('call c,%(a16)s', 2), 0xDE: ('sbc a,%(d8)s', 1), 0xDF: ('rst $18', 0),
    0xE0: ('ldh [%(a8)s],a', 1), 0xE1: ('pop hl', 0), 0xE2: ('ld [c],a', 0), 0xE5: ('push hl', 0),
    0xE6: ('and %(d8)s', 1), 0xE7: ('rst $20', 0), 0xE8: ('add sp,%(r8)s', 1),
    0xE9: ('jp hl', 0), 0xEA: ('ld [%(a16)s],a', 2), 0xEE: ('xor %(d8)s', 1),
    0xEF: ('rst $28', 0),
    0xF0: ('ldh a,[%(a8)s]', 1), 0xF1: ('pop af', 0), 0xF2: ('ld a,[c]', 0), 0xF3: ('di', 0),
    0xF5: ('push af', 0), 0xF6: ('or %(d8)s', 1), 0xF7: ('rst $30', 0),
    0xF8: ('ld hl,sp%(r8s)s', 1), 0xF9: ('ld sp,hl', 0), 0xFA: ('ld a,[%(a16)s]', 2),
    0xFB: ('ei', 0), 0xFE: ('cp %(d8)s', 1), 0xFF: ('rst $38', 0),
}


def decode(rom, off, pc):
    """-> (text, length). pc is the CPU address the byte at `off` is mapped to."""
    op = rom[off]
    if op == 0xCB:
        sub = rom[off + 1]
        kind, z = sub >> 6, sub & 7
        if kind == 0:
            return '%s %s' % (CBOPS[(sub >> 3) & 7], R[z]), 2
        return '%s %d,%s' % (['', 'bit', 'res', 'set'][kind], (sub >> 3) & 7, R[z]), 2
    if 0x40 <= op <= 0x7F:
        if op == 0x76:
            return 'halt', 1
        return 'ld %s,%s' % (R[(op >> 3) & 7], R[op & 7]), 1
    if 0x80 <= op <= 0xBF:
        return '%s%s' % (ALU[(op >> 3) & 7], R[op & 7]), 1
    tbl = LOW if op < 0x40 else HIGH
    if op not in tbl:
        return 'db $%02X' % op, 1
    fmt, extra = tbl[op]
    n = 1 + extra
    vals = {}
    if extra == 1:
        b = rom[off + 1]
        vals['d8'] = '$%02X' % b
        vals['a8'] = '$FF%02X' % b
        rel = b - 256 if b > 127 else b
        vals['r8'] = '$%04X' % ((pc + 2 + rel) & 0xFFFF)
        vals['r8s'] = '%+d' % rel
    elif extra == 2:
        w = rom[off + 1] | (rom[off + 2] << 8)
        vals['d16'] = '$%04X' % w
        vals['a16'] = '$%04X' % w
    return fmt % vals if vals else fmt, n


# ---------------------------------------------------------------- boundaries
BOUNDARY_WINDOW = 64


def boundary_votes(rom, at, window=BOUNDARY_WINDOW):
    """-> (lands_on, steps_over) for linear sweeps that run up to file offset `at`.

    A byte scan for an instruction cannot tell whether it found one: `01 CF 7E` reads as
    `ld bc,$7ECF` wherever it appears, including inside the OPERAND of the `ld [$CF01],a`
    that really starts one byte earlier. That is not hypothetical -- it shipped, and it
    corrupted the message system (see FINDINGS.md).

    The disambiguator is that LR35902 code self-synchronises: start a linear decode at
    almost any nearby byte and within a handful of instructions it converges on the real
    stream. So decode from every offset in the preceding `window` bytes and count how many
    sweeps land exactly ON `at` against how many step OVER it inside a longer instruction.
    Real sites come back near-unanimous one way or the other -- measured on this ROM's 41
    immediate references, the four contested sites vote 63/1, 1/63, 0/64 and 0/64.
    """
    on = over = 0
    for start in range(max(0, at - window), at):
        off = start
        while off < at:
            try:
                _, n = decode(rom, off, 0)
            except IndexError:
                n = 1
            off += n
        if off == at:
            on += 1
        else:
            over += 1
    return on, over


def is_instruction_start(rom, at, window=BOUNDARY_WINDOW):
    """True if `at` is where an instruction really begins, by majority of sweeps."""
    on, over = boundary_votes(rom, at, window)
    return on > over


def main():
    a = sys.argv[1:]
    rom = open(a[0], 'rb').read()
    off = int(a[1], 16)
    count = int(a[2], 16) if len(a) > 2 else 0x60
    if '--bank' in a:
        bank = int(a[a.index('--bank') + 1], 0)
        off = bank * 0x4000 + (off - (0x4000 if bank else 0))
    bank = off // 0x4000
    base = 0x4000 if bank else 0
    end = off + count
    while off < end:
        pc = off % 0x4000 + base
        try:
            txt, n = decode(rom, off, pc)
        except IndexError:
            break
        raw = rom[off:off + n].hex(' ')
        print('  %d:$%04X  %-9s %s' % (bank, pc, raw, txt))
        off += n


if __name__ == '__main__':
    main()
