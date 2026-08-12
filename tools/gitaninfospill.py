#!/usr/bin/env python3
"""Replay the Log-3 Gitan Floor -> Info dismissal regression.

``saves/shiren_en_log_3_gitan_crash.srm`` starts Log 3 one tile above 699 Gitan.
Holding B while moving down steps onto it without opening the menu. The route then
opens Floor, selects Info, and dismisses the one-page description. The three-choice
Gitan action box must return with the LCD enabled and the Floor/Info transaction clear.

The original transaction finalizer assumed every Floor action box had four rows. Gitan
has only Take/Toss/Info, so its redraw ended on row 2 and state 4 was never published;
the game kept running behind a permanently disabled, white LCD.
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


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log_3_gitan_crash.srm')
SCRIPT = {
    60: ('start',), 120: ('start',), 180: ('start',), 240: ('start',),
    300: ('a',),                  # Adventure
    350: ('down',), 400: ('down',), 460: ('a',),  # Log 3
    530: ('a',),                  # Continue
    2050: ('b', 'down'),          # stand on the Gitan without opening the menu
    2140: ('b',), 2220: ('down',), 2300: ('a',),  # Menu -> Floor
    2420: ('down',), 2480: ('down',), 2540: ('a',),  # Info
    2800: ('a',),                 # dismiss its only page
}
DISMISS = 2800
FRAMES = 3000
ACTION_SHAPE = (13, 3, 3, 5, 2)


def dark_pixels(image):
    return sum(value < 128 for value in image.convert('L').tobytes())


def run(rom, ram, png=None):
    profile = menuspill.renderer_profile(rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('gitaninfospill: requires the approved proportional renderer')
    PyBoy = _import_pyboy()
    problems = []
    with tempfile.TemporaryDirectory(prefix='gitaninfospill-') as tmp:
        work = os.path.join(tmp, 'gitan.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        dispatches = []
        action_rows = []
        white = []
        bad_frames = []
        halts = []

        def dispatch(_context=None):
            dispatches.append((frame[0], pb.register_file.A))

        def far_entry(_context=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if frame[0] >= DISMISS and shape == ACTION_SHAPE:
                action_rows.append((frame[0], pb.register_file.D, pb.register_file.HL,
                                    pb.memory[0xC0D7]))

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)
        for frame[0] in range(FRAMES):
            for button in SCRIPT.get(frame[0], ()):
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if frame[0] >= DISMISS:
                if not pb.memory[0xFF40] & 0x80:
                    white.append(frame[0])
                elif pb.memory[0xC0D7] == 0 and frame[0] > DISMISS:
                    bad = menuspill.frame_invariant(pb, profile)
                    if bad and len(bad_frames) < 8:
                        bad_frames.append((frame[0], bad[:2]))
                if pb.register_file.PC == 0x0038:
                    halts.append(frame[0])

        final = pb.screen.image.copy()
        final_state = pb.memory[0xC0D7]
        final_lcdc = pb.memory[0xFF40]
        final_pc = pb.register_file.PC
        if png:
            final.save(png)
            print('gitaninfospill: wrote %s' % png)
        pb.stop(save=False)

    indices = [screen for _at, screen in dispatches]
    expected = (20, 4, 0, 20)
    cursor = 0
    for screen in indices:
        if cursor < len(expected) and screen == expected[cursor]:
            cursor += 1
    if cursor != len(expected):
        problems.append('dispatch sequence %s does not contain %s' % (indices, expected))
    rows = [row for _at, row, _key, _state in action_rows]
    if rows != [0, 1, 2]:
        problems.append('returned Gitan action rows are %s, expected [0, 1, 2]' % rows)
    if not white:
        problems.append('dismissal never entered its atomic LCD-off interval')
    if final_state != 0:
        problems.append('Floor/Info transaction ended in state %d, expected 0' % final_state)
    if not final_lcdc & 0x80:
        problems.append('LCD remained disabled after the Gitan action redraw')
    if dark_pixels(final) < 300:
        problems.append('settled return is still blank (%d dark pixels)' % dark_pixels(final))
    if bad_frames:
        problems.append('visible proportional ownership failed at %s' % bad_frames)
    if halts:
        problems.append('CPU reached rst $38 at frame(s) %s' % halts[:8])

    print('gitaninfospill: dispatches %s; action rows %s; %d white frame(s); '
          'final state=%d LCDC=$%02X PC=$%04X dark=%d; %d problem(s)'
          % (' '.join('f%d:%d' % event for event in dispatches), rows, len(white),
             final_state, final_lcdc, final_pc, dark_pixels(final), len(problems)))
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
            raise SystemExit('gitaninfospill: missing %s' % path)
    return run(args.rom, args.ram, args.png)


if __name__ == '__main__':
    raise SystemExit(main())
