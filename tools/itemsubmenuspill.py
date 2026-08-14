#!/usr/bin/env python3
"""Exercise page-history-sensitive Item Action and Info lifecycles.

The ordinary fixtures historically covered only a four-row Action picker opened from
the initial Item-page ownership permutation.  Real menus also have five/six rows, and a
page flip changes which high Item slice is free.  These two routes therefore verify:

* all six Square-Pot Action rows remain proportional, including Name and Info;
* Action -> low Info -> Items after three page flips never repaints resident text;
* Item page right/left -> four-row Action -> both Silver-Arrow Info pages -> Items ->
  Action cancel is safe when the Item-owner permutation differs from initial entry;
* every scoped transition keeps LCDC.7 enabled and exposes complete old/new rows only.
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
import menuspill                                                  # noqa: E402
import menuvwf                                                    # noqa: E402
from floorinfospill import row_backtracks, row_states, visual_rows  # noqa: E402


BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a', 2620: 'b', 2720: 'a',
}
CASES = (
    {
        'label': 'six-row-low',
        'ram': 'shiren_en_log_1_dragons_maw.srm',
        'schedule': {
            2820: 'right', 2880: 'right', 2940: 'right', 3060: 'a',
            3160: 'down', 3220: 'down', 3280: 'down',
            3340: 'down', 3400: 'down', 3480: 'a', 3680: 'b',
        },
        'action_at': 3479,
        'action_rows': 6,
        'transitions': (
            ('items-action', 3060),
            ('action-info', 3480),
            ('info-items', 3680),
        ),
        'frames': 3800,
    },
    {
        'label': 'high-info-history',
        'ram': 'shiren_en_item_menu_wood_arrow.srm',
        'schedule': {
            2820: 'right', 2900: 'left',
            3000: 'down', 3060: 'down', 3120: 'down', 3180: 'down', 3260: 'a',
            3360: 'down', 3420: 'down', 3480: 'down', 3560: 'a',
            3720: 'a', 3900: 'b', 4000: 'a', 4100: 'b',
        },
        'action_at': 3559,
        'action_rows': 4,
        'transitions': (
            ('items-action', 3260),
            ('action-info-1', 3560),
            ('info-1-info-2', 3720),
            ('info-2-items', 3900),
            ('items-action-again', 4000),
            ('action-cancel-items', 4100),
        ),
        'frames': 4220,
    },
)
ACTION_SHAPE_PREFIX = (13, 1)
HIGH_OWNERS = tuple(sorted(menuvwf.ITEM_HIGH_SLICES))
ACTION_RUNS = tuple((base, base + cap)
                    for base, cap in zip(menuvwf.ITEM_ACTION_BASES,
                                         menuvwf.ITEM_ACTION_CAPS))


def staged_row(pb, source, limit=24):
    out = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            return tuple(out)
        out.append(value)
    return tuple(out)


def action_ref(value):
    return any(lo <= value < hi for lo, hi in ACTION_RUNS)


def visual_tiles(image):
    rgb = image.convert('RGB')
    return tuple(rgb.crop((column * 8, row * 8,
                           column * 8 + 8, row * 8 + 8)).tobytes()
                 for row in range(18) for column in range(20))


def exact_cell_states(image, old_tiles, new_tiles):
    states = []
    for got, old, new in zip(visual_tiles(image), old_tiles, new_tiles):
        if got == old == new:
            states.append('=')
        elif got == old:
            states.append('O')
        elif got == new:
            states.append('N')
        else:
            states.append('X')
    return ''.join(states)


def cell_row_summary(states):
    out = []
    for row in range(18):
        active = set(states[row * 20:(row + 1) * 20]) - {'='}
        if not active:
            out.append('=')
        elif 'X' in active:
            out.append('X')
        elif active == {'O'}:
            out.append('O')
        elif active == {'N'}:
            out.append('N')
        else:
            out.append('M')
    return ''.join(out)


def run_case(PyBoy, rom, case, png_dir=None):
    problems = []
    profile = menuspill.renderer_profile(rom)
    schedule = dict(BOOT)
    schedule.update(case['schedule'])
    samples = {label: [] for label, _at in case['transitions']}
    before = {}
    white = {label: [] for label, _at in case['transitions']}
    action_events = []
    action_endpoint = {}

    with tempfile.TemporaryDirectory(prefix='itemsubmenuspill-') as tmp:
        work = os.path.join(tmp, 'item-submenu.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(os.path.join(ROOT, 'saves', case['ram']), work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)
        frame = [0]
        screen = [None]
        dispatches = []

        def dispatch(_ctx=None):
            screen[0] = pb.register_file.A
            dispatches.append((frame[0], screen[0]))

        def far_entry(_ctx=None):
            if pb.register_file.A == 0xFD and pb.register_file.D & 0x80:
                return
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if (screen[0] != 2 or shape[:2] != ACTION_SHAPE_PREFIX or
                    shape[2] != case['action_rows'] or shape[3:] != (5, 2)):
                return
            source = pb.memory[0xC69F] | pb.memory[0xC6A0] << 8
            action_events.append((frame[0], pb.register_file.D, pb.register_file.HL,
                                  source, staged_row(pb, source)))

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)

        for current in range(case['frames']):
            frame[0] = current
            for label, at in case['transitions']:
                if current == at:
                    before[label] = pb.screen.image.copy()
            button = schedule.get(current)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            for label, at in case['transitions']:
                if at <= current <= at + 100:
                    image = pb.screen.image.copy()
                    samples[label].append((current, image))
                    if not pb.memory[0xFF40] & 0x80:
                        white[label].append(current)
                    if png_dir:
                        os.makedirs(png_dir, exist_ok=True)
                        image.save(os.path.join(
                            png_dir, '%s_%s_f%04d.png' %
                            (case['label'], label, current)))
            if current == case['action_at']:
                live_rows = {event[1]: event for event in action_events}
                action_endpoint.update({
                    'records': tuple(menuspill.records(pb, profile)),
                    'state': pb.memory[menuvwf.ITEM_STATE_AT],
                    'image': pb.screen.image.copy(),
                    'exact': {
                        rownum: menuspill.visible_row_matches(
                            pb, profile, event[2], list(event[4][1:]), raw=1,
                            allowed_runs=ACTION_RUNS + profile['runs'])
                        for rownum, event in live_rows.items()
                        if event[4] and event[4][0] == 0
                    },
                })

        final = {
            'state': pb.memory[menuvwf.ITEM_STATE_AT],
            'low': pb.memory[menuvwf.ITEM_LOW_ROW_AT],
            'owners': tuple(pb.memory[address] for address in
                            range(menuvwf.ITEM_ROWS_AT, menuvwf.ITEM_FREE_AT + 1)),
            'refs': tuple((row, col, pb.memory[0x9800 + 32 * row + col])
                          for row in range(18) for col in range(20)
                          if action_ref(pb.memory[0x9800 + 32 * row + col])),
            'records': tuple(record for record in menuspill.records(pb, profile)
                             if any(lo < record[1] + record[2] and
                                    record[1] < hi for lo, hi in ACTION_RUNS)),
        }

        rows = {}
        for event in action_events:
            rows[event[1]] = event
        if sorted(rows) != list(range(case['action_rows'])):
            problems.append('%s Action rows are %s, expected 0-%d' %
                            (case['label'], sorted(rows), case['action_rows'] - 1))
        endpoint_records = action_endpoint.get('records', ())
        for rownum in range(case['action_rows']):
            event = rows.get(rownum)
            if event is None:
                continue
            _at, _rownum, key, _source, staged = event
            if not staged or staged[0] != 0:
                problems.append('%s Action row %d has invalid raw prefix %s' %
                                (case['label'], rownum, staged))
                continue
            base = menuvwf.ITEM_ACTION_BASES[rownum]
            cap = menuvwf.ITEM_ACTION_CAPS[rownum]
            expected = (key, base, cap, 1)
            if expected not in endpoint_records:
                problems.append('%s Action row %d has no record $%04X:$%02X+%d/raw1'
                                % (case['label'], rownum, key, base, cap))
            elif not action_endpoint.get('exact', {}).get(rownum):
                problems.append('%s Action row %d planes are not exact' %
                                (case['label'], rownum))

        pb.stop(save=False)

    traces = {}
    for label, _at in case['transitions']:
        transition = samples[label]
        if label not in before or not transition:
            problems.append('%s %s has no frame samples' % (case['label'], label))
            continue
        old = visual_rows(before[label])
        new = visual_rows(transition[-1][1])
        if old == new:
            problems.append('%s %s produced no rendered change' % (case['label'], label))
            continue
        observations = []
        exact_observations = []
        cell_mode = label == 'action-cancel-items'
        if cell_mode:
            old_tiles = visual_tiles(before[label])
            new_tiles = visual_tiles(transition[-1][1])
        for at, image in transition:
            exact = (exact_cell_states(image, old_tiles, new_tiles)
                     if cell_mode else row_states(image, old, new))
            states = cell_row_summary(exact) if cell_mode else exact
            if not observations or observations[-1][1] != states:
                observations.append((at, states))
            if not exact_observations or exact_observations[-1][1] != exact:
                exact_observations.append((at, exact))
        traces[label] = observations
        bad = [(at, states) for at, states in exact_observations if 'X' in states]
        if bad:
            shown = [(at, cell_row_summary(states) if cell_mode else states)
                     for at, states in bad[:12]]
            problems.append('%s %s exposes incomplete row(s) %s' %
                            (case['label'], label,
                             ' '.join('f%d:%s' % event for event in shown)))
        backtracks = row_backtracks(exact_observations)
        if backtracks:
            rendered = (' '.join('f%d:r%d/c%d' % (at, cell // 20, cell % 20)
                                 for at, cell in backtracks[:12]) if cell_mode else
                        ' '.join('f%d:r%d' % event for event in backtracks[:12]))
            problems.append('%s %s backtracks %s' %
                            (case['label'], label, rendered))
        if white[label]:
            problems.append('%s %s disables LCD at %s' %
                            (case['label'], label,
                             ' '.join('f%d' % at for at in white[label][:12])))

    if action_endpoint.get('state') != menuvwf.ITEM_STATE_ACTION:
        problems.append('%s Action endpoint state is $%02X, expected $%02X' %
                        (case['label'], action_endpoint.get('state', 0),
                         menuvwf.ITEM_STATE_ACTION))
    if final['state'] != menuvwf.ITEM_STATE_SETTLED or final['low'] != 0xFF:
        problems.append('%s final Item state/low is $%02X/$%02X' %
                        (case['label'], final['state'], final['low']))
    if tuple(sorted(final['owners'])) != HIGH_OWNERS:
        problems.append('%s final Item owners are %s' %
                        (case['label'], '/'.join('$%02X' % v for v in final['owners'])))
    if final['refs'] or final['records']:
        problems.append('%s leaves Action refs/records %s / %s' %
                        (case['label'], final['refs'][:8], final['records'][:8]))

    print('itemsubmenuspill: %s Action=%d rows; %s; %d problem(s)' %
          (case['label'], len(rows),
           ' | '.join('%s %s' %
                      (label, ' '.join('f%d:%s' % event
                                       for event in traces.get(label, ())))
                      for label, _at in case['transitions']), len(problems)))
    for problem in problems:
        print('  ' + problem)
    return problems


def run(rom, png_dir=None):
    PyBoy = _import_pyboy()
    problems = []
    for case in CASES:
        problems.extend(run_case(PyBoy, rom, case, png_dir))
    if problems:
        raise SystemExit('itemsubmenuspill: %d problem(s)' % len(problems))
    print('itemsubmenuspill: five/six-row Action and low/high Info returns are clean')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--png-dir')
    args = parser.parse_args()
    for case in CASES:
        path = os.path.join(ROOT, 'saves', case['ram'])
        if not os.path.exists(path):
            raise SystemExit('itemsubmenuspill: missing ' + path)
    run(args.rom, args.png_dir)


if __name__ == '__main__':
    main()
