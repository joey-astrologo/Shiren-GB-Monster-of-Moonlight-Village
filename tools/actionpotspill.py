#!/usr/bin/env python3
"""Verify Back/Todo Pot charge rows through Joey's real Log-2 fixture.

Both pots use `$CC` placeholder records rather than ordinary stored items.  The native
expander turns each charge into `  せなか`; the English build must stage and compose
`Press` three times without leaking kana-shaped fixed cells or VWF pool ownership.
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gbrun import PRESS_FRAMES, _import_pyboy                    # noqa: E402
import itemfix                                                    # noqa: E402
import menuspill                                                  # noqa: E402
import menuvwf                                                    # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log_2_action_pots.srm')
BASE_ROUTE = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 360: 'down', 420: 'a', 480: 'a',       # Adventure -> Log 2
    2620: 'b', 2740: 'a',                            # Menu -> Items
    3200: 'a', 3400: 'a',                            # item -> See
}
CASES = (
    ('Back Pot', 0x81, 1),
    ('Todo Pot', 0x88, 2),
)
FRAMES = 3700
CONTENT_SHAPE = (0, 3, 3, 18, 2)
CONTENT_BASE = 0xC616
TARGET = bytes(menuspill.encode(itemfix.ACTION_POT_TEXT))
STAGED = bytes((0, 0)) + TARGET
STRIDE = len(STAGED) + 1                         # row plus $FF terminator


def staged_row(pb, source, limit=32):
    out = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            break
        out.append(value)
    return bytes(out)


def run_case(PyBoy, rom, ram, label, item_id, downs, png_dir=None, trace=False):
    profile = menuspill.renderer_profile(rom)
    problems = []
    schedule = dict(BASE_ROUTE)
    for step in range(downs):
        schedule[3000 + step * 60] = 'down'

    with tempfile.TemporaryDirectory(prefix='actionpotspill-') as tmp:
        work = os.path.join(tmp, 'action-pot.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        dispatches = []
        selected = []
        rows = []

        def dispatch(_context=None):
            dispatches.append((frame[0], pb.register_file.A))
            if pb.register_file.A == 12:
                # The selected canonical object is copied to $CF79; its item ID is the
                # second byte. This proves the two nearly identical routes hit different
                # real pot types instead of testing one row twice.
                selected.append(pb.memory[0xCF7A])

        def far_entry(_context=None):
            if frame[0] < 3350:
                return
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if shape != CONTENT_SHAPE:
                return
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            rows.append((frame[0], pb.register_file.D, pb.register_file.HL,
                         source, staged_row(pb, source)))

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)
        for current in range(FRAMES):
            frame[0] = current
            button = schedule.get(current)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()

        image = pb.screen.image.copy()
        if png_dir:
            os.makedirs(png_dir, exist_ok=True)
            image.save(os.path.join(png_dir,
                                    label.lower().replace(' ', '_') + '.png'))

        if selected != [item_id]:
            problems.append('%s selected IDs %s, expected $%02X'
                            % (label, ' '.join('$%02X' % value for value in selected),
                               item_id))
        if [rownum for _at, rownum, _key, _source, _row in rows] != [0, 1, 2]:
            problems.append('%s composed rows %s, expected 0,1,2'
                            % (label, [row[1] for row in rows]))
        for at, rownum, key, source, row in rows:
            expected_source = CONTENT_BASE + rownum * STRIDE
            if source != expected_source:
                problems.append('%s row %d source at f%d is $%04X, expected $%04X'
                                % (label, rownum, at, source, expected_source))
            if row != STAGED:
                problems.append('%s row %d staged %s, expected %s'
                                % (label, rownum, row.hex(' '), STAGED.hex(' ')))
            elif not menuspill.visible_row_matches(pb, profile, key, TARGET, raw=2):
                problems.append('%s row %d is not plane-exact VWF `%s`'
                                % (label, rownum, itemfix.ACTION_POT_TEXT))
        bad = menuspill.frame_invariant(pb, profile)
        if bad:
            problems.append('%s leaves %d unowned proportional tile(s): %s'
                            % (label, len(bad), bad[:8]))
        if trace:
            for row in rows:
                print('  %s f%d d%d key=$%04X src=$%04X cells=%s'
                      % ((label,) + row[:4] + (row[4].hex(' '),)))
        pb.stop(save=False)

    if not any(index == 12 for _at, index in dispatches):
        problems.append('%s never dispatched the Pot contents screen' % label)
    return problems, rows


def run(rom, ram=RAM, png_dir=None, trace=False):
    profile = menuspill.renderer_profile(rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('actionpotspill: requires the approved proportional renderer')
    PyBoy = _import_pyboy()
    problems = []
    for label, item_id, downs in CASES:
        found, rows = run_case(PyBoy, rom, ram, label, item_id, downs,
                               png_dir, trace)
        problems.extend(found)
        print('actionpotspill: %-8s %d charge row(s)' % (label, len(rows)))
    for problem in problems:
        print('  ' + problem)
    print('actionpotspill: %d problem(s)' % len(problems))
    if not problems:
        print('actionpotspill: Back/Todo Pot charges are plane-exact `Press`')
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png-dir')
    parser.add_argument('--trace', action='store_true')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('actionpotspill: missing %s' % path)
    return run(args.rom, args.ram, args.png_dir, args.trace)


if __name__ == '__main__':
    raise SystemExit(main())
