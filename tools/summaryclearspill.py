#!/usr/bin/env python3
"""Keep complete proportional difficulty labels beside both native clear badges.

Replay the tester's SRAM through Log selection, Continue/B, and Rankings returns.
Inspect the final framebuffer after the native badge writer, where the old generic
row-epilogue audit missed Keyaki covering the beginning of Expert and Normal.
Producer-level difficulty variants retain the real save, badge flags and native path.
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gbrun import PRESS_FRAMES, _import_pyboy
import menuspill
import orochisymbolspill
from orochipopupspill import GOLD_PLANES
from startspill import boot_script

RAM = os.path.join(ROOT, 'saves', 'shiren_en-moonlight-clear-icon.srm')
# Native-control planes, independently captured with --no-menuvwf. Orochi uses the
# already established oracle; Keyaki is the adjacent four-tile, 16x16 native asset.
BADGE_PLANES = dict(GOLD_PLANES)
BADGE_PLANES.update({
    0xCF: bytes.fromhex('7f7f8f8fb6bbdbedcef7b1ff8effc0ff'),
    0xD0: bytes.fromhex('b1fffeaee8e8b2a091938e8887877f7f'),
    0xD1: bytes.fromhex('fefed9e9adf563ffb3ffffff01ff7fff'),
    0xD2: bytes.fromhex('f3dfd35fb1df391f693fe57f93fffefe'),
})
BADGE_CELLS = ((9, 5, 0xCB), (9, 6, 0xCD), (9, 7, 0xCF), (9, 8, 0xD1),
               (10, 5, 0xCC), (10, 6, 0xCE), (10, 7, 0xD0), (10, 8, 0xD2))
LOG_BUTTONS = boot_script({300: ('a',), 380: ('down',), 460: ('up',),
                           540: ('a',), 620: ('b',), 700: ('b',), 780: ('a',)})
LOG_CHECKS = {340: 'initial', 500: 'log_cycle', 580: 'continue_popup',
              660: 'popup_return', 820: 'root_return'}
RANK_BUTTONS = {frame: (button,) for frame, button in orochisymbolspill.BUTTONS.items()}
RANK_CHECKS = {frame: name for frame, name in orochisymbolspill.CHECKPOINTS.items()
               if name == 'initial_log' or name.startswith('returned_log')}
DIFFICULTIES = ('Easy', 'Normal', 'Hard', 'Expert')


def _text_pixels(text, profile):
    tiles = menuspill.compose(menuspill.encode(text), profile)
    rows = [tuple(bool(tile[y * 2] & (0x80 >> x))
                  for tile in tiles for x in range(8)) for y in range(8)]
    width = max(x for row in rows for x, ink in enumerate(row) if ink) + 1
    return tuple(row[:width] for row in rows)


def _find_text(image, text, profile):
    expected = _text_pixels(text, profile)
    pixels = image.load()
    width = len(expected[0])
    # Both icons occupy x=40..71. Require at least four clear pixels before the
    # whole word, and keep every letter inside the summary's x=40..151 interior.
    return next((left for left in range(76, 153 - width)
                 if all(tuple(pixels[left + x, 72 + y] == (0, 0, 0)
                              for x in range(width)) == expected[y]
                        for y in range(8))), None)


def _run(PyBoy, rom, ram, profile, cgb, buttons, checks, difficulty, png_dir):
    failures, visible_frames = [], 0
    label = ('CGB' if cgb else 'DMG') + '/' + (DIFFICULTIES[difficulty - 1]
                                             if difficulty else 'saved')
    with tempfile.TemporaryDirectory(prefix='summaryclearspill-') as tmp:
        work = os.path.join(tmp, 'summary.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=cgb)
        pb.set_emulation_speed(0)
        if difficulty:
            pb.hook_register(4, 0x69D9,
                             lambda _ctx: setattr(pb.register_file, 'C', difficulty), None)
        bad_planes = set()
        for frame in range(max(checks) + 1):
            for button in buttons.get(frame, ()):
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            selected = all(pb.memory[0x9800 + row * 32 + col] == tile
                           for row, col, tile in BADGE_CELLS)
            if selected and pb.memory[0xFF40] & 0x80:
                visible_frames += 1
                for tile, want in BADGE_PLANES.items():
                    at = menuspill.tile_data_addr(tile)
                    if bytes(pb.memory[at:at + 16]) != want:
                        bad_planes.add(tile)
            if frame not in checks:
                continue
            name = checks[frame]
            if not selected or pb.memory[0xFF40] & 0x88 != 0x80:
                failures.append('%s: both native badges were not visible' % name)
            image = pb.screen.image.copy().convert('RGB')
            text = DIFFICULTIES[difficulty - 1] if difficulty else 'Expert'
            if _find_text(image, text, profile) is None:
                failures.append('%s: complete %s is not visible beside Keyaki' % (name, text))
            if bytes(pb.memory[0x994F:0x9951]) != bytes((0x07, 0x3C)):
                failures.append('%s: native six-attempt count changed' % name)
            if png_dir:
                image.save(os.path.join(png_dir, label.replace('/', '_') + '_' + name + '.png'))
        pb.stop(save=False)
    if bad_planes:
        failures.append('native badge tiles exposed corrupt: ' +
                        ', '.join('$%02X' % tile for tile in sorted(bad_planes)))
    if visible_frames < 10:
        failures.append('fewer than ten frames showed both badges')
    print('summaryclearspill: %s; %d checkpoints; %d badge frames; %d problem(s)' %
          (label, len(checks), visible_frames, len(failures)))
    for failure in failures:
        print('  ' + failure)
    return len(failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png-dir')
    args = parser.parse_args()
    if args.png_dir:
        os.makedirs(args.png_dir, exist_ok=True)
    profile = menuspill.renderer_profile(args.rom)
    PyBoy = _import_pyboy()
    failures = 0
    for cgb in (False, True):
        for buttons, checks in ((LOG_BUTTONS, LOG_CHECKS), (RANK_BUTTONS, RANK_CHECKS)):
            failures += _run(PyBoy, args.rom, args.ram, profile, cgb, buttons, checks,
                             None, args.png_dir)
        for difficulty in range(1, 5):
            failures += _run(PyBoy, args.rom, args.ram, profile, cgb,
                             boot_script({300: ('a',)}), {340: 'difficulty'},
                             difficulty, args.png_dir)
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
