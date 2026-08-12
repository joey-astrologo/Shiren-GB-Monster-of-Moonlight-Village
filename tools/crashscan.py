#!/usr/bin/env python3
"""Detect a HALT headlessly: does this build crash during real play?

The gap this fills. `gbrun.py --compare` samples one frame, so it cannot see a crash that
happens later; `msgdur.py` measures how long a message stays up, and a crashed ROM looks
to it like a message that stayed up forever -- which is exactly how a real crash was once
recorded here as "walk divergence". Neither of them looks at the CPU.

The signal is the DMG's own failure mode: an unmapped or blank read returns $FF, `$FF` is
`rst $38`, and $0038 is itself $FF, so the CPU recurses there until the stack is gone. So
`PC == $0038` is a crash, full stop, and it is visible by sampling PC once a frame.

    crashscan.py <rom> [<rom> ...] [--seeds N] [--frames N] [--state S] [--stack]

`--stack` dumps SP, the return addresses on the stack and the recent PC history at the
moment of the crash, which is what names the routine that jumped into nothing. That dump
is what identified the cross-bank message-queue references: bank 13 was mapped, the stack
held `$00E7` (inside the relocated loop2) and `$68xx` (bank 13's message reader), and the
death message had been repointed out from under `5:$44B8`.

DO NOT hook $0038 instead. pyboy hangs once the ROM is spinning there -- see HANDOFF.md
TRAPS, "pyboy hooks are not free instrumentation". Sampling is cheap and just as reliable.

Reaching a crash needs real gameplay, so the input is the same seeded random walk
`msgdur.py` uses. ONE seed proves nothing: of twelve seeds only two reached the death that
crashed. Sweep them.
"""
import argparse
import collections
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SEQ = ['right', 'down', 'left', 'up', 'a', 'right', 'down', 'a']
WINDOW = 240              # frames of PC history kept for the spin test and the dump


def _import_pyboy():
    """See tools/gbrun.py: tools/dis.py shadows the stdlib `dis` that pyboy imports."""
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path[:] = [p for p in sys.path if os.path.abspath(p or '.') != here]
    mod = sys.modules.get('dis')
    if mod is not None and not hasattr(mod, 'COMPILER_FLAG_NAMES'):
        del sys.modules['dis']
    import pyboy
    return pyboy.PyBoy


def label(pc):
    """The resident addresses worth naming, so a dump reads as prose."""
    if 0x0062 <= pc <= 0x00FF:
        return '  <- DTE expander / loop2 / dte_box'
    if 0x3FEC <= pc <= 0x3FFF:
        return '  <- dte_box_hi (bank 0 tail)'
    if pc == 0x0038:
        return '  <- rst $38 (executing $FF)'
    if pc == 0x028B:
        return '  <- message-queue push'
    return ''


def scan(rom, state, frames, seed, step, want_stack):
    """-> None if healthy, else a dict describing the halt."""
    import random
    PyBoy = _import_pyboy()
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(state, 'rb') as f:
        pb.load_state(f)

    rng = random.Random(seed)
    hist = collections.deque(maxlen=WINDOW)
    out = None
    for i in range(frames):
        if i >= 60 and (i - 60) % step == 0:
            pb.button(rng.choice(SEQ), 5)      # 5 frames: a 1-frame press is not seen
        pb.tick()
        pc = pb.register_file.PC
        hist.append((i, pc))
        if pc == 0x0038:
            out = {'why': 'PC at $0038 -- executing $FF (rst $38 recursion)', 'frame': i}
        elif 0x8000 <= pc < 0xA000:
            out = {'why': 'PC in VRAM -- execution left the ROM', 'frame': i}
        elif len(hist) == WINDOW:
            top, n = collections.Counter(p for _, p in hist).most_common(1)[0]
            if n > WINDOW - 40:
                out = {'why': 'PC pinned at $%04X for %d of %d frames -- stuck loop'
                              % (top, n, WINDOW), 'frame': i}
        if out:
            out['pc'] = pc
            out['sp'] = pb.register_file.SP
            out['bank'] = pb.memory[0x4000]
            out['lcdc'] = pb.memory[0xFF40]
            if want_stack:
                sp = out['sp']
                out['stack'] = [pb.memory[sp + k] | (pb.memory[sp + k + 1] << 8)
                                for k in range(0, 24, 2) if sp + k + 1 <= 0xFFFE]
                seen = []
                for f, p in hist:
                    if not seen or seen[-1][1] != p:
                        seen.append((f, p))
                out['hist'] = seen[-16:]
            break
    pb.stop(save=False)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('roms', nargs='+')
    ap.add_argument('--state', default=os.path.join(ROOT, 'saves/dungeon.state'))
    ap.add_argument('--frames', type=int, default=20000)
    ap.add_argument('--seeds', type=int, default=8)
    ap.add_argument('--step', type=int, default=12)
    ap.add_argument('--stack', action='store_true', help='dump SP, stack and PC history')
    args = ap.parse_args()

    bad = 0
    for rom in args.roms:
        name = os.path.basename(rom)
        for seed in range(1, args.seeds + 1):
            r = scan(rom, args.state, args.frames, seed, args.step, args.stack)
            if r is None:
                print('%-22s seed %-3d OK' % (name, seed))
                continue
            bad += 1
            print('%-22s seed %-3d HALT at frame %d: %s'
                  % (name, seed, r['frame'], r['why']))
            print('    PC $%04X   SP $%04X   bank %d mapped   LCDC $%02X (LCD %s)'
                  % (r['pc'], r['sp'], r['bank'], r['lcdc'],
                     'ON' if r['lcdc'] & 0x80 else 'OFF'))
            if args.stack:
                print('    stack, newest first (return addresses):')
                for k, v in enumerate(r['stack']):
                    print('      [SP+%2d] $%04X%s' % (k * 2, v, label(v)))
                print('    recent distinct PCs:')
                for f, p in r['hist']:
                    print('      frame %6d  $%04X%s' % (f, p, label(p)))
    print()
    print('%d halt(s) across %d rom(s) x %d seed(s)'
          % (bad, len(args.roms), args.seeds))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
