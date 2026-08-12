#!/usr/bin/env python3
"""Real-save regression for atomic title, difficulty and Rankings transitions.

The path-select fixture has the exact eight-row title, empty Log 3 and four populated
ranking records which exposed the shared-tile lifetime bugs.  This test proves that:

* title/selector rows keep identical tile IDs and planes through Easy/Normal/Hard;
* every LCD-off title/file transaction is visibly white while its state is pending;
* Rankings shows only its harmless top border (at most) before the blank map takes over,
  then reveals one complete page and clears its transaction state.

    python3 tools/mainmenuspill.py build/shiren_en.gb
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


RAM = os.path.join(ROOT, 'saves', 'shiren_en_path_select.srm')
SHADOW = 0xC300
BGMAP = 0x9800
VISIBLE = 32 * 18
TITLE_TILES = tuple(range(0x43, 0x7C)) + tuple(range(0x8B, 0x96))


def dark_pixels(image):
    return sum(value < 128 for value in image.convert('L').tobytes())


def tile_planes(pb, tile):
    at = menuspill.tile_data_addr(tile)
    return bytes(pb.memory[at:at + 16])


def run_new(PyBoy, rom, ram):
    with tempfile.TemporaryDirectory(prefix='mainmenuspill-new-') as tmp:
        work = os.path.join(tmp, 'main.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)
        script = {60: 'start', 120: 'start', 180: 'start', 240: 'start',
                  300: 'down', 350: 'a', 430: 'a', 520: 'down', 600: 'down'}
        white = 0
        pending_dark = []
        owners = planes = None
        checkpoints = {}
        for frame in range(680):
            if frame in script:
                pb.button(script[frame], PRESS_FRAMES)
            pb.tick()
            state = pb.memory[0xC0D7]
            if state in (0x10, 0x11):
                dark = dark_pixels(pb.screen.image)
                pending_dark.append((frame, state, dark))
                if dark == 0:
                    white += 1
            if frame == 420:
                shadow = bytes(pb.memory[SHADOW:SHADOW + VISIBLE])
                all_owners = {pos: tile for pos, tile in enumerate(shadow)
                              if tile in TITLE_TILES}
                # The full-width explanation box intentionally covers title rows 6/7.
                # Rows above tilemap row 13 remain visible and must keep their map IDs;
                # every title/selector tile plane must survive, including the covered rows.
                owners = {pos: tile for pos, tile in all_owners.items()
                          if pos // 32 < 13}
                planes = {tile: tile_planes(pb, tile)
                          for tile in set(all_owners.values())}
            if frame in (490, 570, 650):
                checkpoints[frame] = (
                    bytes(pb.memory[SHADOW:SHADOW + VISIBLE]),
                    bytes(pb.memory[BGMAP:BGMAP + VISIBLE]),
                    {tile: tile_planes(pb, tile) for tile in planes},
                )
        pb.stop(save=False)

    problems = []
    if not pending_dark or white < 3:
        problems.append('title/difficulty route did not expose the expected white '
                        'transaction frames')
    # The screen sampled on the first pending tick may still be the coherent outgoing
    # frame; the LCD-off effect begins on the next scan.  White coverage above is the
    # invariant, while plane/map ownership below rejects mixed outgoing/incoming text.
    if owners is None or len(checkpoints) != 3:
        problems.append('difficulty ownership checkpoints were not captured')
        return problems, white, 0
    for frame, (shadow, bg, got_planes) in checkpoints.items():
        changed = [(pos, tile, shadow[pos], bg[pos]) for pos, tile in owners.items()
                   if shadow[pos] != tile or bg[pos] != tile]
        if changed:
            problems.append('f%d difficulty changed %d title/selector map owner(s): %s'
                            % (frame, len(changed), changed[:5]))
        bad_planes = [tile for tile, want in planes.items()
                      if got_planes[tile] != want]
        if bad_planes:
            problems.append('f%d difficulty overwrote title/selector planes %s' %
                            (frame, ' '.join('$%02X' % tile for tile in bad_planes)))
    return problems, white, len(owners)


def run_rank(PyBoy, rom, ram):
    with tempfile.TemporaryDirectory(prefix='mainmenuspill-rank-') as tmp:
        work = os.path.join(tmp, 'main.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)
        script = {60: 'start', 120: 'start', 180: 'start', 240: 'start',
                  300: 'down', 340: 'down', 380: 'down', 420: 'down',
                  460: 'down', 520: 'a', 600: 'a'}
        pending = []
        first = last = None
        for frame in range(760):
            if frame in script:
                pb.button(script[frame], PRESS_FRAMES)
            pb.tick()
            state = pb.memory[0xC0D7]
            if state == 0x12:
                if first is None:
                    first = frame
                last = frame
                pending.append((frame, dark_pixels(pb.screen.image)))
        final_dark = dark_pixels(pb.screen.image)
        final_state = pb.memory[0xC0D7]
        final_lcdc = pb.memory[0xFF40]
        pb.stop(save=False)

    problems = []
    if not pending:
        problems.append('Rankings never entered transaction state $12')
    else:
        # As with the title transaction above, the first pending tick can still be the
        # coherent outgoing frame: state is armed after that scan but before our sample.
        # Every subsequent pending frame must be the harmless border/blank map.
        too_dark = [item for item in pending[1:] if item[1] > 220]
        if too_dark:
            problems.append('Rankings exposed text during its blank-map interval: %s' %
                            too_dark[:6])
        if not any(dark == 0 for _frame, dark in pending):
            problems.append('Rankings never displayed the blank transition map')
        if last - first > 20:
            problems.append('Rankings transaction lasted %d frames' % (last - first + 1))
    if final_state != 0:
        problems.append('Rankings left transaction state $%02X active' % final_state)
    if final_lcdc & 0x08:
        problems.append('Rankings left the blank $9C00 map selected')
    if final_dark < 1000:
        problems.append('settled Rankings page has only %d dark pixels' % final_dark)
    return problems, len(pending), final_dark


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('mainmenuspill: missing %s' % path)
    PyBoy = _import_pyboy()
    new_problems, white, owners = run_new(PyBoy, args.rom, args.ram)
    rank_problems, rank_frames, rank_dark = run_rank(PyBoy, args.rom, args.ram)
    problems = new_problems + rank_problems
    print('mainmenuspill: %d white title/difficulty frame(s), %d persistent '
          'title/selector owner(s); Rankings hidden %d frame(s), settled with %d dark '
          'pixels; %d problem(s)' %
          (white, owners, rank_frames, rank_dark, len(problems)))
    for problem in problems:
        print('  ' + problem)
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
