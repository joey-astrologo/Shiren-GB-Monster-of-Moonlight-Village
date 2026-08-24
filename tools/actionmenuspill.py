#!/usr/bin/env python3
"""Prove the held-Items Action overlay lifecycle on every Item page.

The real four-page Dragon's Maw save contains all ownership heights needed by the
checkpoint: ordinary four-row pickers, identity-hidden five-row pickers, and a six-row
identity-hidden Pot.  Five independent boots also cover both Equip and Remove.

For each case this fixture opens screen 2, moves the cursor to the last verb and back,
then presses B.  It requires the direct 0,1,2 stack gate, private $C7-$DE verb slices,
an exact box-6 parent restore inside VBlank, no redundant Status/Items replay, unchanged
pixels outside that footprint, no blank/mixed/unowned state inside it, an immutable
status Window, the identical Item page/selection on return, prompt post-B input, and no
LCD-off or all-white frame. Synthesized exact short-page shapes additionally cover one
through four pages and retained record counts below five.
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


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log_1_dragons_maw.srm')
BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a',
    2620: 'b', 2720: 'a',
}
OPEN_AT = 3300
FRAMES = 4300
ITEM_SHAPE = (0, 3, 5, 18, 0x02)
ACTION_PREFIX = (13, 1)
ACTION_SUFFIX = (5, 0x02)
VISIBLE_BG_ROWS = range(16)       # WY=$80 overlays rows 16-17 with the Window.
VISIBLE_WINDOW_ROWS = range(2)

CASES = (
    ('page1-equip', 0, ('Equip', 'Toss', 'Drop', 'Info'), 20),
    ('page1-remove', 1, ('Remove', 'Toss', 'Drop', 'Info'), 20),
    ('page2-hidden-bracer', 6, ('Equip', 'Toss', 'Drop', 'Name', 'Info'), 20),
    ('page3-food', 10, ('Eat', 'Toss', 'Drop', 'Info'), 20),
    ('page4-hidden-pot', 15, ('See', 'Put', 'Toss', 'Drop', 'Name', 'Info'), 20),
    ('one-item-page', 0, ('Equip', 'Toss', 'Drop', 'Info'), 1),
    ('short-page2', 6, ('Equip', 'Toss', 'Drop', 'Name', 'Info'), 7),
    ('short-page3', 10, ('Eat', 'Toss', 'Drop', 'Info'), 11),
    ('short-page4', 15, ('See', 'Put', 'Toss', 'Drop', 'Name', 'Info'), 16),
)


def snapshot(pb):
    return {
        'bg': bytes(pb.memory[0x9800:0x9C00]),
        'window': bytes(pb.memory[0x9C00:0xA000]),
        'tiles': bytes(pb.memory[0x8800:0x9800]),
        'lcdc': pb.memory[0xFF40],
    }


def tile_planes(state, tile):
    start = menuspill.tile_data_addr(tile) - 0x8800
    return state['tiles'][start:start + 16]


def resolved(state, layer, row, col):
    tile = state[layer][row * 32 + col]
    return tile, tile_planes(state, tile)


def visible_layer_equal(left, right, layer, rows):
    return all(resolved(left, layer, row, col) == resolved(right, layer, row, col)
               for row in rows for col in range(20))


def white_frame(image):
    return len(set(image.convert('RGB').getdata())) == 1


def staged_row(pb, source, limit=18):
    out = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            break
        out.append(value)
    return bytes(out)


def private_row_matches(pb, profile, key, codes, base):
    """Plane-exact Action check without widening menuspill's global pool allowlist."""
    want = menuspill.compose(codes, profile)
    first = key + 2 - menuspill.SHADOW       # border + one raw cursor cell
    if len(want) > 4:
        return False
    for index, tile_bytes in enumerate(want):
        tile = pb.memory[menuspill.BGMAP + first + index]
        if tile != base + index:
            return False
        at = menuspill.tile_data_addr(tile)
        if bytes(pb.memory[at:at + 16]) != bytes(tile_bytes):
            return False
    return True


def runtime_labels():
    _gate_code, gate = gbasm.assemble(menuvwf.ACTION_GATE_SRC,
                                      menuvwf.ACTION_GATE_AT)
    _pop_code, pop = gbasm.assemble(menuvwf.ACTION_POP_SRC,
                                    menuvwf.ACTION_POP_AT)
    _blank_code, blank = gbasm.assemble(menuvwf.ACTION_BLANK_SRC,
                                        menuvwf.ACTION_BLANK_AT)
    return gate, pop, blank


def run_case(PyBoy, rom, ram, profile, labels, case, png_dir=None, frames=FRAMES):
    label, selector, expected_words, inventory_count = case
    page, item_row = selector // 5 + 1, selector % 5
    expected_rows = len(expected_words)
    footprint = {(row, col)
                 for row in range(1, 2 * expected_rows + 2)
                 for col in range(13, 20)}
    problems = []

    with tempfile.TemporaryDirectory(prefix='actionmenuspill-') as tmp:
        run_rom = os.path.join(tmp, 'action.gb')
        shutil.copyfile(rom, run_rom)
        shutil.copyfile(ram, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        schedule = dict(BOOT)
        for index in range(page - 1):
            schedule[2820 + index * 80] = 'right'
        for index in range(item_row):
            schedule[3120 + index * 60] = 'down'
        schedule[OPEN_AT] = 'a'

        dispatches = []
        current_action = [None]
        action_rows = []
        action_records = {}
        gate_calls = []
        gate_collisions = []
        pop_calls = []
        handler_returns = []
        item_rebuild_rows = []
        post_input_at = [None]
        post_input_accepts = []
        post_input_restores = []
        restore_events = []
        restore_failures = []
        lifecycle_events = []
        cursor_checks = {}
        cursor_results = []
        action_check_at = [None]
        cancel_at = [None]
        pre_open = [None]
        pre_open_menu = [None]
        action_state = [None]
        pre_cancel = [None]
        final_state = [None]
        final_menu = [None]
        lcd_off = []
        white = []
        outside_diffs = []
        window_diffs = []
        inside_bad = []
        mixed_footprints = []

        def dispatch(_ctx=None):
            dispatches.append((frame[0], pb.register_file.A,
                               tuple(pb.memory[0xC534 + index] for index in range(4))))

        def menurow(_ctx=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if not (shape[:2] == ACTION_PREFIX and shape[3:] == ACTION_SUFFIX):
                current_action[0] = None
                return
            row = pb.register_file.D
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            current_action[0] = (row, pb.register_file.HL, staged_row(pb, source))

        def row_end(_ctx=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if cancel_at[0] is not None and shape == ITEM_SHAPE:
                item_rebuild_rows.append((frame[0], pb.register_file.D))
            if current_action[0] is None:
                return
            row, key, staged = current_action[0]
            action_rows.append((frame[0], row, key, staged))
            matches = [record for record in menuspill.records(pb, profile)
                       if record[0] == key]
            if matches:
                action_records[row] = matches[-1]
            current_action[0] = None
            if row != expected_rows - 1 or cancel_at[0] is not None:
                return
            action_check_at[0] = frame[0] + 30
            at = frame[0] + 70
            cursor = 0
            for _index in range(expected_rows - 1):
                schedule[at] = 'down'
                cursor += 1
                cursor_checks[at + 15] = cursor
                at += 60
            for _index in range(expected_rows - 1):
                schedule[at] = 'up'
                cursor -= 1
                cursor_checks[at + 15] = cursor
                at += 60
            cancel_at[0] = at
            schedule[at] = 'b'

        def gate_call(_ctx=None):
            if frame[0] >= OPEN_AT - 2:
                gate_calls.append(frame[0])

        def gate_collision(_ctx=None):
            if frame[0] >= OPEN_AT - 2:
                gate_collisions.append(frame[0])

        def pop_call(_ctx=None):
            if frame[0] >= OPEN_AT - 2 and pb.memory[0xC6A3] == 2:
                pop_calls.append((frame[0], pb.register_file.HL,
                                  pb.memory[0xC1B3]))

        def restored(_ctx=None):
            if frame[0] >= OPEN_AT - 2:
                restore_events.append((frame[0], pb.memory[0xFF44], snapshot(pb)))
                lifecycle_events.append('restore')

        def handler_return(_ctx=None):
            if cancel_at[0] is not None and frame[0] >= cancel_at[0]:
                handler_returns.append(frame[0])
                if post_input_at[0] is None:
                    post_input_at[0] = frame[0] + 6
                    schedule[post_input_at[0]] = 'down'
                    schedule[post_input_at[0] + 40] = 'up'

        def restore_failed(_ctx=None):
            if frame[0] >= OPEN_AT - 2:
                restore_failures.append(frame[0])

        gate, pop, blank = labels
        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], menurow, None)
        pb.hook_register(31, menuvwf.ROW_EPILOG, row_end, None)
        pb.hook_register(menuvwf.ACTION_GATE_BANK, gate['actiongate'], gate_call, None)
        pb.hook_register(menuvwf.ACTION_GATE_BANK, gate['agcollision'],
                         gate_collision, None)
        pb.hook_register(menuvwf.ACTION_POP_BANK, pop['actionpop'], pop_call, None)
        pb.hook_register(4, 0x568F, handler_return, None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, blank['abrestored'], restored, None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, blank['abfail'],
                         restore_failed, None)

        for frame[0] in range(frames):
            if frame[0] == OPEN_AT - 1:
                if inventory_count < 20:
                    # Start from a genuinely rendered page, then impose the exact native
                    # short-page shape before Action admission: item count, retained row
                    # records, empty trailing interiors, and page markers. This covers
                    # the one- through four-page state space without inventing verbs.
                    pb.memory[0xC6AA] = inventory_count
                    live_rows = inventory_count - 5 * (page - 1)
                    pb.memory[0xC1B2] = live_rows
                    for row in range(live_rows, 5):
                        y = 4 + 2 * row
                        for col in range(1, 19):
                            pb.memory[0x9800 + y * 32 + col] = 0
                            pb.memory[0xC300 + y * 32 + col] = 0
                    markers = [0xBC] * 4
                    for index in range(page):
                        markers[index] = 0xC5
                    markers[page - 1] = 0xC6 if page > 1 else 0xBC
                    for index, tile in enumerate(markers):
                        pb.memory[0x9800 + 3 * 32 + 15 + index] = tile
                        pb.memory[0xC300 + 3 * 32 + 15 + index] = tile
                pre_open[0] = snapshot(pb)
                pre_open_menu[0] = tuple(pb.memory[address] for address in
                                         (0xC6A0, 0xC6A1, 0xC6A2, 0xC6A3,
                                          0xC6A4, 0xC6A5, 0xC6A6, 0xC6BB,
                                          0xC1AE, 0xC1AF, 0xC1B0, 0xC1B1, 0xC1B2))
            if cancel_at[0] is not None and frame[0] == cancel_at[0] - 1:
                pre_cancel[0] = snapshot(pb)
            button = schedule.get(frame[0])
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()

            if post_input_at[0] is not None and frame[0] >= post_input_at[0]:
                current_selector = pb.memory[0xC6AC]
                if not post_input_accepts and current_selector != selector:
                    post_input_accepts.append((frame[0], current_selector))
                if post_input_accepts and frame[0] >= post_input_at[0] + 40 and \
                        current_selector == selector and not post_input_restores:
                    post_input_restores.append(frame[0])

            if frame[0] in cursor_checks:
                actual = pb.memory[0xC6A5]
                cursor_results.append((frame[0], actual, cursor_checks[frame[0]]))

            if action_check_at[0] is not None and frame[0] == action_check_at[0]:
                action_state[0] = snapshot(pb)
                for row, word in enumerate(expected_words):
                    event = next((event for event in action_rows if event[1] == row), None)
                    if event is None:
                        continue
                    _at, _row, key, _staged = event
                    if not private_row_matches(
                            pb, profile, key, menuspill.encode(word),
                            menuvwf.ACTION_POOL_BASE + 4 * row):
                        problems.append('%s row %d `%s` is not plane-exact VWF'
                                        % (label, row, word))

            active = frame[0] >= OPEN_AT - 2 and (
                cancel_at[0] is None or frame[0] <= cancel_at[0] + 150)
            if active:
                state = snapshot(pb)
                if not state['lcdc'] & 0x80:
                    lcd_off.append(frame[0])
                image = pb.screen.image.copy()
                if white_frame(image):
                    white.append(frame[0])
                if png_dir and (frame[0] == OPEN_AT or
                                frame[0] == action_check_at[0] or
                                (cancel_at[0] is not None and
                                 cancel_at[0] - 2 <= frame[0] <= cancel_at[0] + 60)):
                    os.makedirs(png_dir, exist_ok=True)
                    image.save(os.path.join(png_dir, '%s_f%04d.png' %
                                            (label, frame[0])))
                if pre_open[0] is not None and (post_input_at[0] is None or
                                                frame[0] < post_input_at[0]):
                    for row in VISIBLE_BG_ROWS:
                        for col in range(20):
                            if (row, col) in footprint:
                                continue
                            if resolved(state, 'bg', row, col) != \
                                    resolved(pre_open[0], 'bg', row, col):
                                outside_diffs.append((frame[0], row, col))
                                break
                        if outside_diffs and outside_diffs[-1][0] == frame[0]:
                            break
                    if not visible_layer_equal(state, pre_open[0], 'window',
                                               VISIBLE_WINDOW_ROWS):
                        window_diffs.append(frame[0])
                if cancel_at[0] is not None and frame[0] >= cancel_at[0] and \
                        pre_open[0] is not None and pre_cancel[0] is not None:
                    for row, col in footprint:
                        actual = resolved(state, 'bg', row, col)
                        allowed = {
                            resolved(pre_open[0], 'bg', row, col),
                            resolved(pre_cancel[0], 'bg', row, col),
                        }
                        if actual not in allowed:
                            inside_bad.append((frame[0], row, col, actual[0]))
                            break
                    parent = all(resolved(state, 'bg', row, col) ==
                                 resolved(pre_open[0], 'bg', row, col)
                                 for row, col in footprint)
                    action = all(resolved(state, 'bg', row, col) ==
                                 resolved(pre_cancel[0], 'bg', row, col)
                                 for row, col in footprint)
                    if not parent and not action:
                        mixed_footprints.append(frame[0])

            if cancel_at[0] is not None and frame[0] == cancel_at[0] + 140:
                final_state[0] = snapshot(pb)

        final_selector = pb.memory[0xC6AC]
        final_transaction = pb.memory[0xC1B3]
        final_gate = pb.memory[0xC1B6]
        final_screen = pb.memory[0xC6A3]
        final_count = pb.memory[0xC6AA]
        final_menu[0] = tuple(pb.memory[address] for address in
                              (0xC6A0, 0xC6A1, 0xC6A2, 0xC6A3,
                               0xC6A4, 0xC6A5, 0xC6A6, 0xC6BB,
                               0xC1AE, 0xC1AF, 0xC1B0, 0xC1B1, 0xC1B2))
        pb.stop(save=False)

    expected_staged = [bytes((0,)) + bytes(menuspill.encode(word))
                       for word in expected_words]
    actual_staged = [event[3] for event in action_rows]
    if actual_staged != expected_staged:
        problems.append('%s staged rows %s, expected %s'
                        % (label, [row.hex(' ') for row in actual_staged],
                           [row.hex(' ') for row in expected_staged]))
    if [event[1] for event in action_rows] != list(range(expected_rows)):
        problems.append('%s drew action rows %s, expected 0..%d'
                        % (label, [event[1] for event in action_rows], expected_rows - 1))
    for row in range(expected_rows):
        record = action_records.get(row)
        expected = (menuvwf.ACTION_POOL_BASE + 4 * row, 4, 1)
        actual = None if record is None else record[1:]
        if actual != expected:
            problems.append('%s row %d allocation is %s, expected base/cap/raw %s'
                            % (label, row, actual, expected))

    if pre_open[0] is None or action_state[0] is None or pre_cancel[0] is None or \
            final_state[0] is None:
        problems.append('%s missed one or more lifecycle snapshots' % label)
    else:
        live_ids = [pre_open[0]['bg'][row * 32 + col]
                    for row in VISIBLE_BG_ROWS for col in range(20)]
        live_ids += [pre_open[0]['window'][row * 32 + col]
                     for row in VISIBLE_WINDOW_ROWS for col in range(20)]
        collisions = [tile for tile in live_ids
                      if menuvwf.ACTION_POOL_BASE <= tile < menuvwf.ACTION_POOL_END]
        if collisions:
            problems.append('%s parent references private Action IDs %s'
                            % (label, ' '.join('$%02X' % tile
                                               for tile in sorted(set(collisions)))))
        if final_state[0]['bg'] != pre_open[0]['bg']:
            problems.append('%s final BG map differs from its original Item page' % label)
        if not visible_layer_equal(final_state[0], pre_open[0], 'bg',
                                   VISIBLE_BG_ROWS):
            problems.append('%s final Item pixels differ from the original page' % label)
        if not visible_layer_equal(final_state[0], pre_open[0], 'window',
                                   VISIBLE_WINDOW_ROWS):
            problems.append('%s final Window differs from the original page' % label)

    if len(gate_calls) != 1 or gate_collisions:
        problems.append('%s Action admission/collision calls are %s/%s, expected 1/0'
                        % (label, gate_calls, gate_collisions))
    if len(pop_calls) != 1 or pop_calls[0][1] != 0x5689:
        problems.append('%s exact B-pop calls are %s, expected one with HL=$5689'
                        % (label, pop_calls))
    if len(handler_returns) != 1:
        problems.append('%s B-handler returns are %s, expected one'
                        % (label, handler_returns))
    elif handler_returns[0] - cancel_at[0] > 3:
        problems.append('%s B handler held input for %d frames after cancel'
                        % (label, handler_returns[0] - cancel_at[0]))
    if len(post_input_accepts) != 1 or post_input_at[0] is None or \
            post_input_accepts[0][0] - post_input_at[0] > 2:
        problems.append('%s first post-B Down was not accepted promptly: press=%s result=%s'
                        % (label, post_input_at[0], post_input_accepts))
    if len(post_input_restores) != 1:
        problems.append('%s post-B Down/Up did not restore selector %d: %s'
                        % (label, selector, post_input_restores))
    if len(restore_events) != 1:
        problems.append('%s regional parent restores are %d, expected one'
                        % (label, len(restore_events)))
    else:
        _restore_at, ly, restored_state = restore_events[0]
        if not 0x90 <= ly <= 0x99:
            problems.append('%s Action parent restore completed at LY=$%02X, '
                            'outside VBlank'
                            % (label, ly))
        if lifecycle_events != ['restore']:
            problems.append('%s lifecycle event order is %s, expected one direct restore'
                            % (label, lifecycle_events))
        unrestored = [(row, col, restored_state['bg'][row * 32 + col])
                      for row, col in footprint
                      if resolved(restored_state, 'bg', row, col) !=
                      resolved(pre_open[0], 'bg', row, col)]
        if unrestored:
            problems.append('%s Action footprint did not resolve to its parent: %s'
                            % (label, unrestored[:8]))
    if restore_failures:
        problems.append('%s reached conservative Action fallback at %s'
                        % (label, restore_failures))
    if lcd_off:
        problems.append('%s disabled the LCD at %s' % (label, lcd_off[:12]))
    if white:
        problems.append('%s produced all-white frames at %s' % (label, white[:12]))
    if outside_diffs:
        problems.append('%s changed pixels outside box 6 at %s'
                        % (label, outside_diffs[:8]))
    if window_diffs:
        problems.append('%s changed the persistent Window at %s'
                        % (label, window_diffs[:8]))
    if inside_bad:
        problems.append('%s published an unowned box-6 cell at %s'
                        % (label, inside_bad[:8]))
    if mixed_footprints:
        problems.append('%s exposed a mixed/blank Action-parent footprint at %s'
                        % (label, mixed_footprints[:12]))
    bad_cursor = [entry for entry in cursor_results if entry[1] != entry[2]]
    if len(cursor_results) != 2 * (expected_rows - 1) or bad_cursor:
        problems.append('%s cursor checks are %s, expected complete last-row round trip'
                        % (label, cursor_results))
    replay_dispatches = [(at, screen) for at, screen, _stack in dispatches
                         if at >= cancel_at[0]]
    if replay_dispatches or item_rebuild_rows:
        problems.append('%s performed redundant post-B screen/row replay: %s / %s'
                        % (label, replay_dispatches, item_rebuild_rows))
    if (final_screen, final_selector, final_transaction, final_gate) != \
            (1, selector, 0, 0):
        problems.append('%s final screen/selector/state/gate is %s, expected %s'
                        % (label,
                           (final_screen, final_selector, final_transaction, final_gate),
                           (1, selector, 0, 0)))
    if final_count != inventory_count:
        problems.append('%s final item count is %d, expected synthesized %d'
                        % (label, final_count, inventory_count))
    expected_menu = (0x42, 0, 0x12, 1, 4, selector % 5, 0, 5,
                     pre_open_menu[0][8], pre_open_menu[0][9],
                     pre_open_menu[0][10], 4, pre_open_menu[0][12])
    if final_menu[0] != expected_menu:
        problems.append('%s fast-return menu state is %s, expected %s'
                        % (label, final_menu[0], expected_menu))

    print('actionmenuspill: %-20s page %d selector %d, %d rows, cursor %d, '
          'restore LY=%s, B return=%s, input=%s, LCD-off %d, white %d; %d problem(s)'
          % (label, page, selector, expected_rows, len(cursor_results),
             ('missing' if not restore_events else '$%02X' % restore_events[0][1]),
             ('missing' if not handler_returns else '+%d frames' %
              (handler_returns[0] - cancel_at[0])),
             ('missing' if not post_input_accepts else '+%d frames' %
              (post_input_accepts[0][0] - post_input_at[0])),
             len(lcd_off), len(white), len(problems)))
    for problem in problems:
        print('  ' + problem)
    return problems


def run(rom, ram=RAM, png_dir=None, frames=FRAMES):
    profile = menuspill.renderer_profile(rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('actionmenuspill: requires the approved proportional renderer')
    PyBoy = _import_pyboy()
    labels = runtime_labels()
    problems = []
    for case in CASES:
        problems.extend(run_case(PyBoy, rom, ram, profile, labels, case,
                                 png_dir, frames))
    if problems:
        raise SystemExit('actionmenuspill: %d total problem(s)' % len(problems))
    print('actionmenuspill: one through four full/short pages, Equip/Remove, and '
          '4/5/6-row held Action open/cursor/B/input lifecycles remain prompt, LCD-on, '
          'and ownership-exact')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png-dir')
    parser.add_argument('--frames', type=int, default=FRAMES)
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('actionmenuspill: missing ' + path)
    run(args.rom, args.ram, args.png_dir, args.frames)


if __name__ == '__main__':
    main()
