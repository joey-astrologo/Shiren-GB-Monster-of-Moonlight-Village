#!/usr/bin/env python3
"""Regression for the translated native Normal-clear teaser (ending case 4).

The tracked ending SRAM naturally follows the Hard route and therefore selects dispatcher
case 5 after its full credit roll. A real Normal clear selects case 4 instead. This test
changes only the dispatcher's incoming case from 5 to 4, before the dispatcher runs; it
then observes the real case-4 producer, the installed post-producer hook and the settled
teaser. It never rewrites the difficulty byte or calls the English renderer directly.

``endingcreditspill.py`` replays the same SRAM without this test-only dispatch selection
and independently proves all Hard credits plus the native case-5 plain End screen.
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import dotfont
import endingcreditspill
import normalending
from gbrun import PRESS_FRAMES, _import_pyboy


RAM = endingcreditspill.RAM
FRAMES = endingcreditspill.FRAMES
ADVANCE_UNTIL = endingcreditspill.ADVANCE_UNTIL
BOOT = endingcreditspill.BOOT

CASE_SELECT = (31, 0x75ED)              # immediately after native ``ld a,$05``
CASE_ENTRY = (31, 0x79B9)
NORMAL_CASE = 4
SETTLE_FRAMES = 165                     # measured native fade/dwell: f20235 -> f20400
JAPANESE_ROWS = (3, 4, 12, 13, 15, 16)


def _far_entry(rom):
    with open(rom, 'rb') as source:
        data = source.read()
    at = normalending._off(normalending.FAR_BANK, 0x4000) + \
        normalending.FAR_INDEX - 1
    entry = data[at] | (data[at + 1] << 8)
    if entry == 0xFFFF:
        raise SystemExit('normalendspill: ROM has no Normal-ending far entry')
    return entry


def _expanded_planes(pack):
    return b''.join(bytes((row, row)) for row in pack)


def _expected_text_row(row, records):
    cells = bytearray(20)
    for record_row, x, tile, count in records:
        if record_row == row:
            cells[x:x + count] = bytes(range(tile, tile + count))
    return bytes(cells)


def run(rom, ram, png=None):
    PyBoy = _import_pyboy()
    records, expected_pack = normalending.graphics(dotfont.load_approved())
    entry = _far_entry(rom)
    if entry != normalending.CODE_ORG:
        raise SystemExit('normalendspill: helper entry is $%04X, expected $%04X' %
                         (entry, normalending.CODE_ORG))

    with open(rom, 'rb') as source:
        rom_data = source.read()
    data_at = normalending._off(normalending.FAR_BANK, normalending.DATA_ORG)
    problems = []
    if rom_data[data_at:data_at + len(expected_pack)] != expected_pack:
        problems.append('installed 1bpp raster differs from approved English rows')

    with tempfile.TemporaryDirectory(prefix='normalendspill-') as tmp:
        work = os.path.join(tmp, 'normal-ending.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)
        frame_now = [0]
        selections = []
        case_entries = []
        overlay_calls = []
        native_setup = []
        due = [None]
        capture = [None]

        def select_normal(_ctx=None):
            selections.append((frame_now[0], pb.register_file.A))
            pb.register_file.A = NORMAL_CASE

        def at_case(_ctx=None):
            case_entries.append((frame_now[0], pb.register_file.A))

        def at_overlay(_ctx=None):
            overlay_calls.append(frame_now[0])
            # This hook runs after the native case-4 producer and immediately before
            # the English overlay.  Retain the native card's palette/tile polarity so
            # the regression does not infer either one from the Hard-ending fixture's
            # eventual RGB screenshot.
            native_setup.append({
                'bgp': pb.memory[0xFF47],
                'blank': bytes(pb.memory[0x9000:0x9010]),
            })
            due[0] = frame_now[0] + SETTLE_FRAMES

        pb.hook_register(*CASE_SELECT, select_normal, None)
        pb.hook_register(*CASE_ENTRY, at_case, None)
        # The wrapper is shared by all native ending cards.  Hook its case-4-only branch,
        # not the far entry, so this observation proves that the conditional overlay ran.
        _code, labels = normalending._helper(records, expected_pack)
        pb.hook_register(normalending.FAR_BANK, labels['english'], at_overlay, None)

        for frame in range(FRAMES):
            frame_now[0] = frame
            for button in BOOT.get(frame, ()):
                pb.button(button, PRESS_FRAMES)
            if 2660 <= frame < ADVANCE_UNTIL and (frame - 2660) % 60 == 0:
                pb.button('a', PRESS_FRAMES)
            pb.tick()
            if due[0] is not None and capture[0] is None and frame >= due[0]:
                capture[0] = {
                    'frame': frame,
                    'image': pb.screen.image.copy().convert('RGB'),
                    'map': bytes(pb.memory[normalending.MAP_BASE:
                                           normalending.MAP_BASE + 32 * 18]),
                    'planes': bytes(pb.memory[normalending.TILE_VRAM:
                                              normalending.TILE_VRAM +
                                              len(expected_pack) * 2]),
                    'lcdc': pb.memory[0xFF40],
                }
        pb.stop(save=False)

    if len(selections) != 1 or selections[0][1] != 5:
        problems.append('case selector observations were %r, expected one native case 5' %
                        (selections,))
    if len(case_entries) != 1:
        problems.append('native case-4 entry observations were %r' % (case_entries,))
    if len(overlay_calls) != 1:
        problems.append('English post-producer hook ran %d time(s), expected once' %
                        len(overlay_calls))
    elif case_entries and not 0 <= overlay_calls[0] - case_entries[0][0] <= 120:
        problems.append('English hook frame %d is not in the native case-4 setup window '
                        'after frame %d' % (overlay_calls[0], case_entries[0][0]))
    if len(native_setup) != 1:
        problems.append('native case-4 setup observations were %r' % (native_setup,))
    else:
        setup = native_setup[0]
        if setup['bgp'] != 0xE4:
            problems.append('native case-4 BGP is $%02X, expected $E4' % setup['bgp'])
        if setup['blank'] != b'\xFF' * 16:
            problems.append('native black tile is %s, expected 16 FF bytes' %
                            setup['blank'].hex())
        black_bits = sum(bin(value).count('1') for value in expected_pack)
        if not expected_pack or black_bits <= len(expected_pack) * 4:
            problems.append('English raster does not use the native black-background '
                            'polarity')
        print('normalendspill: native case-4 BGP=$%02X black-tile=%s' %
              (setup['bgp'], setup['blank'].hex()))
    if capture[0] is None:
        problems.append('translated teaser never reached its settled dwell')
    else:
        result = capture[0]
        if png:
            result['image'].save(png)
            print('normalendspill: wrote %s' % png)
        if result['planes'] != _expanded_planes(expected_pack):
            problems.append('English VRAM planes do not match approved 1bpp raster')
        for row in JAPANESE_ROWS + (normalending.BOTTOM_ROW,):
            wanted = _expected_text_row(row, records)
            actual = result['map'][row * 32:row * 32 + 20]
            if actual != wanted:
                problems.append('teaser map row %d is %s, expected %s' %
                                (row, actual.hex(), wanted.hex()))
        native_end = tuple(bytes(range(0x0C + row * 0x10,
                                       0x10 + row * 0x10))
                           for row in range(4))
        end_map = tuple(result['map'][row * 32 + 8:row * 32 + 12]
                        for row in range(7, 11))
        if end_map != native_end:
            problems.append('native green End map changed: %r' % (end_map,))
        if result['lcdc'] != 0xC5:
            problems.append('settled native teaser LCDC is $%02X, expected $C5' %
                            result['lcdc'])
        colors = list(result['image'].getdata())
        black = sum(color == (0, 0, 0) for color in colors)
        green = sum(color == (123, 255, 49) for color in colors)
        lit = len(colors) - black
        if black < 21000 or green < 100 or lit < 250:
            problems.append('settled screen is not the expected dark translated card '
                            '(black=%d green=%d lit=%d)' % (black, green, lit))

    print('normalendspill: native case 4 selected at the dispatcher; English hook after '
          'the real producer; %d approved tiles/map/planes exact; Japanese rows cleared; '
          'native black/white polarity and End retained; %d problem(s)' %
          (len(expected_pack) // 8, len(problems)))
    for problem in problems:
        print('  ' + problem)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('normalendspill: missing %s' % path)
    return run(args.rom, args.ram, args.png)


if __name__ == '__main__':
    raise SystemExit(main())
