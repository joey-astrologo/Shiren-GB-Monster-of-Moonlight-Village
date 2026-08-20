#!/usr/bin/env python3
"""Verify both special status Path values reached by the Fay SRAM.

The real SRAM route enters Fay's Puzzles, starts puzzle 1 and opens the status menu.
The title must remain the full proportional ``Fay's Puzzles``; only the ten-cell Path
value becomes proportional ``Puzzle``. A second run continues Log 1 and requires the
same private four-tile field for ``Expert``. This catches accidental shared-string
renames, stale padding, incorrect planes and any overrun into the column-19 border.
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gbrun import _import_pyboy, PRESS_FRAMES                 # noqa: E402
import menuspill                                               # noqa: E402
import statusspill                                             # noqa: E402
import statusvwf                                               # noqa: E402
import dotfont                                                 # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_fays_puzzles.srm')
SHADOW = 0xC3C9                    # status row 6, columns 9..19
BGMAP = 0x98C9
FRAMES = 2660
BOOT = {
    700: 'start', 760: 'start', 820: 'start', 880: 'start',
}
FAY_ROUTE = {
    **BOOT,
    1230: 'down', 1270: 'down', 1310: 'down', 1350: 'down', 1390: 'down',
    1460: 'a',                    # Fay's Puzzles
    1750: 'a', 1950: 'a',        # puzzle 1, then enter
    2500: 'b',                    # in-dungeon status menu
}
EXPERT_ROUTE = {
    **BOOT,
    1230: 'a',                    # Adventure
    1460: 'a', 1700: 'a',        # Log 1, Continue
    2500: 'b',
}


def expected(label):
    base, cap = statusvwf.PRIVATE_RUNS['Path']
    return bytes((0,)) * (10 - cap) + bytes(range(base, base + cap)) + bytes((0xBF,))


def run_route(PyBoy, rom, ram, profile, name, route, label, want_mode,
              required_dispatch, check_title=False, png=None):
    problems = []
    dispatches = []
    title_matches = []
    want = expected(label)

    with tempfile.TemporaryDirectory(prefix='faypathspill-%s-' % name.lower()) as tmp:
        work = os.path.join(tmp, 'path.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)
        frame = [0]

        def dispatch(_ctx=None):
            dispatches.append((frame[0], pb.register_file.A))

        pb.hook_register(4, 0x48AA, dispatch, None)
        title_codes = menuspill.encode("Fay's Puzzles")
        for current in range(FRAMES):
            frame[0] = current
            button = route.get(current)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if check_title and current == 1120:
                for record in menuspill.records(pb, profile):
                    if menuspill.visible_row_matches(
                            pb, profile, record[0], title_codes, raw=1):
                        title_matches.append(record)

        shadow = bytes(pb.memory[SHADOW:SHADOW + len(want)])
        bgmap = bytes(pb.memory[BGMAP:BGMAP + len(want)])
        mode = pb.memory[0xC9E6]
        invariant = menuspill.frame_invariant(pb, profile)
        base, cap = statusvwf.PRIVATE_RUNS['Path']
        planes = {tile: bytes(pb.memory[menuspill.tile_data_addr(tile):
                                      menuspill.tile_data_addr(tile) + 16])
                  for tile in range(base, base + cap)}
        image = pb.screen.image.copy()
        pb.stop(save=False)

    if check_title and not title_matches:
        problems.append("title menu did not visibly retain proportional `Fay's Puzzles`")
    if not any(index == required_dispatch for _at, index in dispatches):
        problems.append('%s route never dispatched expected screen %d' %
                        (name, required_dispatch))
    if not any(index == 0 for _at, index in dispatches):
        problems.append('%s route never opened the in-dungeon status menu' % name)
    if mode != want_mode:
        problems.append('%s Path mode is $%02X, expected $%02X' %
                        (name, mode, want_mode))
    if shadow != want:
        problems.append('%s shadow is %s, expected %s (right-aligned `%s` + border)' %
                        (name, shadow.hex(' '), want.hex(' '), label))
    if bgmap != want:
        problems.append('%s BG map is %s, expected %s' %
                        (name, bgmap.hex(' '), want.hex(' ')))
    wants = statusspill.expected_tiles(dotfont.load_approved(), label, cap, right=True)
    for index, raster in enumerate(wants):
        if planes[base + index] != raster:
            problems.append('%s Path tile $%02X is not plane-exact' %
                            (name, base + index))
            break
    if invariant:
        problems.append('%s settled menu has %d VWF ownership error(s): %s' %
                        (name, len(invariant), invariant[:4]))
    if png:
        image.save(png)
    print('faypathspill: %-6s mode=%d Path=%s border=$%02X dispatches=%s; %d problem(s)' %
          (name, mode, shadow[:-1].hex(' '), shadow[-1],
           ' '.join('f%d:%d' % event for event in dispatches), len(problems)))
    return problems


def run(rom, ram, png=None):
    profile = menuspill.renderer_profile(rom)
    PyBoy = _import_pyboy()
    fay_png = expert_png = None
    if png:
        root, ext = os.path.splitext(png)
        fay_png, expert_png = root + '-puzzle' + ext, root + '-expert' + ext
    problems = run_route(PyBoy, rom, ram, profile, 'Puzzle', FAY_ROUTE, 'Puzzle', 0,
                         17, check_title=True, png=fay_png)
    problems += run_route(PyBoy, rom, ram, profile, 'Expert', EXPERT_ROUTE, 'Expert', 4,
                          21, png=expert_png)
    for problem in problems:
        print('  ' + problem)
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.isfile(path):
            raise SystemExit('faypathspill: missing %s' % path)
    return 1 if run(args.rom, args.ram, args.png) else 0


if __name__ == '__main__':
    raise SystemExit(main())
