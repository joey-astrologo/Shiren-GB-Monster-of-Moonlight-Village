#!/usr/bin/env python3
"""Replay Joey's unidentified Hyakki Shield and prove both name paths stay VWF.

``saves/shiren_en_log_1_shield_VWF.srm`` has the exact object observed in game.  Its
canonical record is an unidentified Hyakki Shield whose hidden +3 is revealed only when
equipped.  Before that, the native formatter deliberately appends two `$88` stars.  The
Japanese ROM was independently replayed with the same object record and renders the same
two marks (`ヒャッキのたて★★`), so they are content rather than padding to discard.

This route boots Log 1, opens Items, then selects Info.  It requires:

* the real item-list row to stage ``00 00 Hyakki Shield 88 88 FF``, allocate a two-raw-cell
  proportional record, and match the installed English/native-star planes exactly;
* the real item-information title to stage ``7D Hyakki Shield 7D FF``, allocate a zero-raw
  proportional record, and match the approved hyphen-normalized planes exactly.
* Action open/cursor navigation, Action -> Info, Info -> Items, and Action cancel ->
  Items to keep the LCD enabled and expose only complete old/new rendered tile cells.
  Native map publication may replace different cells of one 20-cell row in successive
  frames; individual cells may never contain a blended third raster.

Exit 1 if the save changes, either row falls back to fixed width, or any visible plane
differs. This fixture hides only the equipment modifier, not the item's identity, so its
body correctly remains the ordinary translated Hyakki Shield description. The distinct
identity-hidden branch shared by appearance names is exercised by ``unidentifiedhelp.py``.
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
from floorinfospill import row_backtracks, visual_rows  # noqa: E402


BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a',
    2620: 'b', 2720: 'a',       # Menu -> Items
    2820: 'a',                  # open the selected item's action box
    2920: 'down', 3020: 'down', 3120: 'down', 3220: 'a',  # Info
    3400: 'b',                  # Info -> Items
    3520: 'a', 3600: 'b',      # Action open, then cancel -> Items
}
TRANSITIONS = (
    ('items-to-action', 2820),
    ('action-cursor-1', 2920),
    ('action-cursor-2', 3020),
    ('action-cursor-3', 3120),
    ('action-to-info', 3220),
    ('info-to-items', 3400),
    ('items-to-action-again', 3520),
    ('action-cancel-to-items', 3600),
)
ITEM_SHAPE = (0, 3, 5, 18, 0x02)
INFO_SHAPE = (0, 3, 5, 18, 0x00)
NAME = tuple(menuspill.encode('Hyakki Shield'))
LIST_CODES = NAME + (0x88, 0x88)
INFO_CODES = (0x7D,) + NAME + (0x7D,)


def visual_tiles(image):
    """Exact 8x8 framebuffer cells in tilemap order."""
    rgb = image.convert('RGB')
    return tuple(rgb.crop((column * 8, row * 8,
                           column * 8 + 8, row * 8 + 8)).tobytes()
                 for row in range(18) for column in range(20))


def tile_states(image, old_tiles, new_tiles):
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


def compact_tile_rows(states):
    """Summarize 20 cell states per row; M is an exact old/new cell mixture."""
    rows = []
    for row in range(18):
        active = set(states[row * 20:(row + 1) * 20]) - {'='}
        if not active:
            rows.append('=')
        elif 'X' in active:
            rows.append('X')
        elif active == {'O'}:
            rows.append('O')
        elif active == {'N'}:
            rows.append('N')
        else:
            rows.append('M')
    return ''.join(rows)


def staged_row(pb, source, limit=32):
    row = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            return tuple(row)
        row.append(value)
    return tuple(row)


def exact_visible(pb, profile, event, codes, raw, label, problems,
                  allowed_runs=None):
    if event is None:
        problems.append('%s row never reached the proportional renderer' % label)
        return False
    _at, key, _source, staged = event
    want_staged = ((0, 0) + tuple(codes) if raw == 2 else tuple(codes))
    if staged != want_staged:
        problems.append('%s staged %s, expected %s'
                        % (label, ' '.join('$%02X' % c for c in staged),
                           ' '.join('$%02X' % c for c in want_staged)))
        return False
    matching = [record for record in menuspill.records(pb, profile)
                if record[0] == key and record[3] == raw]
    if not matching:
        problems.append('%s fell back to fixed width (no raw=%d allocator record)'
                        % (label, raw))
        return False
    if not menuspill.visible_row_matches(
            pb, profile, key, list(codes), raw=raw, allowed_runs=allowed_runs):
        problems.append('%s visible planes do not match proportional composition' % label)
        return False
    return True


def run(rom_path, ram_path, png=None, frames=3740):
    profile = menuspill.renderer_profile(rom_path)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('unidentifiedspill: requires the proportional renderer')
    PyBoy = _import_pyboy()
    problems = []
    with tempfile.TemporaryDirectory(prefix='unidentifiedspill-') as tmp:
        run_rom = os.path.join(tmp, 'unidentified.gb')
        shutil.copyfile(rom_path, run_rom)
        shutil.copyfile(ram_path, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)
        frame = [0]
        dispatches = []
        events = {'list': None, 'info': None}
        checks = {'list': False, 'info': False}
        before = {}
        samples = {name: [] for name, _at in TRANSITIONS}
        lcd_off = {name: [] for name, _at in TRANSITIONS}
        state_traces = {}

        def dispatch(_ctx=None):
            dispatches.append((frame[0], pb.register_file.A))

        def far_entry(_ctx=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if pb.register_file.D != 0 or shape not in (ITEM_SHAPE, INFO_SHAPE):
                return
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            row = staged_row(pb, source)
            if shape == ITEM_SHAPE and row[2:] == LIST_CODES:
                events['list'] = (frame[0], pb.register_file.HL, source, row)
            elif shape == INFO_SHAPE and row == INFO_CODES:
                events['info'] = (frame[0], pb.register_file.HL, source, row)

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)
        for current in range(frames):
            frame[0] = current
            for name, at in TRANSITIONS:
                if current == at:
                    before[name] = pb.screen.image.copy()
            button = BOOT.get(current)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            for name, at in TRANSITIONS:
                if at <= current <= at + 70:
                    samples[name].append((current, pb.screen.image.copy()))
                    if not pb.memory[0xFF40] & 0x80:
                        lcd_off[name].append(current)
            if current == 2780:
                checks['list'] = exact_visible(
                    pb, profile, events['list'], LIST_CODES, 2, 'unidentified list', problems)
                if png:
                    stem, ext = os.path.splitext(png)
                    pb.screen.image.save(stem + '_list' + (ext or '.png'))
            if current == 3340:
                checks['info'] = exact_visible(
                    pb, profile, events['info'], INFO_CODES, 0, 'item Info title', problems,
                    allowed_runs=menuspill.INFO_LOW_RUN)
                if png:
                    stem, ext = os.path.splitext(png)
                    pb.screen.image.save(stem + '_info' + (ext or '.png'))
        pb.stop(save=False)

    for name, _at in TRANSITIONS:
        transition = samples[name]
        if name not in before or not transition:
            problems.append('%s has no rendered-frame samples' % name)
            continue
        old_image = before[name]
        new_image = transition[-1][1]
        old = visual_rows(old_image)
        new = visual_rows(new_image)
        old_tiles = visual_tiles(old_image)
        new_tiles = visual_tiles(new_image)
        if old == new:
            problems.append('%s produced no rendered change' % name)
        observations = []
        cell_observations = []
        for at, image in transition:
            cells = tile_states(image, old_tiles, new_tiles)
            states = compact_tile_rows(cells)
            if not observations or observations[-1][1] != states:
                observations.append((at, states))
            if not cell_observations or cell_observations[-1][1] != cells:
                cell_observations.append((at, cells))
        state_traces[name] = observations
        first_new = next((i for i, (_frame, states) in enumerate(cell_observations)
                          if all(state in '=N' for state in states)), None)
        if first_new is None:
            problems.append('%s never reaches its settled tile cells' % name)
        bad = [(at, tuple((cell // 20, cell % 20)
                          for cell, state in enumerate(states) if state == 'X'))
               for at, states in cell_observations if 'X' in states]
        if bad:
            problems.append('%s exposes blended/incomplete tile cell(s) %s'
                            % (name, ' '.join(
                                'f%d:%s' % (at, ','.join('r%d/c%d' % cell
                                                         for cell in cells[:8]))
                                for at, cells in bad[:12])))
        backtracks = row_backtracks(cell_observations)
        if backtracks:
            problems.append('%s returns published cell(s) to old pixels %s'
                            % (name, ' '.join('f%d:r%d/c%d' %
                                              (at, cell // 20, cell % 20)
                                              for at, cell in backtracks[:12])))
        if lcd_off[name]:
            problems.append('%s disables the LCD at %s'
                            % (name, ' '.join('f%d' % at for at in lcd_off[name][:12])))

    if not any(screen == 1 for _at, screen in dispatches):
        problems.append('real route never dispatched the Items screen')
    if not any(screen == 4 for _at, screen in dispatches):
        problems.append('real route never dispatched the Info screen')
    print('unidentifiedspill: dispatches %s; list=%s info=%s; %d problem(s)'
          % (' '.join('f%d:%d' % event for event in dispatches),
             'plane-exact' if checks['list'] else 'FAILED',
             'plane-exact' if checks['info'] else 'FAILED', len(problems)))
    print('unidentifiedspill: rendered row states %s' % ' | '.join(
          '%s %s' % (name, ' '.join('f%d:%s' % event
                                     for event in state_traces.get(name, ())))
          for name, _at in TRANSITIONS))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('unidentifiedspill: failed')
    print('unidentifiedspill: item Action/Info stays LCD-on with complete rows')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=os.path.join(
        ROOT, 'saves/shiren_en_log_1_shield_VWF.srm'))
    parser.add_argument('--png')
    args = parser.parse_args()
    if not os.path.exists(args.ram):
        raise SystemExit('unidentifiedspill: missing RAM fixture: ' + args.ram)
    run(args.rom, args.ram, args.png)


if __name__ == '__main__':
    main()
