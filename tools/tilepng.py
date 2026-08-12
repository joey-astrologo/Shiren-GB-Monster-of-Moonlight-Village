#!/usr/bin/env python3
"""Render GB tile data from the ROM to a PNG grid, for eyeballing fonts and graphics.

usage: tilepng.py <rom> <hex-offset> <ntiles> <out.png> [--2bpp] [--cols N] [--zoom N]
"""
import sys, zlib, struct

def png(path, w, h, rgb_rows):
    raw = b''.join(b'\0' + bytes(r) for r in rgb_rows)
    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    out = b'\x89PNG\r\n\x1a\n'
    out += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
    out += chunk(b'IDAT', zlib.compress(raw, 9))
    out += chunk(b'IEND', b'')
    open(path, 'wb').write(out)

# GB shades, index 0 = lightest
PAL = [(255, 255, 255), (170, 170, 170), (85, 85, 85), (0, 0, 0)]
GRID = (255, 80, 80)

def decode(data, off, n, bpp):
    """-> list of n tiles, each 8x8 list of palette indices."""
    step = 8 if bpp == 1 else 16
    tiles = []
    for t in range(n):
        b = data[off + t * step: off + t * step + step]
        if len(b) < step:
            b = b + b'\0' * (step - len(b))
        px = []
        for y in range(8):
            if bpp == 1:
                lo, hi = b[y], 0
            else:
                lo, hi = b[y * 2], b[y * 2 + 1]
            px.append([((lo >> (7 - x)) & 1) | (((hi >> (7 - x)) & 1) << 1) for x in range(8)])
        tiles.append(px)
    return tiles

def main():
    a = sys.argv[1:]
    rom, off, n, out = a[0], int(a[1], 16), int(a[2]), a[3]
    bpp = 2 if '--2bpp' in a else 1
    cols = int(a[a.index('--cols') + 1]) if '--cols' in a else 16
    zoom = int(a[a.index('--zoom') + 1]) if '--zoom' in a else 3

    data = open(rom, 'rb').read()
    tiles = decode(data, off, n, bpp)
    rows = (n + cols - 1) // cols
    # 1px grid line between tiles
    W, H = cols * (8 * zoom + 1) + 1, rows * (8 * zoom + 1) + 1
    img = [[GRID] * W for _ in range(H)]
    for i, t in enumerate(tiles):
        cx, cy = i % cols, i // cols
        ox, oy = cx * (8 * zoom + 1) + 1, cy * (8 * zoom + 1) + 1
        for y in range(8):
            for x in range(8):
                c = PAL[t[y][x]]
                for dy in range(zoom):
                    for dx in range(zoom):
                        img[oy + y * zoom + dy][ox + x * zoom + dx] = c
    png(out, W, H, [[v for p in row for v in p] for row in img])
    print("wrote %s  %dx%d  %d tiles (%dbpp) from 0x%06X" % (out, W, H, n, bpp, off))

main()
