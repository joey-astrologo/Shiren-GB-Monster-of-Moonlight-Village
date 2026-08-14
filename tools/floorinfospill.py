#!/usr/bin/env python3
"""Replay the Floor Wood Arrow action/Info transitions from cartridge RAM.

``saves/shiren_en_item_menu_wood_arrow.srm`` has Log 1 standing on a Wood Arrow.
The route opens Menu -> Floor, selects Info, advances its two pages, and returns to
the action picker.  The Japanese game keeps the LCD enabled and progressively publishes
complete tile rows.  Each rendered row may therefore come from either endpoint, but a
white LCD-off frame or a row matching neither complete endpoint is a regression.
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


BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a',
    2620: 'b', 2700: 'down', 2780: 'a',
    2860: 'down', 2900: 'down', 2940: 'down',
    3000: 'a', 3400: 'a', 3800: 'a',
}
TRANSITIONS = (
    ('action-to-info-1', 3000),
    ('info-1-to-info-2', 3400),
    ('info-2-to-action', 3800),
)
WOOD_ARROW = bytes(menuspill.encode('Wood Arrow'))


def staged_row(pb, source, limit=32):
    out = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            break
        out.append(value)
    return bytes(out)


def visual_rows(image):
    """Exact full-width rendered tile rows, with no text-cell exemptions."""
    rgb = image.convert('RGB')
    return tuple(rgb.crop((0, row * 8, 160, row * 8 + 8)).tobytes()
                 for row in range(18))


def row_states(image, old_rows, new_rows):
    states = []
    for got, old, new in zip(visual_rows(image), old_rows, new_rows):
        if got == old == new:
            states.append('=')
        elif got == old:
            states.append('O')
        elif got == new:
            states.append('N')
        else:
            states.append('X')
    return ''.join(states)


def row_backtracks(observations):
    """Rows which returned to the old raster after first showing the new raster."""
    seen_new = set()
    backtracks = []
    for at, states in observations:
        for row, state in enumerate(states):
            if state == 'N':
                seen_new.add(row)
            elif state == 'O' and row in seen_new:
                backtracks.append((at, row))
    return backtracks


def run(rom_path, ram_path, png_dir=None, frames=3900, trace=False):
    profile = menuspill.renderer_profile(rom_path)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('floorinfospill: requires the Dot proportional renderer')
    if png_dir:
        os.makedirs(png_dir, exist_ok=True)

    PyBoy = _import_pyboy()
    problems = []
    with tempfile.TemporaryDirectory(prefix='floorinfospill-') as tmp:
        run_rom = os.path.join(tmp, 'floorinfo.gb')
        shutil.copyfile(rom_path, run_rom)
        shutil.copyfile(ram_path, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        dispatches = []
        calls = []
        before = {}
        samples = {name: [] for name, _at in TRANSITIONS}
        white = {name: [] for name, _at in TRANSITIONS}
        state_traces = {}

        def dispatch(_ctx=None):
            dispatches.append((frame[0], pb.register_file.A))

        def far_entry(_ctx=None):
            # The fixed-font restorer calls menurow with A=$FD to read one source
            # byte.  Ignore those calls in the rendered-row trace.
            if pb.register_file.A == 0xFD and pb.register_file.D & 0x80:
                return
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            calls.append((frame[0], pb.register_file.D, pb.register_file.HL,
                          pb.memory[0xC1B1], shape, source,
                          staged_row(pb, source)))

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
                    snapshot = pb.screen.image.copy()
                    samples[name].append((current, snapshot))
                    if not pb.memory[0xFF40] & 0x80:
                        white[name].append(current)
                    if png_dir:
                        snapshot.save(os.path.join(
                            png_dir, '%s_f%04d.png' % (name, current)))

        pb.stop(save=False)

    indices = [index for _at, index in dispatches]
    expected = (20, 4, 4, 0, 20)
    cursor = 0
    for index in indices:
        if cursor < len(expected) and index == expected[cursor]:
            cursor += 1
    if cursor != len(expected):
        problems.append('dispatch sequence %s does not contain %s'
                        % (indices, list(expected)))

    headers = [row for _at, _d, _key, _mode, shape, _source, row in calls
               if shape[:4] == (0, 0, 1, 18) and row == bytes([0]) + WOOD_ARROW]
    if not headers:
        problems.append('real route never composed the one-prefix Wood Arrow header')

    for name, _at in TRANSITIONS:
        transition = samples[name]
        if not transition or name not in before:
            problems.append('%s has no frame samples' % name)
            continue
        old = visual_rows(before[name])
        new = visual_rows(transition[-1][1])
        if old == new:
            problems.append('%s produced no rendered change' % name)
        observations = []
        for at, image in transition:
            states = row_states(image, old, new)
            if not observations or observations[-1][1] != states:
                observations.append((at, states))
        state_traces[name] = observations
        first_new = next((i for i, (_frame, image) in enumerate(transition)
                          if all(state in '=N' for state in
                                 row_states(image, old, new))), None)
        if first_new is None:
            problems.append('%s never reaches its settled tile rows' % name)
        bad = [(at, states) for at, states in observations if 'X' in states]
        if bad:
            problems.append('%s exposes blended/incomplete tile row(s) %s'
                            % (name, ' '.join('f%d:%s' % event for event in bad[:16])))
        backtracks = row_backtracks(observations)
        if backtracks:
            problems.append('%s returns published row(s) to old pixels %s'
                            % (name, ' '.join('f%d:r%d' % event
                                              for event in backtracks[:16])))
        if white[name]:
            problems.append('%s disables the LCD at %s'
                            % (name, ' '.join('f%d' % at for at in white[name][:16])))

    print('floorinfospill: dispatches %s' %
          ' '.join('f%d:%d' % event for event in dispatches))
    print('floorinfospill: LCD-off frame counts %s' %
          ' '.join('%s=%d' % (name, len(white[name])) for name, _at in TRANSITIONS))
    print('floorinfospill: rendered row states %s' % ' | '.join(
          '%s %s' % (name, ' '.join('f%d:%s' % event
                                     for event in state_traces.get(name, ())))
          for name, _at in TRANSITIONS))
    if trace:
        for call in calls:
            at, rownum, key, mode, shape, source, row = call
            if 2750 <= at <= 3850:
                print('  f%d d%d key=$%04X mode%d shape=%s src=$%04X row=%s'
                      % (at, rownum, key, mode, shape, source, row.hex(' ')))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('floorinfospill: %d problem(s)' % len(problems))
    print('floorinfospill: LCD-on transitions contain only complete old/new tile rows')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=os.path.join(
        ROOT, 'saves/shiren_en_item_menu_wood_arrow.srm'))
    parser.add_argument('--png-dir')
    parser.add_argument('--frames', type=int, default=3900)
    parser.add_argument('--trace', action='store_true')
    args = parser.parse_args()
    if not os.path.exists(args.ram):
        raise SystemExit('floorinfospill: missing RAM fixture: %s' % args.ram)
    run(args.rom, args.ram, args.png_dir, args.frames, args.trace)


if __name__ == '__main__':
    main()
