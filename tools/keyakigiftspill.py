#!/usr/bin/env python3
"""Replay Keyaki's Log-2 Otogiri Herb gift and guard its hidden receipt record.

Walking left once in ``shiren_en_log2_walk_left.srm`` starts four messages at
14:$5294, $529F, $52AB and $52B8. The receipt at $52AB was absent from extraction:
its ``$E3 $FE`` pair is an item-substitution opcode plus selector, but the extractor
mistook the argument $FE for an impossible opcode and reused the record as free space.
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
import build                                                     # noqa: E402
import pool as textpool                                          # noqa: E402
from gbrun import _import_pyboy, PRESS_FRAMES                    # noqa: E402

LOC = '14:$52AB'
BANK, ADDRESS = 14, 0x52AB
TEXT = '<name> received<br> <cE3:FE>.'
EXPECTED_STARTS = (0x5294, 0x529F, 0x52AB, 0x52B8)
BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 360: 'down', 420: 'a', 500: 'a',
    2150: 'left', 2300: 'a', 2500: 'a', 2700: 'a',
}


def offset(bank, address):
    return bank * 0x4000 + address - (0x4000 if bank else 0)


def verify_record(rom):
    problems = []
    manifest = json.load(open(os.path.join(ROOT, 'script', 'script.json'), encoding='utf-8'))
    row = next((entry for entry in manifest['strings'] if entry['loc'] == LOC), None)
    if row is None:
        problems.append('%s is absent from script.json' % LOC)
    elif not row.get('runtime_entry'):
        problems.append('%s is not declared as a runtime-observed entry' % LOC)
    elif row['jp'] != '<name>は<br><cE3:FE>を もらった。':
        problems.append('%s source decoded as %r' % (LOC, row['jp']))

    record = rom[offset(BANK, ADDRESS):offset(BANK, ADDRESS) + textpool.RECORD_LEN]
    if record[:1] != bytes([textpool.MARK]):
        problems.append('%s is not a pool redirect record' % LOC)
    else:
        got = textpool.record_text(record, rom)
        want = build.encode_en(TEXT, BANK) + b'\xFF'
        if got != want:
            problems.append('%s pool text differs from script/en.tsv' % LOC)
    return problems, record


def run(rom_path, ram_path, png=None, frames=2860):
    rom = open(rom_path, 'rb').read()
    problems, record = verify_record(rom)
    PyBoy = _import_pyboy()
    with tempfile.TemporaryDirectory(prefix='keyakigiftspill-') as tmp:
        run_rom = os.path.join(tmp, 'keyaki.gb')
        shutil.copyfile(rom_path, run_rom)
        shutil.copyfile(ram_path, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null')
        pb.set_emulation_speed(0)
        frame = [0]
        staged = []
        receipt = None

        def at_stager(_ctx=None):
            # The game calls this path twice per logical line. Collapse duplicates below.
            staged.append(pb.register_file.HL)

        pb.hook_register(BANK, 0x400D, at_stager, None)
        for current in range(frames):
            frame[0] = current
            button = BOOT.get(current)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if current == 2650:
                receipt = pb.screen.image.copy()

        starts = []
        for address in staged:
            if not starts or starts[-1] != address:
                starts.append(address)
        if tuple(starts) != EXPECTED_STARTS:
            problems.append('live event staged %s, expected %s' % (
                ' '.join('$%04X' % value for value in starts) or 'nothing',
                ' '.join('$%04X' % value for value in EXPECTED_STARTS)))
        if receipt is None:
            problems.append('receipt screenshot was not captured')
        else:
            grey = receipt.convert('L').crop((0, 104, 160, 144))
            ink = sum(pixel < 96 for pixel in grey.getdata())
            if ink < 100:
                problems.append('receipt dialogue area is blank (%d dark pixels)' % ink)
            if png:
                receipt.save(png)
                print('keyakigiftspill: wrote %s' % png)
        pb.stop(save=False)

    print('keyakigiftspill: record %s; starts %s' % (
        record.hex(' '), ' '.join('$%04X' % value for value in starts)))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('keyakigiftspill: %d problem(s)' % len(problems))
    print('keyakigiftspill: Otogiri Herb receipt and complete Keyaki event ALL OK')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=os.path.join(
        ROOT, 'saves', 'shiren_en_log2_walk_left.srm'))
    parser.add_argument('--png')
    parser.add_argument('--frames', type=int, default=2860)
    args = parser.parse_args()
    if not os.path.exists(args.ram):
        raise SystemExit('keyakigiftspill: missing RAM fixture: %s' % args.ram)
    run(args.rom, args.ram, args.png, args.frames)


if __name__ == '__main__':
    main()
