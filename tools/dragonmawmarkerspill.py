#!/usr/bin/env python3
"""Replay and center-check the real floor-19 Dragon's Maw arrival card.

``saves/shiren_en_log_1_dragons_maw.srm`` opens Log 1 directly on floor 19.  Besides its
item coverage, this makes it the authoritative route for the widest numbered arrival
label.  The test boots the log normally, requires selector 5 / floor 19 at the native
card entry, compares all three uploaded tile rows and verifies the visible ink occupies
x=5..154. Those exact 5/5px source margins guard the approved raster placement.

usage: dragonmawmarkerspill.py ROM [--ram FILE] [--png FILE]
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gbrun import _import_pyboy, PRESS_FRAMES                    # noqa: E402
import markers                                                    # noqa: E402


CARD_ENTRY = (31, 0x6134)
SELECTOR = 5
FLOOR = 19
CAPTURE_AT = 590
FRAMES = 680
EXPECTED_X_BOUNDS = (5, 154)
BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a',
}


def _ink_bounds(raster):
    points = []
    for tile_x in range(20):
        tile_numbers = (tile_x * 2, tile_x * 2 + 1, 40 + tile_x)
        for tile_y, tile in enumerate(tile_numbers):
            source = raster[tile * 16:(tile + 1) * 16]
            for y in range(8):
                lo, hi = source[y * 2:y * 2 + 2]
                for x in range(8):
                    if (lo | hi) & (0x80 >> x):
                        points.append((tile_x * 8 + x, tile_y * 8 + y))
    if not points:
        return None
    return (min(x for x, _y in points), max(x for x, _y in points),
            min(y for _x, y in points), max(y for _x, y in points))


def run(rom, ram, png=None):
    PyBoy = _import_pyboy()
    problems = []
    with tempfile.TemporaryDirectory(prefix='dragonmawmarkerspill-') as tmp:
        run_rom = os.path.join(tmp, 'dragonmaw.gb')
        shutil.copyfile(rom, run_rom)
        shutil.copyfile(ram, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)
        frame = [0]
        observed = []

        def at_card(_context):
            de = (pb.register_file.D << 8) | pb.register_file.E
            observed.append((frame[0], (pb.memory[de + 2] & 0x0E) >> 1,
                             pb.memory[de + 1]))

        pb.hook_register(*CARD_ENTRY, at_card, None)
        for current in range(FRAMES):
            frame[0] = current
            button = BOOT.get(current)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if png and current == CAPTURE_AT:
                pb.screen.image.save(png)

        actual = bytes(pb.memory[0x8800:0x8C00])
        upper = bytes(pb.memory[0x9900:0x9914])
        lower = bytes(pb.memory[0x9920:0x9934])
        third = bytes(pb.memory[0x9940:0x9954])
        blank = bytes(pb.memory[0x9960:0x9974])
        pb.stop(save=False)

    expected = markers.render_card(None, SELECTOR, FLOOR)
    if observed != [(541, SELECTOR, FLOOR)]:
        problems.append('card entries %s, expected [(541, 5, 19)]' % (observed,))
    if actual != expected:
        problems.append('%d/%d VRAM byte(s) differ from floor-19 raster' %
                        (sum(a != b for a, b in zip(actual, expected)), len(expected)))
    if upper != bytes(range(0x80, 0xA8, 2)) \
            or lower != bytes(range(0x81, 0xA8, 2)) \
            or third != bytes(range(markers.THIRD_ROW_TILE,
                                    markers.THIRD_ROW_TILE + 20)) \
            or blank != bytes((markers.BLANK_ROW_TILE,)) * 20:
        problems.append('three-row tilemap or blank guard differs')
    bounds = _ink_bounds(actual)
    if bounds is None or bounds[:2] != EXPECTED_X_BOUNDS:
        problems.append('visible x bounds are %s, expected %s' %
                        (bounds[:2] if bounds else None, EXPECTED_X_BOUNDS))

    print('dragonmawmarkerspill: Log 1 selected floor %d / %s; x=%s; '
          '%d problem(s)' %
          (FLOOR, markers.LABELS[SELECTOR],
           '%d..%d (5/5px margins)' % EXPECTED_X_BOUNDS, len(problems)))
    for problem in problems:
        print('  ' + problem)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=os.path.join(
        ROOT, 'saves/shiren_en_log_1_dragons_maw.srm'))
    parser.add_argument('--png')
    args = parser.parse_args()
    if not os.path.exists(args.ram):
        raise SystemExit('dragonmawmarkerspill: missing RAM fixture: ' + args.ram)
    raise SystemExit(run(args.rom, args.ram, args.png))


if __name__ == '__main__':
    main()
