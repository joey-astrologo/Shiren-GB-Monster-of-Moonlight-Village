#!/usr/bin/env python3
"""Regressions for Erase Log 3 rebuilding the title menu with Copy Log in VWF.

Both dedicated fixtures are byte-for-byte copies of the supplied Koppa-floor-v2 SRAM.
They begin with all three logs occupied, so the title menu has six rows and no Copy Log.
One route erases Log 3 directly after boot; the other loads Log 1, uses Quit to save and
return to the title, then erases Log 3.  Those paths enter the rebuilt title transaction
with different LCD states, and both exposed stale four-tile allocator records.  The game
then rebuilds an eight-row title menu containing New Log and Copy Log. Every rebuilt title
row must own a proportional allocator record, exact shadow cells, and exact VRAM planes.

    python3 tools/copylogspill.py build/shiren_en.gb
    python3 tools/copylogspill.py build/shiren_en.gb --png-dir build/copylogspill
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
import menuromcensus                                           # noqa: E402
import menuspill                                                # noqa: E402
import menuvwf                                                 # noqa: E402


DIRECT_RAM = os.path.join(ROOT, 'saves', 'shiren_en_log_3_erase_copy_log_vwf.srm')
QUIT_RAM = os.path.join(ROOT, 'saves', 'shiren_en_log_1_quit_erase_copy_log_vwf.srm')
TITLE_SHAPE = (0, 1, 8, 11, 2)
TITLE_ROWS = (
    'Adventure', 'New Log', 'Copy Log', 'Erase Log',
    'Rename', 'Rank/Pass', 'Replay', "Fay's Puzzles",
)
DIRECT_SCRIPT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'down', 350: 'a', 400: 'down', 450: 'down', 520: 'a',
    680: 'down', 750: 'a',
}
QUIT_SCRIPT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a',
    2620: 'b', 2700: 'up', 2780: 'a', 2920: 'a',
    3350: 'down', 3420: 'a', 3500: 'down', 3570: 'down', 3650: 'a',
    3820: 'down', 3900: 'a',
}
SHADOW = 0xC300
BGMAP = 0x9800


def encoded(text):
    return bytes(menuvwf.propvwf.EN_CODES[ch] for ch in text)


def run(rom_path, ram_path, script, label, png=None, frames=900):
    PyBoy = _import_pyboy()
    profile = menuspill.renderer_profile(rom_path)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('copylogspill: requires the proportional production renderer')

    problems = []
    pending = [None]
    calls = []
    final_rows = {}
    with tempfile.TemporaryDirectory(prefix='copylogspill-') as tmp:
        work = os.path.join(tmp, 'copylog.gb')
        shutil.copyfile(rom_path, work)
        shutil.copyfile(ram_path, work + '.ram')
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        frame = [0]

        def at_entry(_ctx=None):
            shape = tuple(pb.memory[at] for at in range(0xC69A, 0xC69F))
            if shape != TITLE_SHAPE:
                return
            row = pb.register_file.D
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            cells = []
            for at in range(source, source + 18):
                value = pb.memory[at]
                if value == 0xFF:
                    break
                cells.append(value)
            pending[0] = (frame[0], row, pb.register_file.HL, bytes(cells))

        def at_epilog(_ctx=None):
            item = pending[0]
            if item is None:
                return
            pending[0] = None
            seen_frame, row, key, cells = item
            calls.append((seen_frame, row))
            if row >= len(TITLE_ROWS):
                problems.append('f%d: rebuilt title emitted unexpected row %d' %
                                (seen_frame, row))
                return
            want_codes = encoded(TITLE_ROWS[row])
            if cells != b'\x00' + want_codes:
                problems.append('f%d: row %d is not %r: %s' %
                                (seen_frame, row, TITLE_ROWS[row], cells.hex()))
                return
            pixels = menuspill.compose(want_codes, profile)
            records = [record for record in menuspill.records(pb, profile)
                       if record[0] == key]
            if not records:
                problems.append('f%d: %s has no VWF allocator record' %
                                (seen_frame, TITLE_ROWS[row]))
                return
            _record_key, base, cap, raw = records[-1]
            if raw != 1:
                problems.append('f%d: %s record has raw prefix %d, expected 1' %
                                (seen_frame, TITLE_ROWS[row], raw))
                return
            if cap < len(pixels):
                problems.append('f%d: %s needs %d VWF tiles but retained cap %d' %
                                (seen_frame, TITLE_ROWS[row], len(pixels), cap))
                return
            tile_ids = bytes(base + index for index in range(len(pixels)))
            padding = TITLE_SHAPE[3] - raw - len(pixels)
            want_shadow = b'\xBE\x00' + tile_ids + bytes(padding) + b'\xBF'
            got_shadow = bytes(pb.memory[key:key + len(want_shadow)])
            if got_shadow != want_shadow:
                problems.append('f%d: %s shadow is not VWF: want %s got %s' %
                                (seen_frame, TITLE_ROWS[row], want_shadow.hex(),
                                 got_shadow.hex()))
                return
            for index, want in enumerate(pixels):
                tile = base + index
                at = menuspill.tile_data_addr(tile)
                got = bytes(pb.memory[at:at + 16])
                if got != bytes(want):
                    problems.append('f%d: %s tile $%02X planes differ' %
                                    (seen_frame, TITLE_ROWS[row], tile))
                    return
            final_rows[row] = (key, tile_ids, tuple(bytes(pixel) for pixel in pixels))

        pb.hook_register(*menuromcensus.ROW_ENTRY, at_entry, None)
        pb.hook_register(*menuromcensus.ROW_EPILOG, at_epilog, None)
        for frame[0] in range(frames):
            button = script.get(frame[0])
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()

        if png:
            pb.screen.image.save(png)
            print('copylogspill: wrote %s' % png)
        final_state = pb.memory[0xC0D7]
        final_lcdc = pb.memory[0xFF40]
        for row, (key, tile_ids, pixels) in final_rows.items():
            first = key + 2 - SHADOW
            if bytes(pb.memory[SHADOW + first:SHADOW + first + len(tile_ids)]) != tile_ids:
                problems.append('%s is no longer present in the settled shadow map' %
                                TITLE_ROWS[row])
                continue
            if bytes(pb.memory[BGMAP + first:BGMAP + first + len(tile_ids)]) != tile_ids:
                problems.append('%s is not visible in the settled BG map' % TITLE_ROWS[row])
                continue
            for index, want in enumerate(pixels):
                at = menuspill.tile_data_addr(tile_ids[index])
                if bytes(pb.memory[at:at + 16]) != want:
                    problems.append('%s settled tile $%02X was overwritten' %
                                    (TITLE_ROWS[row], tile_ids[index]))
                    break
        pb.stop(save=False)

    rows_seen = {row for _frame, row in calls}
    missing = set(range(len(TITLE_ROWS))) - rows_seen
    if missing:
        problems.append('post-erase title did not draw row(s) %s' %
                        ', '.join(str(row) for row in sorted(missing)))
    if 2 not in final_rows:
        problems.append('Copy Log never completed a plane-exact VWF row')
    if final_state != 0:
        problems.append('title transaction state remained $%02X' % final_state)
    if not final_lcdc & 0x80:
        problems.append('title route ended with LCD disabled (LCDC=$%02X)' % final_lcdc)

    print('copylogspill: %s rebuilt %d/%d title rows; Copy Log %s; %d problem(s)'
          % (label, len(rows_seen), len(TITLE_ROWS),
           'VWF exact' if 2 in final_rows else 'VWF missing', len(problems)))
    for problem in problems:
        print('  ' + problem)
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--direct-ram', default=DIRECT_RAM)
    parser.add_argument('--quit-ram', default=QUIT_RAM)
    parser.add_argument('--png-dir')
    args = parser.parse_args()
    for path in (args.rom, args.direct_ram, args.quit_ram):
        if not os.path.exists(path):
            raise SystemExit('copylogspill: missing %s' % path)
    if args.png_dir:
        os.makedirs(args.png_dir, exist_ok=True)
    routes = (
        ('direct erase', args.direct_ram, DIRECT_SCRIPT, 900, 'direct.png'),
        ('load/quit/erase', args.quit_ram, QUIT_SCRIPT, 4200, 'quit.png'),
    )
    problems = []
    for label, ram, script, frames, image_name in routes:
        png = os.path.join(args.png_dir, image_name) if args.png_dir else None
        problems.extend('%s: %s' % (label, problem)
                        for problem in run(args.rom, ram, script, label, png, frames))
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
