#!/usr/bin/env python3
"""Replay the Log-1 Decoy Staff battle-name regression.

``saves/shiren_en_log_1_decoy_staff_enemy.srm`` boots with Shiren immediately beside a
Decoy Staff target. Pressing A attacks it. The native actor-name producer used to write
``$20,$18`` (Japanese ``にせ``) before the live player name; the English font displayed
those bytes as ``VN``, yielding ``VNShiren`` in every action report.

This test reaches the producer through the supplied save and proves the decoy invocation
copies exactly the live player name: no prefix bytes, no hardcoded default name, and no
change to ordinary-player invocations.
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gbrun import PRESS_FRAMES, _import_pyboy                  # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log_1_decoy_staff_enemy.srm')
ENTRY = 0x51CA
JOIN = 0x51DA
COPIED = 0x51C0
PLAYER_KIND = 0x12
PLAYER_NAME = 0xCF81
ATTACK = 1100
FRAMES = 1300
SCRIPT = {
    60: ('start',), 120: ('start',), 180: ('start',), 240: ('start',),
    300: ('a',),                  # Adventure
    380: ('a',),                  # Log 1
    460: ('a',),                  # Continue
    ATTACK: ('a',),               # strike the adjacent Shiren decoy
}


def _de(pb):
    return (pb.register_file.D << 8) | pb.register_file.E


def _terminated(pb, address, limit=16):
    out = []
    for offset in range(limit):
        value = pb.memory[address + offset]
        if value == 0xFF:
            return bytes(out)
        out.append(value)
    raise RuntimeError('unterminated player name at $%04X' % address)


def run(rom, ram, png=None):
    PyBoy = _import_pyboy()
    problems = []
    records = []
    active = []
    with tempfile.TemporaryDirectory(prefix='decoynamespill-') as tmp:
        work = os.path.join(tmp, 'decoy.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)
        frame = [0]

        def enter(_context=None):
            active.append({
                'frame': frame[0],
                'kind': pb.memory[0xFF92],
                'start': _de(pb),
                'name': _terminated(pb, PLAYER_NAME),
            })

        def join(_context=None):
            if active:
                active[-1]['join'] = _de(pb)

        def copied(_context=None):
            # $51C0 is shared by every name-table path; only $51CA entries are ours.
            if not active:
                return
            record = active.pop()
            record['end'] = _de(pb)
            record['payload'] = bytes(pb.memory[address]
                                      for address in range(record['start'], record['end']))
            records.append(record)

        pb.hook_register(11, ENTRY, enter, None)
        pb.hook_register(11, JOIN, join, None)
        pb.hook_register(11, COPIED, copied, None)
        for frame[0] in range(FRAMES):
            for button in SCRIPT.get(frame[0], ()):
                pb.button(button, PRESS_FRAMES)
            pb.tick()

        if png:
            pb.screen.image.save(png)
            print('decoynamespill: wrote %s' % png)
        final_pc = pb.register_file.PC
        pb.stop(save=False)

    decoys = [record for record in records
              if record['frame'] >= ATTACK and record['kind'] != PLAYER_KIND]
    players = [record for record in records
               if record['frame'] >= ATTACK and record['kind'] == PLAYER_KIND]
    if not decoys:
        problems.append('the supplied route never produced an attacked decoy name')
    if not players:
        problems.append('the supplied route never produced the attacking player name')
    for record in decoys:
        if record.get('join') != record['start']:
            problems.append('decoy advanced destination $%04X -> $%04X before copying '
                            '(raw prefix survived)' %
                            (record['start'], record.get('join', -1)))
        if record.get('payload') != record['name']:
            problems.append('decoy payload %s differs from live player name %s' %
                            (record.get('payload', b'').hex(' '),
                             record['name'].hex(' ')))
    for record in players:
        if record.get('payload') != record['name']:
            problems.append('ordinary player payload changed: %s vs %s' %
                            (record.get('payload', b'').hex(' '),
                             record['name'].hex(' ')))
    if final_pc == 0x0038:
        problems.append('CPU ended in rst $38')

    summary = ['f%d kind=$%02X %s' %
               (record['frame'], record['kind'], record.get('payload', b'').hex(' '))
               for record in records if record['frame'] >= ATTACK]
    print('decoynamespill: %s; %d decoy / %d player call(s); PC=$%04X; %d problem(s)'
          % (', '.join(summary), len(decoys), len(players), final_pc, len(problems)))
    for problem in problems:
        print('  ' + problem)
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('decoynamespill: missing %s' % path)
    return run(args.rom, args.ram, args.png)


if __name__ == '__main__':
    raise SystemExit(main())
