#!/usr/bin/env python3
"""Exercise player-named unidentified items through their real Log-1 route.

``saves/shiren_en_log1_player_named_items.srm`` has two player-assigned identities on
the last Items page: a bracer named ``Food`` and a staff named ``Poop``.  The native
formatter prepends a category label before copying the six-byte SRAM name.  This test
proves the translated shared producer emits English for every supported category, then
boots the supplied save and requires both real rows to stage and display plane-exact VWF.
"""
import argparse
import os
import shutil
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import gbemu                                                     # noqa: E402
from gbrun import PRESS_FRAMES, _import_pyboy                    # noqa: E402
import itemfix                                                    # noqa: E402
import menuspill                                                  # noqa: E402
import menuvwf                                                    # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log1_player_named_items.srm')
ITEM_SHAPE = (0, 3, 5, 18, 0x02)
ITEM_ROW_TILES = 11
EXPECTED_ROWS = {
    3: tuple(menuspill.encode('Bracer: Food')),
    4: tuple(menuspill.encode('Staff: Poop')),
}
EXPECTED_NAMES = {
    0x0B96: tuple(menuspill.encode('Food')),
    0x0BA6: tuple(menuspill.encode('Poop')),
}
EXPECTED_OBJECTS = {
    18: bytes.fromhex('2D 03 00 84 00 00 FF FF'),
    19: bytes.fromhex('75 05 00 04 00 00 FF FF'),
}
INVENTORY_OFF = 0x03B0
OBJECTS_OFF = 0x0406
BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a',       # Adventure -> Log 1 -> Continue
    2620: 'b', 2720: 'a', 2820: 'left', # Main -> Items -> last page
}


def staged_row(pb, source, limit=32):
    row = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            break
        row.append(value)
    return tuple(row)


def fixture_problems(path):
    data = open(path, 'rb').read()
    if len(data) != 0x8000:
        return ['Log-1 player-name SRAM is %d bytes, expected 32768' % len(data)]
    problems = []
    for offset, expected in EXPECTED_NAMES.items():
        got = tuple(data[offset:offset + len(expected)])
        if got != expected or data[offset + len(expected)] != 0xFF:
            problems.append('SRAM name at +$%04X is %s, expected %s FF' %
                            (offset, bytes(got).hex(' '), bytes(expected).hex(' ')))
    for slot, expected in EXPECTED_OBJECTS.items():
        index = data[INVENTORY_OFF + slot]
        if index >= 128:
            problems.append('inventory slot %d has invalid object index $%02X' %
                            (slot, index))
            continue
        got = data[OBJECTS_OFF + 8 * index:OBJECTS_OFF + 8 * (index + 1)]
        if got != expected:
            problems.append('inventory slot %d object is %s, expected %s' %
                            (slot, got.hex(' '), expected.hex(' ')))
    return problems


def helper_problems(rom_path, profile):
    """Run the installed helper for all categories, including the empty cases."""
    rom = open(rom_path, 'rb').read()
    problems = []
    bank0 = rom[:0x4000]
    start = itemfix.PLAYER_PREFIX_BANK * 0x4000
    bank = rom[start:start + 0x4000]
    table = itemfix.PLAYER_PREFIX_INDEX - 1
    target = bank[table] | (bank[table + 1] << 8)
    if target != itemfix.PLAYER_PREFIX_AT:
        problems.append('player-name far entry points to $%04X, expected $%04X' %
                        (target, itemfix.PLAYER_PREFIX_AT))
        return problems

    expected_code, labels = itemfix._player_prefix_helper()
    at = itemfix.PLAYER_PREFIX_AT - 0x4000
    if bank[at:at + len(expected_code)] != expected_code:
        problems.append('installed player-name helper differs from asserted source')
    if target != labels['prefix']:
        problems.append('installed helper target does not select its prefix entry')

    for category in range(0x0D):
        cpu = gbemu.Cpu({0: bank0, itemfix.PLAYER_PREFIX_BANK: bank},
                        bank=itemfix.PLAYER_PREFIX_BANK)
        cpu.a, cpu.f = category, 0x10
        cpu.b, cpu.c, cpu.hl, cpu.de = 0xB1, 0xC2, 0xD345, 0xC100
        cpu.call(target)
        text = itemfix.PLAYER_PREFIXES.get(category, '')
        expected = bytes(menuspill.encode(text))
        got = bytes(cpu.read(0xC100 + offset) for offset in range(len(expected)))
        if got != expected or cpu.de != 0xC100 + len(expected):
            problems.append('category $%02X emitted %s / DE=$%04X, expected %s / $%04X'
                            % (category, got.hex(' '), cpu.de, expected.hex(' '),
                               0xC100 + len(expected)))
        if (cpu.a, cpu.f, cpu.b, cpu.c, cpu.hl) != (
                category, 0x10, 0xB1, 0xC2, 0xD345):
            problems.append('category $%02X clobbered AF/BC/HL' % category)

    # The player-name field is six characters.  Prove the widest approved nickname can
    # follow every translated prefix without exceeding an Item row's 11-tile slice.
    for category, prefix in sorted(itemfix.PLAYER_PREFIXES.items()):
        codes = tuple(menuspill.encode(prefix + 'WWWWWW'))
        if not menuspill.eligible(codes):
            problems.append('%s plus six-character nickname is not VWF-eligible' %
                            prefix.rstrip())
            continue
        tiles = len(menuspill.compose(codes, profile))
        if tiles > ITEM_ROW_TILES:
            problems.append('%s plus widest nickname needs %d tiles (limit %d)' %
                            (prefix.rstrip(), tiles, ITEM_ROW_TILES))
    return problems


def route_problems(rom_path, ram_path, png=None):
    profile = menuspill.renderer_profile(rom_path)
    problems = fixture_problems(ram_path)
    PyBoy = _import_pyboy()
    with tempfile.TemporaryDirectory(prefix='playernamedspill-') as tmp:
        run_rom = os.path.join(tmp, 'playernamed.gb')
        shutil.copyfile(rom_path, run_rom)
        shutil.copyfile(ram_path, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)
        events = {}

        def far_entry(_context=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if shape != ITEM_SHAPE or pb.register_file.D not in EXPECTED_ROWS:
                return
            rownum = pb.register_file.D
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            row = staged_row(pb, source)
            if row[2:] == EXPECTED_ROWS[rownum]:
                events[rownum] = (pb.register_file.HL, row)

        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)
        for frame in range(2980):
            button = BOOT.get(frame)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()

        records = menuspill.records(pb, profile)
        for rownum, expected in EXPECTED_ROWS.items():
            event = events.get(rownum)
            label = 'row %d `%s`' % (rownum + 1,
                                     'Bracer: Food' if rownum == 3 else 'Staff: Poop')
            if event is None:
                problems.append(label + ' never reached the proportional renderer')
                continue
            key, staged = event
            if staged != (0, 0) + expected:
                problems.append('%s staged %s, expected %s' %
                                (label, bytes(staged).hex(' '),
                                 bytes((0, 0) + expected).hex(' ')))
            matches = [record for record in records
                       if record[0] == key and record[3] == 2]
            if not matches:
                problems.append(label + ' has no raw=2 VWF allocation record')
            if not menuspill.visible_row_matches(pb, profile, key, list(expected), raw=2):
                problems.append(label + ' visible planes differ from VWF composition')
        invariant = menuspill.frame_invariant(pb, profile)
        if invariant:
            problems.append('settled last page has %d allocator invariant violation(s)'
                            % len(invariant))
        if png:
            pb.screen.image.save(png)
        pb.stop(save=False)
    return problems


def run(rom_path, ram_path=None, png=None):
    profile = menuspill.renderer_profile(rom_path)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('playernamedspill: requires the proportional renderer')
    problems = helper_problems(rom_path, profile)
    if ram_path is not None:
        problems.extend(route_problems(rom_path, ram_path, png))
    fixture = ('Log-1 Food/Poop route plane-exact; ' if ram_path else
               'Log-1 fixture not present; ')
    print('playernamedspill: %sall six category prefixes checked; %d problem(s)' %
          (fixture, len(problems)))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('playernamedspill: failed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram')
    parser.add_argument('--png')
    args = parser.parse_args()
    if args.ram is None and os.path.exists(RAM):
        args.ram = RAM
    if args.ram is not None and not os.path.exists(args.ram):
        raise SystemExit('playernamedspill: missing RAM fixture: ' + args.ram)
    run(args.rom, args.ram, args.png)


if __name__ == '__main__':
    main()
