#!/usr/bin/env python3
"""Render status-bar artwork into 1bpp tiles — labels drawn as bitmaps, not characters.

The status bar labels are not text. HP and Lv each occupy one 8x8 source tile, while the
fullness label occupies four consecutive tiles at bank 2 $7D42. Because the original
kana span tile boundaries rather than sitting one-per-cell, the fullness constraint is
32 PIXELS of width, not 5 characters — which is roomier than it first looks.

usage: bartext.py <rom> <bank:$addr> <ntiles> <text> [--out rom] [--preview png]
       bartext.py build/base.gb 2:\\$7D42 4 FULLNESS
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from latinfont import G

BANKSZ = 0x4000


# Hand-drawn labels sized specifically for the status bar. HP and LV reproduce the
# supplied two-row status-bar mock-up exactly; their one-tile budgets and positions stay
# unchanged. FULLNESS reproduces the compact 31x7 artwork supplied for the English bar.
# The leading blank row keeps the tall F clear of the upper divider; the remaining
# column in its four-tile strip stays blank, so the surrounding fields do not need to
# move.
BITMAPS = {
    'HP': (
        '........',
        '.#.#....',
        '.#.#....',
        '.#.#.##.',
        '.###.#.#',
        '.#.#.##.',
        '.#.#.#..',
        '.#.#.#..',
    ),
    'LV': (
        '........',
        '#.......',
        '#.......',
        '#..#..#.',
        '#..#..#.',
        '#..#..#.',
        '#...#.#.',
        '###..#..',
    ),
    'FULLNESS': (
        '...............................',
        '####...........................',
        '#..............................',
        '#...#..#.#..#..#..#.###..##..##',
        '###.#..#.#..#..##.#.#...#...#..',
        '#...#..#.#..#..#.##.##...#...#.',
        '#...#..#.#..#..#..#.#.....#...#',
        '#....##..##.##.#..#.###.##..##.',
    ),
}


def parse_loc(s):
    bank, addr = s.split(':$')
    return int(bank) * BANKSZ + (int(addr, 16) - 0x4000)


def render(text, width_px, pitch=6, top=1):
    """-> list of 8-row bitmaps, one per tile. `pitch` is per-character advance."""
    rows = [[0] * width_px for _ in range(8)]
    if text in BITMAPS:
        art = BITMAPS[text]
        need = max(map(len, art))
        if need > width_px:
            raise SystemExit("bitmap %r needs %dpx, strip is %dpx" %
                             (text, need, width_px))
        for y, line in enumerate(art):
            for x, c in enumerate(line):
                rows[y][x] = c == '#'
    else:
        x = 0
        for ch in text:
            if ch == ' ':
                x += 3
                continue
            if ch not in G:
                raise SystemExit("no glyph for %r (have: %s)" % (ch, ''.join(sorted(G))))
            gl = G[ch]
            for gy, line in enumerate(gl):
                y = gy + top
                if y >= 8:
                    continue
                for gx, c in enumerate(line):
                    if c == '#' and x + gx < width_px:
                        rows[y][x + gx] = 1
            x += pitch
        if x - pitch + 5 > width_px:
            print("WARNING: text needs ~%dpx, strip is %dpx" % (x - pitch + 5, width_px))
    tiles = []
    for t in range(width_px // 8):
        tile = bytearray()
        for y in range(8):
            b = 0
            for bit in range(8):
                if rows[y][t * 8 + bit]:
                    b |= 0x80 >> bit
            tile.append(b)
        tiles.append(bytes(tile))
    return tiles


def main():
    a = sys.argv[1:]
    rom_path, loc, n, text = a[0], a[1], int(a[2]), a[3]
    off = parse_loc(loc)
    rom = bytearray(open(rom_path, 'rb').read())

    tiles = render(text, n * 8)
    print("%s -> %d tiles at %s (file 0x%06X), %dpx strip" % (text, n, loc, off, n * 8))
    for i, t in enumerate(tiles):
        print("   tile %d: %s" % (i, t.hex(' ')))
    # show it
    print()
    for y in range(8):
        line = ''
        for t in tiles:
            line += ''.join('#' if t[y] & (0x80 >> x) else '.' for x in range(8))
        print("   " + line)

    if '--out' in a:
        dst = a[a.index('--out') + 1]
        for i, t in enumerate(tiles):
            rom[off + i * 8: off + i * 8 + 8] = t
        open(dst, 'wb').write(bytes(rom))
        print("\nwrote %s" % dst)


if __name__ == '__main__':
    main()
