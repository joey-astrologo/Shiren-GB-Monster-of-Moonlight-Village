#!/usr/bin/env python3
"""Build the empty-inventory manual fixture through the game's real Drop action.

The source Log 3 carries exactly one item.  This tool opens its ordinary Items/Action
menus, selects Drop, lets the native dungeon action update cartridge RAM, and persists
the result.  It never writes an inventory, object, menu, or game-state address directly.
A clean reboot must then reach screen 6 (``No items held``) from Status -> Items.
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
import actionmenuspill                                         # noqa: E402
import menuspill                                               # noqa: E402
import menuvwf                                                 # noqa: E402


SRAM_SIZE = 4 * 0x2000
ROW_HOOK = None
BOOT_LOG3 = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 380: 'down', 460: 'down', 540: 'a', 700: 'a',
}
DROP_ONLY_ITEM = dict(BOOT_LOG3)
DROP_ONLY_ITEM.update({
    2600: 'b',             # gameplay -> Status
    2700: 'a',             # Status -> Items
    2900: 'a',             # only item -> Action
    3000: 'down', 3060: 'down',
    3180: 'a',             # third Action row -> Drop
    3380: 'left',          # step off the newly dropped item
    3500: 'b',             # field -> Status after the native Drop action
    3600: 'a',             # retained Items row -> No items held
    3860: 'b',             # dismiss and persist from a settled Status parent
})
VERIFY_EMPTY = dict(BOOT_LOG3)
VERIFY_EMPTY.update({2600: 'b', 2700: 'a', 3000: 'b'})


def run(PyBoy, rom, ram, script, frames, save=False):
    with tempfile.TemporaryDirectory(prefix='empty-inventory-srm-') as tmp:
        work = os.path.join(tmp, 'empty-inventory.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)
        dispatches = []
        builds = []
        action_rows = []

        def dispatch(_context=None):
            dispatches.append((pb.frame_count, pb.register_file.A))

        def inventory_build(_context=None):
            builds.append((pb.frame_count, pb.memory[0xC6AA]))

        def menu_row(_context=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if shape[0:2] != (13, 1):
                return
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            action_rows.append((pb.frame_count, pb.register_file.D,
                                actionmenuspill.staged_row(pb, source)))

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(6, 0x4B29, inventory_build, None)
        pb.hook_register(menuvwf.FAR_BANK, ROW_HOOK, menu_row, None)
        for frame in range(frames):
            button = script.get(frame)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
        final_lcdc = pb.memory[0xFF40]
        pb.stop(save=save)
        data = open(work + '.ram', 'rb').read() if save else None
        return dispatches, builds, action_rows, final_lcdc, data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--source', default=os.path.join(
        ROOT, 'tests', 'fixtures', 'saves', 'shiren_en_log3_normal.srm'))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    for path in (args.rom, args.source):
        if not os.path.isfile(path):
            raise SystemExit('makeemptyinventorytest: missing %s' % path)

    PyBoy = _import_pyboy()
    profile = menuspill.renderer_profile(args.rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('makeemptyinventorytest: requires proportional menu renderer')
    # `run` installs the live relocated renderer hook selected by this build.
    global ROW_HOOK
    ROW_HOOK = profile['entry']
    dispatches, builds, action_rows, lcdc, generated = run(
        PyBoy, args.rom, args.source, DROP_ONLY_ITEM, 4100, save=True)
    screens = [screen for _frame, screen in dispatches]
    if screens[-2:] != [6, 0]:
        raise SystemExit('makeemptyinventorytest: generation dispatch tail is %s; '
                         'expected Status -> No-items -> Status; dispatches %s; rows %s' %
                         (screens[-6:], dispatches, action_rows))
    if not lcdc & 0x80:
        raise SystemExit('makeemptyinventorytest: generation ended with LCD disabled')
    if len(generated) != SRAM_SIZE:
        raise SystemExit('makeemptyinventorytest: generated %d bytes, expected %d' %
                         (len(generated), SRAM_SIZE))

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, 'wb') as target:
        target.write(generated)

    verify_dispatches, verify_builds, _verify_rows, verify_lcdc, _unused = run(
        PyBoy, args.rom, args.output, VERIFY_EMPTY, 3300)
    verify_screens = [screen for _frame, screen in verify_dispatches]
    if 6 not in verify_screens:
        raise SystemExit('makeemptyinventorytest: clean reboot did not dispatch '
                         'screen 6: %s; builds %s' % (verify_screens, verify_builds))
    if not verify_lcdc & 0x80:
        raise SystemExit('makeemptyinventorytest: clean screen-6 return left LCD disabled')
    print('makeemptyinventorytest: real one-item Drop -> persisted SRAM -> clean '
          'Status/No-items return; SHA-256 %s' % hashlib.sha256(generated).hexdigest())


if __name__ == '__main__':
    main()
