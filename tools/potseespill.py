#!/usr/bin/env python3
"""Replay Floor -> See for the empty Storage Pot in Joey's Log-1 fixture.

The pot-content viewer is a separate path from the translated item-help table.  This
fixture keeps its empty-row source and rendered VWF planes observable so untranslated
kana cannot silently reappear under the Latin font.
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
SCRIPT = {
    60: ('start',), 120: ('start',), 180: ('start',), 240: ('start',),
    300: ('a',), 420: ('a',), 480: ('a',),
    2620: ('b',), 2700: ('down',), 2780: ('a',),       # Menu -> Floor
    2860: ('down',), 3000: ('a',),                    # See
}
FRAMES = 3400
CONTENT_SHAPE = (0, 3, 3, 18, 2)
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
            if frame[0] < 2950:
                return
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            call = (frame[0], pb.register_file.D, pb.register_file.HL,
                    shape, source, staged_row(pb, source))
            calls.append(call)
            if shape == CONTENT_SHAPE and pb.register_file.D == 0:
                content_calls.append(call)

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)
        for frame[0] in range(FRAMES):
            for button in SCRIPT.get(frame[0], ()):
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
        pb.stop(save=False)

    indices = [index for _at, index in dispatches]
    if 20 not in indices:
        problems.append('real route never dispatched Floor screen 20')
    if 13 not in indices:
        problems.append('real route never dispatched Pot See screen 13')
    if not calls:
        problems.append('See never entered the proportional row renderer')
    print('potseespill: dispatches %s; %d See-era row call(s); %d problem(s)'
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
