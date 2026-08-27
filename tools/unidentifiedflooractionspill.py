#!/usr/bin/env python3
"""Guard Items -> appended Floor -> seven-row unidentified-Pot Action children.

The Log-3 SRAM can reach the same ground Pot through two different native parents.
Direct Status -> Floor uses screen 7, while Status -> Items -> Right to Floor retains
screen 1 and pushes screen 2 for the Action picker.  The latter is the only admitted
screen-2 picker with seven verbs: Take/See/Push/Toss/Swap/Name/Info.

Six protected four-tile slices at $C7-$DE cover its first six rows.  The final Info row
must use the ordinary collision-safe base run; extending the protected pool would collide
with the difficulty renderer at $E0.  This fixture proves the exact no-Lua history, all
seven plane-exact proportional rows, the mixed private/ordinary allocation, retained
Floor title/item pixels, exact See/Info -> Floor returns, and an enabled LCD throughout.
The Info case additionally requires both visible rows below its box to be blank before
the description reuses the final Action row's ordinary tile allocation.
"""
import argparse
import os
import shutil
import sys
import tempfile


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gbrun import PRESS_FRAMES, _import_pyboy                    # noqa: E402
import actionmenuspill                                             # noqa: E402
import gbasm                                                       # noqa: E402
import menuspill                                                   # noqa: E402
import menuvwf                                                     # noqa: E402
import potreturnspill                                              # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log3_unidentified_pot_crash.srm')
SCRIPT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 380: 'down', 460: 'down', 540: 'a', 700: 'a',
    2600: 'b', 2700: 'a',       # Status -> Items
    3000: 'right',              # one carried page -> appended Floor page
    3400: 'a',                  # ground item -> screen-2 Action
    3700: 'down', 3900: 'a',    # -> See -> screen 12
    4300: 'b',                  # See -> exact screen-1 Floor parent
}
INFO_SCRIPT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 380: 'down', 460: 'down', 540: 'a', 700: 'a',
    2600: 'b', 2700: 'a',
    3000: 'right',
    3400: 'a',
    3700: 'down', 3760: 'down', 3820: 'down',
    3880: 'down', 3940: 'down', 4000: 'down',
    4120: 'a',                  # final Action row -> Info screen 4
    4500: 'b',                  # Info -> exact screen-1 Floor parent
}
ACTION_SHAPE = (13, 1, 7, 5, 0x02)
WORDS = ('Take', 'See', 'Push', 'Toss', 'Swap', 'Name', 'Info')
FRAMES = 4700
INFO_FRAMES = 4900


def stack(pb):
    depth = pb.memory[0xC534]
    return tuple(pb.memory[0xC535 + index] for index in range(depth + 1))


def run(rom, ram=RAM, png=None, frames=None, trace=False, path='see'):
    if path not in ('see', 'info'):
        raise SystemExit('unidentifiedflooractionspill: unknown path %s' % path)
    script = SCRIPT if path == 'see' else INFO_SCRIPT
    if frames is None:
        frames = FRAMES if path == 'see' else INFO_FRAMES
    profile = menuspill.renderer_profile(rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('unidentifiedflooractionspill: requires Dot proportional mode')
    PyBoy = _import_pyboy()
    problems = []

    with tempfile.TemporaryDirectory(prefix='unidentifiedflooractionspill-') as tmp:
        work = os.path.join(tmp, 'floor-action.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        current = [None]
        rows = []
        records = {}
        gate_calls = []
        gate_collisions = []
        lcd_off = []
        white = []
        floor_parent = [None]
        action_state = [None]
        action_records = [None]
        action_exact = [None]
        info_tail = []
        pot_entry_attempts = []
        page_blanks = []
        pot_entry_lifecycle = []
        entry_samples = []

        def row_start(_context=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if shape != ACTION_SHAPE:
                current[0] = None
                return
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            current[0] = (pb.register_file.D, pb.register_file.HL,
                          actionmenuspill.staged_row(pb, source))

        def row_end(_context=None):
            if current[0] is None:
                return
            row, key, staged = current[0]
            rows.append((frame[0], row, key, staged))
            matches = [record for record in menuspill.records(pb, profile)
                       if record[0] == key]
            if matches:
                records[row] = matches[-1]
            current[0] = None

        gate = gbasm.assemble(menuvwf.ACTION_GATE_SRC,
                              menuvwf.ACTION_GATE_AT)[1]
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], row_start, None)
        pb.hook_register(31, menuvwf.ROW_EPILOG, row_end, None)
        pb.hook_register(menuvwf.ACTION_GATE_BANK, gate['actiongate'],
                         lambda _context=None: gate_calls.append(frame[0]), None)
        pb.hook_register(menuvwf.ACTION_GATE_BANK, gate['agcollision'],
                         lambda _context=None: gate_collisions.append(frame[0]), None)
        page_labels, _region_labels = menuvwf.item_transition_labels()
        info_labels = menuvwf.info_lifecycle_labels()

        def page_blank(_context=None):
            page_blanks.append((
                frame[0], pb.memory[0xC6A3], pb.memory[0xC1B3],
                pb.memory[0xC1B6], pb.memory[0xC1B7], stack(pb)))

        def pot_entry_attempt(_context=None):
            depth = pb.memory[0xC534]
            pot_entry_attempts.append({
                'frame': frame[0],
                'a': pb.register_file.A,
                'd': pb.register_file.D,
                'hl': pb.register_file.HL,
                'screen': pb.memory[0xC6A3],
                'state': pb.memory[0xC1B3],
                'phase': pb.memory[0xC1B6],
                'floor': pb.memory[0xC1B7],
                'render_phase': pb.memory[0xC1B1],
                'c0d5': pb.memory[0xC0D5],
                'shadow': pb.memory[0xC0D9] | (pb.memory[0xC0DA] << 8),
                'context': pb.memory[0xC6A6],
                'flags': pb.memory[0xC6DE],
                'count': pb.memory[0xC6AA],
                'selector': pb.memory[0xC6AC],
                'rows': pb.memory[0xC6BB],
                'depth': depth,
                'stack': tuple(pb.memory[0xC535 + index]
                               for index in range(depth + 1)),
                'shape': tuple(pb.memory[address]
                               for address in range(0xC69A, 0xC69F)),
                'display': tuple(pb.memory[address] for address in
                                 (0xFF40, 0xFF42, 0xFF43, 0xFF4A, 0xFF4B)),
            })

        pb.hook_register(menuvwf.ITEM_PAGE_BANK, page_labels['pbdisable'],
                         page_blank, None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK,
                         info_labels['potentrybegin'], pot_entry_attempt, None)
        for label in ('potentrychrome', 'potentrypublish', 'potentrypublished'):
            pb.hook_register(
                menuvwf.ACTION_BLANK_BANK, info_labels[label],
                lambda _context=None, name=label: pot_entry_lifecycle.append((
                    frame[0], name, pb.memory[0xC6A3], pb.memory[0xC1B3],
                    pb.memory[0xC1B6], pb.memory[0xC6BB])), None)
        if path == 'info':
            def info_box_done(_context=None):
                info_tail.append((
                    frame[0], pb.memory[0xC6A3], stack(pb),
                    tuple(bytes(pb.memory[0x9800 + row * 0x20:
                                          0x9814 + row * 0x20])
                          for row in (14, 15)),
                    tuple(bytes(pb.memory[0xC300 + row * 0x20:
                                          0xC314 + row * 0x20])
                          for row in (14, 15))))

            pb.hook_register(menuvwf.ACTION_BLANK_BANK,
                             info_labels['infoboxdone'], info_box_done, None)

        for frame[0] in range(frames):
            if frame[0] == 3399:
                floor_parent[0] = actionmenuspill.snapshot(pb)
            if frame[0] == 3599:
                action_state[0] = {
                    'screen': pb.memory[0xC6A3],
                    'stack': stack(pb),
                    'selector': pb.memory[0xC6AC],
                    'shape': tuple(pb.memory[address]
                                   for address in range(0xC69A, 0xC69F)),
                    'gate': pb.memory[0xC1B6],
                }
                action_records[0] = menuspill.records(pb, profile)
                action_exact[0] = {}
                for row, word in enumerate(WORDS):
                    record = records.get(row)
                    action_exact[0][row] = bool(
                        record and actionmenuspill.private_row_matches(
                            pb, profile, record[0], menuspill.encode(word),
                            record[1]))
            button = script.get(frame[0])
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            owned = frame[0] >= 2998
            if path == 'see' and 3900 <= frame[0] <= 4000:
                entry_samples.append((
                    frame[0], bytes(pb.memory[0x9800:0x9C00]),
                    bool(pb.memory[0xFF40] & 0x80), pb.memory[0xC6A3],
                    pb.memory[0xC1B3], pb.memory[0xC1B6],
                    pb.memory[0xC6BB], pb.screen.image.copy()))
            if owned:
                if not pb.memory[0xFF40] & 0x80:
                    lcd_off.append(frame[0])
                if len(set(pb.screen.image.convert('RGB').getdata())) == 1:
                    white.append(frame[0])

        final_screen = pb.memory[0xC6A3]
        final_stack = stack(pb)
        final_selector = pb.memory[0xC6AC]
        final_shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
        final_transaction = pb.memory[0xC1B3]
        returned = actionmenuspill.snapshot(pb)
        if png:
            pb.screen.image.save(png)
            print('unidentifiedflooractionspill: wrote %s' % png)

        expected_action = {
            'screen': 2, 'stack': (0, 1, 2), 'selector': 0xFF,
            'shape': ACTION_SHAPE, 'gate': 1,
        }
        if action_state[0] != expected_action:
            problems.append('settled Action state is %s, expected %s'
                            % (action_state[0], expected_action))
        if len(gate_calls) != 1 or gate_collisions:
            problems.append('Action admission/collision calls are %s/%s, expected 1/0'
                            % (gate_calls, gate_collisions))

        expected_staged = [bytes((0,)) + bytes(menuspill.encode(word))
                           for word in WORDS]
        if [event[1] for event in rows] != list(range(7)):
            problems.append('Action row order is %s, expected 0..6'
                            % [event[1] for event in rows])
        if [event[3] for event in rows] != expected_staged:
            problems.append('staged Action words are %s, expected %s'
                            % ([event[3].hex(' ') for event in rows],
                               [value.hex(' ') for value in expected_staged]))
        for row, word in enumerate(WORDS):
            record = records.get(row)
            expected_base = (menuvwf.ACTION_POOL_BASE + 4 * row
                             if row < 6 else menuvwf.POOL_BASE)
            expected = (expected_base, 4, 1)
            actual = None if record is None else record[1:]
            if actual != expected:
                problems.append('row %d `%s` allocation is %s, expected %s'
                                % (row, word, actual, expected))
                continue
            if action_exact[0] is None or not action_exact[0].get(row):
                problems.append('row %d `%s` is not plane-exact proportional text'
                                % (row, word))
        if action_records[0] is None or len(action_records[0]) != 8:
            problems.append('settled record count is %d, expected one Floor row plus '
                            'seven Action rows' %
                            (0 if action_records[0] is None
                             else len(action_records[0])))

        if path == 'info':
            blank_tail = (bytes(20), bytes(20))
            if len(info_tail) != 1:
                problems.append('Info box completion events are %s, expected one'
                                % (info_tail,))
            elif (info_tail[0][1], info_tail[0][2]) != (4, (0, 1, 2, 4)):
                problems.append('Info tail was captured on screen/stack %d/%s, expected '
                                '4/(0,1,2,4)' % (info_tail[0][1], info_tail[0][2]))
            elif info_tail[0][3] != blank_tail or info_tail[0][4] != blank_tail:
                problems.append('Info rows 14-15 retain Action references: BG %s, shadow %s'
                                % (tuple(row.hex() for row in info_tail[0][3]),
                                   tuple(row.hex() for row in info_tail[0][4])))
        else:
            expected_entry = {
                'screen': 12, 'state': 0, 'phase': 1, 'floor': 1,
                'render_phase': 1, 'c0d5': 1, 'shadow': 0xC380,
                'context': 0, 'flags': 0, 'count': 4, 'selector': 0,
                'rows': 4, 'depth': 3, 'stack': (0, 1, 2, 12),
                'shape': (0, 3, 4, 18, 2),
                'display': (0xE7, 0, 0, 0x80, 7),
            }
            first_entry = pot_entry_attempts[0] if pot_entry_attempts else None
            actual_entry = (None if first_entry is None else
                            {key: first_entry[key] for key in expected_entry})
            if actual_entry != expected_entry:
                problems.append('first appended Floor -> Pot predicate is %s, '
                                'expected %s' % (actual_entry, expected_entry))
            if page_blanks:
                problems.append('appended Floor -> Pot See executed page blanker(s) %s'
                                % (page_blanks,))
            viewer_samples = [sample for sample in entry_samples
                              if sample[3] in (12, 13) and 1 <= sample[6] <= 5]
            chrome_frames = [sample[0] for sample in viewer_samples
                             if potreturnspill.pot_chrome_complete(
                                 sample[1], sample[6])]
            settled_title = (potreturnspill.pot_title_pixels(viewer_samples[-1][7])
                             if viewer_samples else None)
            text_frames = [sample[0] for sample in viewer_samples
                           if settled_title is not None and
                           potreturnspill.pot_title_pixels(sample[7]) ==
                           settled_title]
            if not chrome_frames:
                problems.append('appended Floor -> Pot See never exposed complete chrome')
            elif not text_frames or not potreturnspill.pot_text_visible(
                    viewer_samples[-1][7]):
                problems.append('appended Floor -> Pot See never exposed Pot text')
            elif chrome_frames[0] >= text_frames[0]:
                problems.append('appended Floor Pot text appeared at f%d before an '
                                'earlier empty-chrome frame (first chrome f%d)' %
                                (text_frames[0], chrome_frames[0]))
            lifecycle = tuple(label for _at, label, screen, _state, _phase, _rows
                              in pot_entry_lifecycle if screen in (12, 13))
            if (lifecycle.count('potentrychrome') != 1 or
                    lifecycle.count('potentrypublished') != 1 or
                    not lifecycle or lifecycle[-1] != 'potentrypublished' or
                    len(lifecycle) < 3 or lifecycle[-2] != 'potentrypublish'):
                problems.append('appended Floor Pot entry lifecycle order is %s' %
                                (lifecycle,))

        expected_floor_shape = (0, 0, 1, 4, 0x50)
        if (final_screen, final_stack, final_selector, final_shape,
                final_transaction) != (1, (0, 1), 0xFF,
                                       expected_floor_shape, 0):
            problems.append('%s return settled as screen/stack/selector/shape/state '
                            '%d/%s/$%02X/%s/%d, expected exact screen-1 Floor parent'
                            % (path.title(), final_screen, final_stack, final_selector,
                               final_shape, final_transaction))
        if floor_parent[0] is None:
            problems.append('missed the outgoing Floor-parent snapshot')
        else:
            if returned['bg'] != floor_parent[0]['bg']:
                problems.append('%s return BG tilemap differs from outgoing Floor parent'
                                % path.title())
            if not actionmenuspill.visible_layer_equal(
                    returned, floor_parent[0], 'bg', range(16)):
                problems.append('%s return BG pixels differ from outgoing Floor parent'
                                % path.title())
            if not actionmenuspill.visible_layer_equal(
                    returned, floor_parent[0], 'window', range(2)):
                problems.append('%s return Window differs from outgoing Floor parent'
                                % path.title())
        if lcd_off:
            problems.append('LCDC bit 7 cleared during owned paging/Action/return at frame(s) %s'
                            % lcd_off)
        if white:
            problems.append('owned paging/Action/return produced all-white frame(s) %s'
                            % white)
        pb.stop(save=False)

    if trace:
        print('unidentifiedflooractionspill: rows %s' % (rows,))
        print('unidentifiedflooractionspill: records %s' % (records,))
        print('unidentifiedflooractionspill: Pot entry attempts %s' %
              (pot_entry_attempts,))
        print('unidentifiedflooractionspill: page blanks %s' % (page_blanks,))
        print('unidentifiedflooractionspill: Pot entry lifecycle %s' %
              (pot_entry_lifecycle,))
        if path == 'info':
            print('unidentifiedflooractionspill: Info tail %s' % (info_tail,))
    for problem in problems:
        print('  ' + problem)
    print('unidentifiedflooractionspill: screen-2 seven-row picker -> %s -> Floor; '
          'allocations %s; LCD-off %d, white %d; %d problem(s)'
          % (path.title(),
             ' '.join('$%02X' % records[row][1] for row in sorted(records)),
             len(lcd_off), len(white), len(problems)))
    if problems:
        raise SystemExit('unidentifiedflooractionspill: %d problem(s)' % len(problems))
    print('unidentifiedflooractionspill: Items -> Floor Info row is proportional and '
          '%s returns to its exact parent without whole-LCD blanking'
          % path.title())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png')
    parser.add_argument('--frames', type=int)
    parser.add_argument('--path', choices=('see', 'info'), default='see')
    parser.add_argument('--trace', action='store_true')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('unidentifiedflooractionspill: missing %s' % path)
    run(args.rom, args.ram, args.png, args.frames, args.trace, args.path)


if __name__ == '__main__':
    main()
