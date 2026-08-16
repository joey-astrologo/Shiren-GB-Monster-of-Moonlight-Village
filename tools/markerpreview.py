#!/usr/bin/env python3
"""Render a contact sheet of all eight installed arrival-card forms.

This reads the same source-raster masks as the ROM installer, including the exact F1
Forest path. It is an artwork audition, while markerspill.py and floormarkerspill.py
prove the actual emulator VRAM/map results.

usage: markerpreview.py [OUTPUT.png] [--scale N]
"""
import argparse
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import markers                                                    # noqa: E402


CASES = ((0, 0), (1, 1), (2, 5), (3, 10),
         (4, 12), (5, 19), (6, 21), (7, 50))


def screen_from_raster(data, rows=None):
    """Paint one 1024-byte card raster onto a 160x144 screen.

    Split out of ``_screen`` so a caller holding a raster from somewhere else -- the
    native Japanese cards read out of a running emulator, say -- gets an identical
    contact-sheet cell without duplicating the tile walk.

    ``rows`` optionally supplies the three live tilemap rows as tile IDs, which is what
    makes a native card come out right: the replacement fills its third row from
    ``THIRD_ROW_TILE`` upwards, while the Japanese card leaves that row at the clear tile
    and never writes the raster behind it.  Assuming the English layout there paints
    whatever the previous screen happened to leave in those tiles.  Default keeps the
    generated-card layout so existing callers are unaffected.
    """
    image = Image.new('RGB', (160, 144), (240, 240, 240))
    pixels = image.load()
    tiles = []
    for tile in range(markers.VISIBLE_TILE_COUNT):
        source = data[tile * 16:(tile + 1) * 16]
        lines = []
        for y in range(8):
            lo, hi = source[y * 2:y * 2 + 2]
            lines.append([bool((lo | hi) & (0x80 >> x)) for x in range(8)])
        tiles.append(lines)
    for tile_x in range(20):
        if rows is None:
            selected = (tile_x * 2, tile_x * 2 + 1, 40 + tile_x)
        else:
            selected = tuple(row[tile_x] for row in rows)
        for tile_y, tile in enumerate(selected):
            if not 0 <= tile < len(tiles):
                continue
            for y, line in enumerate(tiles[tile]):
                for x, ink in enumerate(line):
                    if ink:
                        pixels[tile_x * 8 + x, markers.STRIP_SCREEN_TOP + tile_y * 8 + y] \
                            = (0, 0, 0)
    return image


def _screen(selector, number):
    return screen_from_raster(markers.render_card(None, selector, number))


def contact_sheet(screens, columns=4):
    """Grid the given 160x144 screens in reading order."""
    rows = (len(screens) + columns - 1) // columns
    sheet = Image.new('RGB', (160 * columns, 144 * rows), (240, 240, 240))
    for index, screen in enumerate(screens):
        sheet.paste(screen, ((index % columns) * 160, (index // columns) * 144))
    return sheet


def render(output, scale):
    sheet = contact_sheet([_screen(selector, number) for selector, number in CASES])
    if scale != 1:
        sheet = sheet.resize((sheet.width * scale, sheet.height * scale),
                             Image.Resampling.NEAREST)
    sheet.save(output)
    print('markerpreview: wrote %s (%d representative cards, %dx)' %
          (output, len(CASES), scale))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', nargs='?', default='build/arrival_cards_source.png')
    parser.add_argument('--scale', type=int, default=2)
    args = parser.parse_args()
    if args.scale < 1:
        raise SystemExit('markerpreview: --scale must be positive')
    render(args.output, args.scale)


if __name__ == '__main__':
    main()
