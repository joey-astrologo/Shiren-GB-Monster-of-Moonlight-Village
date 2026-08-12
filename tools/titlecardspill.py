#!/usr/bin/env python3
"""Fresh-boot regression for the approved pre-intro copyright-card mock-up.

The control ROM is derived from the supplied build by restoring the one native call at
9:$4115. This makes the comparison exact: every other translation and graphics patch is
identical. The test requires all 96 deduplicated tiles, the complete visible 20x18 map and
the exact source-raster hash while proving unrelated VRAM, native timing and scene-0 entry
stay unchanged. When the separate English illustrated-logo module is absent, it also
compares that later screen exactly; when present, titlelogospill.py owns that deliberately
changed screen.

usage: titlecardspill.py ROM [--png FILE]
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import titlecard                                                  # noqa: E402
import titlelogo                                                  # noqa: E402
from gbrun import PRESS_FRAMES, _import_pyboy                     # noqa: E402


CARD_FRAME = 360
PRE_CARD_FRAME = 300
POST_CARD_FRAME = 570
LATER_TITLE_FRAME = 790
TITLE_SKIP = {700: 'start', 760: 'start'}


def _native_control(rom, path):
    data = bytearray(open(rom, 'rb').read())
    at = titlecard._off(titlecard.SOURCE_BANK, titlecard.HOOK_AT)
    native = bytes((0xCD, titlecard.NATIVE_DECOMPRESS & 0xFF,
                    titlecard.NATIVE_DECOMPRESS >> 8))
    if bytes(data[at:at + 3]) != titlecard._hook():
        raise SystemExit('titlecardspill: %s does not contain the English card hook' % rom)
    data[at:at + 3] = native

    # Keep the temporary comparison cartridge internally consistent.
    header = 0
    for i in range(0x134, 0x14D):
        header = (header - data[i] - 1) & 0xFF
    data[0x14D] = header
    data[0x14E] = data[0x14F] = 0
    global_sum = sum(data) & 0xFFFF
    data[0x14E] = global_sum >> 8
    data[0x14F] = global_sum & 0xFF
    open(path, 'wb').write(data)


def _run(PyBoy, rom, frames, buttons=None):
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    buttons = buttons or {}
    wanted = set(frames)
    captures = {}
    for frame in range(max(frames) + 1):
        if frame in buttons:
            pb.button(buttons[frame], PRESS_FRAMES)
        pb.tick()
        if frame in wanted:
            captures[frame] = {
                'image': pb.screen.image.copy(),
                'tiles': bytes(pb.memory[0x8000:0x9800]),
                'map': bytes(pb.memory[0x9800:0x9C00]),
                'lcdc': pb.memory[0xFF40],
                'bgp': pb.memory[0xFF47],
            }
    pb.stop(save=False)
    return captures


def run(rom, png=None):
    PyBoy = _import_pyboy()
    rom_data = open(rom, 'rb').read()
    logo_pointer = titlelogo._off(titlelogo.FAR_BANK, 0x4000) + titlelogo.FAR_UPLOAD - 1
    logo_enabled = rom_data[logo_pointer:logo_pointer + 2] != b'\xFF\xFF'
    with tempfile.TemporaryDirectory(prefix='titlecardspill-') as tmp:
        target = os.path.join(tmp, 'target.gb')
        control = os.path.join(tmp, 'control.gb')
        shutil.copyfile(rom, target)
        _native_control(rom, control)

        ordinary = (PRE_CARD_FRAME, CARD_FRAME, POST_CARD_FRAME)
        got = _run(PyBoy, target, ordinary)
        # The overlay consumes part of the already-LCD-off loading interval.  Compare the
        # first animated intro frame against a narrow control window rather than demanding
        # that both CPUs land on the same animation tick at the host frame boundary.
        control_frames = tuple(sorted(set(ordinary + tuple(
            range(POST_CARD_FRAME - 2, POST_CARD_FRAME + 3)))))
        native = _run(PyBoy, control, control_frames)
        later = _run(PyBoy, target, (LATER_TITLE_FRAME,), TITLE_SKIP)
        later_native = _run(PyBoy, control, (LATER_TITLE_FRAME,), TITLE_SKIP)
        if png:
            got[CARD_FRAME]['image'].save(png)

    problems = []
    built = titlecard.compile_graphics()
    card_tiles = got[CARD_FRAME]['tiles']
    native_tiles = native[CARD_FRAME]['tiles']

    changed_tile_offsets = set()
    exact = 0
    total = 0
    for tile, expected in built['groups']:
        dest = titlecard._vram_addr(tile)
        start = dest - 0x8000
        actual = card_tiles[start:start + len(expected)]
        total += len(expected)
        exact += sum(a == b for a, b in zip(actual, expected))
        changed_tile_offsets.update(range(start, start + len(expected)))
        if actual != expected:
            problems.append('%d/%d tile byte(s) differ at VRAM $%04X'
                            % (sum(a != b for a, b in zip(actual, expected)),
                               len(expected), dest))

    for offset, (actual, original) in enumerate(zip(card_tiles, native_tiles)):
        if offset not in changed_tile_offsets and actual != original:
            problems.append('unrelated tile VRAM changed first at $%04X'
                            % (0x8000 + offset))
            break

    actual_map = got[CARD_FRAME]['map']
    original_map = native[CARD_FRAME]['map']
    changes = {}
    compact_live_map = bytearray()
    map_exact = 0
    for y in range(titlecard.MAP_HEIGHT):
        for x in range(titlecard.MAP_WIDTH):
            address = titlecard.MAP_AT + y * 32 + x
            expected = built['map'][y * titlecard.MAP_WIDTH + x]
            changes[address] = expected
            actual = actual_map[address - 0x9800]
            compact_live_map.append(actual)
            map_exact += actual == expected
            if actual != expected and not any(p.startswith('tilemap ') for p in problems):
                problems.append('tilemap $%04X is $%02X, expected $%02X'
                                % (address, actual, expected))
    for offset, (actual, original) in enumerate(zip(actual_map, original_map)):
        if 0x9800 + offset not in changes and actual != original:
            problems.append('unrelated BG map changed first at $%04X' % (0x9800 + offset))
            break

    live_blob = card_tiles[titlecard._vram_addr(0) - 0x8000:
                           titlecard._vram_addr(0) - 0x8000 + titlecard.TILE_BYTES]
    live_raster = titlecard._raster_indices(live_blob, bytes(compact_live_map))
    if live_raster != built['raster']:
        problems.append('live tile/map expansion differs from approved 160x144 raster')

    if got[PRE_CARD_FRAME]['image'].tobytes() != \
            native[PRE_CARD_FRAME]['image'].tobytes():
        problems.append('screen differs before the dated card')
    if got[CARD_FRAME]['image'].tobytes() == native[CARD_FRAME]['image'].tobytes():
        problems.append('English card is pixel-identical to the Japanese control')
    if got[CARD_FRAME]['bgp'] != native[CARD_FRAME]['bgp']:
        problems.append('card changed native BGP palette mapping ($%02X -> $%02X)'
                        % (native[CARD_FRAME]['bgp'], got[CARD_FRAME]['bgp']))
    post_image = got[POST_CARD_FRAME]['image'].tobytes()
    if not any(post_image == native[frame]['image'].tobytes()
               for frame in range(POST_CARD_FRAME - 2, POST_CARD_FRAME + 3)):
        problems.append('post-card screen does not match the native intro timing window')
    later_same = later[LATER_TITLE_FRAME]['image'].tobytes() == \
        later_native[LATER_TITLE_FRAME]['image'].tobytes()
    if logo_enabled and later_same:
        problems.append('installed English illustrated logo is not visible')
    if not logo_enabled and not later_same:
        problems.append('later illustrated title screen differs from the native control')

    print('titlecardspill: %d/%d tile byte(s), %d/%d visible map cell(s), and '
          '160x144 raster exact; unrelated VRAM/native palette exact; later title %s; '
          '%d problem(s)'
          % (exact, total, map_exact, titlecard.MAP_BYTES,
             'English logo active' if logo_enabled else 'native/exact', len(problems)))
    for problem in problems:
        print('  ' + problem)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--png')
    args = parser.parse_args()
    if not os.path.exists(args.rom):
        raise SystemExit('titlecardspill: missing %s' % args.rom)
    raise SystemExit(run(args.rom, args.png))


if __name__ == '__main__':
    main()
