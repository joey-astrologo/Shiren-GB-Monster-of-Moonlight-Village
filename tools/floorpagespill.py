#!/usr/bin/env python3
"""Exercise the standing-item Floor page appended after carried Item pages.

The Wood Arrow SRAM stands on a ground item while carrying four pages of inventory.
Three independent routes page right through selectors 0/5/10/15 to the special selector
$FF, prove that the completed Floor page contains only its header and one ground-item
box, then leave it with B, Right, or Left. Items -> Floor must publish a complete empty
one-row box before its text, while Floor -> page 1 and Floor -> page 4 must publish a
complete empty five-row box before theirs. No route may use the conservative LCD-off
fallback.
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
    300: 'a', 420: 'a', 480: 'a', 2620: 'b',
}
ITEM_SHAPE = (0, 3, 5, 18, 0x02)
EXPECTED_SELECTORS = (0, 5, 10, 15)
EXPECTED_CAPS = (6, 7, 5, 2, 4, 4, 4, 4, 4)


def snapshot(pb):
    return {
        'bg': bytes(pb.memory[0x9800:0x9C00]),
        'shadow': bytes(pb.memory[0xC300:0xC700]),
        'window': bytes(pb.memory[0x9C00:0xA000]),
        'tiles': bytes(pb.memory[0x8800:0x9800]),
        'lcdc': pb.memory[0xFF40],
        'ly': pb.memory[0xFF44],
    }


def white_frame(image):
    return len(set(image.convert('RGB').getdata())) == 1


def runtime_labels():
    font = statusvwf.propvwf.dotfont.load_approved()
    widths = tuple(font.advance_code(code) for code in statusvwf.SLOT_CODES)
    _code, found = gbasm.assemble(statusvwf._source(widths), statusvwf.CODE_AT)
    return found


def visible_row(tilemap, row):
    return tilemap[row * 32:row * 32 + 20]


def title_matches(pb, profile, text):
    """Compare the four-cell ROM-static header by pixels, not allocator membership."""
    want = menuspill.compose(menuspill.encode(text), profile)
    for index, expected in enumerate(want):
        tile = pb.memory[0x9821 + index]
        at = menuspill.tile_data_addr(tile)
        if bytes(pb.memory[at:at + 16]) != bytes(expected):
            return False
    return True


def run(rom_path, ram_path, png_dir=None, frames=3700, leave_button='b',
        trace_render=False, rapid=False, settle_frames=1):
    profile = menuspill.renderer_profile(rom_path)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('floorpagespill: requires the Dot proportional renderer')
    if png_dir:
        os.makedirs(png_dir, exist_ok=True)
    PyBoy = _import_pyboy()
    labels = runtime_labels()
    problems = []

    with tempfile.TemporaryDirectory(prefix='floorpagespill-') as tmp:
        run_rom = os.path.join(tmp, 'floorpage_%s.gb' % leave_button)
        shutil.copyfile(rom_path, run_rom)
        shutil.copyfile(ram_path, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        scheduled = dict(BOOT)
        item_open = [False]
        page_completes = []
        right_presses = []
        floor_at = [None]
        floor_state = [None]
        floor_title_ok = [None]
        return_title_ok = [None]
        floor_exit_at = [None]
        return_completes = []
        floor_entry_blank_commits = []
        floor_blank_commits = []
        b_at = [None]
        status_dispatches = []
        status_entries = []
        uploads = []
        upload_starts = []
        fallbacks = []
        regional_fallbacks = []
        regional_blanks = []
        regional_rows = []
        samples = []
        render_trace = []

        def trace_row(source, limit=32):
            values = []
            for address in range(source, source + limit):
                value = pb.memory[address]
                values.append(value)
                if value == 0xFF:
                    break
            return tuple(values)

        def dispatch(_ctx=None):
            screen = pb.register_file.A
            if screen == 0 and not item_open[0] and b_at[0] is None:
                scheduled[frame[0] + 80] = 'a'
                item_open[0] = True
            if screen == 0 and b_at[0] is not None:
                status_dispatches.append(frame[0])

        def item_row(_ctx=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if trace_render and item_open[0]:
                source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
                render_trace.append((frame[0], 'row', shape, pb.register_file.D,
                                     pb.memory[0xC6AC], pb.memory[0xC1B3],
                                     pb.memory[0xC1B5], pb.memory[0xC1B6],
                                     source, trace_row(source)))
            if shape != ITEM_SHAPE or pb.register_file.D != 4:
                return
            selector = pb.memory[0xC6AC]
            if selector not in EXPECTED_SELECTORS:
                return
            if floor_at[0] is not None:
                if not return_completes:
                    return_completes.append((frame[0], selector))
                return
            if page_completes and page_completes[-1][1] == selector:
                return
            page_completes.append((frame[0], selector))
            if not rapid or len(page_completes) == 1:
                at = frame[0] + 90
                scheduled[at] = 'right'
                right_presses.append(at)

        def redraw_return(_ctx=None):
            if not rapid or not item_open[0]:
                return
            selector = pb.memory[0xC6AC]
            if selector == 0xFF and pb.memory[0xC1B7] == 1:
                if floor_at[0] is None:
                    floor_at[0] = frame[0]
                    floor_state[0] = snapshot(pb)
                    floor_title_ok[0] = title_matches(pb, profile, 'Floor')
                    at = frame[0] + settle_frames
                    scheduled[at] = leave_button
                return
            if floor_at[0] is not None:
                if leave_button in ('left', 'right'):
                    return_title_ok[0] = title_matches(pb, profile, 'Items')
                return
            if (page_completes and
                    len(right_presses) < len(page_completes)):
                at = frame[0] + settle_frames
                scheduled[at] = 'right'
                right_presses.append(at)

        def status_entry(_ctx=None):
            if b_at[0] is None:
                return
            status_entries.append({
                'frame': frame[0],
                'stack': tuple(pb.memory[0xC534 + i] for i in range(3)),
                'screen': pb.memory[0xC6A3],
                'count': pb.memory[0xC6AA],
                'selector': pb.memory[0xC6AC],
                'latch': pb.memory[0xC1B7],
                'lcdc': pb.memory[0xFF40],
                'scroll': (pb.memory[0xFF42], pb.memory[0xFF43]),
                'window': (pb.memory[0xFF4A], pb.memory[0xFF4B]),
            })

        def upload_start(_ctx=None):
            if b_at[0] is not None:
                upload_starts.append((frame[0], pb.memory[0xFF44],
                                      pb.memory[statusvwf.S_CAP]))

        def upload_done(_ctx=None):
            if b_at[0] is not None:
                uploads.append((frame[0], pb.memory[0xFF44],
                                pb.memory[statusvwf.S_CAP]))

        def fallback(_ctx=None):
            if b_at[0] is not None:
                fallbacks.append(frame[0])

        def regional_fallback(_ctx=None):
            if right_presses:
                regional_fallbacks.append(frame[0])

        def regional_blank_done(_ctx=None):
            if floor_at[0] is None and pb.memory[0xC6AC] == 0xFF:
                floor_entry_blank_commits.append((frame[0], snapshot(pb)))
            if floor_exit_at[0] is not None and leave_button in ('left', 'right'):
                floor_blank_commits.append((frame[0], pb.memory[0xC6AC],
                                            pb.memory[0xC1B7], snapshot(pb)))

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(4, 0x4856, redraw_return, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], item_row, None)
        pb.hook_register(statusvwf.FAR_BANK, labels['statusentry'], status_entry, None)
        pb.hook_register(statusvwf.FAR_BANK, labels['uploadcopy'], upload_start, None)
        pb.hook_register(statusvwf.FAR_BANK, labels['uploadlivedone'], upload_done, None)
        pb.hook_register(statusvwf.FAR_BANK, labels['statusready'], fallback, None)
        _region_code, region_labels = gbasm.assemble(
            menuvwf.ITEM_REGION_SRC, menuvwf.ITEM_REGION_AT)
        _phase_code, phase_labels = gbasm.assemble(
            menuvwf.ITEM_SHAPE_PHASE_SRC, menuvwf.ITEM_SHAPE_PHASE_AT)
        _return_code, return_labels = gbasm.assemble(
            menuvwf.ITEM_RETURN_SRC, menuvwf.ITEM_RETURN_AT)
        pb.hook_register(menuvwf.ITEM_REGION_BANK, region_labels['ircheck'],
                         lambda _ctx=None: regional_rows.append(
                             (frame[0], pb.register_file.D, pb.register_file.B,
                              pb.memory[0xC6AC], pb.memory[0xC69C],
                              pb.memory[0xC69D])), None)
        pb.hook_register(menuvwf.ITEM_REGION_BANK, region_labels['irfaillcd'],
                         regional_fallback, None)
        pb.hook_register(menuvwf.ITEM_REGION_BANK, region_labels['irdisable'],
                         lambda _ctx=None: regional_blanks.append(frame[0]), None)
        pb.hook_register(menuvwf.ITEM_REGION_BANK, region_labels['irarmed'],
                         regional_blank_done, None)
        if trace_render:
            def trace_hook(label):
                return lambda _ctx=None: render_trace.append(
                    (frame[0], label, pb.register_file.D, pb.memory[0xC6AC],
                     pb.memory[0xC1B3], pb.memory[0xC1B5], pb.memory[0xC1B6]))
            pb.hook_register(menuvwf.ITEM_RETURN_BANK,
                             phase_labels['itemshapephase'],
                             trace_hook('phase-entry'), None)
            pb.hook_register(menuvwf.ITEM_RETURN_BANK, phase_labels['ispshape'],
                             trace_hook('phase-shape'), None)
            pb.hook_register(menuvwf.ITEM_RETURN_BANK, return_labels['irtshape'],
                             trace_hook('tail-shape'), None)

        for frame[0] in range(frames):
            if (not rapid and floor_at[0] is None and pb.memory[0xC6A3] == 1 and
                    pb.memory[0xC6AC] == 0xFF and pb.memory[0xC1B7] == 1):
                floor_at[0] = frame[0]
                scheduled[frame[0] + 90] = leave_button
            if (not rapid and floor_at[0] is not None and floor_state[0] is None and
                    frame[0] == floor_at[0] + 60):
                floor_state[0] = snapshot(pb)
                floor_title_ok[0] = title_matches(pb, profile, 'Floor')
                if png_dir:
                    pb.screen.image.save(os.path.join(
                        png_dir, 'standing_floor_%s_settled_f%04d.png' %
                        (leave_button, frame[0])))
            action = scheduled.get(frame[0])
            if (action == leave_button and floor_at[0] is not None and
                    floor_exit_at[0] is None):
                floor_exit_at[0] = frame[0]
            if action == 'b' and floor_at[0] is not None and b_at[0] is None:
                b_at[0] = frame[0]
            if action:
                pb.button(action, PRESS_FRAMES)
            pb.tick()
            if (png_dir and leave_button in ('left', 'right') and
                    floor_exit_at[0] is not None and
                    floor_exit_at[0] <= frame[0] <= floor_exit_at[0] + 35):
                pb.screen.image.save(os.path.join(
                    png_dir, 'floor_%s_transition_f%04d.png' %
                    (leave_button, frame[0])))
            if (png_dir and len(right_presses) == 4 and
                    right_presses[-1] <= frame[0] <= right_presses[-1] + 35):
                pb.screen.image.save(os.path.join(
                    png_dir, 'items_to_floor_%s_f%04d.png' %
                    (leave_button, frame[0])))
            if right_presses and frame[0] >= right_presses[0] - 2:
                samples.append((frame[0], snapshot(pb), pb.screen.image.copy()))

        final = snapshot(pb)

        if tuple(selector for _at, selector in page_completes) != EXPECTED_SELECTORS:
            problems.append('completed carried selectors %s, expected %s' %
                            (tuple(selector for _at, selector in page_completes),
                             EXPECTED_SELECTORS))
        if len(right_presses) != 4:
            problems.append('scheduled %d right presses, expected four' %
                            len(right_presses))
        if floor_at[0] is None or floor_state[0] is None:
            problems.append('standing-item Floor page never reached its settled latch')
        else:
            if not floor_title_ok[0]:
                problems.append('settled standing-item page header is not exact `Floor`')
            state = floor_state[0]
            floor_cursor = (state['shadow'][0x82], state['bg'][0x82])
            if floor_cursor != (0x81, 0x81):
                problems.append('settled Floor cursor shadow/BG is $%02X/$%02X, '
                                'expected $81/$81' % floor_cursor)
            top = bytes((0xB8,)) + bytes((0xBC,)) * 18 + bytes((0xB9,))
            bottom = bytes((0xBA,)) + bytes((0xBD,)) * 18 + bytes((0xBB,))
            for layer in ('bg', 'shadow'):
                tilemap = state[layer]
                if visible_row(tilemap, 3) != top:
                    problems.append('Floor %s ground-item top border is %s' %
                                    (layer, visible_row(tilemap, 3).hex(' ')))
                middle = visible_row(tilemap, 4)
                if middle[0] != 0xBE or middle[19] != 0xBF:
                    problems.append('Floor %s ground-item middle borders are $%02X/$%02X'
                                    % (layer, middle[0], middle[19]))
                if visible_row(tilemap, 5) != bottom:
                    problems.append('Floor %s ground-item bottom border is %s' %
                                    (layer, visible_row(tilemap, 5).hex(' ')))
                bad = next(((row, visible_row(tilemap, row)) for row in range(6, 16)
                            if visible_row(tilemap, row) != bytes(20)), None)
                if bad is not None:
                    row, data = bad
                    problems.append('Floor %s row %d retained cells %s, expected zero' %
                                    (layer, row, data.hex(' ')))

        top = bytes((0xB8,)) + bytes((0xBC,)) * 18 + bytes((0xB9,))
        side = bytes((0xBE,)) + bytes(18) + bytes((0xBF,))
        bottom = bytes((0xBA,)) + bytes((0xBD,)) * 18 + bytes((0xBB,))
        if len(floor_entry_blank_commits) != 1:
            problems.append('observed %d Items-to-Floor blank commits, expected 1' %
                            len(floor_entry_blank_commits))
        else:
            at, state = floor_entry_blank_commits[0]
            if not 0x90 <= state['ly'] <= 0x99:
                problems.append('Items-to-Floor chrome ended outside VBlank at f%d '
                                '(LY=$%02X)' % (at, state['ly']))
            expected_rows = {3: top, 4: side, 5: bottom}
            expected_rows.update((row, bytes(20)) for row in range(6, 14))
            for layer in ('bg', 'shadow'):
                bad = next(((row, visible_row(state[layer], row), want)
                            for row, want in sorted(expected_rows.items())
                            if visible_row(state[layer], row) != want), None)
                if bad is not None:
                    row, data, want = bad
                    problems.append('Items-to-Floor blank %s row %d is %s, '
                                    'expected %s' %
                                    (layer, row, data.hex(' '), want.hex(' ')))

        if floor_exit_at[0] is None:
            problems.append('never scheduled %s from the settled standing-item Floor page'
                            % leave_button)
        if leave_button == 'b':
            if b_at[0] is None:
                problems.append('never scheduled B from the settled standing-item Floor page')
            if not status_dispatches:
                problems.append('standing-item Floor B never dispatched Status')
            if len(status_entries) != 1:
                problems.append('standing-item Floor reached Status entry %d times, '
                                'expected 1' % len(status_entries))
            else:
                entry = status_entries[0]
                expected = {
                    'stack': (0, 0, 1), 'screen': 0, 'count': 18,
                    'selector': 0xFF, 'latch': 1,
                    'scroll': (0, 0), 'window': (0x80, 0x07),
                }
                for key, want in expected.items():
                    if entry[key] != want:
                        problems.append('Status-entry %s is %r, expected %r' %
                                        (key, entry[key], want))
                if entry['lcdc'] & 0xF8 != 0xE0:
                    problems.append('Status-entry LCDC is $%02X, expected $E0-$E7' %
                                    entry['lcdc'])
            if fallbacks:
                problems.append('Floor-to-Status used LCD-off fallback at %s' %
                                ' '.join('f%d' % at for at in fallbacks))
        else:
            expected_selector = 0 if leave_button == 'right' else 15
            if return_title_ok[0] is None:
                return_title_ok[0] = title_matches(pb, profile, 'Items')
            if tuple(selector for _at, selector in return_completes) != \
                    (expected_selector,):
                problems.append('Floor %s completed selectors %s, expected ($%02X,)' %
                                (leave_button,
                                 tuple(selector for _at, selector in return_completes),
                                 expected_selector))
            if len(floor_blank_commits) != 1:
                problems.append('Floor %s observed %d regional blank commits, expected 1'
                                % (leave_button, len(floor_blank_commits)))
            else:
                at, selector, latch, state = floor_blank_commits[0]
                if (selector, latch) != (expected_selector, 1):
                    problems.append('Floor %s blank f%d selector/latch is $%02X/%d, '
                                    'expected $%02X/1' %
                                    (leave_button, at, selector, latch,
                                     expected_selector))
                if not 0x90 <= state['ly'] <= 0x99:
                    problems.append('Floor %s chrome ended outside VBlank at f%d '
                                    '(LY=$%02X)' %
                                    (leave_button, at, state['ly']))
                expected_rows = {3: top, 13: bottom}
                expected_rows.update((row, side) for row in range(4, 13))
                for layer in ('bg', 'shadow'):
                    bad = next(((row, visible_row(state[layer], row), want)
                                for row, want in sorted(expected_rows.items())
                                if visible_row(state[layer], row) != want), None)
                    if bad is not None:
                        row, data, want = bad
                        problems.append('Floor %s blank %s row %d is %s, expected %s' %
                                        (leave_button, layer, row, data.hex(' '),
                                         want.hex(' ')))
            if pb.memory[0xC6A3] != 1:
                problems.append('Floor %s ended on screen %d, expected Items screen 1' %
                                (leave_button, pb.memory[0xC6A3]))
            if pb.memory[0xC6AC] != expected_selector:
                problems.append('Floor %s ended on selector $%02X, expected $%02X' %
                                (leave_button, pb.memory[0xC6AC], expected_selector))
            if return_title_ok[0] is not True:
                problems.append('Floor %s return header is not exact `Items`' %
                                leave_button)
            cursor = (pb.memory[0xC382], pb.memory[0x9882])
            if cursor != (0x81, 0x81):
                problems.append('Floor %s return cursor shadow/BG is $%02X/$%02X, '
                                'expected $81/$81' %
                                (leave_button, cursor[0], cursor[1]))
        if regional_fallbacks:
            problems.append('Items-to-Floor used regional LCD-off fallback at %s' %
                            ' '.join('f%d' % at for at in regional_fallbacks))
        if regional_blanks:
            problems.append('Items-to-Floor executed regional LCD-off write at %s' %
                            ' '.join('f%d' % at for at in regional_blanks))
        expected_caps = EXPECTED_CAPS if leave_button == 'b' else ()
        if tuple(cap for _at, _ly, cap in uploads) != expected_caps:
            problems.append('live Status upload caps are %s, expected %s' %
                            (tuple(cap for _at, _ly, cap in uploads), expected_caps))
        if len(upload_starts) != len(uploads):
            problems.append('observed %d Status upload starts and %d completions' %
                            (len(upload_starts), len(uploads)))
        for at, ly, cap in uploads:
            if not 0x90 <= ly <= 0x99:
                problems.append('cap-%d upload ended outside VBlank at f%d (LY=$%02X)' %
                                (cap, at, ly))
        lcd_off = [at for at, state, _image in samples
                   if not state['lcdc'] & 0x80]
        whites = [at for at, _state, image in samples if white_frame(image)]
        if lcd_off:
            problems.append('route rendered with LCD off at %s' %
                            ' '.join('f%d' % at for at in lcd_off))
        if whites:
            problems.append('route produced an all-white frame at %s' %
                            ' '.join('f%d' % at for at in whites))
        if leave_button == 'b' and pb.memory[0xC6A3] != 0:
            problems.append('route ended on screen %d, expected Status screen 0' %
                            pb.memory[0xC6A3])
        if pb.memory[0xC1B7] != 0:
            problems.append('settled-Floor latch remained %d after %s exit' %
                            (pb.memory[0xC1B7], leave_button))
        if leave_button == 'b':
            problems.extend(menuspill.status_fragment_problems(pb))
        pb.stop(save=False)

    destination = ('Status f%d' % status_dispatches[0] if status_dispatches else
                   '$%02X f%d' % return_completes[0][::-1]
                   if return_completes else 'missing')
    print('floorpagespill: %-5s pages %s; Floor settled f%s; leave f%s -> %s' %
          (leave_button, ' '.join('f%d:$%02X' % event for event in page_completes),
           floor_at[0], floor_exit_at[0], destination))
    print('floorpagespill: %d live Status uploads; LCD-off %d, white %d; '
          'regional branch/write, status fallback %d/%d/%d' %
          (len(uploads), len(lcd_off), len(whites), len(regional_fallbacks),
           len(regional_blanks), len(fallbacks)))
    if trace_render:
        for event in render_trace:
            print('floorpagespill: trace %r' % (event,))
    for problem in problems:
        print('  ' + problem)
        if problems:
            print('  regional rows: %s' %
              ' '.join('f%d:d%d/b%d/s$%02X/%d,%d' % event
                       for event in regional_rows))
    if problems:
        raise SystemExit('floorpagespill: %d problem(s)' % len(problems))
    print('floorpagespill: standing-item Floor %s route is chrome-exact and stays live' %
          leave_button)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=os.path.join(
        ROOT, 'saves/shiren_en_item_menu_wood_arrow.srm'))
    parser.add_argument('--png-dir')
    parser.add_argument('--frames', type=int, default=3700)
    parser.add_argument('--trace-render', action='store_true')
    parser.add_argument('--rapid', action='store_true',
                        help='schedule each page input from the native redraw return')
    parser.add_argument('--settle-frames', type=int, default=1,
                        help='with --rapid, frames from redraw return to next input')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('floorpagespill: missing %s' % path)
    for leave_button in ('b', 'right', 'left'):
        run(args.rom, args.ram, args.png_dir, args.frames, leave_button,
            args.trace_render, args.rapid, args.settle_frames)


if __name__ == '__main__':
    main()
