#!/usr/bin/env python3
"""Verify the status-screen Path value through the real Log-2 sign route.

``saves/shiren_en_path_select.srm`` has one active adventure in Log 2 and a path
selection sign one tile above Shiren.  Each run enters Log 2, talks to the sign, selects
Easy/Normal/Hard, closes the dialogue, and opens the status menu.  The value writer is
fixed-cell (not VWF), so this asserts its exact shadow and BG-map cells: all three values
must end at column 18 and leave the column-19 border intact.
"""
import argparse
import os
import shutil
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
from gbrun import _import_pyboy, PRESS_FRAMES                    # noqa: E402
import menuspill                                                  # noqa: E402


# Title -> Adventure -> Log 2 -> Continue, then face/use the sign and advance to its
# picker.  The final choice input and status-menu B press are added independently below.
BASE_ROUTE = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 360: 'down', 420: 'a', 480: 'a',
    2680: 'a', 2860: 'a',
}
CHOICES = (
    ('Easy', 1, 6),
    ('Normal', 2, 4),
    ('Hard', 3, 6),
)
VALUE_SHADOW = 0xC3C9             # status row 6, column 9
VALUE_MAP = 0x98C9
VALUE_CELLS = 10                   # columns 9..18
RIGHT_BORDER = 0xBF                # column 19
FRAMES = 3500


def expected_cells(label, prefix):
    return bytes([menuspill.EN_CODES[' ']] * prefix + menuspill.encode(label))


def run_choice(PyBoy, rom_path, ram_path, name, mode, prefix, png_dir=None):
    problems = []
    schedule = dict(BASE_ROUTE)
    for step in range(mode - 1):
        schedule[2960 + step * 40] = 'down'
    schedule[3040] = 'a'
    schedule[3260] = 'b'

    with tempfile.TemporaryDirectory(prefix='pathspill-') as tmp:
        run_rom = os.path.join(tmp, 'path.gb')
        shutil.copyfile(rom_path, run_rom)
        shutil.copyfile(ram_path, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        dispatches = []

        def dispatch(_ctx=None):
            dispatches.append((frame[0], pb.register_file.A))

        pb.hook_register(4, 0x48AA, dispatch, None)
        for current in range(FRAMES):
            frame[0] = current
            button = schedule.get(current)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()

        shadow = bytes(pb.memory[VALUE_SHADOW:VALUE_SHADOW + VALUE_CELLS + 1])
        bgmap = bytes(pb.memory[VALUE_MAP:VALUE_MAP + VALUE_CELLS + 1])
        actual_mode = pb.memory[0xC9E6]
        image = pb.screen.image.copy()
        pb.stop(save=False)

    expected = expected_cells(name, prefix)
    if len(expected) != VALUE_CELLS:
        problems.append('%s test definition occupies %d cells, expected %d'
                        % (name, len(expected), VALUE_CELLS))
    if actual_mode != mode:
        problems.append('%s selection left path mode %d, expected %d'
                        % (name, actual_mode, mode))
    if not any(index == 0 for _at, index in dispatches):
        problems.append('%s route never dispatched the in-dungeon status menu' % name)
    if shadow[:VALUE_CELLS] != expected:
        problems.append('%s shadow $%04X is %s, expected %s'
                        % (name, VALUE_SHADOW, shadow[:VALUE_CELLS].hex(' '),
                           expected.hex(' ')))
    if shadow[VALUE_CELLS] != RIGHT_BORDER:
        problems.append('%s overwrote shadow column-19 border: $%02X, expected $%02X'
                        % (name, shadow[VALUE_CELLS], RIGHT_BORDER))
    if bgmap != shadow:
        problems.append('%s BG map $%04X is %s, unlike settled shadow %s'
                        % (name, VALUE_MAP, bgmap.hex(' '), shadow.hex(' ')))

    if png_dir:
        os.makedirs(png_dir, exist_ok=True)
        image.save(os.path.join(png_dir, name.lower() + '.png'))
    return problems, dispatches, shadow


def run(rom_path, ram_path, png_dir=None):
    PyBoy = _import_pyboy()
    problems = []
    for name, mode, prefix in CHOICES:
        found, dispatches, shadow = run_choice(
            PyBoy, rom_path, ram_path, name, mode, prefix, png_dir)
        problems.extend(found)
        print('pathspill: %-6s mode=%d cells=%s dispatches=%s'
              % (name, mode, shadow.hex(' '),
                 ' '.join('f%d:%d' % event for event in dispatches)))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('pathspill: %d problem(s)' % len(problems))
    print('pathspill: Easy/Normal/Hard are right-aligned at column 18; border preserved')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=os.path.join(
        ROOT, 'saves/shiren_en_path_select.srm'))
    parser.add_argument('--png-dir')
    args = parser.parse_args()
    if not os.path.exists(args.ram):
        raise SystemExit('pathspill: missing RAM fixture: %s' % args.ram)
    run(args.rom, args.ram, args.png_dir)


if __name__ == '__main__':
    main()
