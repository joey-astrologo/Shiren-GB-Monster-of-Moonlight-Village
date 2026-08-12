#!/usr/bin/env python3
"""Does the dialogue box ever draw a tile that belongs to a DIFFERENT line?

This is the check that would have caught the column-19 spill, and nothing else in the
battery could: every other check compares the build against a MODEL of the screen, and
the model did not know the tilemap existed. This one reads the tilemap the PPU reads.

WHAT IT WATCHES. The composer's three text lines are window-map rows 2, 4 and 6 at
`$9C40` / `$9C80` / `$9CC0`, and a line owns exactly 18 consecutive VRAM tiles out of
`$8A80` / `$8BA0` / `$8CC0` -- tilemap indices `$A8..$B9`, `$BA..$CB`, `$CC..$DD`. Two
invariants of the BOX follow, neither a property of any one string:

  * columns 0 and 19+ are box, so they hold no text tile at all;
  * a row's columns 1..18 are one CONSECUTIVE run: whatever tile column 1 holds, column
    c holds that plus c-1 (or the fill `$E2`, where the typewriter has not reached yet).

So a byte in `$A8..$DD` outside columns 1..18 is text drawn where no text can be, which
is what a player sees as a fragment of the next line hanging off the right-hand edge.

**WHICH TILES A ROW HOLDS IS NOT FIXED, and assuming it was is how the first draft of
this file cried wolf over the dungeon.** When the box is full the composer scrolls by
re-pointing the rows rather than moving pixels -- `13:$52A0` and `13:$5318` are the
rotated `(row, base)` pairs -- so row 2 legitimately holds `$CC..$DD` a third of the
time. The invariant is the RUN, not the base.

**`--no-vwf` FAILS THIS, and that is not a bug in the control.** A line owns 18 tiles
whatever the pen is, but production `script/en.tsv` may stage 30 Dot glyphs, and a
fixed-width pen would need up to 30 tiles in a row that has 18. The village composer
(`13:$687B`) has no cell budget to stop it -- the only bound is dte_rom's 49-byte guard at
`$CF38` -- so the control genuinely draws six characters past the end of the row. Measured
2026-08-05: 1901 spilling frames against the VWF build's 0. `--no-vwf` is a bisect control
for the RENDERER and is fed a script it was never sized for; do not read its failure here
as a regression, and do not "fix" it by rewrapping at 18.

WHY IT DRIVES THE GAME. The spill lives in the TYPEWRITER -- `13:$6B59` reveals one cell
a frame as the text types -- so it exists only in frames no static model produces, and a
screenshot of the finished box no longer shows it. It has to be watched while the box is
filling, which means playing.

    boxspill.py build/shiren_en.gb                 # every state, several seeds
    boxspill.py build/shiren_en.gb --seeds 2 --frames 1500

Exit 1 if any frame spills, or if no run ever opened the box -- a clean sweep that never
saw text is not evidence and does not get to pass.
"""
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gbrun import _import_pyboy, WALK_SEQ, PRESS_FRAMES

WINDOW = 0x9C00
ROWS = (0x9C40, 0x9C80, 0x9CC0)  # the three text rows (13:$6B43)
BASES = (0xA8, 0xBA, 0xCC)       # the three tile runs a row may be pointed at (13:$6B40)
CELLS = 18                       # tiles a line owns
FILL = 0xE2                      # the box's blank cell
TEXT_LO, TEXT_HI = 0xA8, 0xDD    # every tile the three lines own


def check(win):
    """`win` is the 512 bytes at $9C00. -> [(row, col, tile, why)] for illegal cells."""
    bad = []
    for row, addr in enumerate(ROWS):
        off = addr - WINDOW
        cells = win[off:off + 32]
        for col in list(range(0, 1)) + list(range(CELLS + 1, 32)):
            if TEXT_LO <= cells[col] <= TEXT_HI:
                bad.append((row, col, cells[col], 'text in a box column'))
        base = next((cells[c] - (c - 1) for c in range(1, CELLS + 1)
                     if TEXT_LO <= cells[c] <= TEXT_HI), None)
        if base is None:
            continue                                    # nothing typed into this row yet
        if base not in BASES:
            bad.append((row, 1, cells[1], 'run starts at $%02X, not a line base' % base))
            continue
        for col in range(1, CELLS + 1):
            if cells[col] != FILL and cells[col] != base + col - 1:
                bad.append((row, col, cells[col],
                            'breaks the run from $%02X' % base))
    return bad


def run(rom, state, seed, frames, quiet=False):
    PyBoy = _import_pyboy()
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    if state:
        with open(state, 'rb') as f:
            pb.load_state(f)
    rng = random.Random(seed)
    worst, hits, textframes = None, 0, 0
    for f in range(frames):
        if f >= 60 and (f - 60) % 12 == 0:
            pb.button(rng.choice(WALK_SEQ), PRESS_FRAMES)
        pb.tick()
        win = bytes(pb.memory[WINDOW:WINDOW + 0x200])
        if any(TEXT_LO <= win[a - WINDOW + c] <= TEXT_HI
               for a in ROWS for c in range(1, CELLS + 1)):
            textframes += 1
        bad = check(win)
        if bad:
            hits += 1
            if worst is None or len(bad) > len(worst[1]):
                worst = (f, bad)
    pb.stop(save=False)
    if not quiet:
        print('  %-30s %5d frames, text up in %4d, spilling in %4d'
              % ('%s seed %s' % (os.path.basename(state or 'boot'), seed),
                 frames, textframes, hits))
        if worst:
            for row, col, v, why in worst[1][:6]:
                print('      f%-6d row %d column %-2d tile $%02X  -- %s'
                      % (worst[0], row, col, v, why))
    return hits, textframes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('--states', default='saves/town.state,saves/dungeon.state')
    ap.add_argument('--seeds', type=int, default=4)
    ap.add_argument('--frames', type=int, default=3000)
    a = ap.parse_args()

    print('boxspill: %s' % a.rom)
    total = text = 0
    for st in [s for s in a.states.split(',') if os.path.exists(s)]:
        for seed in range(a.seeds):
            h, t = run(a.rom, st, seed, a.frames)
            total += h
            text += t
    if not text:
        raise SystemExit('boxspill: the box never opened in any run, so this measured '
                         'nothing. Check the save states before believing a pass.')
    print('boxspill: %d spilling frames out of %d with text on screen' % (total, text))
    raise SystemExit(1 if total else 0)


if __name__ == '__main__':
    main()
