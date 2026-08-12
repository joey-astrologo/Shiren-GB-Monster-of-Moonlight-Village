#!/usr/bin/env python3
"""Fresh-cart regression for the Moonlight Village arrival-card raster.

The card exists for only a short interval after name confirmation, so an end-state smoke
test cannot see it. This drives the deterministic blank-cartridge New Log route, samples
the live card, and requires all 1,024 VRAM bytes plus the native even/odd rows, new third
row and guarded blank row to be exact. The expected raster is the approved 160x144
Moonlight Village reference embedded in the source asset.

usage: markerspill.py ROM [--png FILE]
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import dotfont                                                    # noqa: E402
import markers                                                    # noqa: E402
from gbrun import _import_pyboy, PRESS_FRAMES                     # noqa: E402
from namerun import END_COL, FIRST, NAV_FRESH, STEP, WHERE        # noqa: E402


NAME = 'Shiren'
CARD_DELAY = 70


def run(rom, png=None):
    PyBoy = _import_pyboy()
    with tempfile.TemporaryDirectory(prefix='markerspill-') as tmp:
        work = os.path.join(tmp, 'fresh.gb')
        shutil.copyfile(rom, work)
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)

        steps = [WHERE[ch] + (None,) for ch in NAME] + [(0, None, END_COL)]
        end_at = FIRST + STEP * len(steps)
        card_at = end_at + CARD_DELAY
        fade_at = (card_at - 6, card_at - 3, card_at)
        fade_images = {}
        for frame in range(card_at + 1):
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
            pb.tick()
            if frame in fade_at:
                fade_images[frame] = pb.screen.image.convert('L').tobytes()

        actual = bytes(pb.memory[0x8800:0x8C00])
        upper = bytes(pb.memory[0x9900:0x9914])
        lower = bytes(pb.memory[0x9920:0x9934])
        third = bytes(pb.memory[0x9940:0x9954])
        blank = bytes(pb.memory[0x9960:0x9974])
        lcdc = pb.memory[0xFF40]
        if png:
            pb.screen.image.save(png)
        pb.stop(save=False)

    expected = markers.render_strip(dotfont.load_approved())
    want_upper = bytes(range(0x80, 0xA8, 2))
    want_lower = bytes(range(0x81, 0xA8, 2))
    want_third = bytes(range(markers.THIRD_ROW_TILE,
                             markers.THIRD_ROW_TILE + 20))
    want_blank = bytes((markers.BLANK_ROW_TILE,)) * 20
    problems = []
    if actual != expected:
        diffs = sum(a != b for a, b in zip(actual, expected))
        problems.append('%d/%d village-card VRAM byte(s) differ' % (diffs, len(expected)))
    if upper != want_upper:
        problems.append('upper tilemap row is %s, expected %s'
                        % (upper.hex(' '), want_upper.hex(' ')))
    if lower != want_lower:
        problems.append('lower tilemap row is %s, expected %s'
                        % (lower.hex(' '), want_lower.hex(' ')))
    if third != want_third:
        problems.append('third tilemap row is %s, expected %s'
                        % (third.hex(' '), want_third.hex(' ')))
    if blank != want_blank:
        problems.append('blank guard row is %s, expected %s'
                        % (blank.hex(' '), want_blank.hex(' ')))
    final_ink = bytes(value != 255 for value in fade_images[card_at])
    if any(bytes(value != 255 for value in fade_images[frame]) != final_ink
           for frame in fade_at[:-1]):
        problems.append('fade exposes a partial or unrelated raster before the final card')

    maps_exact = upper == want_upper and lower == want_lower \
        and third == want_third and blank == want_blank
    print('markerspill: frame %d LCDC=$%02X; %d/%d raster bytes exact; '
          'three-row tilemap + blank guard %s; three-phase fade clean; %d problem(s)'
          % (card_at, lcdc, sum(a == b for a, b in zip(actual, expected)),
             len(expected), 'exact' if maps_exact else 'DIFFERS', len(problems)))
    for problem in problems:
        print('  ' + problem)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--png')
    args = parser.parse_args()
    if not os.path.exists(args.rom):
        raise SystemExit('markerspill: missing %s' % args.rom)
    raise SystemExit(run(args.rom, args.png))


if __name__ == '__main__':
    main()
