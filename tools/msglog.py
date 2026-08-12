#!/usr/bin/env python3
"""Transcribe every line the COMPOSER draws during a run, with the frame it drew it on.

`gbrun.py --trace` says WHICH loop ran; this says WHAT it read. Hooks the two composer
loops, decodes the source string through tools/codec.py, and prints a transcript -- which
is how the seeded dungeon walk was shown to produce real combat messages
(`<var>から <cE4>ポイントのダメージをうけた`, `<var>をやっつけた`) rather than the menu
text an earlier button schedule had been measuring.

Use it to see what the message system actually composed, and pair it with
tools/msgdur.py, which measures how long each of those messages then STAYS on screen.

    msglog.py <rom> [--frames N] [--seed N] [--state S] [--all]

`13:$40D8` is the 18-cell loop (source in hl, a ROM string). `13:$6893` is the second
loop, hooked to bank 0, whose source is the WRAM buffer at $CF8F that the message queue
assembles at runtime -- a line logged there is text no static check can see.
"""
import argparse
import collections
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import codec                                    # before pyboy: see _import_pyboy

SITES = [(13, 0x40D8, '18cell'), (13, 0x6893, 'loop2')]


def _import_pyboy():
    """See tools/gbrun.py -- tools/dis.py shadows the stdlib `dis` that pyboy pulls in."""
    here = os.path.join(ROOT, 'tools')
    sys.path[:] = [p for p in sys.path
                   if os.path.abspath(p or '.') != os.path.abspath(here)]
    mod = sys.modules.get('dis')
    if mod is not None and not hasattr(mod, 'COMPILER_FLAG_NAMES'):
        del sys.modules['dis']
    import pyboy
    return pyboy.PyBoy


def show(raw):
    return ''.join(codec.CHARS.get(b, '<$%02X>' % b) for b in raw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('--state', default=os.path.join(ROOT, 'saves/dungeon.state'))
    ap.add_argument('--frames', type=int, default=20000)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--step', type=int, default=12)
    ap.add_argument('--all', action='store_true',
                    help='keep repeated redraws instead of collapsing them')
    args = ap.parse_args()

    import random
    PyBoy = _import_pyboy()
    pb = PyBoy(args.rom, window='null')
    pb.set_emulation_speed(0)
    with open(args.state, 'rb') as f:
        pb.load_state(f)

    frame = {'n': 0}
    log = []

    def reader(tag):
        def cb(ctx):
            hl = pb.register_file.HL
            out = bytearray()
            for i in range(64):
                b = pb.memory[(hl + i) & 0xFFFF]
                if b in (0x00, 0xFF):            # terminator, or an unwritten buffer byte
                    break
                out.append(b)
            log.append((frame['n'], tag, hl, bytes(out)))
        return cb

    for bank, addr, tag in SITES:
        pb.hook_register(bank, addr, reader(tag), None)

    # Movement and attacks only, held for 5 frames -- the schedule that actually fights.
    # See msgdur.SEQ: `start` opens the menu and the run ends up in the quit prompt.
    seq = ['right', 'down', 'left', 'up', 'a', 'right', 'down', 'a']
    rng = random.Random(args.seed)
    for i in range(args.frames):
        frame['n'] = i
        if i >= 60 and (i - 60) % args.step == 0:
            pb.button(rng.choice(seq), 5)
        pb.tick()
    pb.stop(save=False)

    seen, last = collections.Counter(), None
    for f, tag, hl, raw in log:
        key = (tag, hl, raw)
        seen[key] += 1
        if key == last and not args.all:
            continue
        last = key
        where = 'ROM' if hl < 0x8000 else 'WRAM'
        print('%6d  %-6s %-4s $%04X %3d  %s' % (f, tag, where, hl, len(raw), show(raw)))
    print('%d composer lines, %d distinct' % (len(log), len(seen)))


if __name__ == '__main__':
    main()
