#!/usr/bin/env python3
"""Verify the English wait card through the real supplied Log-3 Continue route."""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import dotfont                                                    # noqa: E402
from gbrun import PRESS_FRAMES, _import_pyboy                     # noqa: E402
from gitaninfospill import SCRIPT, RAM                            # noqa: E402
import waitcard                                                   # noqa: E402


CAPTURE_FRAME = 700
VRAM_TILES = 0x8010
MAP_BASE = 0x9800
SCREEN_MAP_ROW = 9


def run(rom, ram, png=None):
    PyBoy = _import_pyboy()
    font = dotfont.load_approved()
    expected_tiles, placements = waitcard.render(font)
    problems = []
    with tempfile.TemporaryDirectory(prefix='waitcardspill-') as tmp:
        work = os.path.join(tmp, 'wait.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)
        for frame in range(CAPTURE_FRAME + 1):
            for button in SCRIPT.get(frame, ()):
                pb.button(button, PRESS_FRAMES)
            pb.tick()

        pb.memory[0xFF4F] = 0
        actual_tiles = bytes(pb.memory[VRAM_TILES:VRAM_TILES + waitcard.TILE_BYTES])
        if actual_tiles != expected_tiles:
            problems.append('%d/%d private tile bytes differ' %
                            (sum(a != b for a, b in zip(actual_tiles, expected_tiles)),
                             len(expected_tiles)))

        for row, column in waitcard.DAKUTEN:
            actual = pb.memory[MAP_BASE + (SCREEN_MAP_ROW + row) * 32 + column]
            if actual != 0:
                problems.append('dakuten cell (%d,%d) is $%02X, expected blank' %
                                (column, row, actual))
        for source_row, column, ids in placements:
            row = SCREEN_MAP_ROW + source_row
            actual = bytes(pb.memory[MAP_BASE + row * 32 + column:
                                     MAP_BASE + row * 32 + column + len(ids)])
            if actual != bytes(ids):
                problems.append('line row %d tile IDs are %s, expected %s' %
                                (row, actual.hex(), bytes(ids).hex()))
        if png:
            pb.screen.image.save(png)
            print('waitcardspill: wrote %s' % png)
        pb.stop(save=False)

    print('waitcardspill: real Log-3 Continue frame %d; %d/%d private bytes exact; '
          'two dakuten cells blank; %d problem(s)' %
          (CAPTURE_FRAME, len(expected_tiles), len(expected_tiles), len(problems)))
    for problem in problems:
        print('  ' + problem)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('waitcardspill: missing ' + path)
    return run(args.rom, args.ram, args.png)


if __name__ == '__main__':
    raise SystemExit(main())
