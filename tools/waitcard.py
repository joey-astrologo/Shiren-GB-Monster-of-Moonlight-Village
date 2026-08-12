#!/usr/bin/env python3
"""Install the English dungeon-resume wait card.

Loading an active dungeon log shows a full-screen character graphic while the floor is
restored. Its speech bubble uses ten private one-bit tiles for ``しばらく / おまちください``
(``Please wait a moment``), plus two separate tile-$0B dakuten marks in the rows above.
This module replaces only those private tiles and map cells with the approved compact
font's centered ``Please / wait...``. The character, bubble and floor marker stay native.
"""
import hashlib


TILES_AT = 0x771C4             # bank 29:$71C4; VRAM tiles $01-$0A
TILE_COUNT = 10
TILE_BYTES = TILE_COUNT * 16
TILES_SHA256 = 'efd9474594604af3da283c4fe7436e2e259a340ff10c977f80570ce7eeac70e5'

MAP_WIDTH = 20
MAP_ROWS = 10
MAP_BYTES = MAP_WIDTH * MAP_ROWS
MAPS = (
    (0x778C4, 'a226494033b7d59db26fc6eacd9a46f2289ef91749ee06ac92d7220c2fabae1d'),
    (0x77A90, '355c29eb8abd2298a4d3faa6c7928c4f4700474c2fb406c3daf7c5906cf126f8'),
)

INNER_LEFT = 80
INNER_WIDTH = 56
TEXT_COLUMNS = range(10, 17)
TOP_ROW = 2
BOTTOM_ROW = 4
DAKUTEN = ((1, 12), (3, 14))
LINES = ((TOP_ROW, 'Please'), (BOTTOM_ROW, 'wait...'))


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _line(font, text, first_tile):
    """Return (first map column, tile IDs, interleaved 2bpp bytes)."""
    extent = font.text_extent(text)
    left = INNER_LEFT + (INNER_WIDTH - extent) // 2
    first_column = left // 8
    local_left = left % 8
    tile_count = (local_left + extent + 7) // 8
    if first_tile + tile_count > TILE_COUNT + 1:
        raise SystemExit('waitcard: %r exceeds the ten private text tiles' % text)

    pixels = [[0] * (tile_count * 8) for _ in range(8)]
    pen = local_left
    for ch in text:
        if ch not in font.glyphs:
            raise SystemExit('waitcard: approved font has no %r glyph' % ch)
        for y, row in enumerate(font.glyphs[ch]):
            for x in range(8):
                if row & (0x80 >> x):
                    pixels[y][pen + x] = 1
        pen += font.advance(ch)

    out = bytearray()
    for tile in range(tile_count):
        for y in range(8):
            value = sum(0x80 >> x for x in range(8)
                        if pixels[y][tile * 8 + x])
            out.extend((value, value))
    ids = tuple(range(first_tile, first_tile + tile_count))
    return first_column, ids, bytes(out)


def render(font):
    """Return the ten private tiles and the two centered line placements."""
    tiles = bytearray(TILE_BYTES)
    placements = []
    next_tile = 1
    for row, text in LINES:
        column, ids, data = _line(font, text, next_tile)
        start = (next_tile - 1) * 16
        tiles[start:start + len(data)] = data
        placements.append((row, column, ids))
        next_tile += len(ids)
    return bytes(tiles), tuple(placements)


def patch_map(source, placements):
    out = bytearray(source)
    for row, column in DAKUTEN:
        at = row * MAP_WIDTH + column
        if out[at] != 0x0B:
            raise SystemExit('waitcard: dakuten cell (%d,%d) changed: $%02X' %
                             (column, row, out[at]))
        out[at] = 0
    for row, _text in LINES:
        for column in TEXT_COLUMNS:
            out[row * MAP_WIDTH + column] = 0
    for row, column, ids in placements:
        out[row * MAP_WIDTH + column:row * MAP_WIDTH + column + len(ids)] = bytes(ids)
    return bytes(out)


def install(buf, font, notes=None):
    old_tiles = bytes(buf[TILES_AT:TILES_AT + TILE_BYTES])
    if _digest(old_tiles) != TILES_SHA256:
        raise SystemExit('waitcard: private Japanese tile block changed')
    tiles, placements = render(font)
    buf[TILES_AT:TILES_AT + TILE_BYTES] = tiles

    for offset, expected in MAPS:
        source = bytes(buf[offset:offset + MAP_BYTES])
        if _digest(source) != expected:
            raise SystemExit('waitcard: source map at $%05X changed' % offset)
        buf[offset:offset + MAP_BYTES] = patch_map(source, placements)

    if notes is not None:
        notes.append('waitcard: dungeon-resume bubble reads Please / wait...; '
                     'nine private text tiles, two Japanese dakuten cells cleared')
    return {'tiles': tiles, 'placements': placements}
