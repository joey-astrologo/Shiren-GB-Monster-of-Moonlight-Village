#!/usr/bin/env python3
"""Replay Floor -> See for empty Storage Pots in the Log-1 and Log-2 fixtures.

The pot-content viewer is a separate path from the translated item-help table.  This
fixture keeps its empty-row source and rendered VWF planes observable so untranslated
kana cannot silently reappear under the Latin font. The Log-2 route additionally proves
the compact Pot title's exact five-cell geometry after leaving the wider Floor header.
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import codec                                                     # noqa: E402
from gbrun import PRESS_FRAMES, _import_pyboy                    # noqa: E402
import itemfix                                                   # noqa: E402
import menuspill                                                  # noqa: E402
import menuvwf                                                    # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log_1_pot_see_action.srm')
STORAGE_RAM = os.path.join(ROOT, 'saves', 'shiren_en_log2_storage_pot_menu.srm')
LOG1_SCRIPT = {
    60: ('start',), 120: ('start',), 180: ('start',), 240: ('start',),
    300: ('a',), 420: ('a',), 480: ('a',),
    2620: ('b',), 2700: ('down',), 2780: ('a',),       # Menu -> Floor
    2860: ('down',), 3000: ('a',),                    # See
}
LOG2_SCRIPT = {
    60: ('start',), 120: ('start',), 180: ('start',), 240: ('start',),
    300: ('a',), 360: ('down',), 420: ('a',), 500: ('a',),
    2200: ('b',), 2280: ('down',), 2360: ('a',),       # Menu -> Floor
    2480: ('down',), 2600: ('a',),                    # See
}
FRAMES = 3400
CONTENT_SOURCE = 0xC616
TARGET = bytes(menuspill.encode(itemfix.EMPTY_POT_ROW))


def staged_row(pb, source, limit=48):
    out = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            break
        out.append(value)
    return bytes(out)


def run(rom, ram=RAM, png=None, trace=False):
    profile = menuspill.renderer_profile(rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('potseespill: requires the approved proportional renderer')
    PyBoy = _import_pyboy()
    problems = []
    with tempfile.TemporaryDirectory(prefix='potseespill-') as tmp:
        work = os.path.join(tmp, 'pot-see.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        dispatches = []
        calls = []
        content_calls = []

        def dispatch(_context=None):
            dispatches.append((frame[0], pb.register_file.A))

        def far_entry(_context=None):
            # Log 2 reaches See earlier than the original Log-1 fixture.
            if frame[0] < 2500:
                return
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            call = (frame[0], pb.register_file.D, pb.register_file.HL,
                    shape, source, staged_row(pb, source))
            calls.append(call)
            # Pot capacity changes the body height, but its first content row always
            # begins at y=3 and spans the same 18-cell interior.
            if (shape[0], shape[1], shape[3]) == (0, 3, 18) and pb.register_file.D == 0:
                content_calls.append(call)

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)
        script = LOG2_SCRIPT if os.path.basename(ram) == os.path.basename(STORAGE_RAM) else LOG1_SCRIPT
        for frame[0] in range(FRAMES):
            for button in script.get(frame[0], ()):
                pb.button(button, PRESS_FRAMES)
            pb.tick()

        final = pb.screen.image.copy()
        if png:
            final.save(png)
            print('potseespill: wrote %s' % png)
        if not content_calls:
            problems.append('See never composed its empty content row')
        else:
            at, _rownum, key, _shape, source, row = content_calls[-1]
            want = bytes((0, 0)) + TARGET
            if source != CONTENT_SOURCE:
                problems.append('empty row source is $%04X, expected $%04X'
                                % (source, CONTENT_SOURCE))
            if row != want:
                problems.append('empty row at f%d is %s, expected %s'
                                % (at, row.hex(' '), want.hex(' ')))
            elif not menuspill.visible_row_matches(pb, profile, key, TARGET, raw=2):
                problems.append('visible empty row is not plane-exact centered `%s`'
                                % itemfix.EMPTY_POT_TEXT)
        if trace:
            for at, rownum, key, shape, source, row in calls:
                print('  f%d d%d key=$%04X shape=%s src=$%04X row=%s jp=%r'
                      % (at, rownum, key, shape, source, row.hex(' '),
                         codec.decode(row)))

        # Pot is box 17: x=0, y=0, one text row, three interior cells. The preceding
        # Floor header is much wider, so its row-2 bottom edge must be fully erased
        # outside the compact five-cell title box.
        tilemap = bytes(pb.memory[0x9800:0x9A40])
        top = bytes((0xB8, 0xBC, 0xBC, 0xBC, 0xB9))
        bottom = bytes((0xBA, 0xBD, 0xBD, 0xBD, 0xBB))
        row0 = tilemap[0:20]
        row1 = tilemap[32:52]
        row2 = tilemap[64:84]
        if row0[:5] != top or any(row0[5:]):
            problems.append('Pot title top/tail is %s' % row0.hex(' '))
        if row1[0] != 0xBE or row1[4] != 0xBF or any(row1[5:]):
            problems.append('Pot title text/tail is %s' % row1.hex(' '))
        if row2[:5] != bottom or any(row2[5:]):
            problems.append('Pot title bottom/tail is %s' % row2.hex(' '))
        pb.stop(save=False)

    indices = [index for _at, index in dispatches]
    if 20 not in indices:
        problems.append('real route never dispatched Floor screen 20')
    if 13 not in indices:
        problems.append('real route never dispatched Pot See screen 13')
    if not calls:
        problems.append('See never entered the proportional row renderer')
    print('potseespill: dispatches %s; %d See-era row call(s); compact title exact; '
          '%d problem(s)'
          % (' '.join('f%d:%d' % event for event in dispatches), len(calls),
             len(problems)))
    for problem in problems:
        print('  ' + problem)
    if not problems:
        print('potseespill: shared empty-Pot viewer is plane-exact `%s`'
              % itemfix.EMPTY_POT_TEXT)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png')
    parser.add_argument('--trace', action='store_true')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('potseespill: missing %s' % path)
    return run(args.rom, args.ram, args.png, args.trace)


if __name__ == '__main__':
    raise SystemExit(main())
