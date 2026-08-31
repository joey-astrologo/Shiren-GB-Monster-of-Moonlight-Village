#!/usr/bin/env python3
"""Protect the saved-Log Orochi badge across retained Start overlays.

The completed-Log badge is native graphics at tiles $CB-$CE.  The generic two-row
ROM-text allocator also began at $CB, so opening the Log popup repainted the badge with
letters from ``Continue``.  This real-save regression watches every frame from the
settled summary through the popup, requires the four native planes never to change, and
proves both popup rows use their context-local proportional slices instead.  A second
real-input route opens Erase's No/Yes confirmation and selects No; the returned summary
must restore every badge plane before it is visible again.
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gbrun import PRESS_FRAMES, _import_pyboy                 # noqa: E402
import menuspill                                               # noqa: E402
import menuvwf                                                 # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_fays_puzzles.srm')
BUTTONS = {
    700: 'start', 760: 'start', 820: 'start', 880: 'start',
    1230: 'a',                    # Adventure -> saved Log summaries
    1460: 'a',                    # Log 1 -> Continue/New Game
}
WATCH_FIRST = 1450
SETTLED_FRAME = 1490
FINAL_FRAME = 1540
MAP = 0x9800
VISIBLE_ROWS = 18
VISIBLE_COLS = 20
EMBLEM_CELLS = ((9, 5, 0xCB), (9, 6, 0xCD),
                (10, 5, 0xCC), (10, 6, 0xCE))
GOLD_PLANES = {
    0xCB: bytes.fromhex('7f7ff9febccfe6bbdbfdfff796f3ceff'),
    0xCD: bytes.fromhex('fefe9f7f3df367dddbbfffef69cf73ff'),
    0xCC: bytes.fromhex('d9e6eef7f0bfabfbebffa7bf929c7f7f'),
    0xCE: bytes.fromhex('9b6777ef0ffdd5dfd7ffe5fd4939fefe'),
}
POPUP_ROWS = (
    (5, 5, 'Continue', menuvwf.CONFIRM_POOL_ROWS[0]),
    (7, 5, 'New Game', menuvwf.CONFIRM_POOL_ROWS[1]),
)
ERASE_BUTTONS = {
    700: 'start', 760: 'start', 820: 'start', 880: 'start',
    1250: 'down',                 # Erase Log on this six-row Start root
    1460: 'a',                    # Erase Log -> saved Log summary
    1800: 'a',                    # saved Log -> No/Yes confirmation
    2200: 'a',                    # No -> returned saved Log summary
}
ERASE_WATCH_FIRST = 1750
ERASE_FINAL_FRAME = 2450
DISPATCH = (4, 0x48AA)


def tile_plane(pb, tile):
    at = menuspill.tile_data_addr(tile)
    return bytes(pb.memory[at:at + 16])


def run(rom, ram, png=None):
    profile = menuspill.renderer_profile(rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('orochipopupspill: requires the Dot proportional renderer')
    PyBoy = _import_pyboy()
    problems = []
    corrupt_frames = []
    badge_frames = 0

    with tempfile.TemporaryDirectory(prefix='orochipopupspill-') as tmp:
        work = os.path.join(tmp, 'popup.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)

        for frame in range(FINAL_FRAME + 1):
            button = BUTTONS.get(frame)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if frame < WATCH_FIRST:
                continue
            map_ok = all(pb.memory[MAP + row * 32 + col] == tile
                         for row, col, tile in EMBLEM_CELLS)
            if map_ok:
                badge_frames += 1
                if any(tile_plane(pb, tile) != GOLD_PLANES[tile]
                       for _row, _col, tile in EMBLEM_CELLS):
                    corrupt_frames.append(frame)

        if badge_frames != FINAL_FRAME - WATCH_FIRST + 1:
            problems.append('badge map was selected for %d/%d watched frames' %
                            (badge_frames, FINAL_FRAME - WATCH_FIRST + 1))
        if corrupt_frames:
            problems.append('Orochi badge planes were overwritten at frames %s' %
                            ','.join(str(frame) for frame in corrupt_frames[:12]))

        used = set()
        for row, col, label, base in POPUP_ROWS:
            pixels = menuspill.compose(menuspill.encode(label), profile)
            want_ids = bytes(base + index for index in range(len(pixels)))
            got_ids = bytes(pb.memory[MAP + row * 32 + col:
                                      MAP + row * 32 + col + len(pixels)])
            if got_ids != want_ids:
                problems.append('%s map IDs are %s, expected %s' %
                                (label, got_ids.hex(' '), want_ids.hex(' ')))
            for index, want in enumerate(pixels):
                tile = base + index
                used.add(tile)
                if tile_plane(pb, tile) != bytes(want):
                    problems.append('%s tile $%02X planes differ' % (label, tile))

        popup_cells = {(row, col) for row in (5, 7) for col in range(4, 14)}
        generic = set(range(menuvwf.ROM_POOL_BASE, menuvwf.ROM_POOL_END))
        bad_refs = []
        for row, col in popup_cells:
            tile = pb.memory[MAP + row * 32 + col]
            if tile in generic:
                bad_refs.append((row, col, tile))
        if bad_refs:
            problems.append('popup still references generic badge-overlapping tiles: %s' %
                            ', '.join('(%d,%d)=$%02X' % ref for ref in bad_refs))

        if png:
            pb.screen.image.save(png)
        pb.stop(save=False)

    erase_corrupt = []
    erase_dispatches = []
    returned_badge_frames = 0
    with tempfile.TemporaryDirectory(prefix='orochierasespill-') as tmp:
        work = os.path.join(tmp, 'erase.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        current_frame = [0]

        def dispatch(_context=None):
            erase_dispatches.append((current_frame[0], pb.register_file.A))

        pb.hook_register(*DISPATCH, dispatch, None)
        for frame in range(ERASE_FINAL_FRAME + 1):
            current_frame[0] = frame
            button = ERASE_BUTTONS.get(frame)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if frame < ERASE_WATCH_FIRST:
                continue
            map_ok = all(pb.memory[MAP + row * 32 + col] == tile
                         for row, col, tile in EMBLEM_CELLS)
            if not map_ok:
                continue
            if frame >= 2200:
                returned_badge_frames += 1
            bad = tuple(tile for _row, _col, tile in EMBLEM_CELLS
                        if tile_plane(pb, tile) != GOLD_PLANES[tile])
            if bad:
                erase_corrupt.append((frame, bad))
        pb.stop(save=False)

    screens = tuple(screen for _frame, screen in erase_dispatches)
    if screens != (15, 23, 24, 15, 23):
        problems.append('Erase No route screens are %s, expected root/summary/'
                        'confirmation/returned-summary' % (screens,))
    if not returned_badge_frames:
        problems.append('Erase No route never exposed the returned Orochi summary')
    if erase_corrupt:
        first_frame, first_tiles = erase_corrupt[0]
        problems.append('Erase No exposed corrupt Orochi planes from frame %d; first '
                        'tiles %s' %
                        (first_frame, ' '.join('$%02X' % tile for tile in first_tiles)))

    for problem in problems:
        print('  ' + problem)
    print('orochipopupspill: %d popup badge frame(s), popup tiles %s; Erase screens %s, '
          '%d returned badge frame(s); %d problem(s)' %
          (badge_frames, ' '.join('$%02X' % tile for tile in sorted(used)),
           ','.join(str(screen) for screen in screens), returned_badge_frames,
           len(problems)))
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('orochipopupspill: missing %s' % path)
    return run(args.rom, args.ram, args.png)


if __name__ == '__main__':
    raise SystemExit(main())
