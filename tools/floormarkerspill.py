#!/usr/bin/env python3
"""Exact runtime regression for all English town/dungeon arrival-card forms.

The real ``saves/town.state`` route reaches Forest 1F. That proves the native selector and
floor byte still feed the replacement and gives a pixel-exact check of Joey's second
approved mock-up. Every native selector/floor pairing is replayed, then isolated runs
substitute every floor value 1-50 while rotating across the seven dungeon selectors. This
exercises all eleven bases, all fifty live number fields, the three visible tile rows and
the extra blank guard row through the game's actual VBlank queue. A separate raster
invariant requires number/name top alignment and balanced outer ink margins.

usage: floormarkerspill.py ROM [--state FILE] [--png FILE]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import dotfont                                                    # noqa: E402
import markers                                                    # noqa: E402
from gbrun import _import_pyboy, PRESS_FRAMES                     # noqa: E402


CARD_ENTRY = (31, 0x6134)
CARD_AT = 875
STEP = 6
OUT_OF_HOUSE = 40
WEST = 190

# Forest 1F is the unmodified real route. First cover the native floor/selector table,
# including numberless Dragon's Maw and Moon Exit; 1-50 then rotate over every selector
# so all shared live fields still reach the actual uploader.
CASES = tuple(dict.fromkeys(
    ((None, None),) + markers.ACTIVE_CARD_CASES + tuple(
        (1 + (number - 1) % 7, number)
        for number in range(1, markers.MAX_FLOOR + 1))))


def _schedule():
    out = {}
    frame = 0
    for _ in range(OUT_OF_HOUSE):
        out.setdefault(frame, []).append('down')
        frame += STEP
    for index in range(WEST):
        out.setdefault(frame, []).append('left')
        frame += STEP
        if index % 4 == 3:
            out.setdefault(frame, []).append('a')
            frame += 8
    return out


def _run_case(PyBoy, rom, state, force_selector, force_number, font, png=None):
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(state, 'rb') as src:
        pb.load_state(src)

    frame = [0]
    observed = []

    def at_card(_context):
        de = (pb.register_file.D << 8) | pb.register_file.E
        selector = (pb.memory[de + 2] & 0x0E) >> 1
        number = pb.memory[de + 1]
        observed.append((frame[0], selector, number))
        if force_selector is not None:
            pb.memory[de + 2] = force_selector << 1
            pb.memory[de + 1] = force_number

    pb.hook_register(*CARD_ENTRY, at_card, None)
    schedule = _schedule()
    for current in range(CARD_AT + 1):
        frame[0] = current
        for button in schedule.get(current, ()):
            pb.button(button, PRESS_FRAMES)
        pb.tick()

    if force_selector is None:
        selector, number = observed[-1][1:] if observed else (-1, -1)
    else:
        selector, number = force_selector, force_number
    actual = bytes(pb.memory[0x8800:0x8C00])
    upper = bytes(pb.memory[0x9900:0x9914])
    lower = bytes(pb.memory[0x9920:0x9934])
    third = bytes(pb.memory[0x9940:0x9954])
    blank = bytes(pb.memory[0x9960:0x9974])
    if png:
        pb.screen.image.save(png)
    pb.stop(save=False)

    expected = markers.render_card(font, selector, number) \
        if 0 <= selector < len(markers.LABELS) else b''
    want_upper = bytes(range(0x80, 0xA8, 2))
    want_lower = bytes(range(0x81, 0xA8, 2))
    want_third = bytes(range(markers.THIRD_ROW_TILE,
                             markers.THIRD_ROW_TILE + 20))
    want_blank = bytes((markers.BLANK_ROW_TILE,)) * 20
    problems = []
    if len(observed) != 1:
        problems.append('observed %d card entries, expected one' % len(observed))
    if force_selector is None and (selector, number) != (1, 1):
        problems.append('real route selected (%d, %d), expected Forest 1F' %
                        (selector, number))
    if actual != expected:
        problems.append('%d/%d VRAM byte(s) differ' %
                        (sum(a != b for a, b in zip(actual, expected)), len(expected)))
    if upper != want_upper or lower != want_lower or third != want_third \
            or blank != want_blank:
        problems.append('three-row tilemap or blank guard differs')
    return selector, number, problems


def run(rom, state, png=None):
    PyBoy = _import_pyboy()
    font = dotfont.load_approved()
    results = []
    for index, (selector, number) in enumerate(CASES):
        shot = png if index == 0 else None
        results.append(_run_case(PyBoy, rom, state, selector, number, font, shot))

    forms = {(selector, bool(number)) for selector, number, _problems in results}
    missing = set(markers.VARIANTS) - forms
    numbers = {number for _selector, number, _problems in results if number}
    problems = [(selector, number, problem)
                for selector, number, case_problems in results
                for problem in case_problems]

    aligned = 0
    for selector, number in markers.ACTIVE_CARD_CASES:
        metrics = markers.card_metrics(selector, number)
        left, _top, right, _bottom = metrics['bounds']
        if number:
            if metrics['number_top'] != metrics['name_top']:
                problems.append((selector, number,
                                 'number top %s differs from name top %s' %
                                 (metrics['number_top'], metrics['name_top'])))
            else:
                aligned += 1
        margin_delta = abs(left - (markers.STRIP_WIDTH - 1 - right))
        if margin_delta > 4:
            problems.append((selector, number,
                             'ink bounds x=%d..%d have %dpx outer-margin imbalance' %
                             (left, right, margin_delta)))
    if missing:
        problems.append((-1, -1, 'stored form(s) untested: %s' % sorted(missing)))
    if numbers != set(range(1, markers.MAX_FLOOR + 1)):
        problems.append((-1, -1, 'live number coverage is %s' % sorted(numbers)))

    exact = len(results) - len({(selector, number) for selector, number, _ in problems
                                if selector >= 0})
    print('floormarkerspill: real route Forest 1F; %d/%d card cases exact; '
          '%d/%d active numbered cards top-aligned/centered; '
          '%d/%d live number fields exercised; %d problem(s)' %
          (exact, len(results), aligned,
           sum(len(floors) for floors in markers.ACTIVE_NUMBERED_FLOORS.values()),
           len(numbers), markers.MAX_FLOOR, len(problems)))
    for selector, number, problem in problems:
        prefix = '%s %s: ' % (markers.LABELS[selector], number) if selector >= 0 else ''
        print('  ' + prefix + problem)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--state', default=os.path.join(ROOT, 'saves/town.state'))
    parser.add_argument('--png')
    args = parser.parse_args()
    if not os.path.exists(args.rom):
        raise SystemExit('floormarkerspill: missing %s' % args.rom)
    if not os.path.exists(args.state):
        raise SystemExit('floormarkerspill: missing %s' % args.state)
    raise SystemExit(run(args.rom, args.state, args.png))


if __name__ == '__main__':
    main()
