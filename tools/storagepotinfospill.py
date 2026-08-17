#!/usr/bin/env python3
"""Regression for the six-choice Storage Pot Floor/Info return.

Log 2 in ``shiren_en_log2_storage_pot_menu.srm`` stands on a Storage Pot. The route
opens Floor, selects Info, then presses B. Info's bottom edge occupies screen row 11;
the restored six-choice picker must turn that row back into an interior spacer and put
its only bottom edge on row 15. This catches the former extra border below ``Toss``.
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gbrun import PRESS_FRAMES, _import_pyboy                  # noqa: E402
import menuspill                                                # noqa: E402
import menuvwf                                                  # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log2_storage_pot_menu.srm')
SCRIPT_PREFIX = {
    60: ('start',), 120: ('start',), 180: ('start',), 240: ('start',),
    300: ('a',), 360: ('down',), 420: ('a',), 500: ('a',),  # Adventure, Log 2
    2200: ('b',), 2280: ('down',), 2360: ('a',),             # Menu -> Floor
}


def navigation_script(action_count, dismiss_button='b'):
    script = dict(SCRIPT_PREFIX)
    for index in range(action_count - 1):
        script[2480 + index * 60] = ('down',)
    info = 2480 + (action_count - 1) * 60
    script[info] = ('a',)
    script[info + 420] = (dismiss_button,)
    return script, info + 420, info + 620


def run(rom, ram, png=None, action_count=6, label='storagepotinfospill',
        dismiss_button='b'):
    action_shape = (13, 3, action_count, 5, 2)
    script, return_frame, frame_count = navigation_script(action_count, dismiss_button)
    profile = menuspill.renderer_profile(rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('%s: requires the approved proportional renderer' % label)
    PyBoy = _import_pyboy()
    problems = []
    with tempfile.TemporaryDirectory(prefix='storagepotinfospill-') as tmp:
        work = os.path.join(tmp, 'floor-action.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        dispatches = []
        action_rows = []
        white = []
        halts = []

        def dispatch(_context=None):
            dispatches.append((frame[0], pb.register_file.A))

        def far_entry(_context=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if frame[0] >= return_frame and shape == action_shape:
                action_rows.append((frame[0], pb.register_file.D, pb.memory[0xC1B3]))

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)
        for frame[0] in range(frame_count):
            for button in script.get(frame[0], ()):
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if frame[0] >= return_frame:
                if not pb.memory[0xFF40] & 0x80:
                    white.append(frame[0])
                if pb.register_file.PC == 0x0038:
                    halts.append(frame[0])

        final = pb.screen.image.copy()
        final_state = pb.memory[0xC1B3]
        final_lcdc = pb.memory[0xFF40]
        tilemap = bytes(pb.memory[0x9800:0x9A40])
        if png:
            final.save(png)
            print('%s: wrote %s' % (label, png))
        pb.stop(save=False)

    indices = [screen for _at, screen in dispatches]
    expected = (20, 4, 0, 20)
    cursor = 0
    for screen in indices:
        if cursor < len(expected) and screen == expected[cursor]:
            cursor += 1
    if cursor != len(expected):
        problems.append('dispatch sequence %s does not contain %s' % (indices, expected))

    rows = [row for _at, row, _state in action_rows]
    if rows != list(range(action_count)):
        problems.append('returned action rows are %s, expected 0..%d'
                        % (rows, action_count - 1))
    if not white:
        problems.append('return never entered its atomic LCD-off interval')
    if final_state != 0:
        problems.append('Floor/Info transaction ended in state %d, expected 0' % final_state)
    if not final_lcdc & 0x80:
        problems.append('LCD remained disabled after the action redraw')
    if halts:
        problems.append('CPU reached rst $38 at frame(s) %s' % halts[:8])

    def cells(row):
        start = row * 32 + 13
        return tilemap[start:start + 7]

    top = bytes((0xB8,)) + bytes((0xBC,)) * 5 + bytes((0xB9,))
    interior = bytes((0xBE,)) + bytes(5) + bytes((0xBF,))
    bottom = bytes((0xBA,)) + bytes((0xBD,)) * 5 + bytes((0xBB,))
    if cells(3) != top:
        problems.append('action top edge is %s' % cells(3).hex(' '))
    bottom_row = 3 + action_count * 2
    # Odd rows are spacers. Row 11 is the important one for menus taller than four
    # choices: it used to retain Info's edge.
    for row in range(5, bottom_row, 2):
        if cells(row) != interior:
            problems.append('action spacer row %d is %s' % (row, cells(row).hex(' ')))
    if cells(bottom_row) != bottom:
        problems.append('action bottom edge row %d is %s'
                        % (bottom_row, cells(bottom_row).hex(' ')))
    # A shorter picker must not retain any edge from the taller Info body or a
    # previously drawn picker. This is what catches Gitan's detached row-11 edge.
    blank = bytes(7)
    for row in range(bottom_row + 1, 18):
        if cells(row) != blank:
            problems.append('stale action-box cells remain on row %d: %s'
                            % (row, cells(row).hex(' ')))

    print('%s: dispatches %s; action rows %s; %d white frame(s); '
          'row11=%s row%d=%s; %d problem(s)'
          % (label, ' '.join('f%d:%d' % event for event in dispatches), rows, len(white),
             cells(11).hex(' '), bottom_row, cells(bottom_row).hex(' '), len(problems)))
    for problem in problems:
        print('  ' + problem)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('storagepotinfospill: missing %s' % path)
    return run(args.rom, args.ram, args.png)


if __name__ == '__main__':
    raise SystemExit(main())
