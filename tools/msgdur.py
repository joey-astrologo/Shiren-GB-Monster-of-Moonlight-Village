#!/usr/bin/env python3
"""Measure how long dungeon messages STAY ON SCREEN, headlessly.

This is the check the project did not have. `--compare` samples one frame and a tile
count cannot see a duration, so "dungeon messages expire too fast to read" was detectable
only by Joey playing. It is measurable after all, because of how the ROM draws them:

**The message box is the WINDOW layer, and its height is WY (`$FF4A`).** In the dungeon
the window is parked at WY 136 -- one row, the status bar. A message slides it up to
WY 99 over three frames, holds it there, and slides it back. So the message's LIFETIME is
the number of frames WY stays above the status-bar line, and that is a number two builds
can be compared on.

`tilemap_background` cannot see this at all (terrain fills every row) and neither can the
window tilemap: the text is written once and left there, and what changes is WY.

    msgdur.py <rom> [<rom> ...] [--frames N] [--seed N]

Prints every message interval and a summary per ROM. Reaching a message needs real
gameplay -- a fixed walk down a corridor produces none -- so the input is a SEEDED random
walk weighted toward movement and attacks, with no `start`/`select` (those open the menu,
and the quit prompt then eats the rest of the run). The seed makes it repeatable, which is
what lets two builds be compared at all.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# WY when the window is parked at the status bar. Anything smaller means the box is open.
CLOSED_WY = 136
# WY 123 is the first frame of the slide; treat anything below the parked value as open.
OPEN_MAX_WY = CLOSED_WY - 1

# Movement and attack only. `start` opens the in-game menu and `a` then selects Quit,
# after which the run measures the save prompt instead of the dungeon.
SEQ = ['right', 'down', 'left', 'up', 'a', 'right', 'down', 'a']


def _import_pyboy():
    """See tools/gbrun.py: tools/dis.py shadows the stdlib `dis` and pyboy imports it."""
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path[:] = [p for p in sys.path if os.path.abspath(p or '.') != here]
    mod = sys.modules.get('dis')
    if mod is not None and not hasattr(mod, 'COMPILER_FLAG_NAMES'):
        del sys.modules['dis']
    import pyboy
    return pyboy.PyBoy


def measure(rom, state, frames, seed, step, quiet=False):
    """-> [(start-frame, frames-open, minimum-WY)] for every message box in the run."""
    import random
    PyBoy = _import_pyboy()
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(state, 'rb') as f:
        pb.load_state(f)

    rng = random.Random(seed)
    spans, start, low = [], None, 255
    for i in range(frames):
        if i >= 60 and (i - 60) % step == 0:
            # pyboy's default press is one frame, which this ROM does not always see.
            # Five frames is what makes a scripted walk actually walk -- gbrun.py's
            # --press does NOT do this, which is why its traces came back empty.
            pb.button(rng.choice(SEQ), 5)
        pb.tick()
        wy = pb.memory[0xFF4A]
        if wy <= OPEN_MAX_WY:
            if start is None:
                start, low = i, wy
            low = min(low, wy)
        elif start is not None:
            spans.append((start, i - start, low))
            start, low = None, 255
    if start is not None:
        spans.append((start, frames - start, low))
    pb.stop(save=False)
    return spans


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('roms', nargs='+')
    ap.add_argument('--state', default=os.path.join(ROOT, 'saves/dungeon.state'))
    ap.add_argument('--frames', type=int, default=20000)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--step', type=int, default=12, help='frames between button presses')
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    for rom in args.roms:
        spans = measure(rom, args.state, args.frames, args.seed, args.step)
        # The slide itself is 3 frames each way; a span shorter than that is the box
        # opening and closing on the same message, not a message anyone could read.
        held = [n for _, n, _ in spans]
        print('%-24s %3d message boxes' % (os.path.basename(rom), len(spans)))
        if args.verbose:
            for at, n, lo in spans:
                print('    frame %6d  open %4d frames  (min WY %d)' % (at, n, lo))
        if held:
            held_sorted = sorted(held)
            print('    frames open: total %d  median %d  min %d  max %d'
                  % (sum(held), held_sorted[len(held_sorted) // 2],
                     held_sorted[0], held_sorted[-1]))


if __name__ == '__main__':
    main()
