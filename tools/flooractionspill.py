#!/usr/bin/env python3
"""Prove fast Action dismissal from the standing-item Floor page.

The Wood Arrow save carries four Item pages and stands on a ground item.  This fixture
pages to the appended Floor page, opens its four-row Action picker, and presses B.  The
picker must restore the complete settled Floor parent in one VBlank, return directly to
screen-1 input, and accept an immediate Left page input without an LCD-off/full-screen
blank or a redundant Status/Floor reconstruction.
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
import actionmenuspill                                             # noqa: E402
import gbasm                                                       # noqa: E402
import menuspill                                                   # noqa: E402
import menuvwf                                                     # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_item_menu_wood_arrow.srm')
BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a', 2620: 'b',
}
ITEM_SHAPE = (0, 3, 5, 18, 0x02)
ACTION_SHAPE = (13, 1, 4, 5, 0x02)
WORDS = ('Take', 'Fire', 'Swap', 'Info')
FRAMES = 3900
FOOTPRINT = {(row, col) for row in range(1, 10) for col in range(13, 20)}


def runtime_labels():
    _gate_code, gate = gbasm.assemble(menuvwf.ACTION_GATE_SRC,
                                      menuvwf.ACTION_GATE_AT)
    _pop_code, pop = gbasm.assemble(menuvwf.ACTION_POP_SRC,
                                    menuvwf.ACTION_POP_AT)
    _blank_code, blank = gbasm.assemble(menuvwf.ACTION_BLANK_SRC,
                                        menuvwf.ACTION_BLANK_AT)
    return gate, pop, blank


def run(rom, ram=RAM, png_dir=None, frames=FRAMES):
    profile = menuspill.renderer_profile(rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('flooractionspill: requires the approved proportional renderer')
    if png_dir:
        os.makedirs(png_dir, exist_ok=True)
    PyBoy = _import_pyboy()
    gate, pop, blank = runtime_labels()
    problems = []

    with tempfile.TemporaryDirectory(prefix='flooractionspill-') as tmp:
        run_rom = os.path.join(tmp, 'flooraction.gb')
        shutil.copyfile(rom, run_rom)
        shutil.copyfile(ram, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        schedule = dict(BOOT)
        item_open = [False]
        page_completes = []
        floor_at = [None]
        action_at = [None]
        cancel_at = [None]
        post_input_at = [None]
        floor_parent = [None]
        pre_cancel = [None]
        fast_return = [None]
        fast_machine = [None]
        action_current = [None]
        action_rows = []
        action_records = {}
        action_check_at = [None]
        gate_calls = []
        gate_collisions = []
        pop_calls = []
        restores = []
        restore_failures = []
        handler_returns = []
        post_input_accepts = []
        replay_dispatches = []
        rebuild_rows = []
        lcd_off = []
        white = []
        outside_diffs = []
        window_diffs = []
        inside_bad = []
        mixed_footprints = []

        def dispatch(_ctx=None):
            screen = pb.register_file.A
            if screen == 0 and not item_open[0]:
                schedule[frame[0] + 80] = 'a'
                item_open[0] = True
            if (cancel_at[0] is not None and frame[0] >= cancel_at[0] and
                    (post_input_at[0] is None or frame[0] < post_input_at[0])):
                replay_dispatches.append((frame[0], screen))

        def menurow(_ctx=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if shape == ITEM_SHAPE and pb.register_file.D == 4:
                selector = pb.memory[0xC6AC]
                if (selector in (0, 5, 10, 15) and
                        (not page_completes or page_completes[-1][1] != selector)):
                    page_completes.append((frame[0], selector))
                    schedule[frame[0] + 90] = 'right'
            if shape != ACTION_SHAPE:
                action_current[0] = None
                return
            row = pb.register_file.D
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            action_current[0] = (row, pb.register_file.HL,
                                 actionmenuspill.staged_row(pb, source))

        def row_end(_ctx=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if (cancel_at[0] is not None and shape == ITEM_SHAPE and
                    (post_input_at[0] is None or frame[0] < post_input_at[0])):
                rebuild_rows.append((frame[0], pb.register_file.D))
            if action_current[0] is None:
                return
            row, key, staged = action_current[0]
            action_rows.append((frame[0], row, key, staged))
            matches = [record for record in menuspill.records(pb, profile)
                       if record[0] == key]
            if matches:
                action_records[row] = matches[-1]
            action_current[0] = None
            if row == len(WORDS) - 1 and cancel_at[0] is None:
                action_check_at[0] = frame[0] + 30
                cancel_at[0] = frame[0] + 70
                schedule[cancel_at[0]] = 'b'

        def redraw_return(_ctx=None):
            if (floor_at[0] is None and pb.memory[0xC6AC] == 0xFF and
                    pb.memory[0xC1B7] == 1):
                floor_at[0] = frame[0]
                action_at[0] = frame[0] + 90
                schedule[action_at[0]] = 'a'

        def gate_call(_ctx=None):
            if action_at[0] is not None and frame[0] >= action_at[0] - 2:
                gate_calls.append(frame[0])

        def gate_collision(_ctx=None):
            if action_at[0] is not None and frame[0] >= action_at[0] - 2:
                gate_collisions.append(frame[0])

        def pop_call(_ctx=None):
            if cancel_at[0] is not None and frame[0] >= cancel_at[0] - 2:
                pop_calls.append((frame[0], pb.register_file.HL,
                                  pb.memory[0xC1B3]))

        def restored(_ctx=None):
            if cancel_at[0] is not None:
                restores.append((frame[0], pb.memory[0xFF44],
                                 actionmenuspill.snapshot(pb)))

        def restore_failed(_ctx=None):
            if cancel_at[0] is not None:
                restore_failures.append(frame[0])

        def handler_return(_ctx=None):
            if cancel_at[0] is None or frame[0] < cancel_at[0]:
                return
            handler_returns.append(frame[0])
            fast_return[0] = actionmenuspill.snapshot(pb)
            fast_machine[0] = {
                'stack': tuple(pb.memory[0xC534 + index] for index in range(4)),
                'descriptor': tuple(pb.memory[0xC69A + index] for index in range(7)),
                'menu': tuple(pb.memory[address] for address in
                              (0xC6A3, 0xC6A4, 0xC6A5, 0xC6A6, 0xC6A7,
                               0xC6A8, 0xC6AA, 0xC6AC, 0xC6BB)),
                'transaction': tuple(pb.memory[address] for address in
                                     (0xC1B1, 0xC1B2, 0xC1B3, 0xC1B6, 0xC1B7)),
            }
            post_input_at[0] = frame[0] + 6
            schedule[post_input_at[0]] = 'left'

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(4, 0x4856, redraw_return, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], menurow, None)
        pb.hook_register(31, menuvwf.ROW_EPILOG, row_end, None)
        pb.hook_register(menuvwf.ACTION_GATE_BANK, gate['actiongate'], gate_call, None)
        pb.hook_register(menuvwf.ACTION_GATE_BANK, gate['agcollision'],
                         gate_collision, None)
        pb.hook_register(menuvwf.ACTION_POP_BANK, pop['actionpop'], pop_call, None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, blank['abrestored'], restored, None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, blank['abfail'],
                         restore_failed, None)
        pb.hook_register(4, 0x568F, handler_return, None)

        for frame[0] in range(frames):
            if action_at[0] is not None and frame[0] == action_at[0] - 1:
                floor_parent[0] = actionmenuspill.snapshot(pb)
            if cancel_at[0] is not None and frame[0] == cancel_at[0] - 1:
                pre_cancel[0] = actionmenuspill.snapshot(pb)
            button = schedule.get(frame[0])
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()

            if (post_input_at[0] is not None and frame[0] >= post_input_at[0] and
                    not post_input_accepts and pb.memory[0xC6AC] == 15):
                post_input_accepts.append(frame[0])

            if action_check_at[0] is not None and frame[0] == action_check_at[0]:
                for row, word in enumerate(WORDS):
                    event = next((event for event in action_rows if event[1] == row), None)
                    if event is None:
                        continue
                    _at, _row, key, _staged = event
                    if not actionmenuspill.private_row_matches(
                            pb, profile, key, menuspill.encode(word),
                            menuvwf.ACTION_POOL_BASE + 4 * row):
                        problems.append('Floor Action row %d `%s` is not plane-exact VWF' %
                                        (row, word))

            active = action_at[0] is not None and frame[0] >= action_at[0] - 2 and \
                (post_input_accepts == [] or frame[0] <= post_input_accepts[0] + 2)
            if active:
                state = actionmenuspill.snapshot(pb)
                if not pb.memory[0xFF40] & 0x80:
                    lcd_off.append(frame[0])
                image = pb.screen.image.copy()
                if actionmenuspill.white_frame(image):
                    white.append(frame[0])
                if floor_parent[0] is not None and \
                        (post_input_at[0] is None or frame[0] < post_input_at[0]):
                    for row in actionmenuspill.VISIBLE_BG_ROWS:
                        for col in range(20):
                            if (row, col) in FOOTPRINT:
                                continue
                            if actionmenuspill.resolved(state, 'bg', row, col) != \
                                    actionmenuspill.resolved(
                                        floor_parent[0], 'bg', row, col):
                                outside_diffs.append((frame[0], row, col))
                                break
                        if outside_diffs and outside_diffs[-1][0] == frame[0]:
                            break
                    if not actionmenuspill.visible_layer_equal(
                            state, floor_parent[0], 'window',
                            actionmenuspill.VISIBLE_WINDOW_ROWS):
                        window_diffs.append(frame[0])
                if (cancel_at[0] is not None and frame[0] >= cancel_at[0] and
                        floor_parent[0] is not None and pre_cancel[0] is not None and
                        (post_input_at[0] is None or frame[0] < post_input_at[0])):
                    for row, col in FOOTPRINT:
                        actual = actionmenuspill.resolved(state, 'bg', row, col)
                        allowed = {
                            actionmenuspill.resolved(
                                floor_parent[0], 'bg', row, col),
                            actionmenuspill.resolved(pre_cancel[0], 'bg', row, col),
                        }
                        if actual not in allowed:
                            inside_bad.append((frame[0], row, col, actual[0]))
                            break
                    parent = all(actionmenuspill.resolved(state, 'bg', row, col) ==
                                 actionmenuspill.resolved(
                                     floor_parent[0], 'bg', row, col)
                                 for row, col in FOOTPRINT)
                    action = all(actionmenuspill.resolved(state, 'bg', row, col) ==
                                 actionmenuspill.resolved(
                                     pre_cancel[0], 'bg', row, col)
                                 for row, col in FOOTPRINT)
                    if not parent and not action:
                        mixed_footprints.append(frame[0])
                if png_dir and (frame[0] == action_at[0] or
                                (cancel_at[0] is not None and
                                 cancel_at[0] - 2 <= frame[0] <= cancel_at[0] + 12)):
                    image.save(os.path.join(png_dir, 'floor_action_f%04d.png' % frame[0]))

        final_selector = pb.memory[0xC6AC]
        pb.stop(save=False)

    if tuple(selector for _at, selector in page_completes) != (0, 5, 10, 15):
        problems.append('carried page completions are %s, expected 0/5/10/15' %
                        [selector for _at, selector in page_completes])
    expected_staged = [bytes((0,)) + bytes(menuspill.encode(word)) for word in WORDS]
    if [event[3] for event in action_rows] != expected_staged:
        problems.append('Floor Action staged rows are %s, expected %s' %
                        ([event[3].hex(' ') for event in action_rows],
                         [row.hex(' ') for row in expected_staged]))
    if [event[1] for event in action_rows] != list(range(len(WORDS))):
        problems.append('Floor Action row order is %s, expected 0..3' %
                        [event[1] for event in action_rows])
    for row in range(len(WORDS)):
        record = action_records.get(row)
        expected = (menuvwf.ACTION_POOL_BASE + 4 * row, 4, 1)
        actual = None if record is None else record[1:]
        if actual != expected:
            problems.append('Floor Action row %d allocation is %s, expected %s' %
                            (row, actual, expected))

    if floor_at[0] is None or floor_parent[0] is None:
        problems.append('settled standing-item Floor parent was not captured')
    if len(gate_calls) != 1 or gate_collisions:
        problems.append('Action gate/collision calls are %s/%s, expected 1/0' %
                        (gate_calls, gate_collisions))
    if len(pop_calls) != 1 or pop_calls[0][1] != 0x5689:
        problems.append('B-pop calls are %s, expected one with HL=$5689' %
                        (pop_calls,))
    if len(restores) != 1:
        problems.append('regional Floor restores are %d, expected one' % len(restores))
    else:
        _restore_at, restore_ly, restored_state = restores[0]
        if not 0x90 <= restore_ly <= 0x99:
            problems.append('regional Floor restore ended at LY=$%02X, outside VBlank' %
                            restore_ly)
        if floor_parent[0] is not None:
            unrestored = [(row, col) for row, col in FOOTPRINT
                          if actionmenuspill.resolved(restored_state, 'bg', row, col) !=
                          actionmenuspill.resolved(
                              floor_parent[0], 'bg', row, col)]
            if unrestored:
                problems.append('regional Floor restore left parent differences at %s' %
                                unrestored[:8])
    if restore_failures:
        problems.append('Floor Action B reached fallback at %s' % restore_failures)
    if len(handler_returns) != 1:
        problems.append('B-handler returns are %s, expected one' % handler_returns)
    elif handler_returns[0] - cancel_at[0] > 3:
        problems.append('B handler held input for %d frames after cancel' %
                        (handler_returns[0] - cancel_at[0]))
    if len(post_input_accepts) != 1 or post_input_at[0] is None or \
            post_input_accepts[0] - post_input_at[0] > 2:
        problems.append('first post-B Left was not accepted promptly: press=%s result=%s' %
                        (post_input_at[0], post_input_accepts))
    if replay_dispatches or rebuild_rows:
        problems.append('B dismissal replayed a screen/Item row before input: %s / %s' %
                        (replay_dispatches, rebuild_rows))
    if floor_parent[0] is not None and fast_return[0] is not None:
        if fast_return[0]['bg'] != floor_parent[0]['bg']:
            problems.append('fast-return BG map differs from settled Floor parent')
        if not actionmenuspill.visible_layer_equal(
                fast_return[0], floor_parent[0], 'bg', actionmenuspill.VISIBLE_BG_ROWS):
            problems.append('fast-return Floor pixels differ from settled parent')
        if not actionmenuspill.visible_layer_equal(
                fast_return[0], floor_parent[0], 'window',
                actionmenuspill.VISIBLE_WINDOW_ROWS):
            problems.append('fast-return Window differs from settled parent')
    else:
        problems.append('fast-return Floor snapshot is missing')
    expected_machine = {
        'stack': (1, 0, 1, 2),
        'descriptor': (0, 0, 1, 4, 0x50, 0x5C, 0x43),
        'menu': (1, 0, 0, 0, 0x82, 0, 18, 0xFF, 1),
        'transaction': (4, 1, 0, 0, 1),
    }
    if fast_machine[0] != expected_machine:
        problems.append('fast-return Floor machine state is %s, expected %s' %
                        (fast_machine[0], expected_machine))
    if lcd_off:
        problems.append('Floor Action lifecycle disabled LCD at %s' % lcd_off[:12])
    if white:
        problems.append('Floor Action lifecycle produced white frames at %s' % white[:12])
    if outside_diffs:
        problems.append('Floor Action changed pixels outside box 6 at %s' %
                        outside_diffs[:8])
    if window_diffs:
        problems.append('Floor Action changed the persistent Window at %s' %
                        window_diffs[:8])
    if inside_bad:
        problems.append('Floor Action published an unowned box-6 cell at %s' %
                        inside_bad[:8])
    if mixed_footprints:
        problems.append('Floor Action exposed a mixed Action/parent footprint at %s' %
                        mixed_footprints[:12])
    if final_selector != 15:
        problems.append('post-B Left ended at selector $%02X, expected $0F' %
                        final_selector)

    print('flooractionspill: pages %s; Floor f%s, Action f%s, B f%s; restore %s, '
          'return %s, input %s; LCD-off %d, white %d; %d problem(s)' %
          (' '.join('f%d:$%02X' % event for event in page_completes),
           floor_at[0], action_at[0], cancel_at[0],
           ('missing' if not restores else 'LY=$%02X' % restores[0][1]),
           ('missing' if not handler_returns else '+%d frames' %
            (handler_returns[0] - cancel_at[0])),
           ('missing' if not post_input_accepts else '+%d frames' %
            (post_input_accepts[0] - post_input_at[0])),
           len(lcd_off), len(white), len(problems)))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('flooractionspill: %d problem(s)' % len(problems))
    print('flooractionspill: standing-item Floor Action B restores its exact parent and '
          'returns directly to responsive screen-1 input')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png-dir')
    parser.add_argument('--frames', type=int, default=FRAMES)
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('flooractionspill: missing ' + path)
    run(args.rom, args.ram, args.png_dir, args.frames)


if __name__ == '__main__':
    main()
