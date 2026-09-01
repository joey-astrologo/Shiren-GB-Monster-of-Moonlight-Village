#!/usr/bin/env python3
"""Build the full-inventory Floor/Pot/Put selector fixture through a real Drop.

The source Log 1 has four carried pages and an identified Storage Pot on page three. This
tool pages to that Pot, uses its native Action -> Drop command, and persists the resulting
nineteen-item log while Shiren stands on the dropped Pot.  No inventory, object, menu, or
game-state address is written directly.  Clean reboots must reach the Put selector from
both direct Floor and the Items-appended Floor page.
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


SRAM_SIZE = 4 * 0x2000
BOOT_LOG1 = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a',
}
DROP_POT = dict(BOOT_LOG1)
DROP_POT.update({
    2620: 'b', 2720: 'a',
    2820: 'right', 2920: 'right',
    3300: 'a',
    3400: 'down', 3460: 'down', 3520: 'down',
    3640: 'a',
})
DIRECT_PUT = dict(BOOT_LOG1)
DIRECT_PUT.update({
    2620: 'b', 2720: 'down', 2820: 'a',
    3000: 'down', 3100: 'down', 3240: 'a',
})
APPENDED_PUT = dict(BOOT_LOG1)
APPENDED_PUT.update({
    2620: 'b', 2720: 'a',
    2820: 'right', 2920: 'right', 3020: 'right', 3120: 'right',
    3340: 'a', 3460: 'down', 3560: 'down', 3700: 'a',
})


def run(PyBoy, rom, ram, script, frames, save=False):
    with tempfile.TemporaryDirectory(prefix='floor-pot-selector-srm-') as tmp:
        work = os.path.join(tmp, 'floor-pot-selector.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)
        dispatches = []
        pb.hook_register(
            4, 0x48AA,
            lambda _context=None: dispatches.append((pb.frame_count,
                                                      pb.register_file.A)), None)
        for frame in range(frames):
            button = script.get(frame)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
        final_lcdc = pb.memory[0xFF40]
        final_count = pb.memory[0xC6AA]
        pb.stop(save=save)
        data = open(work + '.ram', 'rb').read() if save else None
        return dispatches, final_count, final_lcdc, data


def reaches_put(dispatches):
    # Native screen 14 is the shared Floor candidate selector: both Swap and a
    # ground-Pot Put action use it.  Carried-Pot Put independently uses screen 11.
    return any(screen == 14 for _frame, screen in dispatches)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--source', default=os.path.join(
        ROOT, 'saves', 'shiren_en_log1_player_named_items.srm'))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    for path in (args.rom, args.source):
        if not os.path.isfile(path):
            raise SystemExit('makefloorpotselectortest: missing %s' % path)

    PyBoy = _import_pyboy()
    dispatches, count, lcdc, generated = run(
        PyBoy, args.rom, args.source, DROP_POT, 4100, save=True)
    screens = [screen for _frame, screen in dispatches]
    if not screens or screens[-1] != 2:
        raise SystemExit('makefloorpotselectortest: Drop route dispatch tail is %s, '
                         'expected a final Items Action before native field return; %s' %
                         (screens[-6:], dispatches))
    # C6AA remains the outgoing twenty-row display count after the native field action;
    # the clean reboots below rebuild it from the canonical nineteen-item inventory.
    if not lcdc & 0x80:
        raise SystemExit('makefloorpotselectortest: generation ended with LCD disabled')
    if len(generated) != SRAM_SIZE:
        raise SystemExit('makefloorpotselectortest: generated %d bytes, expected %d' %
                         (len(generated), SRAM_SIZE))

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, 'wb') as target:
        target.write(generated)

    direct, direct_count, direct_lcdc, _unused = run(
        PyBoy, args.rom, args.output, DIRECT_PUT, 3500)
    appended, appended_count, appended_lcdc, _unused = run(
        PyBoy, args.rom, args.output, APPENDED_PUT, 4000)
    if not reaches_put(direct):
        raise SystemExit('makefloorpotselectortest: clean direct Floor route missed '
                         'screen 14: %s' % (direct,))
    if not reaches_put(appended):
        raise SystemExit('makefloorpotselectortest: clean appended Floor route missed '
                         'screen 14: %s' % (appended,))
    if (direct_count, appended_count) != (19, 19):
        raise SystemExit('makefloorpotselectortest: clean counts are %d/%d, expected 19/19'
                         % (direct_count, appended_count))
    if not direct_lcdc & appended_lcdc & 0x80:
        raise SystemExit('makefloorpotselectortest: clean Put route ended LCD-off')
    print('makefloorpotselectortest: real page-3 Storage Pot Drop -> persisted SRAM -> clean '
          'direct/appended Put selectors; SHA-256 %s' %
          hashlib.sha256(generated).hexdigest())


if __name__ == '__main__':
    main()
