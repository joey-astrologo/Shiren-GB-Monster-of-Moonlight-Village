#!/usr/bin/env python3
"""Compare Rankings transitions after fresh boot and a real dungeon save/quit.

Reuse the curated Quit/Erase fixture, but stop before Erase and open Rank instead.
The native dungeon path must leave a dirty $9C00 map before the LCD-off title
initializer; every later Rankings transition must display a blank map while its
VBlank queue builds the board. No SRAM, WRAM, or CPU-state substitutions are used.
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import copylogspill
from gbrun import PRESS_FRAMES, _import_pyboy
import menuvwf


def _route(quit_first):
    base = 3350 if quit_first else 300
    script = ({frame: button for frame, button in copylogspill.QUIT_SCRIPT.items()
               if frame <= 2920} if quit_first else
              {60: 'start', 120: 'start', 180: 'start', 240: 'start'})
    # This three-log fixture has six title choices; Rank/Pass is the fourth.
    script.update({base: 'down', base + 70: 'down', base + 140: 'down',
                   base + 210: 'a', base + 290: 'a',
                   base + 480: 'b', base + 560: 'a',
                   base + 740: 'b', base + 820: 'a'})
    return base, script, (base + 420, base + 680, base + 940)


def _run(PyBoy, rom, ram, cgb, quit_first, png_dir):
    label = ('CGB' if cgb else 'DMG') + ('/quit' if quit_first else '/fresh')
    base, script, checkpoints = _route(quit_first)
    titles, pages, dispatches, boards = [], [], [], []
    transition_frames, white_frames = [], []
    dirty_frames, corrupt_frames, unsafe_clears = [], [], []
    pending = [None]
    labels = menuvwf.start_transition_labels()
    with tempfile.TemporaryDirectory(prefix='quitrankspill-') as tmp:
        work = os.path.join(tmp, 'rank.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=cgb)
        pb.set_emulation_speed(0)

        def title_start(_ctx):
            if tuple(pb.memory[0xC69A:0xC69D]) != (0, 1, 6):
                return
            pending[0] = {'frame': pb.frame_count, 'lcdc': pb.memory[0xFF40],
                          'dirty': sum(value != 0 for value in pb.memory[0x9C00:0xA000])}

        def title_end(_ctx):
            if pending[0] is not None:
                pending[0]['remaining'] = sum(value != 0 for value in
                                               pb.memory[0x9C00:0xA000])
                titles.append(pending[0])
                pending[0] = None

        def clearing(_ctx):
            if pb.register_file.HL == 0x9C00 and pb.memory[0xFF40] & 0x80:
                unsafe_clears.append(pb.frame_count)

        pb.hook_register(menuvwf.START_TRANSITION_BANK, labels['stoff'], title_start, None)
        pb.hook_register(menuvwf.START_TRANSITION_BANK, labels['stdone'], title_end, None)
        pb.hook_register(menuvwf.START_TRANSITION_BANK, labels['stclearmap'], clearing, None)
        pb.hook_register(31, 0x4662, lambda _ctx: pages.append(pb.frame_count), None)
        pb.hook_register(4, 0x48AA,
                         lambda _ctx: dispatches.append((pb.frame_count, pb.register_file.A)),
                         None)
        previous_selected = False
        for frame in range(checkpoints[-1] + 1):
            if frame in script:
                pb.button(script[frame], PRESS_FRAMES)
            pb.tick()
            selected = (pb.memory[0xC1B3] in (0x12, 0x14) and
                        pb.memory[0xFF40] & 0x88 == 0x88)
            if selected:
                transition_frames.append(frame)
                if any(pb.memory[0x9C00:0xA000]):
                    dirty_frames.append(frame)
                # The first frame may contain scanlines from the outgoing menu.
                # Once selected across a whole frame, every displayed pixel is white.
                if previous_selected:
                    image = pb.screen.image.copy().convert('RGB')
                    if image.getextrema() != ((255, 255),) * 3:
                        corrupt_frames.append(frame)
                    else:
                        white_frames.append(frame)
                    if png_dir and len(white_frames) + len(corrupt_frames) == 1:
                        image.save(os.path.join(png_dir, label.replace('/', '_') + '_transition.png'))
            previous_selected = selected
            if frame in checkpoints:
                # Rankings disables the Window. Quit may retain different WY and
                # offscreen map cells; compare the displayed map, pixels and BG state.
                image = pb.screen.image.copy().convert('RGB')
                boards.append({'pixels': image.tobytes(),
                               'map': b''.join(bytes(pb.memory[0x9800 + row * 32:
                                                               0x9800 + row * 32 + 20])
                                               for row in range(18)),
                               'display': tuple(pb.memory[addr] for addr in
                                                (0xFF40, 0xFF42, 0xFF43, 0xFF47)),
                               'state': pb.memory[0xC1B3]})
                if png_dir:
                    image.save(os.path.join(png_dir, label.replace('/', '_') + '_board%d.png'
                                            % len(boards)))
        pb.stop(save=False)
    problems = []
    if len(pages) != 3 or len(boards) != 3:
        problems.append('three complete Rankings entries were not reached')
    if quit_first:
        warm = [entry for entry in titles if 2920 < entry['frame'] < base]
        if (len(warm) != 1 or warm[0]['dirty'] == 0 or warm[0]['lcdc'] & 0x80 or
                not any(480 < frame < 2920 and screen == 0 for frame, screen in dispatches)):
            problems.append('real dungeon/Quit did not reach the dirty, LCD-off title initializer')
    if not titles or any(entry['remaining'] for entry in titles):
        problems.append('title initialization left stale tiles in the transition map')
    if dirty_frames:
        problems.append('%d Rankings frame(s) selected a dirty map; first f%d' %
                        (len(dirty_frames), dirty_frames[0]))
    if corrupt_frames:
        problems.append('%d complete transition frame(s) displayed garbage; first f%d' %
                        (len(corrupt_frames), corrupt_frames[0]))
    if len(white_frames) + len(corrupt_frames) < 3:
        problems.append('too few complete transition frames to validate')
    if unsafe_clears:
        problems.append('transition map was cleared while the LCD was enabled')
    if any(board != boards[0] for board in boards[1:]):
        problems.append('repeated Rankings screens changed')
    if any(board['state'] != 0 or board['display'][0] & 0xA8 != 0x80 for board in boards):
        problems.append('Rankings did not finish on its live $9800 map')
    print('quitrankspill: %s; %d title initializations; %d Rankings entries; '
          '%d clean full transition frames; %d problem(s)' %
          (label, len(titles), len(pages), len(white_frames), len(problems)))
    for problem in problems:
        print('  ' + problem)
    return problems, boards


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom')
    parser.add_argument('--ram', default=copylogspill.QUIT_RAM)
    parser.add_argument('--png-dir')
    args = parser.parse_args()
    if args.png_dir:
        os.makedirs(args.png_dir, exist_ok=True)
    PyBoy = _import_pyboy()
    problems = []
    for cgb in (False, True):
        fresh_errors, fresh = _run(PyBoy, args.rom, args.ram, cgb, False, args.png_dir)
        quit_errors, returned = _run(PyBoy, args.rom, args.ram, cgb, True, args.png_dir)
        problems.extend(fresh_errors + quit_errors)
        if fresh != returned:
            failure = '%s: save/quit Rankings differ from fresh-boot Rankings' % ('CGB' if cgb else 'DMG')
            print('quitrankspill: ' + failure)
            problems.append(failure)
    return int(bool(problems))


if __name__ == '__main__':
    raise SystemExit(main())
