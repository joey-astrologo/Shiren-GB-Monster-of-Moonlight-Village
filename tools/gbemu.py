#!/usr/bin/env python3
"""A deliberately tiny LR35902 interpreter, for testing ROM patches on the desktop.

This is not an emulator. There is no PPU, no timing, no interrupts. It exists so that a
hand-written patch can be RUN against a reference implementation before it ever reaches
hardware -- which is how tools/dte_rom.py's expander is checked against tools/dte.py.

It refuses to guess. Any opcode not explicitly implemented raises, so a patch cannot be
silently mis-executed into a passing test. Add opcodes as patches need them.

The memory map mirrors the cartridge: $0000-$3FFF is bank 0, $4000-$7FFF is whichever
bank was last selected by a write to $2000-$3FFF, and $8000 up is flat RAM. That is
enough to exercise a resident routine that maps a data bank over the caller's.
"""

Z_FLAG = 0x80
C_FLAG = 0x10

# `inc r` / `dec r` for the seven 8-bit registers. $34/$35 -- inc/dec [hl] -- are
# deliberately absent: nothing has needed them, and the point of this file is that an
# unimplemented opcode raises rather than being guessed at.
INC_DEC = {}
for _i, _name in enumerate(['b', 'c', 'd', 'e', 'h', 'l', None, 'a']):
    if _name is not None:
        INC_DEC[0x04 + _i * 8] = (_name, 1)
        INC_DEC[0x05 + _i * 8] = (_name, -1)


class Halt(Exception):
    """Raised when the routine under test returns past its entry frame."""


class Cpu:
    def __init__(self, banks, bank=1):
        """`banks` maps bank number -> bytes. Bank 0 must be present."""
        self.banks = {n: bytearray(b) for n, b in banks.items()}
        self.ram = bytearray(0x8000)          # $8000-$FFFF, flat
        self.bank = bank
        self.a = self.b = self.c = self.d = self.e = self.h = self.l = 0
        self.f = 0
        self.sp = 0xDFFF
        self.pc = 0
        self.ime = True
        self.steps = 0

    # ---- memory ----------------------------------------------------------------
    def read(self, addr):
        addr &= 0xFFFF
        if addr < 0x4000:
            return self.banks[0][addr]
        if addr < 0x8000:
            return self.banks[self.bank][addr - 0x4000]
        return self.ram[addr - 0x8000]

    def write(self, addr, val):
        addr &= 0xFFFF
        val &= 0xFF
        if 0x2000 <= addr < 0x4000:           # MBC3 ROM bank select
            self.bank = val or 1
            return
        if addr < 0x8000:
            raise RuntimeError('write to ROM at $%04X' % addr)
        self.ram[addr - 0x8000] = val

    # ---- helpers ---------------------------------------------------------------
    @property
    def de(self):
        return (self.d << 8) | self.e

    @de.setter
    def de(self, v):
        self.d, self.e = (v >> 8) & 0xFF, v & 0xFF

    @property
    def hl(self):
        return (self.h << 8) | self.l

    @hl.setter
    def hl(self, v):
        self.h, self.l = (v >> 8) & 0xFF, v & 0xFF

    def _push(self, v):
        self.sp = (self.sp - 2) & 0xFFFF
        self.ram[self.sp - 0x8000] = v & 0xFF
        self.ram[self.sp - 0x8000 + 1] = (v >> 8) & 0xFF

    def _pop(self):
        v = self.ram[self.sp - 0x8000] | (self.ram[self.sp - 0x8000 + 1] << 8)
        self.sp = (self.sp + 2) & 0xFFFF
        return v

    def _imm8(self):
        v = self.read(self.pc)
        self.pc += 1
        return v

    def _imm16(self):
        v = self.read(self.pc) | (self.read(self.pc + 1) << 8)
        self.pc += 2
        return v

    def _cond(self, op):
        """Condition encoded in bits 3-4 of a jr/jp/ret/call opcode."""
        return {0: not self.f & Z_FLAG, 1: bool(self.f & Z_FLAG),
                2: not self.f & C_FLAG, 3: bool(self.f & C_FLAG)}[(op >> 3) & 3]

    def _cp(self, n):
        self.f = (Z_FLAG if self.a == n else 0) | (C_FLAG if self.a < n else 0)

    # ---- the interpreter -------------------------------------------------------
    def step(self):
        self.steps += 1
        op = self.read(self.pc)
        self.pc += 1

        if op == 0xFE:                                        # cp n
            self._cp(self._imm8())
        elif op == 0xA7:                                      # and a
            self.f = Z_FLAG if self.a == 0 else 0             # clears carry
        elif op == 0x37:                                      # scf
            self.f = (self.f & Z_FLAG) | C_FLAG
        elif op == 0x18:                                      # jr n
            n = self._imm8()
            self.pc += n - 256 if n > 127 else n
        elif op in (0x20, 0x28, 0x30, 0x38):                  # jr cc,n
            n = self._imm8()
            if self._cond(op):
                self.pc += n - 256 if n > 127 else n
        elif op == 0xC3:                                      # jp nn
            self.pc = self._imm16()
        elif op in (0xC2, 0xCA, 0xD2, 0xDA):                  # jp cc,nn
            target = self._imm16()
            if self._cond(op):
                self.pc = target
        elif op == 0xCD:                                      # call nn
            target = self._imm16()
            self._push(self.pc)
            self.pc = target
        elif op == 0xD7:                                      # rst $10 -- the ROM's far call
            # `rst $10 / db index,bank`: map `bank`, call the routine its index table names
            # at ($4000 + index - 1, $4000 + index), then put the caller's bank back.
            #
            # Modelled as a nested run rather than a jump because that is what it does to
            # the REGISTERS, and the registers are the point: 0:$078D pops the caller's
            # af/bc/de/hl just before entering the callee, and the 0:$07D7 trampoline it
            # plants pushes af/hl/bc on the way back out while never touching de. So a far
            # call is transparent in both directions -- measured on the live ROM
            # 2026-07-31, see pool.py fact 4 -- and a callee may return a value in hl.
            index, bank = self._imm8(), self._imm8()
            saved, ret = self.bank, self.pc
            self.bank = bank
            base = 0x4000 + index - 1
            target = self.read(base) | (self.read(base + 1) << 8)
            self.call(target)
            self.bank, self.pc = saved, ret
        elif op == 0xE9:                                      # jp hl
            self.pc = self.hl
        elif op == 0xC9:                                      # ret
            self.pc = self._pop()
        elif op in (0xC0, 0xC8, 0xD0, 0xD8):                  # ret cc
            if self._cond(op):
                self.pc = self._pop()
        elif op == 0xE5:                                      # push hl
            self._push(self.hl)
        elif op == 0xE1:                                      # pop hl
            self.hl = self._pop()
        elif op == 0xF5:                                      # push af
            self._push((self.a << 8) | self.f)
        elif op == 0xF1:                                      # pop af
            v = self._pop()
            self.a, self.f = v >> 8, v & 0xF0
        elif op == 0xC5:                                      # push bc
            self._push((self.b << 8) | self.c)
        elif op == 0xC1:                                      # pop bc
            v = self._pop()
            self.b, self.c = v >> 8, v & 0xFF
        elif op == 0xD5:                                      # push de
            self._push(self.de)
        elif op == 0xD1:                                      # pop de
            self.de = self._pop()
        elif op == 0x3E:                                      # ld a,n
            self.a = self._imm8()
        elif op == 0x06:                                      # ld b,n
            self.b = self._imm8()
        elif op == 0x0E:                                      # ld c,n
            self.c = self._imm8()
        elif op == 0x26:                                      # ld h,n
            self.h = self._imm8()
        elif op == 0x2E:                                      # ld l,n
            self.l = self._imm8()
        elif op == 0x16:                                      # ld d,n
            self.d = self._imm8()
        elif op == 0x1E:                                      # ld e,n
            self.e = self._imm8()
        elif op == 0x21:                                      # ld hl,nn
            self.hl = self._imm16()
        elif op == 0x11:                                      # ld de,nn
            self.de = self._imm16()
        elif op == 0x01:                                      # ld bc,nn
            v = self._imm16()
            self.b, self.c = (v >> 8) & 0xFF, v & 0xFF
        elif op == 0x09:                                      # add hl,bc
            v = self.hl + ((self.b << 8) | self.c)
            self.f = (self.f & Z_FLAG) | (C_FLAG if v > 0xFFFF else 0)
            self.hl = v & 0xFFFF
        elif op == 0x19:                                      # add hl,de
            v = self.hl + self.de
            self.f = (self.f & Z_FLAG) | (C_FLAG if v > 0xFFFF else 0)
            self.hl = v & 0xFFFF
        elif op == 0x29:                                      # add hl,hl
            v = self.hl + self.hl
            self.f = (self.f & Z_FLAG) | (C_FLAG if v > 0xFFFF else 0)
            self.hl = v & 0xFFFF
        elif op == 0xFA:                                      # ld a,[nn]
            self.a = self.read(self._imm16())
        elif op == 0xEA:                                      # ld [nn],a
            self.write(self._imm16(), self.a)
        elif op == 0x02:                                      # ld [bc],a
            self.write((self.b << 8) | self.c, self.a)
        elif op in (0xC6, 0xD6, 0xCE, 0xDE, 0x87):            # add/sub/adc/sbc a,n, add a,a
            # $CE is how bank 13's dispatchers build a handler address: `add a,$CF /
            # ld l,a / ld a,0 / adc a,$68` carries the low byte into the high one. Both
            # composer tables ($4126 and $68CF) are reached that way, so anything that
            # runs a real string through the ROM's own staging loop needs it.
            n = self.a if op == 0x87 else self._imm8()
            cy = 1 if (op in (0xCE, 0xDE) and self.f & C_FLAG) else 0
            r = self.a - n - cy if op in (0xD6, 0xDE) else self.a + n + cy
            self.f = ((Z_FLAG if r & 0xFF == 0 else 0)
                      | (C_FLAG if (r < 0 or r > 0xFF) else 0))
            self.a = r & 0xFF
        elif 0x80 <= op <= 0xBF:                              # add/adc/sub/sbc/and/xor/or/cp a,r
            # The whole group rather than the two the cell map needs, for the reason the
            # CB block gives below: a one-opcode round trip every time a patch reaches for
            # `add a,l` is worse than eight lines here. H is not modelled anywhere in this
            # file, so it is not modelled here either.
            names = ['b', 'c', 'd', 'e', 'h', 'l', None, 'a']
            src = names[op & 7]
            n = self.read(self.hl) if src is None else getattr(self, src)
            kind, cy = (op >> 3) & 7, 1 if self.f & C_FLAG else 0
            if kind == 0:                                     # add
                r = self.a + n
            elif kind == 1:                                   # adc
                r = self.a + n + cy
            elif kind in (2, 7):                              # sub / cp
                r = self.a - n
            elif kind == 3:                                   # sbc
                r = self.a - n - cy
            elif kind == 4:                                   # and
                r = self.a & n
            elif kind == 5:                                   # xor
                r = self.a ^ n
            else:                                             # or
                r = self.a | n
            carry = (r < 0 or r > 0xFF) if kind in (0, 1, 2, 3, 7) else False
            self.f = (Z_FLAG if r & 0xFF == 0 else 0) | (C_FLAG if carry else 0)
            if kind != 7:                                     # cp discards the result
                self.a = r & 0xFF
        elif op == 0xE6:                                      # and n
            self.a &= self._imm8()
            self.f = Z_FLAG if self.a == 0 else 0             # clears carry
        elif op == 0xF6:                                      # or n
            self.a |= self._imm8()
            self.f = Z_FLAG if self.a == 0 else 0
        elif op == 0xCB:                                      # bit/res/set b,r
            # Only the three the pool redirect needs. `bit` writes Z and leaves carry --
            # tools/pool.py's dispatcher tests bit 6 then bit 7 of h with no reload in
            # between, so getting the flag half of this wrong would pass the copy test and
            # still route every string to the wrong bank.
            sub = self._imm8()
            names = ['b', 'c', 'd', 'e', 'h', 'l', None, 'a']
            name, n = names[sub & 7], (sub >> 3) & 7
            # `[hl]` is the one the help renderer needs: 13:$7E16 `bit 7,[hl]` is what
            # chooses table $554A over the $5537 fallback, so reloc_verify cannot drive
            # 13:$7E49 at all without it.
            v = self.read(self.hl) if name is None else getattr(self, name)
            if sub < 0x40:
                # The shift/rotate group, all eight of it. 13:$7E0D turns a table index
                # into a byte offset with `sla c / rl b`, so the help renderer cannot be
                # driven without it; doing the whole group rather than those two keeps the
                # next routine from being another one-opcode round trip. Carry out is the
                # bit that leaves, Z is set on a zero result -- as on hardware.
                kind, cy = (sub >> 3) & 7, 1 if self.f & C_FLAG else 0
                if kind == 0:                                 # rlc
                    out, v = v >> 7, ((v << 1) | (v >> 7)) & 0xFF
                elif kind == 1:                               # rrc
                    out, v = v & 1, ((v >> 1) | (v << 7)) & 0xFF
                elif kind == 2:                               # rl
                    out, v = v >> 7, ((v << 1) | cy) & 0xFF
                elif kind == 3:                               # rr
                    out, v = v & 1, (v >> 1) | (cy << 7)
                elif kind == 4:                               # sla
                    out, v = v >> 7, (v << 1) & 0xFF
                elif kind == 5:                               # sra
                    out, v = v & 1, (v >> 1) | (v & 0x80)
                elif kind == 6:                               # swap
                    out, v = 0, ((v << 4) | (v >> 4)) & 0xFF
                else:                                         # srl
                    out, v = v & 1, v >> 1
                self.f = (Z_FLAG if v == 0 else 0) | (C_FLAG if out else 0)
            elif sub < 0x80:                                  # bit n,r
                self.f = (self.f & C_FLAG) | (0 if v & (1 << n) else Z_FLAG)
                v = None
            elif sub < 0xC0:                                  # res n,r
                v = v & ~(1 << n) & 0xFF
            else:                                             # set n,r
                v = v | (1 << n)
            if v is not None:
                self.write(self.hl, v) if name is None else setattr(self, name, v)
        elif op == 0x12:                                      # ld [de],a
            self.write(self.de, self.a)
        elif op == 0x1A:                                      # ld a,[de]
            self.a = self.read(self.de)
        elif op == 0x0A:                                      # ld a,[bc]
            self.a = self.read((self.b << 8) | self.c)
        elif op == 0x13:                                      # inc de
            self.de = (self.de + 1) & 0xFFFF
        elif op == 0x03:                                      # inc bc
            self.c = (self.c + 1) & 0xFF
            if self.c == 0:
                self.b = (self.b + 1) & 0xFF
        elif op == 0x0B:                                      # dec bc
            self.c = (self.c - 1) & 0xFF
            if self.c == 0xFF:
                self.b = (self.b - 1) & 0xFF
        elif op == 0x17:                                      # rla
            # rotates THROUGH carry, and clears Z -- unlike the CB-prefixed `rl a`,
            # which sets Z. dte_box relies on the carry and on nothing else.
            carry = 1 if self.f & C_FLAG else 0
            self.f = C_FLAG if self.a & 0x80 else 0
            self.a = ((self.a << 1) | carry) & 0xFF
        elif op == 0x23:                                      # inc hl
            self.hl = (self.hl + 1) & 0xFFFF
        elif op == 0x2B:                                      # dec hl
            self.hl = (self.hl - 1) & 0xFFFF
        elif op == 0x2A:                                      # ld a,[hl+]
            self.a = self.read(self.hl)
            self.hl = (self.hl + 1) & 0xFFFF
        elif op == 0x22:                                      # ld [hl+],a
            self.write(self.hl, self.a)
            self.hl = (self.hl + 1) & 0xFFFF
        elif op in INC_DEC:                                   # inc r / dec r
            # H is not modelled -- no patch in this ROM tests it, and the four
            # hand-written cases this replaced did not model it either.
            name, delta = INC_DEC[op]
            v = (getattr(self, name) + delta) & 0xFF
            setattr(self, name, v)
            self.f = (self.f & C_FLAG) | (Z_FLAG if v == 0 else 0)
        elif op in (0x34, 0x35):                              # inc [hl] / dec [hl]
            # Needed by the composer's own line-break handlers: $EF (`<br>`) at 13:$6A6E
            # does `inc [$CF05]` to count the line. Running a real string through the
            # staging loop reaches it, which is what these two were waiting for.
            v = (self.read(self.hl) + (1 if op == 0x34 else -1)) & 0xFF
            self.write(self.hl, v)
            self.f = (self.f & C_FLAG) | (Z_FLAG if v == 0 else 0)
        elif op == 0xF3:                                      # di
            self.ime = False
        elif op == 0xFB:                                      # ei
            self.ime = True
        elif op == 0x00:                                      # nop
            pass
        elif 0x40 <= op <= 0x7F and op != 0x76:               # ld r,r'
            names = ['b', 'c', 'd', 'e', 'h', 'l', None, 'a']
            dst, src = names[(op >> 3) & 7], names[op & 7]
            val = self.read(self.hl) if src is None else getattr(self, src)
            if dst is None:
                self.write(self.hl, val)
            else:
                setattr(self, dst, val)
        else:
            raise NotImplementedError('opcode $%02X at $%04X' % (op, self.pc - 1))

    def call(self, addr, limit=100000):
        """Run `addr` as a subroutine and return when it rets past its own frame."""
        sentinel = 0x7000
        self._push(sentinel)
        self.pc = addr
        floor = self.sp
        while True:
            if self.pc == sentinel:
                return
            if self.sp > floor:
                raise RuntimeError('stack underflow: routine popped past its frame')
            self.step()
            if self.steps > limit:
                raise RuntimeError('did not return within %d steps' % limit)

    def max_stack_depth(self, base):
        return base - self.sp
