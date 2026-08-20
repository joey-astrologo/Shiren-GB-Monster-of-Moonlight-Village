#!/usr/bin/env python3
"""Exercise the status screen and its shared two-row dungeon status bar.

The fixture enters the ordinary dungeon menu. At statusvwf's post-native boundary the
test substitutes long but valid native field cells (six-digit Gitan/EXP, 50F, signed
equipment, 99/99 Strength, Expert Path). It then requires exact private maps and planes,
an LCD-off hook entry, and no private low-page tile references outside the intended
status cells. It also freezes the supplied HP/Lv one-tile artwork in the ROM, independently
of the bitmap generator. This validates the renderer rather than one convenient set of
small values.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import dotfont
from gbrun import _import_pyboy, PRESS_FRAMES
from latinfont import EN_CODES
import statusvwf


STATE = os.path.join(ROOT, 'saves', 'dungeon.state')
SHADOW = 0xC300
BGMAP = 0x9800
WINMAP = 0x9C00
BAR_LABELS = (
    ('Lv', 2, 0x7CF2, bytes.fromhex('00 80 80 92 92 92 8A E4')),
    ('HP', 2, 0x7D02, bytes.fromhex('00 50 50 56 75 56 54 54')),
)

DYNAMIC = (
    ('Gitan', 0xC348, 11, 0xC34E, '999999G'),
    ('Floor', 0xC388, 11, 0xC391, '50F'),
    ('Path', 0xC3C8, 11, 0xC3CF, 'Expert'),
    ('Weapon value', 0xC481, 8, 0xC485, '-999'),
    ('Strength value', 0xC48A, 9, 0xC48F, '99/99'),
    ('Shield value', 0xC4C1, 8, 0xC4C5, '101'),
    ('Experience value', 0xC4CA, 9, 0xC4CF, '999999'),
)
STATIC = (
    ('Weapon', 0xC461, statusvwf.WEAPON_TILES),
    ('Shield', 0xC4A1, statusvwf.SHIELD_TILES),
    ('Strength', 0xC46A, tuple(range(0x0B, 0x11))),
    ('Experience', 0xC4AA, tuple(range(0x04, 0x0B))),
)


def tile_addr(tile):
    return 0x9000 + 16 * tile if tile < 0x80 else 0x8800 + 16 * (tile - 0x80)


def native_codes(text):
    out = []
    for ch in text:
        if ch == 'F':
            out.append(0xB4)
        elif ch == 'G':
            out.append(0xB5)
        elif ch == '-':
            out.append(0x7D)
        else:
            out.append(EN_CODES[ch])
    return bytes(out)


def expected_tiles(font, text, cap, right=True):
    one = [bytearray(8) for _ in range(cap)]
    extent = font.text_extent(text)
    advance = font.text_width(text)
    pen = cap * 8 - advance if right else 0
    if pen < 0 or extent + pen > cap * 8:
        raise AssertionError('%r does not fit %d status tiles' % (text, cap))
    for ch in text:
        glyph = font.glyphs[ch]
        for y, row in enumerate(glyph):
            for x in range(8):
                if row & (0x80 >> x):
                    pixel = pen + x
                    if 0 <= pixel < cap * 8:
                        one[pixel // 8][y] |= 0x80 >> (pixel & 7)
        pen += font.advance(ch)
    return tuple(b''.join(bytes((row, row)) for row in tile) for tile in one)


def labels(font):
    _code, found = statusvwf.gbasm.assemble(
        statusvwf._source(tuple(font.advance_code(c) for c in statusvwf.SLOT_CODES)),
        statusvwf.CODE_AT)
    return found


def run(rom, state=STATE, png=None):
    font = dotfont.load_approved()
    runtime = labels(font)
    PyBoy = _import_pyboy()
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(state, 'rb') as src:
        pb.load_state(src)

    entries = []
    draws = []

    def at_entry(_ctx=None):
        entries.append((pb.memory[0xFF40], pb.memory[0xFF44]))

    def at_draw(_ctx=None):
        draws.append(1)
        for _name, source, cells, _map, text in DYNAMIC:
            data = native_codes(text)
            for index in range(cells):
                pb.memory[source + index] = 0
            start = source + cells - len(data)
            for index, value in enumerate(data):
                pb.memory[start + index] = value

    pb.hook_register(statusvwf.FAR_BANK, runtime['statusentry'], at_entry, None)
    pb.hook_register(statusvwf.FAR_BANK, runtime['statusdraw'], at_draw, None)
    for frame in range(150):
        if frame == 60:
            pb.button('b', PRESS_FRAMES)
        pb.tick()

    shadow = bytes(pb.memory[SHADOW:SHADOW + 32 * 18])
    bg = bytes(pb.memory[BGMAP:BGMAP + 32 * 18])
    win = bytes(pb.memory[WINMAP:WINMAP + 32 * 18])
    planes = {tile: bytes(pb.memory[tile_addr(tile):tile_addr(tile) + 16])
              for tile in set().union(
                  *(set(range(base, base + cap))
                    for base, cap in statusvwf.PRIVATE_RUNS.values()),
                  statusvwf.WEAPON_TILES, statusvwf.SHIELD_TILES)}
    image = pb.screen.image.copy()
    pb.stop(save=False)

    problems = []
    rom_data = open(rom, 'rb').read()
    for name, bank, address, want in BAR_LABELS:
        offset = bank * 0x4000 + address - 0x4000
        got = rom_data[offset:offset + len(want)]
        if got != want:
            problems.append('%s status-bar source is %s, expected approved %s' %
                            (name, got.hex(' '), want.hex(' ')))
    if len(entries) != 1 or len(draws) != 1:
        problems.append('status hook ran %d entry / %d draw times, expected 1/1' %
                        (len(entries), len(draws)))
    if any(lcdc & 0x80 for lcdc, _ly in entries):
        problems.append('status compositor entered with LCD enabled: %s' % entries)

    expected_cells = set()
    for name, source, cells, map_at, text in DYNAMIC:
        base, cap = statusvwf.PRIVATE_RUNS[name]
        want_map = bytes(range(base, base + cap))
        off = map_at - SHADOW
        expected_cells.update(range(off, off + cap))
        if shadow[off:off + cap] != want_map:
            problems.append('%s shadow map is %s, expected %s' %
                            (name, shadow[off:off + cap].hex(' '), want_map.hex(' ')))
        if bg[off:off + cap] != want_map:
            problems.append('%s visible map differs from its private slice' % name)
        wants = expected_tiles(font, text, cap, right=True)
        for index, want in enumerate(wants):
            if planes[base + index] != want:
                problems.append('%s tile $%02X is not exact for %r' %
                                (name, base + index, text))
                break

    for name, map_at, ids in STATIC:
        off = map_at - SHADOW
        expected_cells.update(range(off, off + len(ids)))
        got = shadow[off:off + len(ids)]
        if got != bytes(ids) or bg[off:off + len(ids)] != bytes(ids):
            problems.append('%s static map is %s, expected %s' %
                            (name, got.hex(' '), bytes(ids).hex(' ')))
        wants = expected_tiles(font, name, len(ids), right=False)
        for tile, want in zip(ids, wants):
            if planes[tile] != want:
                problems.append('%s static tile $%02X is not plane-exact' % (name, tile))
                break

    private = set().union(*(set(range(base, base + cap))
                            for base, cap in statusvwf.PRIVATE_RUNS.values()))
    visible = {row * 32 + col for row in range(18) for col in range(20)}
    leaked_bg = [index for index, tile in enumerate(bg) if index in visible
                 and tile in private and index not in expected_cells]
    leaked_win = [index for index, tile in enumerate(win) if index in visible
                  and tile in private]
    if leaked_bg:
        problems.append('private status IDs leak to BG cells %s' % leaked_bg[:12])
    if leaked_win:
        problems.append('private status IDs collide with Window cells %s' % leaked_win[:12])

    if png:
        image.save(png)
        print('statusspill: wrote %s' % png)
    print('statusspill: HP/Lv bar art; %d hook; 4 labels + 7 maximum-shape values; '
          '%d problem(s)' % (len(entries), len(problems)))
    for problem in problems:
        print('  ' + problem)
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--state', default=STATE)
    parser.add_argument('--png')
    args = parser.parse_args()
    problems = run(args.rom, args.state, args.png)
    raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    main()
