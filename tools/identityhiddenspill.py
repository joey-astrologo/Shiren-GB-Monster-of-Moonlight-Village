#!/usr/bin/env python3
"""Save-backed unidentified-item names and shared Info-body regression.

``saves/shiren_en_log_1_dragons_maw.srm`` contains four full item pages with genuine
identity-hidden equipment and staves. This route opens two representative objects through
the normal Log-1 menu:

* ``Opal Bracer★★`` proves an appearance name and the native double-star modifier suffix
  coexist with the proportional item-list and Info-title paths;
* ``Gold Staff`` proves a different unidentified category takes the same help branch.

Both must stage and visibly compose ``Effect is unknown.`` through the real item Info
screen. The static ``unidentifiedhelp.py`` proves `$CF7B`'s hidden-identity branch ignores
all topic/unit selectors; this fixture proves two real objects actually set that branch.
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
import itemfix                                                    # noqa: E402
import menuspill                                                  # noqa: E402
import menuvwf                                                    # noqa: E402


BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a', 2620: 'b', 2720: 'a',
}
ITEM_SHAPE = (0, 3, 5, 18, 0x02)
INFO_SHAPE = (0, 3, 5, 18, 0x00)
BODY_CODES = tuple(itemfix.UNIDENTIFIED_HELP_EN)
TITLE_CODES = ((0x7D,) + tuple(itemfix.UNIDENTIFIED_TITLE_EN) + (0x7D,))

CASES = (
    {
        'label': 'Opal Bracer',
        'list': tuple(menuspill.encode('Opal Bracer')),
        'title': TITLE_CODES,
        # Items -> page 2 -> row 3 -> action row 5 (Info). Identity-hidden objects insert
        # Name before Info; row 4 is the name-entry screen and is an explicit wrong-route
        # guard in the dispatch assertion below.
        'presses': ((2820, 'right'), (2920, 'down'), (3000, 'down'),
                    (3100, 'a'), (3200, 'down'), (3280, 'down'),
                    (3360, 'down'), (3440, 'down'), (3520, 'a')),
        'list_check': 3060,
        'info_check': 3660,
        'frames': 3740,
    },
    {
        'label': 'Gold Staff',
        'list': tuple(menuspill.encode('Gold Staff')),
        'title': TITLE_CODES,
        # Items -> page 3 -> row 5 -> action row 5 (Info).
        'presses': ((2820, 'right'), (2920, 'right'),
                    (3020, 'down'), (3100, 'down'), (3180, 'down'), (3260, 'down'),
                    (3340, 'a'), (3440, 'down'), (3520, 'down'),
                    (3600, 'down'), (3680, 'down'), (3760, 'a')),
        'list_check': 3300,
        'info_check': 3900,
        'frames': 3980,
    },
)


def staged_row(pb, source, limit=32):
    row = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            return tuple(row)
        row.append(value)
    return tuple(row)


def exact_visible(pb, profile, event, codes, raw, label, problems):
    if event is None:
        problems.append('%s never reached the proportional renderer' % label)
        return False
    _at, key, _source, staged = event
    expected_staged = tuple(codes)
    if staged[raw:] != expected_staged:
        problems.append('%s staged payload %s, expected %s (raw prefix %s)' %
                        (label, staged[raw:], expected_staged, staged[:raw]))
        return False
    if not any(record[0] == key and record[3] == raw
               for record in menuspill.records(pb, profile)):
        problems.append('%s has no raw=%d proportional allocation' % (label, raw))
        return False
    if not menuspill.visible_row_matches(pb, profile, key, list(codes), raw=raw):
        problems.append('%s visible planes differ from proportional composition' % label)
        return False
    return True


def run_case(rom_path, ram_path, case, png=None):
    profile = menuspill.renderer_profile(rom_path)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('identityhiddenspill: requires the proportional renderer')
    PyBoy = _import_pyboy()
    problems = []
    with tempfile.TemporaryDirectory(prefix='identityhiddenspill-') as tmp:
        run_rom = os.path.join(tmp, 'identityhidden.gb')
        shutil.copyfile(rom_path, run_rom)
        shutil.copyfile(ram_path, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)
        frame = [0]
        dispatches = []
        events = {'list': None, 'title': None, 'body': None}
        checks = {'list': False, 'title': False, 'body': False}
        observed_item_rows = set()
        observed_info_rows = set()
        schedule = dict(BOOT)
        schedule.update(dict(case['presses']))

        def dispatch(_ctx=None):
            dispatches.append((frame[0], pb.register_file.A))

        def far_entry(_ctx=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if shape not in (ITEM_SHAPE, INFO_SHAPE):
                return
            rownum = pb.register_file.D
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            row = staged_row(pb, source)
            if shape == ITEM_SHAPE:
                observed_item_rows.add(row)
            elif shape == INFO_SHAPE:
                observed_info_rows.add((rownum, row))
            if shape == ITEM_SHAPE and row[2:] == case['list']:
                events['list'] = (frame[0], pb.register_file.HL, source, row)
            elif shape == INFO_SHAPE and rownum == 0 and row == case['title']:
                events['title'] = (frame[0], pb.register_file.HL, source, row)
            elif shape == INFO_SHAPE and rownum == 1 and row == BODY_CODES:
                events['body'] = (frame[0], pb.register_file.HL, source, row)

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)
        for current in range(case['frames']):
            frame[0] = current
            button = schedule.get(current)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if current == case['list_check']:
                checks['list'] = exact_visible(
                    pb, profile, events['list'], case['list'], 2,
                    case['label'] + ' list', problems)
            if current == case['info_check']:
                checks['title'] = exact_visible(
                    pb, profile, events['title'], case['title'], 0,
                    case['label'] + ' Info title', problems)
                checks['body'] = exact_visible(
                    pb, profile, events['body'], BODY_CODES, 0,
                    case['label'] + ' Info body', problems)
        if png:
            stem, ext = os.path.splitext(png)
            pb.screen.image.save(stem + '_' + case['label'].lower().replace(' ', '_') +
                                 (ext or '.png'))
        pb.stop(save=False)

    if not any(screen == 4 for _at, screen in dispatches):
        problems.append(case['label'] + ' never dispatched the Info screen')
    if events['list'] is None:
        problems.append(case['label'] + ' observed item rows: ' + ' | '.join(
            ' '.join('$%02X' % code for code in row) for row in sorted(observed_item_rows)))
    if events['title'] is None:
        problems.append(case['label'] + ' observed Info rows: ' + ' | '.join(
            'd%d:%s' % (rownum, ' '.join('$%02X' % code for code in row))
            for rownum, row in sorted(observed_info_rows)))
    print('identityhiddenspill: %s dispatches %s; list=%s title=%s body=%s; %d problem(s)'
          % (case['label'], ' '.join('f%d:%d' % event for event in dispatches),
             'exact' if checks['list'] else 'FAILED',
             'exact' if checks['title'] else 'FAILED',
             'exact' if checks['body'] else 'FAILED', len(problems)))
    for problem in problems:
        print('  ' + problem)
    return problems


def run(rom_path, ram_path, png=None):
    problems = []
    for case in CASES:
        problems.extend(run_case(rom_path, ram_path, case, png))
    if problems:
        raise SystemExit('identityhiddenspill: %d total problem(s)' % len(problems))
    print('identityhiddenspill: real bracer/staff identities share the translated Info '
          'fallback and all tested rows remain VWF')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=os.path.join(
        ROOT, 'saves/shiren_en_log_1_dragons_maw.srm'))
    parser.add_argument('--png')
    args = parser.parse_args()
    if not os.path.exists(args.ram):
        raise SystemExit('identityhiddenspill: missing RAM fixture: ' + args.ram)
    run(args.rom, args.ram, args.png)


if __name__ == '__main__':
    main()
