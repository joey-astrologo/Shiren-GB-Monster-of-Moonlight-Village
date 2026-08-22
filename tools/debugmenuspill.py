#!/usr/bin/env python3
"""Exercise the GameShark-only item debug picker through its real lifetime.

The hidden picker is not safely reproducible by forcing dispatcher screen 27 from a
fresh dungeon state.  Its historical corruption appears only after the ordinary status
and Items screens have borrowed low fixed-font tile planes.  This fixture therefore
boots Joey's populated item-menu SRAM, visits Menu -> Items first, applies the three
documented GameShark writes, backs into the hidden category picker, pages through both
category tables, and selects every category on both pages.

Acceptance is deliberately renderer-level rather than screenshot-only:

* both category pages must resolve to exact proportional glyph planes;
* paging wide -> narrow -> wide must retain one right border at column 7;
* every nonempty screen-28 row must create one live dynamic VWF record with exact
  glyph planes, while trailing empty rows stay blank; and
* the screen-29 weapon enhancement editor must render every reachable value 0..99
  through the real Up control without growing beyond one reusable VWF record; and
* every visible dynamic tile must retain a valid live owner throughout the result.
"""
import argparse
import os
import shutil
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

from gbrun import _import_pyboy, PRESS_FRAMES                    # noqa: E402
import menuspill                                                  # noqa: E402
import menuvwf                                                    # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_item_menu.srm')
BOOT = {
    60: ('start', PRESS_FRAMES),
    120: ('start', PRESS_FRAMES),
    180: ('start', PRESS_FRAMES),
    240: ('start', PRESS_FRAMES),
    300: ('a', PRESS_FRAMES),
    420: ('a', PRESS_FRAMES),
    480: ('a', PRESS_FRAMES),
    2620: ('b', PRESS_FRAMES),
}
CHEATS = ('011B35C5', '0104A4C6', '01FFADC6')
CATEGORY_SHAPE = (0, 0, 5, 6, 0x50)
PICKER_SHAPE = menuvwf.DEBUG_MENU_SHAPE
VALUE_SHAPE = menuvwf.DEBUG_VALUE_SHAPE
CATEGORY_BASES = (0xCB, 0xCF, 0xD3, 0xD7, 0xDB)
CATEGORY_CAPS = (4, 4, 4, 4, 3)
ROW_ENTRY = (menuvwf.FAR_BANK, None)
ROW_EPILOG = (31, 0x411F)
SHADOW = 0xC300
BGMAP = 0x9800


def _read_row(pb, rom, source, limit=18):
    out = []
    for offset in range(limit + 1):
        address = source + offset
        if 0x4000 <= address < 0x8000:
            value = rom[31 * 0x4000 + address - 0x4000]
        else:
            value = pb.memory[address]
        if value == 0xFF:
            return tuple(out)
        out.append(value)
    raise AssertionError('row at $%04X has no terminator within %d cells' %
                         (source, limit))


def _plane_matches(pb, base, pixels):
    for index, want in enumerate(pixels):
        at = menuspill.tile_data_addr(base + index)
        if bytes(pb.memory[at:at + 16]) != bytes(want):
            return False
    return True


def run(rom_path, ram_path, page, selected_row, *, audit_pages=False,
        audit_values=False,
        png=None, frames=3400):
    profile = menuspill.renderer_profile(rom_path)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('debugmenuspill: requires the Dot proportional renderer')
    rom = open(rom_path, 'rb').read()
    problems = []

    with tempfile.TemporaryDirectory(prefix='debugmenuspill-') as tmp:
        run_rom = os.path.join(tmp, 'debugmenu.gb')
        shutil.copyfile(rom_path, run_rom)
        shutil.copyfile(ram_path, run_rom + '.ram')
        PyBoy = _import_pyboy()
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        scheduled = dict(BOOT)
        dispatches = []
        debug_dispatches = []
        category_rows = []
        picker_rows = []
        value_rows = []
        value_checks = []
        pending = [None]
        category_checks = []
        cheats_on = [False]
        picker_at = [None]
        value_at = [None]
        invariant_problems = []
        lcd_off = []

        def schedule_selection(at):
            for index in range(selected_row):
                scheduled[at + index * 12] = ('down', PRESS_FRAMES)
            scheduled[at + selected_row * 12] = ('a', 1)

        def dispatch(_ctx=None):
            screen = pb.register_file.A
            dispatches.append((frame[0], screen))
            if screen == 0 and not any(
                    button == 'a' for at, (button, _duration) in scheduled.items()
                    if at > frame[0]):
                scheduled[frame[0] + 80] = ('a', PRESS_FRAMES)
            elif screen == 1 and not cheats_on[0]:
                # The corruption requires the ordinary status/Items lifetime first.
                at = frame[0] + 80
                scheduled[at] = ('__cheat_b', PRESS_FRAMES)
            elif screen == 27:
                current_page = pb.memory[0xC6E3]
                debug_dispatches.append((frame[0], current_page))
                ordinal = len(debug_dispatches)
                category_checks.append((frame[0] + 50, ordinal, current_page))
                if audit_pages and ordinal <= 3:
                    scheduled[frame[0] + 80] = ('right', PRESS_FRAMES)
                elif audit_pages and ordinal == 4:
                    schedule_selection(frame[0] + 80)
                elif not audit_pages and current_page != page:
                    scheduled[frame[0] + 80] = ('right', PRESS_FRAMES)
                elif not audit_pages:
                    schedule_selection(frame[0] + 80)
            elif screen == 28 and picker_at[0] is None:
                picker_at[0] = frame[0]
                if audit_values:
                    scheduled[frame[0] + 80] = ('a', 1)
            elif screen == 29 and audit_values and value_at[0] is None:
                value_at[0] = frame[0]
                # Initial zero plus one hundred single-step increments covers every
                # value and proves the native 99 -> 0 wrap.  Keep presses eight frames
                # apart so each VBlank upload is observed before the next redraw.
                for index in range(100):
                    scheduled[frame[0] + 80 + index * 8] = ('up', 1)

        def row_entry(_ctx=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if shape not in (CATEGORY_SHAPE, PICKER_SHAPE, VALUE_SHAPE):
                return
            row = pb.register_file.D
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            data = _read_row(pb, rom, source)
            raw = 1
            codes = data[raw:]
            pending[0] = {
                'frame': frame[0], 'shape': shape, 'row': row,
                'key': pb.register_file.HL, 'source': source,
                'data': data, 'codes': codes, 'pixels': menuspill.compose(codes, profile),
            }

        def row_epilog(_ctx=None):
            expected = pending[0]
            if expected is None:
                return
            pending[0] = None
            row = expected['row']
            if expected['shape'] == CATEGORY_SHAPE:
                if not 0 <= row < 5:
                    problems.append('f%d: category row index %d is invalid' %
                                    (frame[0], row))
                    return
                base = CATEGORY_BASES[row]
                cap = CATEGORY_CAPS[row]
                pixels = expected['pixels']
                if len(pixels) > cap:
                    problems.append('f%d: category row %d paints %d tiles into cap %d' %
                                    (frame[0], row, len(pixels), cap))
                first = expected['key'] + 2
                got = bytes(pb.memory[first:first + len(pixels)])
                want = bytes(range(base, base + len(pixels)))
                if got != want:
                    problems.append('f%d: category row %d shadow IDs %s, expected %s' %
                                    (frame[0], row, got.hex(' '), want.hex(' ')))
                if not _plane_matches(pb, base, pixels):
                    problems.append('f%d: category row %d proportional planes differ' %
                                    (frame[0], row))
                expected['base'] = base
                category_rows.append(expected)
            elif expected['shape'] == PICKER_SHAPE:
                picker_rows.append(expected)
            else:
                value_rows.append(expected)
                value_checks.append((frame[0] + 5, expected))

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(ROW_ENTRY[0], profile['entry'], row_entry, None)
        pb.hook_register(ROW_EPILOG[0], ROW_EPILOG[1], row_epilog, None)

        for current_frame in range(frames):
            frame[0] = current_frame
            action = scheduled.get(current_frame)
            if action:
                button, duration = action
                if button == '__cheat_b':
                    for code in CHEATS:
                        pb.gameshark.add(code)
                    cheats_on[0] = True
                    pb.button('b', duration)
                else:
                    pb.button(button, duration)
            pb.tick()

            for check_at, ordinal, check_page in category_checks:
                if current_frame != check_at:
                    continue
                # Both page descriptors are six cells wide: x0 border, x1..6
                # interior, x7 border.  The historical page-1 -> page-0 shrink left
                # a second BF edge at x6.
                if pb.memory[BGMAP + 7] != 0xB9:
                    problems.append('category page %d top-right border is $%02X, '
                                    'expected $B9' % (ordinal, pb.memory[BGMAP + 7]))
                if pb.memory[BGMAP + 10 * 32 + 7] != 0xBB:
                    problems.append('category page %d bottom-right border is $%02X, '
                                    'expected $BB' %
                                    (ordinal, pb.memory[BGMAP + 10 * 32 + 7]))
                for y in (1, 3, 5, 7, 9):
                    edge = pb.memory[BGMAP + y * 32 + 7]
                    stale = pb.memory[BGMAP + y * 32 + 6]
                    if edge != 0xBF:
                        problems.append('category page %d row %d right edge is $%02X' %
                                        (ordinal, y, edge))
                    if stale == 0xBF:
                        problems.append('category page %d row %d retains a second '
                                        'right edge at column 6' % (ordinal, y))

                # Require the five most recently drawn rows to remain visibly tied to
                # their static proportional planes after native map publication.
                rows = category_rows[-5:]
                if len(rows) != 5 or {row['row'] for row in rows} != set(range(5)):
                    problems.append('category page %d captured rows %s, expected 0-4' %
                                    (ordinal, sorted(row['row'] for row in rows)))
                for row in rows:
                    first = row['key'] + 2 - SHADOW
                    visible = bytes(pb.memory[BGMAP + first:
                                              BGMAP + first + len(row['pixels'])])
                    want_ids = bytes(range(row['base'],
                                           row['base'] + len(row['pixels'])))
                    if visible != want_ids or not _plane_matches(
                            pb, row['base'], row['pixels']):
                        problems.append('category page %d row %d is not visibly '
                                        'plane-exact VWF' % (ordinal, row['row']))

            if picker_at[0] is not None and current_frame >= picker_at[0]:
                if not (pb.memory[0xFF40] & 0x80):
                    lcd_off.append(current_frame)
                bad = menuspill.frame_invariant(pb, profile)
                if bad and len(invariant_problems) < 12:
                    invariant_problems.append((current_frame, bad[:4]))

            for check_at, expected in value_checks:
                if current_frame != check_at:
                    continue
                data = expected['data']
                if (len(data) != 4 or data[0] != 0 or data[1] != 0x7C or
                        not 0 <= data[2] <= 10 or not 1 <= data[3] <= 10):
                    problems.append('f%d: malformed enhancement payload %s' %
                                    (current_frame, data))
                    continue
                records = menuspill.records(pb, profile)
                matches = [record for record in records
                           if record[0] == expected['key'] and record[3] == 1]
                if len(matches) != 1:
                    problems.append('f%d: enhancement key $%04X has records %s' %
                                    (current_frame, expected['key'], matches))
                if len(records) != 5:
                    problems.append('f%d: enhancement redraw has %d records, expected '
                                    'four weapon rows plus one reusable value row' %
                                    (current_frame, len(records)))
                if not menuspill.visible_row_matches(
                        pb, profile, expected['key'], expected['codes'], raw=1):
                    problems.append('f%d: enhancement value %s is not visibly '
                                    'plane-exact VWF' % (current_frame, data))

        if not cheats_on[0]:
            problems.append('GameShark codes were never enabled after the Items screen')
        pages = [page for _at, page in debug_dispatches]
        expected_pages = [0, 1, 0, 1] if audit_pages else ([0, 1] if page else [0])
        if pages[:len(expected_pages)] != expected_pages:
            problems.append('debug category pages were %s, expected %s' %
                            (pages, ' '.join(map(str, expected_pages))))
        if picker_at[0] is None:
            problems.append('real route never dispatched selected-category screen 28')
        if audit_values and value_at[0] is None:
            problems.append('real route never dispatched weapon enhancement screen 29')

        rows = picker_rows[-4:]
        if len(rows) != 4 or {row['row'] for row in rows} != set(range(4)):
            problems.append('selected category captured rows %s, expected 0-3' %
                            sorted(row['row'] for row in rows))
        recs = menuspill.records(pb, profile)
        painted = [row for row in rows if row['codes']]
        expected_records = len(painted) + (1 if audit_values and value_rows else 0)
        if len(recs) != expected_records:
            problems.append('selected category has %d live VWF records, expected %d' %
                            (len(recs), expected_records))
        for row in rows:
            matches = [record for record in recs
                       if record[0] == row['key'] and record[3] == 1]
            if not row['codes']:
                if matches:
                    problems.append('empty selected row %d unexpectedly has VWF '
                                    'records %s' % (row['row'], matches))
                first = row['key'] + 2 - SHADOW
                interior = bytes(pb.memory[BGMAP + first:BGMAP + first + 13])
                if any(interior):
                    problems.append('empty selected row %d exposes nonblank cells %s' %
                                    (row['row'], interior.hex(' ')))
                continue
            if len(matches) != 1:
                problems.append('selected row %d key $%04X has VWF records %s, '
                                'expected exactly one raw-prefix record' %
                                (row['row'], row['key'], matches))
                continue
            _key, base, cap, _raw = matches[0]
            if len(row['pixels']) > cap:
                problems.append('selected row %d paints %d tiles into cap %d' %
                                (row['row'], len(row['pixels']), cap))
            if not menuspill.visible_row_matches(
                    pb, profile, row['key'], row['codes'], raw=1):
                problems.append('selected row %d is not visibly plane-exact VWF' %
                                row['row'])
        if invariant_problems:
            problems.append('selected-category lifetime has unowned/corrupt dynamic '
                            'tiles: %s' % invariant_problems)
        final_bad = menuspill.frame_invariant(pb, profile)
        if final_bad:
            problems.append('settled selected-category invariant: %s' % final_bad[:8])
        if lcd_off:
            problems.append('selected category disabled LCD on frames %s' % lcd_off[:20])
        if pb.memory[0xC11A] != 0:
            problems.append('selected category left VBlank queue mode $%02X active' %
                            pb.memory[0xC11A])

        if audit_values:
            values = []
            for expected in value_rows:
                data = expected['data']
                if (len(data) == 4 and 0 <= data[2] <= 10 and
                        1 <= data[3] <= 10):
                    values.append((0 if data[2] == 0 else data[2] - 1) * 10 +
                                  data[3] - 1)
            if len(value_rows) != 101:
                problems.append('enhancement editor drew %d values, expected initial '
                                'zero plus 100 increments' % len(value_rows))
            missing = sorted(set(range(100)) - set(values))
            if missing:
                problems.append('enhancement VWF sweep missed values %s' % missing)
            if not values or values[0] != 0 or values[-1] != 0 or 99 not in values:
                problems.append('enhancement endpoints/wrap are %s, expected '
                                '0 -> ... -> 99 -> 0' %
                                (values[:1] + values[-2:]))

        if png and picker_at[0] is not None:
            pb.screen.image.save(png)
        pb.stop(save=False)

    ordinary_dispatches = [event for event in dispatches if event[1] != 29]
    value_dispatches = len(dispatches) - len(ordinary_dispatches)
    dispatch_summary = ' '.join('f%d:%d' % event for event in ordinary_dispatches)
    if value_dispatches:
        dispatch_summary += ' screen29x%d' % value_dispatches
    print('debugmenuspill: dispatches %s' % dispatch_summary)
    print('debugmenuspill: target page %d row %d; category pages %s; '
          '%d proportional category row calls' %
          (page, selected_row, ' '.join(map(str, pages)), len(category_rows)))
    print('debugmenuspill: selected screen has %d row calls, %d painted rows, and '
          '%d live VWF records' % (len(picker_rows), len(painted), len(recs)))
    if audit_values:
        print('debugmenuspill: enhancement editor covered %d redraws / %d distinct '
              'values (0..99)' % (len(value_rows), len(set(values))))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('debugmenuspill: %d problem(s)' % len(problems))
    print('debugmenuspill: selected category is LCD-on and plane-exact VWF')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--frames', type=int, default=3400)
    parser.add_argument('--png')
    parser.add_argument('--page', type=int, choices=(0, 1))
    parser.add_argument('--row', type=int, choices=range(5))
    args = parser.parse_args()
    if not os.path.exists(args.ram):
        raise SystemExit('missing RAM fixture: %s' % args.ram)
    if (args.page is None) != (args.row is None):
        raise SystemExit('--page and --row must be supplied together')
    targets = ([(args.page, args.row)] if args.page is not None else
               [(page, row) for page in range(2) for row in range(5)])
    for page, row in targets:
        audit_values = page == 1 and row == 0
        run(args.rom, args.ram, page, row,
            audit_pages=(args.page is None and page == 1 and row == 0),
            audit_values=audit_values,
            png=args.png if len(targets) == 1 else None,
            frames=max(args.frames, 4100 if audit_values else args.frames))
    print('debugmenuspill: all %d selected categories passed' % len(targets))


if __name__ == '__main__':
    main()
