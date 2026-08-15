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


def _screen(selector, number):
    data = markers.render_card(None, selector, number)
    image = Image.new('RGB', (160, 144), (240, 240, 240))
    pixels = image.load()
    tiles = []
    for tile in range(markers.VISIBLE_TILE_COUNT):
        source = data[tile * 16:(tile + 1) * 16]
        rows = []
        for y in range(8):
            lo, hi = source[y * 2:y * 2 + 2]
            rows.append([bool((lo | hi) & (0x80 >> x)) for x in range(8)])
        tiles.append(rows)
    for tile_x in range(20):
        for tile_y, tile in enumerate((tile_x * 2, tile_x * 2 + 1, 40 + tile_x)):
            for y, row in enumerate(tiles[tile]):
                for x, ink in enumerate(row):
                    if ink:
                        pixels[tile_x * 8 + x, markers.STRIP_SCREEN_TOP + tile_y * 8 + y] \
                            = (0, 0, 0)
    return image


def render(output, scale):
    sheet = Image.new('RGB', (160 * 4, 144 * 2), (240, 240, 240))
    for index, (selector, number) in enumerate(CASES):
        sheet.paste(_screen(selector, number), ((index % 4) * 160, (index // 4) * 144))
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
