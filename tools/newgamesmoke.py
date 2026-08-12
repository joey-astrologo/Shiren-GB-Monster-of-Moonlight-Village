#!/usr/bin/env python3
"""Fresh-cart smoke test for the complete New Log -> village transition.

This route is deliberately separate from save-backed menu tests.  The name6 patch copies
an 81-byte new-game record template only on a blank cartridge, so a battery that always
boots an existing save cannot detect damage to that template.  The 2026-08-08 rankings
uploader regression did exactly that: it replaced eight live trailing ``$FF`` bytes and
left the Japanese village-name card on screen forever.

The test drives the same deterministic picker route as ``namerun.py``, waits through the
intro transition, then requires the village's live sprite layer and a changing gameplay
screen after input.  The stuck title card remains pixel-identical, while the walkable
village animates and responds.  A temporary ROM copy guarantees blank cartridge RAM and
leaves the input ROM and its sidecar untouched.

usage: newgamesmoke.py ROM [--png FILE]
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from gbrun import _import_pyboy, PRESS_FRAMES                 # noqa: E402
from namerun import END_COL, FIRST, NAV_FRESH, STEP, WHERE    # noqa: E402


NAME = 'Shiren'
SETTLE = 1600
INPUT_SETTLE = 120


def visible_sprites(pb):
    """Return visible OAM records as (y, x, tile, attributes)."""
    out = []
    for at in range(0xFE00, 0xFEA0, 4):
        y, x, tile, attr = bytes(pb.memory[at:at + 4])
        if 16 <= y < 160 and 8 <= x < 168:
            out.append((y, x, tile, attr))
    return tuple(out)


def run(rom, png=None):
    PyBoy = _import_pyboy()
    with tempfile.TemporaryDirectory(prefix='newgamesmoke-') as tmp:
        work = os.path.join(tmp, 'fresh.gb')
        shutil.copyfile(rom, work)
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)

        steps = [WHERE[ch] + (None,) for ch in NAME] + [(0, None, END_COL)]
        end_at = FIRST + STEP * len(steps)
        arrival = end_at + SETTLE
        stop = arrival + INPUT_SETTLE
        pictures = set()
        states = set()

        for frame in range(stop):
            if FIRST <= frame < end_at:
                row, col, header = steps[(frame - FIRST) // STEP]
                pb.memory[0xC6F5] = row
                if col is not None:
                    pb.memory[0xC6F0] = col
                if header is not None:
                    pb.memory[0xC6F4] = header
                if (frame - FIRST) % STEP == 25:
                    pb.button('a', PRESS_FRAMES)
            elif frame in NAV_FRESH:
                pb.button(NAV_FRESH[frame], PRESS_FRAMES)
            elif frame == arrival:
                pb.button('left', PRESS_FRAMES)

            pb.tick()
            if frame >= arrival:
                pictures.add(bytes(pb.screen.ndarray))
                pc = pb.register_file.PC
                bank = 0 if pc < 0x4000 else pb.memory[0x4000]
                states.add((bank, pc))

        sprites = visible_sprites(pb)
        if png:
            pb.screen.image.save(png)
        pb.stop(save=False)

    problems = []
    if not sprites:
        problems.append('no visible OAM sprites after the village transition')
    if len(pictures) < 2:
        problems.append('the post-transition screen never changed after gameplay input')
    if len(states) < 2:
        problems.append('the CPU did not advance through distinct post-transition states')

    print('newgamesmoke: %d visible sprite(s), %d screen state(s), %d CPU state(s); '
          '%d problem(s)'
          % (len(sprites), len(pictures), len(states), len(problems)))
    for problem in problems:
        print('  ' + problem)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--png')
    args = parser.parse_args()
    if not os.path.exists(args.rom):
        raise SystemExit('newgamesmoke: missing %s' % args.rom)
    raise SystemExit(run(args.rom, args.png))


if __name__ == '__main__':
    main()
