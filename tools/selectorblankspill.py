#!/usr/bin/env python3
"""Exercise every Item/Floor candidate selector without whole-LCD blanking.

The native menu engine reuses two list screens for several superficially different
commands:

* screen 11 is the carried-Pot ``Put`` inventory selector;
* screen 14 is shared by direct/appended Floor ``Swap`` and ground-Pot ``Put``.

The callers do not share a return stack.  In particular, the appended Floor page is
``0,1,2,14``, ordinary direct Floor is ``0,20,14``, and direct ground-Pot Floor is
``0,7,14``.  This regression drives all five selector callers with real SRAM fixtures,
pages Right and Left, and (except for the independently scoped carried-Pot return)
presses B.  It also covers screen 6's empty-inventory overlay and dismissal from
both a clean empty save and the real history produced by eating the final item.

All schedules after a menu opens are attached to actual row-completion hooks rather
than guessed redraw delays.  The owned interval must keep LCDC.7 set, never expose a
uniform full-screen frame, never reach either translation fallback blanker, restore the
exact parent stack, clear the regional state byte, and keep the CPU out of rst $38.
"""

import argparse
import os
import shutil
import sys
import tempfile


TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
FIXTURES = os.path.join(ROOT, 'tests', 'fixtures', 'saves')
sys.path.insert(0, TOOLS)

from gbrun import PRESS_FRAMES, _import_pyboy                    # noqa: E402
import lcdblankaudit                                               # noqa: E402
import menuspill                                                   # noqa: E402
import menuvwf                                                     # noqa: E402
import statusvwf                                                   # noqa: E402


DRAGONS_MAW = os.path.join(FIXTURES, 'shiren_en_log_1_dragons_maw.srm')
WOOD_ARROW = os.path.join(FIXTURES, 'shiren_en_item_menu_wood_arrow.srm')
FLOOR_POT = os.path.join(FIXTURES, 'shiren_en_log1_floor_pot_selector.srm')
EMPTY = os.path.join(FIXTURES, 'shiren_en_log3_empty_inventory.srm')

BOOT_LOG1 = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a', 2620: 'b',
}
BOOT_DRAGONS_MAW = dict(BOOT_LOG1)
BOOT_DRAGONS_MAW.update({2720: 'a', 2820: 'right', 2900: 'right',
                         2980: 'right', 3300: 'a'})
BOOT_EMPTY = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 380: 'down', 460: 'down', 540: 'a', 700: 'a',
    2600: 'b', 2700: 'a',
}
BOOT_LIVE_EMPTY = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 380: 'down', 540: 'a', 700: 'a',
    2600: 'b', 2700: 'a',
}

ITEM_SHAPE = (0, 3, 5, 18, 0x02)
ACTION_PREFIXES = ((13, 1), (13, 3))
STATE = 0xC1B3
FRAMES = 4400
POST_RETURN_FRAMES = 240

CASES = {
    'carried-put': {
        'ram': DRAGONS_MAW,
        'schedule': BOOT_DRAGONS_MAW,
        'selector_screen': 11,
        'selector_stack': (0, 1, 2, 11),
        'count': 20,
        'parent_rows': 6,
        'moves': 1,
        # The reported defect is paging inside Put.  Committing Put is a gameplay
        # boundary and its B return is owned by a separate lifecycle.
        'return': None,
    },
    'direct-swap': {
        'ram': WOOD_ARROW,
        'schedule': {**BOOT_LOG1, 2720: 'down', 2820: 'a'},
        'selector_screen': 14,
        'selector_stack': (0, 20, 14),
        'count': 18,
        'parent_rows': 4,
        'moves': 2,
        'return': (20, (0, 20), None),
    },
    'appended-swap': {
        'ram': WOOD_ARROW,
        'schedule': {**BOOT_LOG1,
            2720: 'a', 2920: 'right', 3040: 'right', 3160: 'right',
            3280: 'right', 3480: 'a',
        },
        'selector_screen': 14,
        'selector_stack': (0, 1, 2, 14),
        'count': 18,
        'parent_rows': 4,
        'moves': 2,
        'return': (1, (0, 1), 1),
    },
    'direct-pot-put': {
        'ram': FLOOR_POT,
        'schedule': {**BOOT_LOG1, 2720: 'down', 2820: 'a'},
        'selector_screen': 14,
        'selector_stack': (0, 7, 14),
        'count': 19,
        'parent_rows': 7,
        'moves': 2,
        'return': (7, (0, 7), None),
    },
    'appended-pot-put': {
        'ram': FLOOR_POT,
        'schedule': {**BOOT_LOG1,
            2720: 'a', 2920: 'right', 3040: 'right', 3160: 'right',
            3280: 'right', 3480: 'a',
        },
        'selector_screen': 14,
        'selector_stack': (0, 1, 2, 14),
        'count': 19,
        'parent_rows': 7,
        'moves': 2,
        'return': (1, (0, 1), 1),
    },
    'empty': {
        'ram': EMPTY,
        'schedule': BOOT_EMPTY,
        'empty': True,
    },
    'empty-after-eat': {
        'ram': EMPTY,
        'schedule': BOOT_LIVE_EMPTY,
        'empty': True,
        'live_eat': True,
    },
}


def stack(pb):
    depth = pb.memory[0xC534]
    return tuple(pb.memory[0xC535 + index] for index in range(depth + 1))


def uniform_frame(image):
    return all(low == high for low, high in image.convert('RGB').getextrema())


def run_case(rom, label, case, frames=FRAMES, trace=False):
    profile = menuspill.renderer_profile(rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('selectorblankspill: requires the approved proportional renderer')
    PyBoy = _import_pyboy()
    problems = []
    empty_case = case.get('empty', False)

    with tempfile.TemporaryDirectory(prefix='selectorblankspill-') as tmp:
        work = os.path.join(tmp, label + '.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(case['ram'], work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        schedule = dict(case['schedule'])
        action_complete = [False]
        selector_rows = []
        selector_dispatches = []
        return_dispatches = []
        empty_dispatches = []
        empty_state_pairs = []
        owned = [False]
        finished = [False]
        settle_after = [None]
        lcd_off = []
        uniform = []
        page_fallbacks = []
        region_fallbacks = []
        status_fallbacks = []
        status_prepublications = []
        off_mutations = []
        halts = []
        events = []
        post_return_visual = []

        def event(kind):
            events.append((frame[0], kind, pb.memory[0xC6A3], stack(pb),
                           pb.memory[0xC6AA], pb.memory[0xC6AC],
                           pb.memory[0xC6BB], pb.memory[STATE],
                           pb.memory[0xC1B4], pb.memory[0xC1B7],
                           pb.memory[0xFF40]))

        def dispatch(_ctx=None):
            screen = pb.register_file.A
            if empty_case:
                if screen == 6:
                    owned[0] = True
                    empty_dispatches.append((frame[0], screen, stack(pb),
                                             pb.memory[0xC6AA]))
                    empty_state_pairs.append((pb.memory[0xC1B5],
                                              pb.memory[0xC1B6]))
                    schedule[frame[0] + 160] = 'b'
                    event('empty-entry')
                elif owned[0] and screen == 0:
                    empty_dispatches.append((frame[0], screen, stack(pb),
                                             pb.memory[0xC6AA]))
                    settle_after[0] = frame[0] + POST_RETURN_FRAMES
                    event('empty-return')
                return

            wanted = case['selector_screen']
            if screen == wanted:
                owned[0] = True
                selector_dispatches.append((frame[0], screen, stack(pb),
                                            pb.memory[0xC6AC]))
                event('selector-dispatch')
            expected_return = case['return']
            if (owned[0] and expected_return is not None and
                    screen == expected_return[0]):
                return_dispatches.append((frame[0], screen, stack(pb),
                                          pb.memory[STATE], pb.memory[0xC1B7]))
                settle_after[0] = frame[0] + POST_RETURN_FRAMES
                event('parent-dispatch')

        def row(_ctx=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            screen = pb.memory[0xC6A3]
            if case.get('live_eat'):
                if (screen == 1 and shape == ITEM_SHAPE and
                        pb.register_file.D == 4 and not action_complete[0]):
                    event('last-item-page')
                    schedule[frame[0] + 70] = 'a'
                    return
                if (shape[:2] in ACTION_PREFIXES and screen == 2 and
                        pb.register_file.D == shape[2] - 1 and
                        not action_complete[0]):
                    action_complete[0] = True
                    event('eat-action-complete')
                    schedule[frame[0] + 70] = 'a'
                    schedule[frame[0] + 380] = 'a'
                    schedule[frame[0] + 480] = 'a'
                    schedule[frame[0] + 680] = 'b'
                    schedule[frame[0] + 780] = 'a'
                return
            if (shape[:2] in ACTION_PREFIXES and screen in (2, 7, 20) and
                    pb.register_file.D == shape[2] - 1 and not action_complete[0]):
                action_complete[0] = True
                event('action-complete')
                for index in range(case['moves']):
                    schedule[frame[0] + 50 + 50 * index] = 'down'
                schedule[frame[0] + 80 + 50 * case['moves']] = 'a'
                return
            if (screen != case['selector_screen'] or shape != ITEM_SHAPE or
                    pb.register_file.D != 4):
                return
            selector_rows.append((frame[0], pb.memory[0xC6AC], stack(pb),
                                  pb.memory[0xC6AA], pb.memory[STATE],
                                  pb.memory[0xC1B4]))
            event('selector-complete')
            if len(selector_rows) == 1:
                schedule[frame[0] + 70] = 'right'
            elif len(selector_rows) == 2:
                schedule[frame[0] + 70] = 'left'
            elif len(selector_rows) == 3:
                if case['return'] is None:
                    finished[0] = True
                else:
                    schedule[frame[0] + 70] = 'b'

        def fallback(target):
            def callback(_ctx=None):
                if owned[0] and not finished[0]:
                    target.append(frame[0])
            return callback

        def display_mutation(site):
            def callback(_ctx=None):
                if owned[0] and not finished[0]:
                    writes_off = (site['encoding'] == 'res-[hl]' or
                                  (site['encoding'] in ('ld', 'ldh') and
                                   not pb.register_file.A & 0x80))
                    if writes_off:
                        off_mutations.append(
                            (frame[0], site['target'], site['bank'], site['address'],
                             pb.register_file.A, pb.memory[0xC110],
                             pb.memory[0xFF40]))
            return callback

        def status_prepublication(_ctx=None):
            if owned[0] and not finished[0]:
                status_prepublications.append(frame[0])
                if trace:
                    event('status-prepublish')

        page_labels, region_labels = menuvwf.item_transition_labels()
        pb.hook_register(4, 0x48AA, dispatch, None)
        if not empty_case or case.get('live_eat'):
            pb.hook_register(menuvwf.FAR_BANK, profile['entry'], row, None)
        pb.hook_register(menuvwf.ITEM_PAGE_BANK, page_labels['pbdisable'],
                         fallback(page_fallbacks), None)
        pb.hook_register(menuvwf.ITEM_REGION_BANK, region_labels['irdisable'],
                         fallback(region_fallbacks), None)
        status_labels = statusvwf.runtime_labels()
        pb.hook_register(statusvwf.FAR_BANK, status_labels['statusdisable'],
                         fallback(status_fallbacks), None)
        pb.hook_register(statusvwf.FAR_BANK, status_labels['statusprepublish'],
                         status_prepublication, None)
        # A native route can clear the LCDC shadow and republish it between two sampled
        # video frames.  Hook the complete static mutation census so a same-frame off/on
        # cycle cannot evade the screenshot assertions.
        for site in lcdblankaudit.display_mutators(rom):
            pb.hook_register(site['bank'], site['address'],
                             display_mutation(site), None)

        for frame[0] in range(frames):
            button = schedule.get(frame[0])
            if button:
                if trace:
                    event('press-' + button)
                pb.button(button, PRESS_FRAMES)
            pb.tick()

            if (trace and empty_case and settle_after[0] is not None and
                    frame[0] <= settle_after[0] - POST_RETURN_FRAMES + 60):
                crop = pb.screen.image.convert('RGB').crop((0, 0, 160, 128))
                colors = crop.getcolors(maxcolors=160 * 128) or []
                majority = max((count for count, _color in colors), default=0)
                post_return_visual.append(
                    (frame[0], len(colors), 160 * 128 - majority,
                     sum(1 for address in range(0x9800, 0x9A00)
                         if pb.memory[address])))

            if owned[0] and not finished[0]:
                if not pb.memory[0xFF40] & 0x80:
                    lcd_off.append(frame[0])
                if uniform_frame(pb.screen.image):
                    uniform.append(frame[0])
                if pb.register_file.PC == 0x0038:
                    halts.append(frame[0])

                if empty_case:
                    if (settle_after[0] is not None and frame[0] >= settle_after[0] and
                            len(empty_dispatches) >= 2 and pb.memory[0xC6A3] == 0 and
                            stack(pb) == (0,) and pb.memory[STATE] == 0):
                        finished[0] = True
                elif case['return'] is not None:
                    target_screen, target_stack, target_floor = case['return']
                    if (settle_after[0] is not None and frame[0] >= settle_after[0] and
                            return_dispatches and pb.memory[0xC6A3] == target_screen and
                            stack(pb) == target_stack and pb.memory[STATE] == 0 and
                            (target_floor is None or
                             pb.memory[0xC1B7] == target_floor)):
                        finished[0] = True

        final = {
            'screen': pb.memory[0xC6A3],
            'stack': stack(pb),
            'count': pb.memory[0xC6AA],
            'selector': pb.memory[0xC6AC],
            'rows': pb.memory[0xC6BB],
            'state': pb.memory[STATE],
            'floor': pb.memory[0xC1B7],
            'lcdc': pb.memory[0xFF40],
            'pc': pb.register_file.PC,
        }
        pb.stop(save=False)

    if empty_case:
        if [(screen, call_stack, count) for _at, screen, call_stack, count
                in empty_dispatches] != [(6, (0, 6), 0), (0, (0,), 0)]:
            problems.append('screen-6 lifecycle was %s, expected entry (0,6) and '
                            'Status return (0,) with count zero' % (empty_dispatches,))
        if len(status_prepublications) != 1:
            problems.append('screen-6 dismissal published Status chrome %d times at '
                            '%s, expected exactly once before Status fields'
                            % (len(status_prepublications), status_prepublications))
        expected_pair = (0x20, 0x01) if case.get('live_eat') else (0x00, 0x00)
        if empty_state_pairs != [expected_pair]:
            problems.append('screen-6 entry history pair was %s, expected [%s]'
                            % (empty_state_pairs, expected_pair))
    else:
        expected_dispatch = (case['selector_screen'], case['selector_stack'])
        actual_dispatches = [(screen, call_stack) for _at, screen, call_stack, _selector
                             in selector_dispatches]
        if not actual_dispatches or any(value != expected_dispatch
                                        for value in actual_dispatches[:3]):
            problems.append('selector dispatches were %s, expected screen/stack %s'
                            % (actual_dispatches, expected_dispatch))
        selectors = [value[1] for value in selector_rows]
        if selectors != [0, 5, 0]:
            problems.append('completed selector pages were %s, expected [0, 5, 0]'
                            % selectors)
        for at, selector, call_stack, count, state, saved_rows in selector_rows:
            if call_stack != case['selector_stack']:
                problems.append('f%d page $%02X used stack %s, expected %s'
                                % (at, selector, call_stack,
                                   case['selector_stack']))
            if count != case['count']:
                problems.append('f%d page $%02X count is %d, expected %d'
                                % (at, selector, count, case['count']))
            if state != 0x16:
                problems.append('f%d page $%02X completed outside regional state $16 '
                                '(saw $%02X)' % (at, selector, state))
            if (case['selector_screen'] == 14 and
                    saved_rows != case['parent_rows']):
                problems.append('f%d screen-14 saved parent height %d, expected %d'
                                % (at, saved_rows, case['parent_rows']))
        if case['return'] is not None:
            target_screen, target_stack, target_floor = case['return']
            if not return_dispatches:
                problems.append('B never redispatched expected parent screen %d'
                                % target_screen)
            if (final['screen'], final['stack'], final['state']) != \
                    (target_screen, target_stack, 0):
                problems.append('return settled screen/stack/state %d/%s/$%02X, '
                                'expected %d/%s/$00'
                                % (final['screen'], final['stack'], final['state'],
                                   target_screen, target_stack))
            if target_floor is not None and final['floor'] != target_floor:
                problems.append('appended Floor flag settled at %d, expected %d'
                                % (final['floor'], target_floor))
        elif (final['screen'], final['stack'], final['state']) != \
                (case['selector_screen'], case['selector_stack'], 0):
            problems.append('carried Put paging settled screen/stack/state '
                            '%d/%s/$%02X, expected live screen 11 selector'
                            % (final['screen'], final['stack'], final['state']))

    if not finished[0]:
        problems.append('owned lifecycle did not settle before frame %d' % frames)
    if page_fallbacks or region_fallbacks or status_fallbacks:
        problems.append('whole-map fallback(s) ran: page=%s region=%s status=%s'
                        % (page_fallbacks, region_fallbacks, status_fallbacks))
    if off_mutations:
        problems.append('same-frame LCD/shadow off mutation(s) ran: %s'
                        % (off_mutations,))
    if lcd_off:
        problems.append('LCDC.7 cleared during owned frames %s' % lcd_off[:16])
    if uniform:
        problems.append('uniform full-screen frame(s) appeared at %s' % uniform[:16])
    if halts or final['pc'] == 0x0038:
        problems.append('CPU reached rst $38 at %s (final PC=$%04X)'
                        % (halts[:16], final['pc']))
    if not final['lcdc'] & 0x80:
        problems.append('route ended with LCD disabled (LCDC=$%02X)'
                        % final['lcdc'])

    if trace:
        for values in events:
            print('selectorblankspill: %-18s f%-4d screen=%d stack=%s count=%d '
                  'selector=$%02X rows=%d state=$%02X saved=%d floor=%d LCDC=$%02X'
                  % (values[1], values[0], values[2], values[3], values[4],
                     values[5], values[6], values[7], values[8], values[9],
                     values[10]))
        for values in post_return_visual:
            print('selectorblankspill: post-return f%-4d colors=%d non-bg=%d '
                  'nonzero-map=%d' % values)
    print('selectorblankspill: %-18s pages=%s stack=%s -> %d/%s; '
          'fallbacks %d/%d/%d; prepublish %d; LCD-off %d, uniform %d; %d problem(s)'
          % (label, '-' if empty_case else
             '/'.join(str(value[1] // 5 + 1) for value in selector_rows),
             '-' if empty_case else case.get('selector_stack'),
             final['screen'], final['stack'], len(page_fallbacks),
             len(region_fallbacks), len(status_fallbacks),
             len(status_prepublications), len(lcd_off), len(uniform),
             len(problems)))
    for problem in problems:
        print('  ' + problem)
    return problems


def run(rom, labels, frames=FRAMES, trace=False):
    problems = []
    for label in labels:
        problems.extend('%s: %s' % (label, problem)
                        for problem in run_case(rom, label, CASES[label], frames, trace))
    print('selectorblankspill: %d route(s), %d total problem(s)' %
          (len(labels), len(problems)))
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--case', action='append', choices=tuple(CASES),
                        help='run only this case; may be repeated')
    parser.add_argument('--frames', type=int, default=FRAMES)
    parser.add_argument('--trace', action='store_true')
    args = parser.parse_args()
    labels = args.case or tuple(CASES)
    for path in (args.rom,) + tuple(CASES[label]['ram'] for label in labels):
        if not os.path.isfile(path):
            raise SystemExit('selectorblankspill: missing %s' % path)
    return run(args.rom, labels, args.frames, args.trace)


if __name__ == '__main__':
    raise SystemExit(main())
