#!/usr/bin/env python3
"""Build the manual carried-unidentified-item Name test SRAM using real inputs only.

The source fixture starts Log 3 above an unidentified Willow Staff. This tool loads that
fixture, takes the staff through the game's Floor Action menu, opens Items, and asks PyBoy
to persist the resulting cartridge RAM. It never writes inventory, object, identity, or
menu-state addresses directly. A second clean boot proves the generated SRAM can reach
the carried staff without replaying the Floor Take or running a Lua script.
"""
import argparse
import hashlib
import os
import shutil
import sys
import tempfile


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from gbrun import PRESS_FRAMES, _import_pyboy                  # noqa: E402


INVENTORY = 0xA3B0
OBJECTS = 0xA406
WILLOW_TYPE = 0x78
SRAM_SIZE = 4 * 0x2000

BOOT_LOG3 = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 380: 'down', 460: 'down', 540: 'a', 700: 'a',
}
TAKE_TO_ITEMS = dict(BOOT_LOG3)
TAKE_TO_ITEMS.update({
    3000: 'b',             # gameplay -> Status
    3400: 'down',          # Status -> Floor
    3600: 'a',
    3900: 'a',             # Willow Staff -> Take
    4300: 'b',             # Floor -> Status
    4500: 'a',             # Status -> Items
})
VERIFY_CARRIED = dict(BOOT_LOG3)
VERIFY_CARRIED.update({3000: 'b', 3400: 'a'})


def run(PyBoy, rom, ram, script, frames, save=False):
    with tempfile.TemporaryDirectory(prefix='item-name-srm-') as tmp:
        work = os.path.join(tmp, 'item-name.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        builds = []
        dispatches = []

        def inventory_build(_context=None):
            indices = []
            for slot in range(20):
                index = pb.memory[INVENTORY + slot]
                if index == 0xFF:
                    break
                indices.append(index)
            records = tuple(bytes(pb.memory[OBJECTS + 8 * index:
                                            OBJECTS + 8 * index + 8])
                            for index in indices)
            builds.append((tuple(indices), records))

        pb.hook_register(6, 0x4B29, inventory_build, None)
        pb.hook_register(4, 0x48AA,
                         lambda _context=None: dispatches.append(pb.register_file.A), None)
        for frame in range(frames):
            action = script.get(frame)
            if action:
                pb.button(action, PRESS_FRAMES)
            pb.tick()
        pb.stop(save=save)
        data = open(work + '.ram', 'rb').read() if save else None
        return builds, dispatches, data


def has_carried_willow(builds):
    return any(any(record[0] == WILLOW_TYPE for record in records)
               for _indices, records in builds)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--source', default=os.path.join(
        ROOT, 'tests/fixtures/saves/shiren_log3_unidentified_naming.srm'))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    for path in (args.rom, args.source):
        if not os.path.isfile(path):
            raise SystemExit('makeitemnametest: missing %s' % path)

    PyBoy = _import_pyboy()
    builds, dispatches, generated = run(
        PyBoy, args.rom, args.source, TAKE_TO_ITEMS, 4900, save=True)
    if dispatches[-4:] != [0, 20, 0, 1]:
        raise SystemExit('makeitemnametest: generation dispatch tail is %s' %
                         dispatches[-4:])
    if not has_carried_willow(builds):
        raise SystemExit('makeitemnametest: real Take route did not carry Willow Staff')
    if len(generated) != SRAM_SIZE:
        raise SystemExit('makeitemnametest: generated %d bytes, expected %d' %
                         (len(generated), SRAM_SIZE))

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, 'wb') as target:
        target.write(generated)

    verify_builds, verify_dispatches, _unused = run(
        PyBoy, args.rom, args.output, VERIFY_CARRIED, 3900)
    if 1 not in verify_dispatches or not has_carried_willow(verify_builds):
        raise SystemExit('makeitemnametest: clean reboot did not reach carried Willow Staff')
    print('makeitemnametest: real Take -> persisted SRAM -> clean Items reboot; '
          'SHA-256 %s' % hashlib.sha256(generated).hexdigest())


if __name__ == '__main__':
    main()
