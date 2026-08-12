#!/usr/bin/env python3
"""Replay the real Floor-menu item header from Joey's cartridge-RAM fixture.

Log 1 in ``saves/shiren_en_ground.srm`` starts with Shiren standing on an Iron Shield.
This tool boots the log normally, opens Menu -> Floor, and requires the live box-5
header to compose ``Iron Shield`` with exactly one raw cursor cell.

    python3 tools/groundspill.py build/shiren_en.gb
    python3 tools/groundspill.py build/shiren_en.gb --png build/ground_live.png
    python3 tools/groundspill.py build/shiren_en.gb --ram saves/shiren_en_ground.srm

The older synthetic fixture accidentally staged two zero cells and therefore proved a
path the game does not use.  This route owns the acceptance claim. Exit 1 if dispatcher
screen 20, its live staged bytes, allocator record, visible Dot planes, or frame residency
does not match.
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
}
STAGING = 0xC616
TARGET = bytes(menuspill.encode('Iron Shield'))
SHAPE = (0, 0, 1, 18, menuvwf.ROM_RAW_PREFIX_BIT)


def staged_row(pb, source, limit=32):
    out = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            return bytes(out)
        out.append(value)
    return bytes(out)


def run(rom_path, ram_path, png=None, frames=3060):
    profile = menuspill.renderer_profile(rom_path)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('groundspill: requires the Dot proportional renderer')
    PyBoy = _import_pyboy()
    problems = []
    with tempfile.TemporaryDirectory(prefix='groundspill-') as tmp:
        run_rom = os.path.join(tmp, 'ground.gb')
        shutil.copyfile(rom_path, run_rom)
        shutil.copyfile(ram_path, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null')
        pb.set_emulation_speed(0)
        frame = [0]
        dispatches = []
        calls = []
        key = [None]
        bad_frames = 0

        def dispatch(_ctx=None):
            dispatches.append((frame[0], pb.register_file.A))

        def far_entry(_ctx=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if shape != SHAPE:
                return
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            row = staged_row(pb, source)
            calls.append((frame[0], source, row))
            key[0] = pb.register_file.HL

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], far_entry, None)
        for current in range(frames):
            frame[0] = current
            button = BOOT.get(current)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if current >= 2790 and pb.memory[0xFF40] & 0x80:
                bad = menuspill.frame_invariant(pb, profile)
                if bad:
                    bad_frames += 1
                    if len(problems) < 6:
                        problems += ['f%d (%d,%d) tile $%02X -- %s'
                                     % ((current,) + entry) for entry in bad[:2]]

        if not any(index == 20 for _at, index in dispatches):
            problems.append('real route never dispatched Floor screen 20')
        if not calls:
            problems.append('real route never entered the exact box-5 proportional path')
        else:
            at, source, row = calls[0]
            want = bytes([0]) + TARGET
            if source != STAGING:
                problems.append('box 5 read $%04X, expected staging $%04X'
                                % (source, STAGING))
            if row != want:
                problems.append('live header at f%d is %s, expected one raw zero + Iron Shield'
                                % (at, row.hex(' ')))
        if key[0] is not None:
            matching = [record for record in menuspill.records(pb, profile)
                        if record[0] == key[0] and record[3] == 1]
            if not matching:
                problems.append('live header has no one-raw-cell allocator record')
            elif not menuspill.visible_row_matches(pb, profile, key[0], TARGET, raw=1):
                problems.append('live Iron Shield planes are not proportional Dot Gothic')
        if png:
            pb.screen.image.save(png)
            print('groundspill: wrote %s' % png)
        pb.stop(save=False)

    print('groundspill: dispatches %s; %d box-5 call(s); %d bad frame(s)'
          % (' '.join('f%d:%d' % event for event in dispatches), len(calls), bad_frames))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('groundspill: %d problem(s)' % len(problems))
    print('groundspill: real Log-1 Floor header and visible Dot planes ALL OK')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=os.path.join(ROOT, 'saves/shiren_en_ground.srm'))
    parser.add_argument('--png')
    parser.add_argument('--frames', type=int, default=3060)
    args = parser.parse_args()
    if not os.path.exists(args.ram):
        raise SystemExit('groundspill: missing RAM fixture: %s' % args.ram)
    run(args.rom, args.ram, args.png, args.frames)


if __name__ == '__main__':
    main()
