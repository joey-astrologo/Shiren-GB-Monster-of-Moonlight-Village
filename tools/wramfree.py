#!/usr/bin/env python3
"""Is a WRAM run the game's or ours? Two proofs, both against game-only code.

Written for menuvwf's scratch run $C0CC-$C0D6 (the bytes after the $C006 queue's
third slot), and the verdict of record, 2026-08-06: 71 raw pair hits, 0 real
references (the one opcode+boundary survivor, 19:$5A26 `ld [$C0D4],sp`, sits in a
graphics-mask data bank between nonsense "instructions"), and 0 dynamic writes.

1. STATIC: every 2-byte little-endian value in the BASE rom that lands in the run,
   then opcode + dis.py boundary-vote filtering. A pair hit only counts if the byte
   before it is a 16-bit-operand opcode AND an instruction really starts there —
   that is what separates `call $3FC0` (opcode CD misread as an operand low byte)
   from a real `ld a,[$C0CD]`. Survivors are listed for judgement, not auto-failed:
   the voter can still be fooled by data, so read the neighbourhood.
2. DYNAMIC: per-frame watch on the --no-menuvwf CONTROL build (game code only)
   across: dungeon menu open/navigate/action-menu/close, seeded town walks
   (dialogue), seeded dungeon walks, and every one of bank 4's 35 forced menu
   screens (menushot's dispatcher trick — shops included). Any byte that ever
   changes is reported with the frame and scenario.

usage: wramfree.py [--lo C0CC] [--hi C0D6]
"""
import os, sys, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.chdir(ROOT)

from gbrun import _import_pyboy, WALK_SEQ, PRESS_FRAMES

LO, HI = 0xC0CC, 0xC0D6          # inclusive; --lo/--hi override
CONTROL = 'build/nomenuvwf.gb'
BASE = 'build/_base_expanded.gb'

if '--lo' in sys.argv:
    LO = int(sys.argv[sys.argv.index('--lo') + 1], 16)
if '--hi' in sys.argv:
    HI = int(sys.argv[sys.argv.index('--hi') + 1], 16)


def static_scan():
    """A pair hit only counts if the byte before it is a 16-bit-operand opcode AND
    dis.py's boundary voter says an instruction really starts there. That is the
    method that separates `call $3FC0` (opcode CD misread as an operand low byte)
    from a real `ld a,[$C0CD]`."""
    import dis as gbdis
    OP16 = {0x01, 0x08, 0x11, 0x21, 0x31,           # ld rr,nn / ld [nn],sp
            0xC2, 0xC3, 0xC4, 0xCA, 0xCC, 0xCD,     # jp/call (a WRAM target would
            0xD2, 0xD4, 0xDA, 0xDC,                  #   be a reference too)
            0xEA, 0xFA}                              # ld [nn],a / ld a,[nn]
    rom = open(BASE, 'rb').read()
    raw = confirmed = 0
    for i in range(1, len(rom) - 1):
        v = rom[i] | (rom[i + 1] << 8)
        if not LO <= v <= HI:
            continue
        raw += 1
        if rom[i - 1] not in OP16:
            continue
        if not gbdis.is_instruction_start(rom, i - 1):
            continue
        confirmed += 1
        bank = (i - 1) // 0x4000
        addr = ((i - 1) % 0x4000) + (0x4000 if bank else 0)
        txt, n = gbdis.decode(rom, i - 1, addr)
        print('   REAL REFERENCE %2d:$%04X  %s' % (bank, addr, txt))
    print('STATIC: %d pair hit(s), %d survive opcode+boundary voting'
          % (raw, confirmed))
    return confirmed


class Watch:
    def __init__(self, rom, state=None):
        PyBoy = _import_pyboy()
        self.pb = PyBoy(rom, window='null')
        self.pb.set_emulation_speed(0)
        if state:
            with open(state, 'rb') as f:
                self.pb.load_state(f)
        else:
            for _ in range(400):
                self.pb.tick()
        self.base = bytes(self.pb.memory[LO:HI + 1])
        self.events = []
        self.frame = 0

    def tick(self, n, tag):
        for _ in range(n):
            self.pb.tick()
            self.frame += 1
            cur = bytes(self.pb.memory[LO:HI + 1])
            if cur != self.base:
                for i, (a, b) in enumerate(zip(self.base, cur)):
                    if a != b:
                        self.events.append((tag, self.frame, LO + i, a, b))
                self.base = cur

    def press(self, btn, tag, settle=40):
        self.pb.button(btn, PRESS_FRAMES)
        self.tick(settle, tag)

    def stop(self):
        self.pb.stop(save=False)
        return self.events


def dungeon_menu():
    w = Watch(CONTROL, 'saves/dungeon.state')
    w.tick(60, 'dungeon idle')
    w.press('b', 'menu open')
    w.press('a', 'item list open')
    for _ in range(4):
        w.press('down', 'item cursor')
    w.press('a', 'action menu')
    w.press('b', 'action close/redraw')
    w.press('b', 'item close')
    w.press('b', 'menu close')
    w.tick(120, 'dungeon after')
    return w.stop()


def seeded(state, seed, frames, tag):
    w = Watch(CONTROL, state)
    rng = random.Random(seed)
    n = 0
    while n < frames:
        w.pb.button(rng.choice(WALK_SEQ), PRESS_FRAMES)
        w.tick(30, tag)
        n += 30
    return w.stop()


def forced_screens():
    """menushot's trick: force each bank-4 dispatcher index, real drawer draws it."""
    sys.path.insert(0, os.path.join(ROOT, 'tools'))   # _import_pyboy strips it
    import menushot
    events = []
    PyBoy = _import_pyboy()
    for idx in range(menushot.TABLE_LEN):
        pb = PyBoy(CONTROL, window='null')
        pb.set_emulation_speed(0)
        with open('saves/dungeon.state', 'rb') as f:
            pb.load_state(f)
        base = bytes(pb.memory[LO:HI + 1])
        fired = {'n': 0}

        def at_dispatch(idx=idx, pb=pb, fired=fired):
            fired['n'] += 1
            if fired['n'] == 1:
                pb.register_file.A = idx

        pb.hook_register(menushot.DISPATCH_BANK, menushot.DISPATCH,
                         lambda _ctx, cb=at_dispatch: cb(), None)
        for f in range(340):
            if f == 60:
                pb.button('b')
            if f == 160:
                pb.button('a')
            pb.tick()
            cur = bytes(pb.memory[LO:HI + 1])
            if cur != base:
                for i, (a, b) in enumerate(zip(base, cur)):
                    if a != b:
                        events.append(('forced screen %d' % idx, f, LO + i, a, b))
                base = cur
        pb.stop(save=False)
    return events


def main():
    static_scan()
    print()
    all_events = []
    all_events += dungeon_menu()
    print('DYNAMIC dungeon menu script: %d event(s)' % len(all_events))
    for s in range(4):
        all_events += seeded('saves/town.state', s, 1500, 'town walk seed %d' % s)
    print('DYNAMIC + town walks: %d event(s) total' % len(all_events))
    for s in range(4):
        all_events += seeded('saves/dungeon.state', s, 1500, 'dungeon walk seed %d' % s)
    print('DYNAMIC + dungeon walks: %d event(s) total' % len(all_events))
    all_events += forced_screens()
    print('DYNAMIC + 35 forced menu screens: %d event(s) total' % len(all_events))
    for tag, f, addr, a, b in all_events:
        print('   %-24s frame %-5d $%04X: $%02X -> $%02X' % (tag, f, addr, a, b))
    if not all_events:
        print('\nOK: the game never wrote $%04X-$%04X in any scenario.' % (LO, HI))
    else:
        print('\nNOT free: %d write(s) above.' % len(all_events))


if __name__ == '__main__':
    main()
