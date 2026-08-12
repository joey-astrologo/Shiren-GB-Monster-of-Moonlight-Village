#!/usr/bin/env python3
"""Replay Nagi's fixture and isolate conservative nested entries from ordinary stairs.

The regression fixture is cartridge RAM, not a PyBoy state: Log 1 in
``saves/shiren_en_rescue.srm`` loads with Nagi following Shiren and the exit stair one
tile above him.  The script boots that log through the real title/file flow, presses Up,
and photographs the first message.

    python3 tools/rescuespill.py build/shiren_en.gb
    python3 tools/rescuespill.py build/shiren_en.gb --png build/rescue_stair.png
    python3 tools/rescuespill.py build/shiren_en.gb --ram saves/shiren_en_rescue.srm

It also follows the conservative pool records at 14:$5AFD, 14:$5B81 and 14:$70BE. Those
interior starts were observed while the ordinary-stair pointer itself was corrupt; they
remain manifested until a broad route sweep proves no independent event can enter them,
but the corrected ordinary stair must NOT stage them. It must stage bank 14's shared
``Go down / Stay here`` choice instead. Exit 1 means the route, isolation, or a redirect
regressed.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import build                                                    # noqa: E402
import koppastairspill                                          # noqa: E402
import pool as textpool                                          # noqa: E402
from gbrun import _import_pyboy, PRESS_FRAMES                    # noqa: E402

RUNTIME_LOCS = ('14:$5AFD', '14:$5B81', '14:$70BE')
COMPANION_INTERIORS = {0x5AFD, 0x5B81, 0x70BE}
BAD_RAW_CONTINUATIONS = {0x5B06, 0x5B1A}
BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a', 2610: 'up',
}


def translation(loc, path):
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        if line.startswith(loc + '\t'):
            return line.split('\t', 1)[1]
    raise SystemExit('rescuespill: %s has no translation in %s' % (loc, path))


def offset(loc):
    bank_s, addr_s = loc.split(':$')
    bank, addr = int(bank_s), int(addr_s, 16)
    return bank * 0x4000 + addr - (0x4000 if bank else 0)


def verify_records(rom, en_path, manifest_path):
    manifest = json.load(open(manifest_path, encoding='utf-8'))
    declared = {entry['loc'] for entry in manifest.get('runtime_interior_entries', [])}
    problems = []
    for loc in RUNTIME_LOCS:
        if loc not in declared:
            problems.append('%s is absent from runtime_interior_entries' % loc)
            continue
        at = offset(loc)
        record = rom[at:at + textpool.RECORD_LEN]
        if record[:1] != bytes([textpool.MARK]):
            problems.append('%s begins $%02X, expected redirect marker $%02X'
                            % (loc, record[0], textpool.MARK))
            continue
        got = textpool.record_text(record, rom)
        want = build.encode_en(translation(loc, en_path), 14) + b'\xFF'
        if got != want:
            problems.append('%s pool text differs from script/en.tsv' % loc)
    return problems


def run(rom_path, ram_path, png=None, frames=3340):
    rom = open(rom_path, 'rb').read()
    problems = verify_records(
        rom, os.path.join(ROOT, 'script/en.tsv'), os.path.join(ROOT, 'script/script.json'))
    choice, load_problems = koppastairspill.verify_loads(rom_path)
    problems.extend(load_problems)

    PyBoy = _import_pyboy()
    with tempfile.TemporaryDirectory(prefix='rescuespill-') as tmp:
        run_rom = os.path.join(tmp, 'rescue.gb')
        shutil.copyfile(rom_path, run_rom)
        shutil.copyfile(ram_path, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null')
        pb.set_emulation_speed(0)
        stager = []
        snapshot = None

        def at_stager(_ctx=None):
            stager.append(pb.register_file.HL)

        pb.hook_register(14, 0x400D, at_stager, None)
        for frame in range(frames):
            button = BOOT.get(frame)
            if frame in (2870, 2990, 3110, 3230):
                button = 'a'
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            # Capture immediately before the first A press. This gives the typewriter the
            # longest passive reveal interval while still photographing the stairs window
            # rather than the next-floor transition.
            if frame == 2869:
                snapshot = pb.screen.image.copy()

        if choice is not None and choice not in stager:
            problems.append('real stair route never staged shared choice 14:$%04X' % choice)
        leaked = sorted(COMPANION_INTERIORS & set(stager))
        if leaked:
            problems.append('ordinary stair staged companion interior(s): %s'
                            % ' '.join('$%04X' % address for address in leaked))
        bad = sorted(BAD_RAW_CONTINUATIONS & set(stager))
        if bad:
            problems.append('raw Japanese continuation(s) reached the stager: %s'
                            % ' '.join('$%04X' % address for address in bad))
        if snapshot is None:
            problems.append('no first-message screenshot was captured')
        else:
            # The old failure alternated with an empty white dialogue area.  This is only
            # a liveness check; record equality above is the content proof.
            grey = snapshot.convert('L')
            dark = sum(pixel < 96 for pixel in grey.crop((0, 104, 160, 144)).getdata())
            if dark < 20:
                problems.append('first-message area is blank (%d dark pixels)' % dark)
            if png:
                snapshot.save(png)
                print('rescuespill: wrote %s' % png)
        pb.stop(save=False)

    print('rescuespill: %d bank-14 stager call(s), starts %s'
          % (len(stager), ' '.join('$%04X' % address for address in sorted(set(stager)))))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('rescuespill: %d problem(s)' % len(problems))
    print('rescuespill: conservative runtime records and ordinary-stair isolation ALL OK')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=os.path.join(ROOT, 'saves/shiren_en_rescue.srm'))
    parser.add_argument('--png')
    parser.add_argument('--frames', type=int, default=3340)
    args = parser.parse_args()
    if not os.path.exists(args.ram):
        raise SystemExit('rescuespill: missing RAM fixture: %s' % args.ram)
    run(args.rom, args.ram, args.png, args.frames)


if __name__ == '__main__':
    main()
