#!/usr/bin/env python3
"""Replay the Floor Wood Arrow action/Info transitions from cartridge RAM.

``saves/shiren_en_item_menu_wood_arrow.srm`` has Log 1 standing on a Wood Arrow.
The route opens Menu -> Floor, selects Info, advances its two pages, and returns to
the action picker.  Every text transition must be atomic: an exposed frame may be the
old screen, the uniform LCD-off screen, or the complete new screen, never a blend.
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


def visual_key(image):
    """Text and boxes, excluding independently written sprites/cursors/pagers/HUD."""
    rgb = image.convert('RGB')
    rgb.paste((0, 0, 0), (64, 56, 96, 96))       # Wood Arrow floor sprite
    rgb.paste((0, 0, 0), (104, 24, 120, 96))     # action cursor / Info down arrow
    rgb.paste((0, 0, 0), (120, 96, 160, 112))    # Info page counter
    rgb.paste((0, 0, 0), (0, 128, 160, 144))     # animated dungeon HUD
    return rgb.tobytes()


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

        def dispatch(_ctx=None):
            dispatches.append((frame[0], pb.register_file.A))

        def far_entry(_ctx=None):
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
        old = visual_key(before[name])
        new = visual_key(transition[-1][1])
        first_new = next((i for i, (_frame, image) in enumerate(transition)
                          if visual_key(image) == new), None)
        if first_new is None:
            problems.append('%s never reaches its settled image' % name)
            continue
        bad = []
        for at, image in transition[:first_new + 1]:
            key = visual_key(image)
            if key not in (old, new) and len(set(image.convert('RGB').getdata())) != 1:
                bad.append(at)
        if bad:
            problems.append('%s has blended/partial text frame(s) %s'
                            % (name, ' '.join('f%d' % at for at in bad[:16])))
        if not white[name]:
            problems.append('%s never enters the white LCD-off state' % name)

    print('floorinfospill: dispatches %s' %
          ' '.join('f%d:%d' % event for event in dispatches))
    print('floorinfospill: white-frame counts %s' %
          ' '.join('%s=%d' % (name, len(white[name])) for name, _at in TRANSITIONS))
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
    print('floorinfospill: real Wood Arrow action/Info transitions are atomic')


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
