#!/usr/bin/env python3
"""Prove cursed/plated equipment rows stay on the proportional item path.

The curse case appends a genuine canonical Nagamaki record with byte-3 flags $94.  The
plating case temporarily substitutes the exact 18-glyph hostile row from playtesting:
``E True Rapier+99★`` ($84 raw equipment marker, cursor cell, VWF text, native $8A
star).  The original staging bytes and next-row pointer are restored immediately after
that one row returns, so the remaining real item page draws normally.

Both rows must receive allocator records and match the installed approved-font/native-star
planes exactly. Exit 1 on fixed-width fallback, wrapping, corrupt raw markers, or pixels.
"""
import argparse
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
from gbrun import _import_pyboy, PRESS_FRAMES                    # noqa: E402
from latinfont import EN_CODES                                   # noqa: E402
import menuspill                                                  # noqa: E402
import menuvwf                                                    # noqa: E402

INVENTORY = 0xA3B0
OBJECTS = 0xA406
CURSED_NAGAMAKI = (0x01, 0x00, 0x00, 0x94, 0x00, 0x00, 0xFF, 0xFF)
ITEM_SHAPE = (0, 3, 5, 18, 0x02)
PLATED_TEXT = tuple(menuspill.encode('True Rapier+99')) + (0x8A,)
PLATED_ROW = (0x84, 0x00) + PLATED_TEXT + (0xFF,)
CURSED_TEXT = tuple(menuspill.encode('Nagamaki'))


def read_row(pb, source, limit=32):
    row = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        row.append(value)
        if value == 0xFF:
            return row
    # Empty trailing item rows are fixed-width zero runs with no in-range terminator.
    return row


def run(rom, state, png=None, frames=500):
    profile = menuspill.renderer_profile(rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('equipmentmarkerspill: requires the proportional renderer')
    PyBoy = _import_pyboy()
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(state, 'rb') as source:
        pb.load_state(source)

    status = {'injected': False, 'rewritten': False, 'pending': None}
    keys = {}
    drawn = {}

    def inject_cursed(_ctx=None):
        if status['injected']:
            return
        slot = next((index for index in range(20)
                     if pb.memory[INVENTORY + index] == 0xFF), None)
        obj = next((index for index in range(128)
                    if pb.memory[OBJECTS + 8 * index] == 0xFF), None)
        if slot is None or obj is None:
            return
        for offset, value in enumerate(CURSED_NAGAMAKI):
            pb.memory[OBJECTS + 8 * obj + offset] = value
        pb.memory[INVENTORY + slot] = obj
        status['injected'] = True

    def far_entry(_ctx=None):
        shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
        if shape != ITEM_SHAPE:
            return
        source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
        row_number = pb.register_file.D
        key = pb.register_file.HL
        if row_number == 0 and not status['rewritten']:
            original = read_row(pb, source)
            saved = [pb.memory[source + offset]
                     for offset in range(max(len(original), len(PLATED_ROW)))]
            for offset, value in enumerate(PLATED_ROW):
                pb.memory[source + offset] = value
            # The far renderer advances the outer drawer's source pointer. Restore both
            # the bytes and that pointer at 31:$4118 before the next native row begins.
            status['pending'] = (source, saved, source + len(original))
            status['rewritten'] = True
            keys['plated'] = key
            drawn[key] = list(PLATED_ROW[:-1])
            return
        row = read_row(pb, source)
        drawn[key] = row[:-1]
        if row[:2] == [0x87, 0x00]:
            keys['cursed'] = key

    def restore_staging(_ctx=None):
        pending = status['pending']
        if pending is None:
            return
        source, saved, next_source = pending
        for offset, value in enumerate(saved):
            pb.memory[source + offset] = value
        # 31:$4118 stores A as the next-source low byte, then B as its high byte.
        pb.register_file.A = next_source & 0xFF
        pb.register_file.B = next_source >> 8
        status['pending'] = None

    pb.hook_register(6, 0x4B29, inject_cursed, None)
    pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)
    pb.hook_register(31, 0x4118, restore_staging, None)
    for frame in range(frames):
        if frame == 60:
            pb.button('b', PRESS_FRAMES)
        if frame == 160:
            pb.button('a', PRESS_FRAMES)
        pb.tick()

    problems = []
    if not status['injected']:
        problems.append('canonical cursed Nagamaki was not injected')
    if not status['rewritten'] or status['pending'] is not None:
        problems.append('plated hostile row was not drawn and restored')
    for kind in ('plated', 'cursed'):
        if kind not in keys:
            problems.append('%s equipment row never reached the renderer' % kind)

    records = menuspill.records(pb, profile)
    for kind, codes, marker in (
            ('plated', PLATED_TEXT, 0x84), ('cursed', CURSED_TEXT, 0x87)):
        key = keys.get(kind)
        if key is None:
            continue
        matches = [record for record in records if record[0] == key and record[3] == 2]
        if not matches:
            problems.append('%s row fell back instead of allocating VWF tiles' % kind)
            continue
        if pb.memory[key + 1] != marker:
            problems.append('%s raw marker is $%02X, expected $%02X'
                            % (kind, pb.memory[key + 1], marker))
        if not menuspill.visible_row_matches(pb, profile, key, list(codes), raw=2):
            problems.append('%s visible planes do not match proportional composition'
                            % kind)

    checked = [0]
    problems += menuspill.settled_check(pb, profile, 'equipment markers', checked, drawn)
    if png:
        pb.screen.image.save(png)
        print('  wrote ' + png)
    pb.stop(save=False)

    print('equipmentmarkerspill: plated/cursed keys %s; %d plane-exact row check(s); '
          '%d problem(s)' % (keys, checked[0], len(problems)))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('equipmentmarkerspill: failed')
    print('equipmentmarkerspill: native status symbols and proportional names coexist')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--state', default=os.path.join(ROOT, 'saves/dungeon.state'))
    parser.add_argument('--png')
    args = parser.parse_args()
    if not os.path.exists(args.state):
        raise SystemExit('equipmentmarkerspill: missing state fixture: ' + args.state)
    run(args.rom, args.state, args.png)


if __name__ == '__main__':
    main()
