#!/usr/bin/env python3
"""Render a menu box's native source geometry the way bank 31 draws it.

Box widening is a purely visual change and the reference verifier says nothing about it:
it proves a string still resolves, not that a box looks right. This closes part of that
gap without an emulator by replaying the drawer's own algorithm against the ROM bytes --
so it catches an off-screen box, a row that overflows its width, a mis-split block, or
padding in the wrong place.

What it CANNOT tell you: whether the box overlaps text some other routine drew (the item
list under the action menu), or whether a WRAM-staged box gets the content you expect.
Those still need a screenshot.

This intentionally models the original fixed-cell drawer. It is useful for descriptor,
row-source and border geometry; it is not a proportional-pixel fit test. Production Dot
rows are checked by `fontaudit.py`, `menuspill.py`, and `menuromspill.py`.

usage: boxpreview.py <rom> [box-id ...] [--screen] [--jp]
       no ids            every box with ROM text
       --screen          place each box on a 20x18 screen grid instead of listing rows
       --jp              decode with the Japanese table instead of the Latin font
"""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import codec
from latinfont import EN_CODES

BANKSZ = 0x4000
SCREEN_W, SCREEN_H = 20, 18

# The Latin font is written over the kana tiles in place, so a code renders as whichever
# letter latinfont put at that index. Inverting EN_CODES is therefore the only honest way
# to show what the screen will say.
EN_CHARS = {v: k for k, v in sorted(EN_CODES.items(), reverse=True)}

BORDER = {0xB8: '/', 0xB9: '\\', 0xBA: '\\', 0xBB: '/', 0xBC: '-', 0xBD: '-',
          0xBE: '|', 0xBF: '|', 0x81: '>', 0x83: '|', 0x85: '|'}


def glyph(b, jp=False):
    if b in BORDER:
        return BORDER[b]
    if b == 0x00:
        return ' '
    if not jp and b in EN_CHARS:
        return EN_CHARS[b]
    t = codec.decode(bytes([b]))
    return t if len(t) == 1 else '·'


def draw_row(rom, off, width, jp=False):
    """Replay 31:$40D8 for one row -> (rendered cells, offset just past the row).

    Left border, then exactly `width` cells: an $FF stops consuming and pads the rest with
    blanks, and a dakuten draws over the previous cell without taking one of its own
    (31:$4124 peeks the next byte to decide, so a trailing dakuten is consumed even once
    the width is used up).
    """
    out, c = [], width
    while c > 0:
        b = rom[off]
        if b == codec.TERMINATOR:
            out.append(' ')                    # blank padding, source not advanced
        else:
            off += 1
            if b in codec.COMBINING:
                if out:
                    out[-1] += '̣'        # drawn over the preceding cell
            else:
                out.append(glyph(b, jp))
        if rom[off] not in codec.COMBINING:
            c -= 1
    if rom[off] == codec.TERMINATOR:
        off += 1
    return out, off


def render(rom, box, jp=False):
    """-> [ (column, row, text) ] for the box's border and every text row."""
    x, y, w = box['x'], box['y'], box['width']
    lines = [(x, y, '/' + '-' * w + '\\')]
    if box['wram']:
        lines += [(x, y + 1 + r, '|' + '?' * w + '|') for r in range(box['rows'])]
    else:
        off = box['bank'] * BANKSZ + (box['text'] - 0x4000)
        for r in range(box['rows']):
            cells, off = draw_row(rom, off, w, jp)
            lines.append((x, y + 1 + r, '|' + ''.join(cells) + '|'))
    lines.append((x, y + box['rows'] + 1, '\\' + '-' * w + '/'))
    return lines


def main():
    a = [v for v in sys.argv[1:] if not v.startswith('--')]
    flags = {v for v in sys.argv[1:] if v.startswith('--')}
    rom = open(a[0], 'rb').read()
    manifest = json.load(open('script/script.json', encoding='utf-8'))
    boxes = manifest['boxes']
    jp = '--jp' in flags

    # Read geometry back out of the ROM, not out of the manifest: the manifest describes
    # the Japanese original, and the whole point is to see what the built ROM will draw.
    for b in boxes:
        d = b['desc']
        b['x'], b['y'], b['rows'], b['width'] = rom[d], rom[d + 1], rom[d + 2], rom[d + 3]
        b['text'] = rom[d + 5] | (rom[d + 6] << 8)
        b['wram'] = not (0x4000 <= b['text'] < 0x8000)

    want = [int(v, 0) for v in a[1:]] or [b['id'] for b in boxes if not b['wram']]
    chosen = [b for b in boxes if b['id'] in want]

    if '--screen' in flags:
        grid = [[' '] * SCREEN_W for _ in range(SCREEN_H)]
        for b in chosen:
            for cx, cy, text in render(rom, b, jp):
                for i, ch in enumerate(text):
                    if 0 <= cy < SCREEN_H and 0 <= cx + i < SCREEN_W:
                        grid[cy][cx + i] = ch
        print('     ' + ''.join(str(i % 10) for i in range(SCREEN_W)))
        print('    +' + '-' * SCREEN_W + '+')
        for i, row in enumerate(grid):
            print('%3d |%s|' % (i, ''.join(row)))
        print('    +' + '-' * SCREEN_W + '+')
        return 0

    for b in chosen:
        # Measured in CELLS, which is width + 2 borders by construction. len(text) would
        # over-count: a dakuten is appended to the preceding character and costs no cell.
        over = ('   ** OFF SCREEN **'
                if b['x'] + b['width'] + 2 > SCREEN_W or b['y'] + b['rows'] + 2 > SCREEN_H
                else '')
        print("box %2d  x=%-2d y=%-2d rows=%d width=%-2d columns %d-%d%s"
              % (b['id'], b['x'], b['y'], b['rows'], b['width'],
                 b['x'], b['x'] + b['width'] + 1, over))
        for _, _, text in render(rom, b, jp):
            print('        ' + text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
