#!/usr/bin/env python3
"""Regress Name entry/return ownership for the seven-row unidentified-Pot picker.

The tracked Log-3 fixture naturally stands on an unidentified Pot.  It exercises the
direct Floor picker and, independently, the Items-appended Floor picker without Lua or
memory injection.  Both Name exits must stay regional; the appended route then dismisses
the rebuilt seven-row Action box and must fast-pop directly to screen 1 without a second
screen-0 replay.
"""
import argparse
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from gbrun import _import_pyboy                         # noqa: E402
import statusvwf                                        # noqa: E402
import unidentifiednamespill as namespill              # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log3_unidentified_pot_crash.srm')
DIRECT_NAME = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 380: 'down', 460: 'down', 540: 'a', 700: 'a',
    2600: 'b', 2700: 'down', 2800: 'a',
    2880: 'down', 2940: 'down', 3000: 'down',
    3060: 'down', 3120: 'down', 3240: 'a',
}
DIRECT_EMPTY_CANCEL = dict(DIRECT_NAME)
DIRECT_EMPTY_CANCEL[3600] = ('b', 5)
DIRECT_REPEAT_CANCEL = dict(DIRECT_EMPTY_CANCEL)
DIRECT_REPEAT_CANCEL.update({4200: 'a', 4600: ('b', 5)})
# Name is row five and Info row six in this seven-row direct-Floor Action picker.
# Exercise the history which previously left $C1B4 stale: visit Info, return to the
# retained Action picker, then enter and cancel Name.
DIRECT_INFO_THEN_NAME = dict(DIRECT_NAME)
DIRECT_INFO_THEN_NAME.update({3240: 'down', 3320: 'a', 3800: 'b',
                              4200: 'up', 4280: 'a', 4700: ('b', 5)})
DIRECT_END = dict(DIRECT_NAME)
DIRECT_END.update({3500: ('a', 5), 3620: ('start', 5), 3720: ('a', 5)})

APPENDED_NAME_ACTION_POP = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 380: 'down', 460: 'down', 540: 'a', 700: 'a',
    3000: 'b', 3400: 'a', 3800: 'right',
    4100: 'a',
    4300: 'down', 4380: 'down', 4460: 'down',
    4540: 'down', 4620: 'down', 4800: 'a',
    5200: ('b', 5),
    5700: ('b', 5),
}


def route_problems(run, label, expected_return, expected_end, expected_cancel,
                   final_screen, final_stack, expected_entries=1):
    problems = []
    screens = [screen for _frame, screen in run['dispatches']]
    try:
        name_at = screens.index(9)
    except ValueError:
        return [label + ' never dispatched Name screen 9']
    got = tuple(screens[name_at:name_at + len(expected_return)])
    if got != expected_return:
        problems.append('%s return dispatches are %s, expected %s' %
                        (label, got, expected_return))
    if len(run['end_calls']) != expected_end:
        problems.append('%s reached End %d times, expected %d' %
                        (label, len(run['end_calls']), expected_end))
    cancels = [entry for entry in run['native_cancel_calls']
               if entry['frame'] >= run['dispatches'][name_at][0]]
    if len(cancels) != expected_cancel:
        problems.append('%s reached empty-name cancel %d times, expected %d' %
                        (label, len(cancels), expected_cancel))
    if run['native_name_restores']:
        problems.append('%s used %d native whole-screen Name restores' %
                        (label, len(run['native_name_restores'])))
    starts = run['regional_name_starts']
    fonts = run['regional_name_fonts']
    entry_blanks = []
    if len(starts) == expected_entries and len(fonts) == expected_entries:
        for start, font in zip(starts, fonts):
            lo = start[0]['frame']
            hi = font[0]['frame']
            entry_blanks.extend(
                entry for entry in run['regional_name_blanks']
                if lo <= entry[0]['frame'] <= hi)
    counts = (len(starts), len(entry_blanks), len(fonts))
    expected_counts = (expected_entries,) * 3
    if counts != expected_counts:
        problems.append('%s regional Name entry start/blank/font counts are %s' %
                        (label, counts))
    if run['status_explicit_blanks']:
        problems.append('%s reached Status LCD-off at %s' %
                        (label, run['status_explicit_blanks']))
    lcd_off = [frame for frame, lcdc, _white in run['transition_samples']
               if not lcdc & 0x80]
    uniform = [frame for frame, _lcdc, white in run['transition_samples'] if white]
    if lcd_off:
        problems.append('%s produced LCD-off frames at %s' %
                        (label, ' '.join('f%d' % frame for frame in lcd_off[:12])))
    if uniform:
        problems.append('%s produced uniform frames at %s' %
                        (label, ' '.join('f%d' % frame for frame in uniform[:12])))
    if run['screen'] != final_screen or run['stack'] != final_stack:
        problems.append('%s settled on screen/stack %d/%s, expected %d/%s' %
                        (label, run['screen'], run['stack'], final_screen, final_stack))
    if not run['lcdc'] & 0x80:
        problems.append('%s ended with LCD disabled' % label)
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('unidentifiedpotnamespill: missing %s' % path)

    PyBoy = _import_pyboy()
    labels = statusvwf.runtime_labels()
    direct_cancel = namespill.snapshot(
        PyBoy, args.rom, DIRECT_EMPTY_CANCEL, 4100, args.ram,
        status_runtime=labels, transition_from=3100)
    direct_end = namespill.snapshot(
        PyBoy, args.rom, DIRECT_END, 4200, args.ram,
        status_runtime=labels, transition_from=3100)
    direct_repeat = namespill.snapshot(
        PyBoy, args.rom, DIRECT_REPEAT_CANCEL, 5100, args.ram,
        status_runtime=labels, transition_from=3100)
    direct_info_name = namespill.snapshot(
        PyBoy, args.rom, DIRECT_INFO_THEN_NAME, 5200, args.ram,
        status_runtime=labels, transition_from=3100)
    appended = namespill.snapshot(
        PyBoy, args.rom, APPENDED_NAME_ACTION_POP, 6100, args.ram,
        status_runtime=labels, transition_from=4650)

    problems = []
    problems.extend(route_problems(
        direct_cancel, 'direct Floor Name empty-B', (9, 0, 7), 0, 1,
        final_screen=7, final_stack=(0, 7)))
    problems.extend(route_problems(
        direct_end, 'direct Floor Name End', (9, 0, 7), 1, 1,
        final_screen=7, final_stack=(0, 7)))
    problems.extend(route_problems(
        direct_repeat, 'direct Floor Name empty-B twice',
        (9, 0, 7, 9, 0, 7), 0, 2,
        final_screen=7, final_stack=(0, 7), expected_entries=2))
    problems.extend(route_problems(
        direct_info_name, 'direct Floor Info then Name empty-B',
        (9, 0, 7), 0, 1,
        final_screen=7, final_stack=(0, 7)))
    info_name_screens = tuple(screen for _frame, screen
                              in direct_info_name['dispatches'])
    if (4, 0, 7, 9, 0, 7) not in tuple(
            info_name_screens[index:index + 6]
            for index in range(max(0, len(info_name_screens) - 5))):
        problems.append('direct Floor Info-then-Name dispatch history is %s' %
                        (info_name_screens,))
    problems.extend(route_problems(
        appended, 'Items-appended Floor Name then Action B', (9, 0, 1, 2), 0, 1,
        final_screen=1, final_stack=(0, 1)))

    print('unidentifiedpotnamespill: direct B/End/repeat/Info-first Name returns + '
          'appended Name/Action-B '
          'pop; %d problem(s)' % len(problems))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('unidentifiedpotnamespill: failed')


if __name__ == '__main__':
    main()
