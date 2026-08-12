#!/usr/bin/env python3
"""Replay the rescued-child final exit and require a live Rankings result page.

Log 1 in ``saves/shiren_en_log_1_freeze_on_exit.srm`` starts one step above the final
exit with Nagi following.  Down opens the ``Go on / Stay here`` choice and A confirms
it.  This is also the shared transition that froze with Koppa.

The rescue-result route disables the LCD before drawing Rankings.  The proportional
rank-name uploader used to arm the VBlank transfer queue anyway; an off LCD never runs
that consumer, so the game remained on a white screen forever.  The fixed route directly
copies all five rows' private tiles while the LCD is off, then reaches the live Rankings
page without using the queue.
"""
import argparse
import os
import shutil
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import gbasm                                                    # noqa: E402
from gbrun import _import_pyboy, PRESS_FRAMES                   # noqa: E402
import menuspill                                                 # noqa: E402
import rankvwf                                                  # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log_1_freeze_on_exit.srm')
BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a',
    2610: 'down',                  # step onto the final exit
    2800: 'a',                     # choose Go on
}
def dark_pixels(image):
    return sum(value < 96 for value in image.convert('L').tobytes())


def run(rom_path, ram_path, png=None, frames=3400):
    profile = menuspill.renderer_profile(rom_path)
    PyBoy = _import_pyboy()
    with tempfile.TemporaryDirectory(prefix='rescueexitspill-') as tmp:
        work = os.path.join(tmp, 'exit.gb')
        shutil.copyfile(rom_path, work)
        shutil.copyfile(ram_path, work + '.ram')
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)

        frame = [0]
        entries = []
        direct = []
        queue_arms = []
        page_calls = []
        _, transition = gbasm.assemble(rankvwf.TRANSITION_SRC, rankvwf.TRANSITION_AT)
        _, upload = gbasm.assemble(rankvwf.UPLOAD_SRC, rankvwf.UPLOAD_AT)

        def at_entry(_ctx=None):
            entries.append((frame[0], bytes(pb.memory[0xC6E3:0xC6E9])))

        pb.hook_register(rankvwf.FAR_BANK, rankvwf.ENTRY_AT, at_entry, None)
        pb.hook_register(rankvwf.TRANSITION_BANK, transition['rankdirect'],
                         lambda _ctx: direct.append(frame[0]), None)
        pb.hook_register(rankvwf.AUX_BANK, upload['arm'],
                         lambda _ctx: queue_arms.append(frame[0]), None)
        pb.hook_register(rankvwf.RANK_BANK, 0x4662,
                         lambda _ctx: page_calls.append(frame[0]), None)

        for value in range(frames):
            frame[0] = value
            button = BOOT.get(value)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()

        shot = pb.screen.image.copy()
        final_dark = dark_pixels(shot)
        final_lcdc = pb.memory[0xFF40]
        final_pc = pb.register_file.PC
        tiles = {
            tile: bytes(pb.memory[menuspill.tile_data_addr(tile):
                                  menuspill.tile_data_addr(tile) + 16])
            for tile in range(rankvwf.POOL_BASE,
                              rankvwf.POOL_BASE + rankvwf.ROWS * rankvwf.TILES_PER_ROW)
        }
        pb.stop(save=False)

    problems = []
    if len(page_calls) != 1:
        problems.append('Rankings page drawer ran %d time(s), expected 1' % len(page_calls))
    if len(entries) != rankvwf.ROWS or len(direct) != rankvwf.ROWS:
        problems.append('rank rows: %d entry / %d LCD-off direct, expected %d/%d'
                        % (len(entries), len(direct), rankvwf.ROWS, rankvwf.ROWS))
    if queue_arms:
        problems.append('LCD-off result armed the VBlank queue at frame(s) %s'
                        % ' '.join(map(str, queue_arms)))
    for row, (_entry_frame, codes) in enumerate(entries):
        visible = list(codes[:codes.find(b'\xFF') if b'\xFF' in codes else len(codes)])
        expected = menuspill.compose(visible, profile)
        expected += [bytearray(16)
                     for _ in range(rankvwf.TILES_PER_ROW - len(expected))]
        base = rankvwf.POOL_BASE + row * rankvwf.TILES_PER_ROW
        for index, want in enumerate(expected):
            got = tiles[base + index]
            if got != bytes(want):
                problems.append('row %d tile $%02X differs after direct copy'
                                % (row, base + index))
                break
    if not final_lcdc & 0x80:
        problems.append('Rankings settled with LCD disabled (LCDC=$%02X)' % final_lcdc)
    if final_dark < 1000:
        problems.append('settled result is still blank (%d dark pixels, PC=$%04X)'
                        % (final_dark, final_pc))

    if png:
        shot.save(png)
        print('rescueexitspill: wrote %s' % png)
    print('rescueexitspill: page=%d; rank rows %d entry / %d direct / %d queue; '
          'LCDC=$%02X PC=$%04X dark=%d; %d problem(s)'
          % (len(page_calls), len(entries), len(direct), len(queue_arms),
             final_lcdc, final_pc, final_dark, len(problems)))
    for problem in problems:
        print('  ' + problem)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png')
    parser.add_argument('--frames', type=int, default=3400)
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('rescueexitspill: missing %s' % path)
    return run(args.rom, args.ram, args.png, args.frames)


if __name__ == '__main__':
    raise SystemExit(main())
