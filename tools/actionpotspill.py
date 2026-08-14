#!/usr/bin/env python3
"""Verify Back/Todo Pot charge rows through Joey's real Log-2 fixture.

Both pots use `$CC` placeholder records rather than ordinary stored items.  The native
expander turns each charge into `  せなか`; the English build must stage and compose
`Press` three times without leaking kana-shaped fixed cells or VWF pool ownership.  It
then presses B through the real Pot -> Items handler and proves both full-screen
transitions stay LCD-on and expose only complete endpoint rows.
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
import itemfix                                                    # noqa: E402
import menuspill                                                  # noqa: E402
import menuvwf                                                    # noqa: E402
from floorinfospill import row_backtracks, row_states, visual_rows  # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log_2_action_pots.srm')
BASE_ROUTE = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 360: 'down', 420: 'a', 480: 'a',       # Adventure -> Log 2
    2620: 'b', 2740: 'a',                            # Menu -> Items
    3200: 'a', 3400: 'a', 3700: 'b',                 # item -> See -> Items
}
CASES = (
    ('Back Pot', 0x81, 1),
    ('Todo Pot', 0x88, 2),
)
FRAMES = 3900
TRANSITIONS = (
    ('Items-to-Action', 3200),
    ('Action-to-Pot', 3400),
    ('Pot-to-Items', 3700),
)
CONTENT_SHAPE = (0, 3, 3, 18, 2)
CONTENT_BASE = 0xC616
TARGET = bytes(menuspill.encode(itemfix.ACTION_POT_TEXT))
STAGED = bytes((0, 0)) + TARGET
STRIDE = len(STAGED) + 1                         # row plus $FF terminator
HIGH_OWNERS = tuple(sorted(menuvwf.ITEM_HIGH_SLICES))
TRANSIENT_RUN = (menuvwf.ITEM_TRANSIENT_BASE,
                 menuvwf.ITEM_TRANSIENT_BASE + menuvwf.ITEM_ROW_TILES)


def staged_row(pb, source, limit=32):
    out = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            break
        out.append(value)
    return bytes(out)


def low_planes(pb):
    """Native signed-mode pixels restored after the transient `$25-$36` borrow."""
    return bytes(pb.memory[address]
                 for tile in range(menuvwf.ITEM_TRANSIENT_BASE, 0x37)
                 for address in range(0x9000 + tile * 16,
                                      0x9000 + (tile + 1) * 16))


def run_case(PyBoy, rom, ram, label, item_id, downs, png_dir=None, trace=False):
    profile = menuspill.renderer_profile(rom)
    problems = []
    schedule = dict(BASE_ROUTE)
    for step in range(downs):
        schedule[3000 + step * 60] = 'down'

    with tempfile.TemporaryDirectory(prefix='actionpotspill-') as tmp:
        work = os.path.join(tmp, 'action-pot.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        dispatches = []
        selected = []
        rows = []
        pot_finish_calls = []
        before = {}
        samples = {name: [] for name, _at in TRANSITIONS}
        white = {name: [] for name, _at in TRANSITIONS}
        state_trace = []
        selection_before = [None]
        low_planes_before = [None]
        pot_endpoint = {}

        def dispatch(_context=None):
            dispatches.append((frame[0], pb.register_file.A))
            if pb.register_file.A == 12:
                # The selected canonical object is copied to $CF79; its item ID is the
                # second byte. This proves the two nearly identical routes hit different
                # real pot types instead of testing one row twice.
                selected.append(pb.memory[0xCF7A])

        def far_entry(_context=None):
            if frame[0] < 3350:
                return
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if shape != CONTENT_SHAPE:
                return
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            rows.append((frame[0], pb.register_file.D, pb.register_file.HL,
                         source, staged_row(pb, source)))

        def pot_finish(_context=None):
            # This entry is reached at the header rborder before the native post-draw
            # replaces the temporary VWF header cells.  Prove the atomic map boundary
            # really owns the disjoint C7/C8 generation at that instant.
            shadow_refs = tuple(
                (row, col, pb.memory[0xC300 + 32 * row + col])
                for row in range(18) for col in range(20)
                if (menuvwf.ROM_POT_HEADER_BASE <=
                    pb.memory[0xC300 + 32 * row + col] <
                    menuvwf.ROM_POT_HEADER_BASE + menuvwf.ROM_POT_HEADER_CAP))
            header_planes = tuple(
                bytes(pb.memory[menuspill.tile_data_addr(tile):
                                menuspill.tile_data_addr(tile) + 16])
                for tile in range(menuvwf.ROM_POT_HEADER_BASE,
                                  menuvwf.ROM_POT_HEADER_BASE +
                                  menuvwf.ROM_POT_HEADER_CAP))
            pot_finish_calls.append((frame[0],
                                     pb.memory[menuvwf.ITEM_STATE_AT],
                                     pb.memory[0xC0DB], shadow_refs,
                                     header_planes))

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)
        with open(rom, 'rb') as source:
            rom_data = source.read()
        pot_finish_ix = (menuvwf.ITEM_POT_FINISH_BANK * menuvwf.BANKSZ +
                         menuvwf.ITEM_POT_FINISH_INDEX - 1)
        pot_finish_entry = (rom_data[pot_finish_ix] |
                            (rom_data[pot_finish_ix + 1] << 8))
        pb.hook_register(menuvwf.ITEM_POT_FINISH_BANK, pot_finish_entry,
                         pot_finish, None)
        for current in range(FRAMES):
            frame[0] = current
            for name, at in TRANSITIONS:
                if current == at:
                    before[name] = pb.screen.image.copy()
            if current == 3199:
                selection_before[0] = pb.memory[0xC6A5]
                low_planes_before[0] = low_planes(pb)
            button = schedule.get(current)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()

            state = pb.memory[menuvwf.ITEM_STATE_AT]
            if (current >= 3150 and
                    (not state_trace or state_trace[-1][1] != state)):
                state_trace.append((current, state))
            for name, at in TRANSITIONS:
                if at <= current <= at + 70:
                    snapshot = pb.screen.image.copy()
                    samples[name].append((current, snapshot))
                    if not pb.memory[0xFF40] & 0x80:
                        white[name].append(current)
                    if png_dir:
                        os.makedirs(png_dir, exist_ok=True)
                        snapshot.save(os.path.join(
                            png_dir, '%s_%s_f%04d.png' %
                            (label.lower().replace(' ', '_'),
                             name.lower().replace('-', '_'), current)))

            # Capture the settled Pot before B replaces it.  The finalizer must already
            # have normalized its transient first row and restored the native low font.
            if current == 3699:
                live_records = menuspill.records(pb, profile)
                lo, hi = TRANSIENT_RUN
                pot_endpoint.update({
                    'exact': tuple(
                        (rownum, menuspill.visible_row_matches(
                            pb, profile, key, TARGET, raw=2))
                        for _at, rownum, key, _source, _row in rows),
                    'state': state,
                    'low': pb.memory[menuvwf.ITEM_LOW_ROW_AT],
                    'owners': tuple(pb.memory[address] for address in range(
                        menuvwf.ITEM_ROWS_AT, menuvwf.ITEM_FREE_AT + 1)),
                    'refs': tuple(
                        (row, col, pb.memory[0x9800 + 32 * row + col])
                        for row in range(18) for col in range(20)
                        if lo <= pb.memory[0x9800 + 32 * row + col] < hi),
                    'records': tuple(record for record in live_records
                                     if record[1] < hi and
                                     record[1] + record[2] > lo),
                    # The native post-draw retains the two completed Pot-header cells
                    # without allocator records.  Admit only those exact coordinates;
                    # their planes are independently compared with the finalizer below.
                    'invariant': tuple(
                        bad for bad in menuspill.frame_invariant(pb, profile)
                        if bad[:3] not in (
                            (1, 2, menuvwf.ROM_POT_HEADER_BASE),
                            (1, 3, menuvwf.ROM_POT_HEADER_BASE + 1))),
                    'header_planes': tuple(
                        bytes(pb.memory[menuspill.tile_data_addr(tile):
                                        menuspill.tile_data_addr(tile) + 16])
                        for tile in range(menuvwf.ROM_POT_HEADER_BASE,
                                          menuvwf.ROM_POT_HEADER_BASE +
                                          menuvwf.ROM_POT_HEADER_CAP)),
                    'low_planes': low_planes(pb),
                })

        image = pb.screen.image.copy()
        if png_dir:
            os.makedirs(png_dir, exist_ok=True)
            image.save(os.path.join(png_dir,
                                    label.lower().replace(' ', '_') + '.png'))

        if selected != [item_id]:
            problems.append('%s selected IDs %s, expected $%02X'
                            % (label, ' '.join('$%02X' % value for value in selected),
                               item_id))
        if [rownum for _at, rownum, _key, _source, _row in rows] != [0, 1, 2]:
            problems.append('%s composed rows %s, expected 0,1,2'
                            % (label, [row[1] for row in rows]))
        for at, rownum, _key, source, row in rows:
            expected_source = CONTENT_BASE + rownum * STRIDE
            if source != expected_source:
                problems.append('%s row %d source at f%d is $%04X, expected $%04X'
                                % (label, rownum, at, source, expected_source))
            if row != STAGED:
                problems.append('%s row %d staged %s, expected %s'
                                % (label, rownum, row.hex(' '), STAGED.hex(' ')))
        exact = dict(pot_endpoint.get('exact', ()))
        for rownum in range(3):
            if not exact.get(rownum):
                problems.append('%s settled Pot row %d is not plane-exact VWF `%s`'
                                % (label, rownum, itemfix.ACTION_POT_TEXT))
        if menuvwf.ITEM_STATE_POT not in [state for _at, state in state_trace]:
            problems.append('%s never enters the dedicated Pot lifecycle state $%02X'
                            % (label, menuvwf.ITEM_STATE_POT))
        if pot_endpoint.get('state') != menuvwf.ITEM_STATE_ACTION:
            problems.append('%s settled Pot lifecycle is $%02X, expected Action $%02X'
                            % (label, pot_endpoint.get('state', 0),
                               menuvwf.ITEM_STATE_ACTION))
        if pot_endpoint.get('low') != 0xFF:
            problems.append('%s settled Pot leaves transient-row owner $%02X'
                            % (label, pot_endpoint.get('low', 0)))
        if tuple(sorted(pot_endpoint.get('owners', ()))) != HIGH_OWNERS:
            problems.append('%s settled Pot owner reservation %s is not a high-slice '
                            'permutation'
                            % (label, '/'.join('$%02X' % owner for owner in
                                               pot_endpoint.get('owners', ())) or
                               'missing'))
        if pot_endpoint.get('refs') or pot_endpoint.get('records'):
            problems.append('%s settled Pot leaves transient refs/records %s / %s'
                            % (label, pot_endpoint.get('refs', ())[:8],
                               pot_endpoint.get('records', ())[:8]))
        if len(pot_finish_calls) != 1:
            problems.append('%s reaches the Pot finalizer %d times, expected once'
                            % (label, len(pot_finish_calls)))
        elif not any(state == menuvwf.ITEM_STATE_POT and
                     base == menuvwf.ROM_POT_HEADER_BASE and refs
                     for _at, state, base, refs, _planes in pot_finish_calls):
            problems.append('%s Pot finalizer never sees the disjoint $%02X-$%02X '
                            'header generation in the completed shadow map'
                            % (label, menuvwf.ROM_POT_HEADER_BASE,
                               menuvwf.ROM_POT_HEADER_BASE +
                               menuvwf.ROM_POT_HEADER_CAP - 1))
        elif pot_endpoint.get('header_planes') != pot_finish_calls[0][4]:
            problems.append('%s settled Pot changed its completed header planes'
                            % label)
        if pot_endpoint.get('invariant'):
            problems.append('%s settled Pot has unowned proportional tile(s): %s'
                            % (label, pot_endpoint['invariant'][:8]))
        if (low_planes_before[0] is None or
                pot_endpoint.get('low_planes') != low_planes_before[0]):
            problems.append('%s settled Pot did not restore native $25-$36 planes'
                            % label)

        state_traces = {}
        for name, _at in TRANSITIONS:
            transition = samples[name]
            if not transition or name not in before:
                problems.append('%s %s has no frame samples' % (label, name))
                continue
            old = visual_rows(before[name])
            new = visual_rows(transition[-1][1])
            if old == new:
                problems.append('%s %s produced no rendered change' % (label, name))
            observations = []
            for at, snapshot in transition:
                states = row_states(snapshot, old, new)
                if not observations or observations[-1][1] != states:
                    observations.append((at, states))
            state_traces[name] = observations
            bad = [(at, states) for at, states in observations if 'X' in states]
            if bad:
                problems.append('%s %s exposes blended/incomplete row(s) %s'
                                % (label, name, ' '.join('f%d:%s' % event
                                                         for event in bad[:12])))
            backtracks = row_backtracks(observations)
            if backtracks:
                problems.append('%s %s returns published row(s) to old pixels %s'
                                % (label, name, ' '.join('f%d:r%d' % event
                                                         for event in backtracks[:12])))
            if white[name]:
                problems.append('%s %s disables the LCD at %s'
                                % (label, name, ' '.join('f%d' % at
                                                         for at in white[name][:12])))

        final_records = menuspill.records(pb, profile)
        lo, hi = TRANSIENT_RUN
        final_refs = [(row, col, pb.memory[0x9800 + 32 * row + col])
                      for row in range(18) for col in range(20)
                      if lo <= pb.memory[0x9800 + 32 * row + col] < hi]
        final_transient_records = [record for record in final_records
                                   if record[1] < hi and record[1] + record[2] > lo]
        final_state = pb.memory[menuvwf.ITEM_STATE_AT]
        final_low = pb.memory[menuvwf.ITEM_LOW_ROW_AT]
        final_owners = tuple(pb.memory[address] for address in range(
            menuvwf.ITEM_ROWS_AT, menuvwf.ITEM_FREE_AT + 1))
        if final_state != menuvwf.ITEM_STATE_SETTLED or final_low != 0xFF:
            problems.append('%s Pot return settles lifecycle $%02X/low $%02X, expected '
                            '$%02X/$FF'
                            % (label, final_state, final_low,
                               menuvwf.ITEM_STATE_SETTLED))
        if tuple(sorted(final_owners)) != HIGH_OWNERS:
            problems.append('%s Pot return owners %s, expected high-slice permutation %s'
                            % (label, '/'.join('$%02X' % owner
                                               for owner in final_owners),
                               '/'.join('$%02X' % owner for owner in HIGH_OWNERS)))
        if final_refs or final_transient_records:
            problems.append('%s Pot return leaves transient refs/records %s / %s'
                            % (label, final_refs[:8], final_transient_records[:8]))
        if selection_before[0] is None or pb.memory[0xC6A5] != selection_before[0]:
            problems.append('%s Pot return changes Item selection %s -> %d'
                            % (label, selection_before[0], pb.memory[0xC6A5]))
        if low_planes_before[0] is None or low_planes(pb) != low_planes_before[0]:
            problems.append('%s returned Items did not retain native $25-$36 planes'
                            % label)
        bad = menuspill.frame_invariant(pb, profile)
        if bad:
            problems.append('%s returned Items leaves %d unowned proportional tile(s): %s'
                            % (label, len(bad), bad[:8]))
        if not any(at >= 3700 and index == 1 for at, index in dispatches):
            problems.append('%s B return never dispatched the Items screen' % label)
        if trace:
            for row in rows:
                print('  %s f%d d%d key=$%04X src=$%04X cells=%s'
                      % ((label,) + row[:4] + (row[4].hex(' '),)))
            print('  %s lifecycle %s' %
                  (label, ' '.join('f%d:$%02X' % event for event in state_trace)))
            print('  %s Pot finalizer %s' % (label, pot_finish_calls))
            print('  %s full rows %s' %
                  (label, ' | '.join('%s %s' %
                                     (name, ' '.join('f%d:%s' % event
                                                     for event in state_traces.get(name, ())))
                                     for name, _at in TRANSITIONS)))
        pb.stop(save=False)

    if not any(index == 12 for _at, index in dispatches):
        problems.append('%s never dispatched the Pot contents screen' % label)
    return problems, rows


def run(rom, ram=RAM, png_dir=None, trace=False):
    profile = menuspill.renderer_profile(rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('actionpotspill: requires the approved proportional renderer')
    PyBoy = _import_pyboy()
    problems = []
    for label, item_id, downs in CASES:
        found, rows = run_case(PyBoy, rom, ram, label, item_id, downs,
                               png_dir, trace)
        problems.extend(found)
        print('actionpotspill: %-8s %d charge row(s)' % (label, len(rows)))
    for problem in problems:
        print('  ' + problem)
    print('actionpotspill: %d problem(s)' % len(problems))
    if not problems:
        print('actionpotspill: Back/Todo Pot `Press` rows and LCD-on Items return ALL OK')
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png-dir')
    parser.add_argument('--trace', action='store_true')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('actionpotspill: missing %s' % path)
    return run(args.rom, args.ram, args.png_dir, args.trace)


if __name__ == '__main__':
    raise SystemExit(main())
