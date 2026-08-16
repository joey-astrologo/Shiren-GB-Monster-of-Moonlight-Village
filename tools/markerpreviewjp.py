#!/usr/bin/env python3
"""Render the ORIGINAL Japanese arrival cards as a markerpreview-style contact sheet.

``markerpreview.py`` auditions the replacement artwork by calling ``markers.render_card``.
There is no equivalent for the cards being replaced: the Japanese card is not a stored
raster at all.  Bank 31 composes it at runtime from a background fill, an optional floor
number, and a place name built out of 16x16 glyphs, so the only faithful way to see one
is to let the game draw it.

So this drives a real build that still contains them.  ``build.py --no-markers`` keeps the
native cards ("town/dungeon arrival cards stay Japanese") while leaving the WRAM layout
that ``saves/town.state`` was captured against untouched.  The route is
``floormarkerspill``'s: reach the arrival card, and force the selector/floor pair at the
card entry the same way that regression does.  The finished VRAM raster is then read from
``$8800-$8BFF`` and painted through ``markerpreview.screen_from_raster``, so a Japanese
cell and an English cell are produced by identical code.

This is a reference sheet for translation work, not a test.  ``floormarkerspill.py`` and
``markerspill.py`` are what prove the shipped English cards.

usage: markerpreviewjp.py [OUTPUT.png] [--rom ROM] [--forms] [--scale N]
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import floormarkerspill                                           # noqa: E402
import markerpreview                                              # noqa: E402
import markers                                                    # noqa: E402
from gbrun import _import_pyboy, PRESS_FRAMES                     # noqa: E402


STATE = os.path.join(ROOT, 'saves', 'town.state')
EXPANDED = os.path.join(ROOT, 'build', '_base_expanded.gb')
SCRIPT = os.path.join(ROOT, 'script', 'en.tsv')
DEFAULT_ROM = os.path.join(ROOT, 'build', 'arrival_cards_native.gb')
CARD_VRAM = (0x8800, 0x8C00)

# Every pairing the native tables at 31:$6358/$6370 can actually select -- twenty-four
# cards over eight place names. `--forms` instead renders one card per name, matching
# markerpreview.py's eight representative cases so the sheets sit side by side.
ALL_CASES = markers.ACTIVE_CARD_CASES
FORM_CASES = markerpreview.CASES


def build_native_rom(path):
    """Build a ROM whose arrival cards are still the Japanese originals."""
    for required in (EXPANDED, SCRIPT):
        if not os.path.exists(required):
            raise SystemExit('markerpreviewjp: missing %s -- run `sh build.sh` first'
                             % required)
    print('markerpreviewjp: building %s (--no-markers)' % os.path.relpath(path, ROOT))
    result = subprocess.run(
        [sys.executable, os.path.join(HERE, 'build.py'), EXPANDED, SCRIPT, path,
         '--dot-font', '--no-markers'],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode != 0:
        sys.stdout.write(result.stdout)
        raise SystemExit('markerpreviewjp: --no-markers build failed')


TILEMAP_ROWS = (0x9900, 0x9920, 0x9940)


def native_raster(PyBoy, rom, selector, number):
    """Return ``(raster, tilemap rows)`` for one natively drawn card.

    The rows matter: the Japanese card leaves its third row at the clear tile, so the
    raster behind that row is stale and must not be painted.
    """
    with tempfile.TemporaryDirectory(prefix='markerpreviewjp-') as tmp:
        work = os.path.join(tmp, 'cards.gb')
        shutil.copyfile(rom, work)
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        with open(STATE, 'rb') as src:
            pb.load_state(src)

        entries = []

        def at_card(_context):
            de = (pb.register_file.D << 8) | pb.register_file.E
            entries.append(((pb.memory[de + 2] & 0x0E) >> 1, pb.memory[de + 1]))
            pb.memory[de + 2] = selector << 1
            pb.memory[de + 1] = number

        pb.hook_register(*floormarkerspill.CARD_ENTRY, at_card, None)
        schedule = floormarkerspill._schedule()
        for current in range(floormarkerspill.CARD_AT + 1):
            for button in schedule.get(current, ()):
                pb.button(button, PRESS_FRAMES)
            pb.tick()
        raster = bytes(pb.memory[CARD_VRAM[0]:CARD_VRAM[1]])
        # Tile IDs are relative to $8800, which is tile $80.
        rows = tuple(tuple(pb.memory[at + column] - 0x80 for column in range(20))
                     for at in TILEMAP_ROWS)
        pb.stop(save=False)

    if len(entries) != 1:
        raise SystemExit('markerpreviewjp: card entry ran %d time(s) for selector %d '
                         'floor %d, expected once' % (len(entries), selector, number))
    return raster, rows


def render(output, rom, cases, scale, columns):
    PyBoy = _import_pyboy()
    screens = []
    for selector, number in cases:
        raster, rows = native_raster(PyBoy, rom, selector, number)
        if not any(raster):
            raise SystemExit('markerpreviewjp: selector %d floor %d drew an empty card'
                             % (selector, number))
        screens.append(markerpreview.screen_from_raster(raster, rows=rows))
        print('  %2d. selector %d floor %-2s  (English: %s)'
              % (len(screens), selector, number or '-', markers.LABELS[selector]))
    sheet = markerpreview.contact_sheet(screens, columns=columns)
    if scale != 1:
        sheet = sheet.resize((sheet.width * scale, sheet.height * scale),
                             Image.Resampling.NEAREST)
    sheet.save(output)
    print('markerpreviewjp: wrote %s (%d native card(s), %dx)'
          % (output, len(screens), scale))


def main():
    parser = argparse.ArgumentParser()
    # Defaults differ per mode: sharing one filename made `--forms` silently overwrite
    # the full sheet, which is exactly the pair a reader runs back to back.
    parser.add_argument('output', nargs='?', default=None)
    parser.add_argument('--rom', default=DEFAULT_ROM,
                        help='a --no-markers build; built on demand if absent')
    parser.add_argument('--forms', action='store_true',
                        help='one card per place name, matching markerpreview.py')
    parser.add_argument('--scale', type=int, default=2)
    parser.add_argument('--columns', type=int, default=4)
    args = parser.parse_args()
    if args.scale < 1:
        raise SystemExit('markerpreviewjp: --scale must be positive')
    if args.columns < 1:
        raise SystemExit('markerpreviewjp: --columns must be positive')
    if not os.path.exists(STATE):
        raise SystemExit('markerpreviewjp: missing %s -- generate it with '
                         '`python3 tools/fixtures.py states build/shiren_en.gb`' % STATE)
    if not os.path.exists(args.rom):
        build_native_rom(args.rom)
    output = args.output or ('build/arrival_cards_japanese_forms.png' if args.forms
                             else 'build/arrival_cards_japanese.png')
    render(output, args.rom, FORM_CASES if args.forms else ALL_CASES,
           args.scale, args.columns)


if __name__ == '__main__':
    main()
