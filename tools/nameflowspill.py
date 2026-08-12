#!/usr/bin/env python3
"""Regression for the saved Copy -> Erase -> New Log name-entry transition.

The start-menu VWF intentionally borrows native tile IDs while its boxes are visible.
That is safe only when a later screen restores every native tile it uses.  A fresh-cart
name-entry test cannot expose this lifetime: Erase confirmation writes ``$89`` while
drawing ``Log: Shiren`` and ``$9E-$A0`` while drawing ``Erase log?``.  Those IDs are
the name-field underline and the fixed-cell ``(``, ``)`` and ``:`` glyphs.

This test follows the player-reported route on a one-log save, compares the settled name
screen with the fresh-cart name screen, and checks the four native tile planes directly.

    python3 tools/nameflowspill.py build/shiren_en.gb \
        --ram saves/shiren_en_path_select.srm --png /tmp/nameflow.png
"""
import argparse
import os
import shutil
import sys
import tempfile


HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gbrun import PRESS_FRAMES, _import_pyboy                  # noqa: E402
from latinfont import FONT_BASE, GLYPH_BYTES                   # noqa: E402


NAME_ENTRY = (4, 0x4B02)
SHADOW = 0xC300
SHADOW_BYTES = 32 * 18
NATIVE_TILES = (0x89, 0x9E, 0x9F, 0xA0)

# One-log fixture route: Copy Log -> source Log 1 -> empty Log 3, Erase Log -> Log 3 ->
# Yes, New Log -> Log 3 -> Easy.  Long gaps make every popup transition deterministic.
COPY_ERASE_NEW = {
    700: 'start', 760: 'start', 820: 'start', 880: 'start',
    1250: 'down', 1310: 'down', 1400: 'a',
    1800: 'a', 2200: 'a',
    2700: 'up', 2800: 'a',
    3350: 'down', 3450: 'down', 3850: 'a',
    4400: 'down', 4500: 'a',
    5200: 'a', 5800: 'a', 6400: 'a',
}
FRESH = {
    700: 'start', 760: 'start', 820: 'start', 880: 'start',
    1320: 'a', 1450: 'a', 1600: 'a',
}


def tile_vram(tile):
    return 0x9000 + 16 * tile if tile < 0x80 else 0x8800 + 16 * (tile - 0x80)


def expected_2bpp(rom, tile):
    """The four guarded tiles are in the ROM's 1bpp source page."""
    at = FONT_BASE + tile * GLYPH_BYTES
    glyph = rom[at:at + GLYPH_BYTES]
    return b''.join(bytes((row, row)) for row in glyph)


def snapshot(PyBoy, rom_path, script, frames, ram=None, png=None):
    with tempfile.TemporaryDirectory(prefix='nameflowspill-') as tmp:
        work = os.path.join(tmp, 'name.gb')
        shutil.copyfile(rom_path, work)
        if ram:
            shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        entry = []
        frame = [0]

        def at_entry(_context=None):
            entry.append((frame[0], pb.memory[0xFF40], pb.memory[0xC6F5],
                          pb.memory[0xC6F0]))

        pb.hook_register(NAME_ENTRY[0], NAME_ENTRY[1], at_entry, None)
        for frame[0] in range(frames):
            button = script.get(frame[0])
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
        result = {
            'image': pb.screen.image.copy(),
            'shadow': bytes(pb.memory[SHADOW:SHADOW + SHADOW_BYTES]),
            'tiles': {tile: bytes(pb.memory[tile_vram(tile):tile_vram(tile) + 16])
                      for tile in NATIVE_TILES},
            'row': pb.memory[0xC6F5],
            'col': pb.memory[0xC6F0],
            'entry': entry,
        }
        if png:
            result['image'].save(png)
        pb.stop(save=False)
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', required=True,
                        help='one-log save with Log 3 empty; the supplied path save works')
    parser.add_argument('--png')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('nameflowspill: missing %s' % path)

    PyBoy = _import_pyboy()
    fresh = snapshot(PyBoy, args.rom, FRESH, 1900)
    routed = snapshot(PyBoy, args.rom, COPY_ERASE_NEW, 7000, args.ram, args.png)
    rom = open(args.rom, 'rb').read()
    problems = []

    if len(fresh['entry']) != 1:
        problems.append('fresh route reached name entry %d times, expected once' %
                        len(fresh['entry']))
    if len(routed['entry']) != 1:
        problems.append('copy/erase route reached name entry %d times, expected once' %
                        len(routed['entry']))
    if (routed['row'], routed['col']) != (1, 0):
        problems.append('copy/erase route starts at row/col %s, expected (1, 0)' %
                        ((routed['row'], routed['col']),))
    if routed['shadow'][0x47] != 0x89:
        problems.append('name-field cursor cell is $%02X, expected native $89' %
                        routed['shadow'][0x47])
    if routed['shadow'][0xE1] != 0xCA:
        problems.append('grid cursor cell is $%02X, expected native $CA on A' %
                        routed['shadow'][0xE1])

    for tile in NATIVE_TILES:
        expected = expected_2bpp(rom, tile)
        if routed['tiles'][tile] != expected:
            problems.append('copy/erase route left native tile $%02X overwritten' % tile)
        if fresh['tiles'][tile] != expected:
            problems.append('fresh route has unexpected native tile $%02X planes' % tile)

    if routed['image'].tobytes() != fresh['image'].tobytes():
        problems.append('copy/erase name screen differs pixelwise from fresh name screen')
    visible = tuple(row * 32 + col for row in range(18) for col in range(20))
    shadow_diffs = [at for at in visible
                    if routed['shadow'][at] != fresh['shadow'][at]]
    if shadow_diffs:
        problems.append('copy/erase visible name shadow differs from fresh at %s' %
                        ' '.join('$%03X' % at for at in shadow_diffs[:12]))

    for problem in problems:
        print('  ' + problem)
    routed_entry = routed['entry'][0] if routed['entry'] else None
    print('nameflowspill: fresh and Copy->Erase->New name screens; entry=%s; '
          '%d native tile(s) exact; %d problem(s)' %
          (routed_entry, len(NATIVE_TILES), len(problems)))
    raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    main()
