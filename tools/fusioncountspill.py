#!/usr/bin/env python3
"""Exercise every real fused-equipment count through Item and Info.

Joey's ``shiren_en_log3_fusion_name.srm`` was captured from Log 3 with a canonical
``Manji Kabura+2`` carrying two seals.  A cold boot restores an older in-dungeon
checkpoint over SRAM bank 0, so this test first validates the supplied Log-3 working
record directly, then reproduces it through the canonical item builder in
``saves/dungeon.state``.

Nine canonical Manji Kabura objects carry masks with popcounts 1 through 9.  The first
five are checked on item page 1, the other four on page 2, and count 9 is selected and
opened in Info.  This proves the game itself emits suffix codes $8C-$94 and that every
one receives a VWF record with exact visible planes.  $95 is asserted to be rejected:
the original weapon/shield masks contain at most nine usable seal bits.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gbrun import PRESS_FRAMES, _import_pyboy                    # noqa: E402
import menuspill                                                  # noqa: E402
import menuvwf                                                    # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log3_fusion_name.srm')
STATE = os.path.join(ROOT, 'saves', 'dungeon.state')
INVENTORY = 0xA3B0
OBJECTS = 0xA406
ITEM_SHAPE = (0, 3, 5, 18, 0x02)
INFO_SHAPE = (0, 3, 5, 18, 0x00)
MANJI = 0x06
BONUS = 2
FLAGS = 0xC4
WEAPON_MASK = 0x01FF
SHIELD_MASK = 0x06FD
EXPECTED_LOG3_OBJECT = bytes((MANJI, BONUS, 0, FLAGS, 0x06, 0, 0xFF, 0xFF))
NAME = tuple(menuspill.encode('Manji Kabura+2'))


def row_at(pb, source, limit=32):
    out = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            break
        out.append(value)
    return tuple(out)


def fixture_problems(path):
    data = open(path, 'rb').read()
    problems = []
    if len(data) != 0x8000:
        return ['Log-3 fusion SRAM is %d bytes, expected 32768' % len(data)]
    first = data[INVENTORY - 0xA000]
    if first == 0xFF or first >= 128:
        problems.append('Log-3 first inventory object index is invalid: $%02X' % first)
        return problems
    start = OBJECTS - 0xA000 + 8 * first
    record = data[start:start + 8]
    if record != EXPECTED_LOG3_OBJECT:
        problems.append('Log-3 first object is %s, expected Manji Kabura+2/two seals %s'
                        % (record.hex(' '), EXPECTED_LOG3_OBJECT.hex(' ')))
    return problems


def run(rom, ram=None, state=STATE, png_dir=None):
    profile = menuspill.renderer_profile(rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('fusioncountspill: requires the proportional renderer')
    fixture_checked = ram is not None
    problems = fixture_problems(ram) if fixture_checked else []
    if max(bin(WEAPON_MASK).count('1'), bin(SHIELD_MASK).count('1')) != 9:
        problems.append('canonical equipment-mask maximum is no longer nine seals')
    if menuspill.eligible((menuvwf.FUSED_LAST + 1,)):
        problems.append('impossible fusion suffix $%02X was admitted'
                        % (menuvwf.FUSED_LAST + 1))

    PyBoy = _import_pyboy()
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(state, 'rb') as source:
        pb.load_state(source)

    injected = [False]
    events = {}
    snapshots = {}
    frame = [0]

    def inject(_context=None):
        if injected[0]:
            return
        free = [index for index in range(128)
                if pb.memory[OBJECTS + 8 * index] == 0xFF]
        if len(free) < 9:
            return
        for count, object_index in enumerate(free[:9], 1):
            mask = (1 << count) - 1
            record = (MANJI, BONUS, 0, FLAGS, mask & 0xFF, mask >> 8, 0xFF, 0xFF)
            for offset, value in enumerate(record):
                pb.memory[OBJECTS + 8 * object_index + offset] = value
            pb.memory[INVENTORY + count - 1] = object_index
        pb.memory[INVENTORY + 9] = 0xFF
        injected[0] = True

    def far_entry(_context=None):
        shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
        if shape not in (ITEM_SHAPE, INFO_SHAPE):
            return
        source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
        codes = row_at(pb, source)
        fused = [code for code in codes if code in menuvwf.FUSED_CODES]
        if len(fused) != 1:
            return
        # FUSED_FIRST is the ZERO-seal code, so the count is the plain offset. It used to
        # be the one-seal code, and this read `+ 1`; admitting $8B shifted the base.
        count = fused[0] - menuvwf.FUSED_FIRST
        events[(shape, count)] = (pb.register_file.HL, codes)

    def snapshot(label, counts, shape, raw):
        records = menuspill.records(pb, profile)
        failures = []
        for count in counts:
            event = events.get((shape, count))
            if event is None:
                failures.append('count %d never reached %s renderer' % (count, label))
                continue
            key, staged = event
            expected = NAME + (menuvwf.FUSED_FIRST + count,)
            if raw == 2:
                if staged != (0, 0) + expected:
                    failures.append('count %d staged %s, expected %s' %
                                    (count, bytes(staged).hex(' '),
                                     bytes((0, 0) + expected).hex(' ')))
            elif staged != (0x7D,) + expected + (0x7D,):
                failures.append('count %d Info title staged %s' %
                                (count, bytes(staged).hex(' ')))
            matches = [record for record in records
                       if record[0] == key and record[3] == raw]
            if not matches:
                failures.append('count %d has no %s VWF record' % (count, label))
            visible = staged[raw:] if raw else staged
            if not menuspill.visible_row_matches(pb, profile, key, list(visible), raw=raw):
                failures.append('count %d %s planes differ' % (count, label))
        snapshots[label] = failures

    pb.hook_register(6, 0x4B29, inject, None)
    pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)
    schedule = {
        60: 'b', 120: 'a',                    # Main -> Items
        280: 'right',                         # counts 6-9
        400: 'down', 440: 'down', 480: 'down', 540: 'a',  # select count 9
        620: 'down', 660: 'down', 700: 'down', 760: 'a',  # Info
    }
    for frame[0] in range(1000):
        button = schedule.get(frame[0])
        if button:
            pb.button(button, PRESS_FRAMES)
        pb.tick()
        if frame[0] == 220:
            snapshot('Items page 1', range(1, 6), ITEM_SHAPE, 2)
        elif frame[0] == 360:
            snapshot('Items page 2', range(6, 10), ITEM_SHAPE, 2)
        elif frame[0] == 900:
            snapshot('count-9 Info title', (9,), INFO_SHAPE, 0)

    if not injected[0]:
        problems.append('nine canonical equipment objects were not injected')
    for label, failures in snapshots.items():
        problems += ['%s: %s' % (label, failure) for failure in failures]
    if set(snapshots) != {'Items page 1', 'Items page 2', 'count-9 Info title'}:
        problems.append('one or more settled checkpoints were not sampled')
    if png_dir:
        os.makedirs(png_dir, exist_ok=True)
        pb.screen.image.save(os.path.join(png_dir, 'fusion_count9_info.png'))
    pb.stop(save=False)

    fixture = ('Log-3 Manji+2 fixture; ' if fixture_checked else
               'Log-3 fixture not present; ')
    print('fusioncountspill: %scanonical counts 1-9 across two Items pages; '
          'count 9 Info; %d problem(s)' % (fixture, len(problems)))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('fusioncountspill: failed')
    print('fusioncountspill: every possible fusion count $8C-$94 is plane-exact VWF; '
          '$95 is rejected')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram')
    parser.add_argument('--state', default=STATE)
    parser.add_argument('--png-dir')
    args = parser.parse_args()
    if args.ram is not None and not os.path.exists(args.ram):
        raise SystemExit('fusioncountspill: missing Log-3 SRAM: ' + args.ram)
    if args.ram is None and os.path.exists(RAM):
        args.ram = RAM
    if not os.path.exists(args.state):
        raise SystemExit('fusioncountspill: missing dungeon state: ' + args.state)
    run(args.rom, args.ram, args.state, args.png_dir)


if __name__ == '__main__':
    main()
