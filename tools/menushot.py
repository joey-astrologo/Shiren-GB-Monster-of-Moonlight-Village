#!/usr/bin/env python3
"""Photograph any of bank 4's 35 menu screens by forcing its dispatcher index.

Same technique as boxscan.py, generalised: `4:$48AA` takes a screen index in `a` and
indexes a 35-entry table at `4:$48C3`. Hooking it and rewriting `a` makes the REAL
routine draw the REAL screen through the REAL drawer -- only the navigation is synthetic.
See the memory `shiren-gb-reaching-any-screen`: this is preferred to writing more button
scripts, and strongly preferred to weakening a check because a screen is hard to reach.

    menushot.py <rom> --index 27 --png out.png
    menushot.py <rom> --sweep --out build/menusweep     # all 35, to find the one you want

A forced screen still exercises the real drawer, so a white screen or a cascade shows up
here exactly as it would in play.
"""
import argparse
import os
import sys


def _import_pyboy():
    """pyboy imports the stdlib `dis`; tools/dis.py is this project's disassembler."""
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path[:] = [p for p in sys.path if os.path.abspath(p or '.') != here]
    m = sys.modules.get('dis')
    if m is not None and not hasattr(m, 'COMPILER_FLAG_NAMES'):
        del sys.modules['dis']
    import pyboy
    return pyboy.PyBoy


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISPATCH = 0x48AA               # bank 4; `a` is the screen index
DISPATCH_BANK = 4
TABLE_LEN = 35


def shot(PyBoy, rom, state, index, frames, settle, png):
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(state, 'rb') as f:
        pb.load_state(f)

    fired = {'n': 0}

    def at_dispatch():
        # Only the FIRST arrival is rewritten. The dispatcher is re-entered while the
        # screen is up (cursor moves re-draw through it), and forcing the index every
        # time would freeze the screen on its first frame instead of letting it settle.
        if fired['n'] == 0 and pb.memory[0xFF00 + 0] is not None:
            pass
        fired['n'] += 1
        if fired['n'] == 1:
            pb.register_file.A = index

    pb.hook_register(DISPATCH_BANK, DISPATCH, lambda _ctx: at_dispatch(), None)

    # Open the menu: B clears whatever box is up, A opens the in-dungeon menu.
    for i in range(frames):
        if i == 60:
            pb.button('b')
        if i == 160:
            pb.button('a')
        pb.tick()
    for _ in range(settle):
        pb.tick()
    if png:
        pb.screen.image.save(png)
    hit = fired['n']
    pb.stop(save=False)
    return hit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('--state', default=os.path.join(ROOT, 'saves/dungeon.state'))
    ap.add_argument('--index', type=int, default=None)
    ap.add_argument('--sweep', action='store_true', help='every index, one PNG each')
    ap.add_argument('--out', default=os.path.join(ROOT, 'build/menusweep'))
    ap.add_argument('--frames', type=int, default=300)
    ap.add_argument('--settle', type=int, default=40)
    ap.add_argument('--png')
    a = ap.parse_args()

    PyBoy = _import_pyboy()
    if a.sweep:
        os.makedirs(a.out, exist_ok=True)
        for i in range(TABLE_LEN):
            p = os.path.join(a.out, 'screen%02d.png' % i)
            n = shot(PyBoy, a.rom, a.state, i, a.frames, a.settle, p)
            print('index %2d  dispatcher hit %d time(s) -> %s' % (i, n, p))
    else:
        if a.index is None:
            raise SystemExit('give --index N or --sweep')
        n = shot(PyBoy, a.rom, a.state, a.index, a.frames, a.settle, a.png)
        print('index %d  dispatcher hit %d time(s)%s'
              % (a.index, n, ' -> %s' % a.png if a.png else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
