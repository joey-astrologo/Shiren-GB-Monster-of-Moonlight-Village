#!/usr/bin/env python3
"""Replay the No-Hunger Bracer pickup and require its complete two-line description.

Log 1 in ``saves/shiren_en_log_1_hunger_bracer_message.srm`` starts with a No-Hunger
Bracer one tile to Shiren's right.  Walking right picks it up; A dismisses the pickup
notice and opens its automatic description.

The original bug showed only ``When equipped:``.  Address-pinned help strings had one
four-byte pool record regardless of line count, so 13:$7D90's unchanged byte pre-scan
queued only their first line.  This check proves the source contains one record per line,
both records remain consecutive for the help renderer, and the real route draws ink on
the second row.
"""
import argparse
import os
import shutil
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import build                                                     # noqa: E402
import dte_rom                                                   # noqa: E402
import pool as textpool                                          # noqa: E402
from gbrun import _import_pyboy, PRESS_FRAMES                    # noqa: E402

LOC = '13:$5B04'
BANK, ADDRESS = 13, 0x5B04
TEXT = '<cF0:03><br>Fullness never falls.<end>'
BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a',
    2610: 'right',                 # pick up the bracer
    2800: 'a',                     # dismiss "Got..." and reveal its description
}


def rom_offset(bank, address):
    return bank * 0x4000 + address - (0x4000 if bank else 0)


def dte_pairs(rom):
    """Return the installed recursive pair table keyed by its actual ROM byte."""
    base = dte_rom.TABLE_BANK * 0x4000
    left = rom[base + 0x100:base + 0x200]
    right = rom[base + 0x200:base + 0x300]
    return {code: (left[code], right[code]) for code in dte_rom.DTE_CODES
            if left[code] != 0xFF}


def expand(data, pairs):
    out, stack = bytearray(), list(reversed(data))
    while stack:
        value = stack.pop()
        if value in pairs:
            stack.extend(reversed(pairs[value]))
        else:
            out.append(value)
    return bytes(out)


def verify_records(rom):
    problems = []
    expected = build.encode_en(TEXT, BANK) + b'\xFF'
    lines = textpool.split_lines(expected)
    size = len(lines) * textpool.RECORD_LEN
    at = rom_offset(BANK, ADDRESS)
    run = rom[at:at + size]
    for index, line in enumerate(lines):
        record = run[index * 4:index * 4 + 4]
        if len(record) != 4 or record[0] != textpool.MARK:
            problems.append('line %d has no pool record at %s+$%02X'
                            % (index + 1, LOC, index * 4))
            continue
        if record[3] != line[-1]:
            problems.append('line %d record ends $%02X, expected $%02X'
                            % (index + 1, record[3], line[-1]))
    if problems:
        return problems, run

    entries = [textpool.record_entry(run[n:n + 4]) for n in range(0, len(run), 4)]
    if any(b - a != textpool.ENTRY_LEN for a, b in zip(entries, entries[1:])):
        problems.append('help index entries are not consecutive: %s'
                        % ' '.join('$%04X' % entry for entry in entries))
    pooled = textpool.run_text(run, rom)
    if textpool.record_text(run[:4], rom) != pooled:
        problems.append('record continuation and per-line records name different text')
    if expand(pooled, dte_pairs(rom)) != expected:
        problems.append('record run does not expand to %r' % TEXT)
    return problems, run


def run(rom_path, ram_path, png=None, frames=2920):
    rom = open(rom_path, 'rb').read()
    problems, records = verify_records(rom)
    PyBoy = _import_pyboy()
    with tempfile.TemporaryDirectory(prefix='nohungerbracerspill-') as tmp:
        run_rom = os.path.join(tmp, 'nohunger.gb')
        shutil.copyfile(rom_path, run_rom)
        shutil.copyfile(ram_path, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)
        frame = [0]
        sources = []
        shot = None

        def at_composer_gate(_ctx=None):
            if frame[0] >= 2750:
                sources.append(pb.register_file.HL)

        pb.hook_register(13, 0x407E, at_composer_gate, None)
        for current in range(frames):
            frame[0] = current
            button = BOOT.get(current)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if current == 2880:
                shot = pb.screen.image.copy()

        want_sources = [ADDRESS + 4 * n for n in range(len(records) // 4)]
        if sources != want_sources:
            problems.append('live description queued %s, expected %s'
                            % (' '.join('$%04X' % source for source in sources) or 'nothing',
                               ' '.join('$%04X' % source for source in want_sources)))
        if shot is None:
            problems.append('description screenshot was not captured')
        else:
            # Row two occupies the last sixteen scanlines.  The broken build had no ink
            # here; a generous threshold avoids tying the check to exact glyph shapes.
            ink = sum(pixel < 80 for pixel in shot.convert('L').crop((0, 128, 160, 144)).getdata())
            if ink < 80:
                problems.append('second description row is blank (%d dark pixels)' % ink)
            if png:
                shot.save(png)
                print('nohungerbracerspill: wrote %s' % png)
        pb.stop(save=False)

    print('nohungerbracerspill: records %s; live queue %s'
          % (records.hex(' '), ' '.join('$%04X' % source for source in sources)))
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('nohungerbracerspill: %d problem(s)' % len(problems))
    print('nohungerbracerspill: No-Hunger Bracer shows both description lines')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=os.path.join(
        ROOT, 'saves/shiren_en_log_1_hunger_bracer_message.srm'))
    parser.add_argument('--png')
    parser.add_argument('--frames', type=int, default=2920)
    args = parser.parse_args()
    if not os.path.exists(args.ram):
        raise SystemExit('nohungerbracerspill: missing RAM fixture: %s' % args.ram)
    run(args.rom, args.ram, args.png, args.frames)


if __name__ == '__main__':
    main()
