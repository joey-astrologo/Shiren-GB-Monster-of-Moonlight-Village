#!/usr/bin/env python3
"""Replay the real Moonlight Exit clear after gameplay has used cinematic scratch.

Log 1 is on floor 49: Right, A, A selects Proceed. Unlike introspill's boot-time
clip override, this route inherits the live menu/dialogue renderer's scratch bytes.
Check the initial forest and black panel, all six cinematic packs, byte-exact
VBlank transfers, cleanup, and all 22 credits through the native story continuation.
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import dotfont
import endingcredits
import intro
from endingcreditspill import BOOT, _far_entry, run as run_credits
from gbrun import PRESS_FRAMES, _import_pyboy
from introspill import expected_uploads


RAM = os.path.join(ROOT, 'saves', 'shiren_en-moonlight-ending.srm')
SOURCE = os.path.join(ROOT, 'build', '_base_expanded.gb')
FRAMES = 8000


def run(rom, ram, source_path, png_dir=None):
    source = open(source_path, 'rb').read()
    canonical = intro.compile_intro(
        source, intro.load_tsv(os.path.join(ROOT, 'script', 'intro.tsv'), source),
        dotfont.load_approved())
    forest_map = source[intro._off(31, 0x5412):intro._off(31, 0x5592)]
    forest_tiles = source[intro._off(31, 0x5592):intro._off(31, 0x5C62)]
    PyBoy = _import_pyboy()
    problems = []
    if png_dir:
        os.makedirs(png_dir, exist_ok=True)

    for cgb in (False, True):
        mode = 'CGB' if cgb else 'DMG'
        failures = set()
        entries, initialized, packs, uploads, done, credits = [], [], [], [], [], []
        active = [False]
        drawing = [False]
        blank_frames = [0]
        clear_count = [0]
        picture = [None]

        with tempfile.TemporaryDirectory(prefix='moonlightendspill-') as tmp:
            work = os.path.join(tmp, 'ending.gb')
            shutil.copyfile(rom, work)
            shutil.copyfile(ram, work + '.ram')
            pb = PyBoy(work, window='null', cgb=cgb)
            pb.set_emulation_speed(0)

            def enter(_ctx):
                de = (pb.register_file.D << 8) | pb.register_file.E
                if pb.memory[de + 0x10] != 1:
                    return
                active[0] = True
                entries.append(bytes(pb.memory[intro.S_SEQ:intro.S_LEFT + 1]))

            def ready(_ctx):
                if not active[0]:
                    return
                initialized.append(bytes(pb.memory[intro.S_SEQ:intro.S_LEFT + 1]))
                packs.append(intro.vram_pack(pb.memory, 0) == canonical['packs'][6])

            def draw(_ctx):
                if active[0]:
                    drawing[0] = True

            def clear(_ctx):
                if not active[0]:
                    return
                clear_count[0] += 1
                index = clear_count[0]
                if index <= 5:
                    packs.append(intro.vram_pack(pb.memory, index) ==
                                 canonical['packs'][6 + index])

            def upload(_ctx):
                if not active[0]:
                    return
                bases = (0xC006, 0xC01C, 0xC032, 0xC048, 0xC05E)
                targets = tuple(pb.memory[base] | (pb.memory[base + 1] << 8)
                                for base in bases)
                # Ordinary cinematic map updates and parked self-copies are allowed;
                # every other pass must be one of the 35 planned hidden-pack uploads.
                normal = (0x99A0, 0x99C0, 0x99E0, 0x9A00, 0xC060)
                parked = tuple(base + 2 for base in bases)
                if targets in (normal, parked):
                    return
                payload = b''.join(bytes(pb.memory[base + 2:base + 22])
                                   for base in bases)
                uploads.append((targets, payload))
                if not (144 <= pb.memory[0xFF44] <= 153 and
                        pb.memory[0xFF41] & 3 == 1):
                    failures.add('cinematic upload ran outside VBlank')

            def finished(_ctx):
                if active[0]:
                    done.append(pb.memory[intro.S_LEFT])
                    active[0] = False

            def credit(_ctx):
                if done:
                    credits.append(pb.register_file.A)

            pb.hook_register(31, 0x4D50, enter, None)
            pb.hook_register(31, 0x4D91, ready, None)
            pb.hook_register(31, 0x51FC, draw, None)
            pb.hook_register(31, 0x5341, clear, None)
            pb.hook_register(31, 0x4D4F, finished, None)
            pb.hook_register(0, 0x1087, upload, None)
            bank = endingcredits.FAR_BANKS[0]
            pb.hook_register(bank, _far_entry(rom, bank), credit, None)

            for frame in range(FRAMES):
                for button in BOOT.get(frame, ()):
                    pb.button(button, PRESS_FRAMES)
                if 2660 <= frame and (frame - 2660) % 60 == 0:
                    pb.button('a', PRESS_FRAMES)
                previous_palette = pb.memory[0xFF47]
                pb.tick()
                if active[0] and initialized:
                    if bytes(pb.memory[0x9000:0x96D0]) != forest_tiles:
                        failures.add('native forest tile planes changed')
                    if bytes(pb.memory[0x9820:0x99A0]) != forest_map:
                        failures.add('native forest tilemap changed')
                    # A fade may update BGP after this frame's visible scan. Require
                    # a complete frame at the final palette before judging pixels.
                    if (not drawing[0] and previous_palette == 0xE4 and
                            pb.memory[0xFF47] == 0xE4):
                        panel = pb.screen.image.crop((0, 104, 160, 144)).convert('RGB')
                        if set(panel.getdata()) != {(0, 0, 0)}:
                            failures.add('initial text panel contains stray graphics')
                        blank_frames[0] += 1
                        picture[0] = pb.screen.image.copy()
                if credits:
                    break
            pb.stop(save=False)

        if len(entries) != 1 or entries[0] == b'\x00\x00\x00':
            failures.add('did not enter the ending from live gameplay scratch')
        if initialized != [b'\x00\x00\x00']:
            failures.add('cinematic initializer retained gameplay scratch: %s' %
                         [value.hex() for value in initialized])
        if blank_frames[0] < 30:
            failures.add('initial black panel was not observed long enough')
        if packs != [True] * 6 or clear_count[0] != 6:
            failures.add('six cinematic packs/clears did not complete: %s / %d' %
                         (packs, clear_count[0]))
        expected = expected_uploads(canonical, 1)
        if uploads != expected:
            failures.add('hidden VBlank transfers differ: got %d, expected %d' %
                         (len(uploads), len(expected)))
        if done != [0] or credits != [0]:
            failures.add('cinematic cleanup/credit entry did not complete: %s / %s' %
                         (done, credits))
        if png_dir and picture[0] is not None:
            picture[0].save(os.path.join(png_dir, mode.lower() + '_before_text.png'))
        print('moonlightendspill: %s; %d pre-text frames; %d/6 packs exact; '
              '%d VBlank transfers; %d problem(s)' %
              (mode, blank_frames[0], sum(packs), len(uploads), len(failures)))
        for failure in sorted(failures):
            print('  ' + failure)
        problems.extend(failures)
    return int(bool(problems))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--source', default=SOURCE)
    parser.add_argument('--png-dir')
    args = parser.parse_args()
    result = run(args.rom, args.ram, args.source, args.png_dir)
    if result:
        return result
    return run_credits(args.rom, args.ram, moonlight_exit=True)


if __name__ == '__main__':
    raise SystemExit(main())
