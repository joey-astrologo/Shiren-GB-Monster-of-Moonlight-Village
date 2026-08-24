#!/usr/bin/env python3
"""Prove that every real Item page can return to Status without a full-screen blank.

The tracked 18-item SRAM supplies four pages, including a short final page.  Four
independent boots leave Items from page 1, 2, 3, and 4 through the real B-button handler.
For each route this test requires the exact root-Status/Items stack predecessor accepted
by ``statusvwf``, an LCD-on status build, nine bounded VBlank uploads, and no rendered
LCD-off/all-white frame.  It also proves that every visible BG cell is always either its
outgoing Item state or its final Status state, while the persistent Window is unchanged.
"""

import argparse
import os
import shutil
import sys
import tempfile


TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

from gbrun import PRESS_FRAMES, _import_pyboy                    # noqa: E402
import gbasm                                                       # noqa: E402
import menuspill                                                   # noqa: E402
import menuvwf                                                     # noqa: E402
import statusvwf                                                   # noqa: E402


BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a',
    2620: 'b',
}
ITEM_SHAPE = (0, 3, 5, 18, 0x02)
EXPECTED_SELECTORS = (0, 5, 10, 15)
EXPECTED_CAPS = (6, 7, 5, 2, 4, 4, 4, 4, 4)
VISIBLE_BG_ROWS = range(16)       # Window begins at screen row 16 (WY=$80).
VISIBLE_WINDOW_ROWS = range(2)


def tile_planes(snapshot, tile):
    address = menuspill.tile_data_addr(tile)
    start = address - 0x8800
    return snapshot['tiles'][start:start + 16]


def snapshot(pb):
    return {
        'bg': bytes(pb.memory[0x9800:0x9C00]),
        'window': bytes(pb.memory[0x9C00:0xA000]),
        'tiles': bytes(pb.memory[0x8800:0x9800]),
        'lcdc': pb.memory[0xFF40],
        'ly': pb.memory[0xFF44],
    }


def cells(state, layer, rows):
    tilemap = state[layer]
    return tuple((tilemap[row * 32 + col],
                  tile_planes(state, tilemap[row * 32 + col]))
                 for row in rows for col in range(20))


def white_frame(image):
    return len(set(image.convert('RGB').getdata())) == 1


def labels():
    font = statusvwf.propvwf.dotfont.load_approved()
    widths = tuple(font.advance_code(code) for code in statusvwf.SLOT_CODES)
    _code, found = gbasm.assemble(statusvwf._source(widths), statusvwf.CODE_AT)
    return found


def run_page(PyBoy, rom_path, ram_path, target, runtime, png_dir=None, frames=3500):
    problems = []
    with tempfile.TemporaryDirectory(prefix='itemexitspill-') as tmp:
        run_rom = os.path.join(tmp, 'itemexit.gb')
        shutil.copyfile(rom_path, run_rom)
        shutil.copyfile(ram_path, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        scheduled = dict(BOOT)
        item_open_scheduled = [False]
        page_starts = []
        page_completes = []
        target_b_at = [None]
        b_at = [None]
        outgoing = [None]
        outgoing_image = [None]
        status_dispatches = []
        status_entries = []
        upload_starts = []
        live_uploads = []
        legacy_fallbacks = []
        samples = []

        def dispatch(_ctx=None):
            screen = pb.register_file.A
            if screen == 0 and not item_open_scheduled[0] and b_at[0] is None:
                scheduled[frame[0] + 80] = 'a'
                item_open_scheduled[0] = True
            if b_at[0] is not None and screen == 0:
                status_dispatches.append(frame[0])

        def item_row(_ctx=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if shape != ITEM_SHAPE:
                return
            row = pb.register_file.D
            if row == 0:
                page_starts.append((frame[0], pb.memory[0xC6AC]))
            if row != 4 or b_at[0] is not None:
                return
            selector = pb.memory[0xC6AC]
            page = selector // 5 + 1 if selector < pb.memory[0xC6AA] else 0
            page_completes.append((frame[0], page, selector))
            at = frame[0] + 90
            if page < target:
                scheduled[at] = 'right'
            elif page == target:
                scheduled[at] = 'b'
                target_b_at[0] = at

        def status_entry(_ctx=None):
            if b_at[0] is None:
                return
            status_entries.append({
                'frame': frame[0],
                'lcdc': pb.memory[0xFF40],
                'ly': pb.memory[0xFF44],
                'stack': tuple(pb.memory[0xC534 + i] for i in range(3)),
                'mode': pb.memory[0xC6A3],
                'count': pb.memory[0xC6AA],
                'selector': pb.memory[0xC6AC],
                'scroll': (pb.memory[0xFF42], pb.memory[0xFF43]),
                'window': (pb.memory[0xFF4A], pb.memory[0xFF4B]),
            })

        def live_done(_ctx=None):
            if b_at[0] is not None:
                live_uploads.append((frame[0], pb.memory[0xFF44],
                                     pb.memory[statusvwf.S_CAP]))

        def upload_start(_ctx=None):
            if b_at[0] is not None:
                upload_starts.append((frame[0], pb.memory[0xFF44],
                                      pb.memory[statusvwf.S_CAP]))

        def fallback(_ctx=None):
            if b_at[0] is not None:
                legacy_fallbacks.append(frame[0])

        pb.hook_register(4, 0x48AA, dispatch, None)
        profile = menuspill.renderer_profile(rom_path)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], item_row, None)
        pb.hook_register(statusvwf.FAR_BANK, runtime['statusentry'], status_entry, None)
        pb.hook_register(statusvwf.FAR_BANK, runtime['uploadcopy'], upload_start, None)
        pb.hook_register(statusvwf.FAR_BANK, runtime['uploadlivedone'], live_done, None)
        pb.hook_register(statusvwf.FAR_BANK, runtime['statusready'], fallback, None)

        for frame[0] in range(frames):
            action = scheduled.get(frame[0])
            if action == 'b' and frame[0] == target_b_at[0] and b_at[0] is None:
                b_at[0] = frame[0]
                outgoing[0] = snapshot(pb)
                outgoing_image[0] = pb.screen.image.copy()
                if png_dir:
                    outgoing_image[0].save(os.path.join(
                        png_dir, 'page%d_outgoing_f%04d.png' % (target, frame[0])))
            if action:
                pb.button(action, PRESS_FRAMES)
            pb.tick()
            if b_at[0] is not None and frame[0] <= b_at[0] + 130:
                image = pb.screen.image.copy()
                samples.append((frame[0], snapshot(pb), image))
                if png_dir and (frame[0] == b_at[0] or
                                frame[0] in status_dispatches or
                                any(frame[0] == event[0] for event in live_uploads)):
                    image.save(os.path.join(
                        png_dir, 'page%d_transition_f%04d.png' % (target, frame[0])))

        if b_at[0] is None or outgoing[0] is None:
            problems.append('page %d never scheduled B from its completed draw' % target)
            final = snapshot(pb)
        else:
            final = samples[-1][1]

        selector = None if outgoing[0] is None else pb.memory[0xC6AC]
        if outgoing[0] is not None:
            # The selected item remains stable through the Status rebuild; use the
            # recorded completed-page selector instead of the final stale WRAM value.
            matching = [event for event in page_completes if event[1] == target]
            selector = matching[-1][2] if matching else None
        if selector != EXPECTED_SELECTORS[target - 1]:
            problems.append('page %d left with selector %r, expected %d' %
                            (target, selector, EXPECTED_SELECTORS[target - 1]))
        if not status_dispatches:
            problems.append('page %d never dispatched root Status after B' % target)
        if len(status_entries) != 1:
            problems.append('page %d reached status entry %d times, expected once' %
                            (target, len(status_entries)))
        else:
            entry = status_entries[0]
            expected_entry = {
                'stack': (0, 0, 1), 'mode': 0, 'count': 18,
                'selector': EXPECTED_SELECTORS[target - 1],
                'scroll': (0, 0), 'window': (0x80, 0x07),
            }
            for key, want in expected_entry.items():
                if entry[key] != want:
                    problems.append('page %d status-entry %s is %r, expected %r' %
                                    (target, key, entry[key], want))
            if entry['lcdc'] & 0xF8 != 0xE0:
                problems.append('page %d status entry LCDC is $%02X, expected $E0-$E7' %
                                (target, entry['lcdc']))
        if legacy_fallbacks:
            problems.append('page %d used the LCD-off status fallback at %s' %
                            (target, ' '.join('f%d' % at for at in legacy_fallbacks)))
        caps = tuple(cap for _at, _ly, cap in live_uploads)
        if caps != EXPECTED_CAPS:
            problems.append('page %d live upload caps are %s, expected %s' %
                            (target, caps, EXPECTED_CAPS))
        for at, ly, cap in live_uploads:
            if not 0x90 <= ly <= 0x99:
                problems.append('page %d cap-%d upload ended outside VBlank at f%d '
                                '(LY=$%02X)' % (target, cap, at, ly))
        if len(upload_starts) != len(live_uploads):
            problems.append('page %d observed %d upload starts and %d completions' %
                            (target, len(upload_starts), len(live_uploads)))
        for start, done in zip(upload_starts, live_uploads):
            if start[1] != 0x90 or start[2] != done[2]:
                problems.append('page %d cap-%d upload began at LY=$%02X '
                                '(completion cap %d)' %
                                (target, start[2], start[1], done[2]))

        lcd_off = [at for at, state, _image in samples if not state['lcdc'] & 0x80]
        whites = [at for at, _state, image in samples if white_frame(image)]
        if lcd_off:
            problems.append('page %d rendered with LCD off at %s' %
                            (target, ' '.join('f%d' % at for at in lcd_off)))
        if whites:
            problems.append('page %d produced an all-white frame at %s' %
                            (target, ' '.join('f%d' % at for at in whites)))

        if outgoing[0] is not None:
            private = ({tile for base, cap in statusvwf.PRIVATE_RUNS.values()
                        for tile in range(base, base + cap)} |
                       set(statusvwf.WEAPON_TILES + statusvwf.SHIELD_TILES))
            outgoing_bg_refs = {outgoing[0]['bg'][row * 32 + col]
                                for row in VISIBLE_BG_ROWS for col in range(20)}
            outgoing_win_refs = {outgoing[0]['window'][row * 32 + col]
                                 for row in VISIBLE_WINDOW_ROWS for col in range(20)}
            collision = sorted(private & (outgoing_bg_refs | outgoing_win_refs))
            if collision:
                problems.append('page %d visibly references status-private tiles %s' %
                                (target, ' '.join('$%02X' % tile
                                                  for tile in collision)))

            old_bg = cells(outgoing[0], 'bg', VISIBLE_BG_ROWS)
            new_bg = cells(final, 'bg', VISIBLE_BG_ROWS)
            old_win = cells(outgoing[0], 'window', VISIBLE_WINDOW_ROWS)
            final_win = cells(final, 'window', VISIBLE_WINDOW_ROWS)
            if final_win != old_win:
                problems.append('page %d changed the persistent Window map/planes' % target)
            regressed = set()
            reached_new = set()
            invalid = []
            for at, state, _image in samples:
                current_bg = cells(state, 'bg', VISIBLE_BG_ROWS)
                current_win = cells(state, 'window', VISIBLE_WINDOW_ROWS)
                if current_win != old_win and len(invalid) < 8:
                    invalid.append((at, 'Window'))
                for index, value in enumerate(current_bg):
                    if value not in (old_bg[index], new_bg[index]):
                        if len(invalid) < 8:
                            invalid.append((at, 'BG cell %d' % index))
                    if old_bg[index] != new_bg[index]:
                        if value == new_bg[index]:
                            reached_new.add(index)
                        elif index in reached_new and value == old_bg[index]:
                            regressed.add(index)
            if invalid:
                problems.append('page %d exposed non-owned intermediate states: %s' %
                                (target, ', '.join('f%d %s' % event
                                                   for event in invalid)))
            if regressed:
                problems.append('page %d regressed %d visible BG cell(s) to Items' %
                                (target, len(regressed)))

        problems.extend('page %d %s' % (target, problem)
                        for problem in menuspill.status_fragment_problems(pb))
        result = {
            'page': target,
            'b_at': b_at[0],
            'dispatch': status_dispatches[0] if status_dispatches else None,
            'entry': status_entries[0]['frame'] if status_entries else None,
            'uploads': tuple(live_uploads),
            'upload_starts': tuple(upload_starts),
            'lcd_off': len(lcd_off),
            'white': len(whites),
            'final_bg': cells(final, 'bg', VISIBLE_BG_ROWS),
            'final_window': cells(final, 'window', VISIBLE_WINDOW_ROWS),
            'problems': problems,
        }
        pb.stop(save=False)
        return result


def run(rom_path, ram_path, png_dir=None, frames=3500):
    if png_dir:
        os.makedirs(png_dir, exist_ok=True)
    profile = menuspill.renderer_profile(rom_path)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('itemexitspill: requires the Dot proportional renderer')
    PyBoy = _import_pyboy()
    runtime = labels()
    results = [run_page(PyBoy, rom_path, ram_path, page, runtime, png_dir, frames)
               for page in range(1, 5)]
    problems = [problem for result in results for problem in result['problems']]

    reference = results[0]
    for result in results[1:]:
        reference_raster = (tuple(planes for _tile, planes in reference['final_bg']),
                            tuple(planes for _tile, planes in reference['final_window']))
        result_raster = (tuple(planes for _tile, planes in result['final_bg']),
                         tuple(planes for _tile, planes in result['final_window']))
        if result_raster != reference_raster:
            problems.append('page %d settles to a different visible Status raster' %
                            result['page'])

    for result in results:
        uploads = ' '.join('f%d:$%02X->$%02X/%d' %
                           (done[0], start[1], done[1], done[2])
                           for start, done in zip(result['upload_starts'],
                                                  result['uploads']))
        print('itemexitspill: page %d B f%s -> Status f%s, entry f%s; %s; '
              'LCD-off %d, white %d' %
              (result['page'], result['b_at'], result['dispatch'], result['entry'],
               uploads, result['lcd_off'], result['white']))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('itemexitspill: %d problem(s)' % len(problems))
    print('itemexitspill: pages 1-4 remain visible until the owned Status redraw replaces them')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=os.path.join(
        ROOT, 'saves/shiren_en_item_menu.srm'))
    parser.add_argument('--png-dir')
    parser.add_argument('--frames', type=int, default=3500)
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('itemexitspill: missing %s' % path)
    run(args.rom, args.ram, args.png_dir, args.frames)


if __name__ == '__main__':
    main()
