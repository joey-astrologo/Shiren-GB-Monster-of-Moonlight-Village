#!/usr/bin/env python3
"""Guard the ordinary-stair choice on the Nagi, Koppa and Fumi routes.

Historical name: this test began as a supposed Koppa-dialogue selector regression.  A
state handoff into the original Japanese ROM proved that premise wrong.  All four supplied
routes stage the same bank-14 ``Descend / Stay here`` choice and transition immediately
after it; none stages Nagi's or Koppa's rescued-child dialogue.

The actual bug was static.  Bank-13 instructions at $549F and $54B5 load ``hl,$46C1``,
select bank $0E, and call the dialogue stager.  Extraction used to assign those operands
to the unrelated string at *bank 13* $46C1.  When that string moved to $5AFD, every stair
load moved with it.  This regression checks both corrected operands and replays two Koppa
floors, Nagi and Fumi to prove they all stage the relocated bank-14 choice.
"""
import argparse
import os
import shutil
import sys
import tempfile


TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import build                                                    # noqa: E402
from gbrun import _import_pyboy, PRESS_FRAMES                   # noqa: E402


CHOICE_LOC = '14:$46C1'
CODE_BANK = 13
LOADS = (0x549F, 0x54B5)
FIXTURES = (
    ('Koppa floor 1', 'shiren_en_log_1_koppa_exit_pee.srm', 'right'),
    ('Koppa floor 2', 'shiren_en_log_1_koppa_exit_pee_v2.srm', 'right'),
    ('Nagi', 'shiren_en_rescue.srm', 'up'),
    ('Fumi', 'shiren_en_log_1_dragons_maw.srm', 'down'),
)
BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a',
}


def translation(loc, path):
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        if line.startswith(loc + '\t'):
            return line.split('\t', 1)[1]
    raise SystemExit('koppastairspill: %s has no translation in %s' % (loc, path))


def rom_offset(bank, addr):
    return bank * 0x4000 + addr - (0x4000 if bank else 0)


def verify_loads(rom_path):
    rom = open(rom_path, 'rb').read()
    problems, targets = [], []
    for addr in LOADS:
        at = rom_offset(CODE_BANK, addr)
        if rom[at] != 0x21:                         # ld hl,nn
            problems.append('%d:$%04X is no longer ld hl,nn (opcode $%02X)'
                            % (CODE_BANK, addr, rom[at]))
            continue
        targets.append(rom[at + 1] | (rom[at + 2] << 8))
    if len(set(targets)) > 1:
        problems.append('stair-choice loads disagree: %s'
                        % ' '.join('$%04X' % value for value in targets))
    if targets and targets[0] in (0x5AFD, 0x7BC2):
        problems.append('stair choice still targets companion dialogue $%04X' % targets[0])

    # The first rendered row is stable even when the builder inserts a cursor reservation
    # on the continuation row.  Checking it ties the corrected operand to the English
    # choice rather than merely proving that both loads agree with one another.
    if targets:
        target = targets[0]
        at = rom_offset(14, target)
        encoded = build.encode_en(translation(CHOICE_LOC,
                                               os.path.join(ROOT, 'script', 'en.tsv')), 14)
        first_row = encoded[:encoded.index(0xEF) + 1]
        if rom[at:at + len(first_row)] != first_row:
            problems.append('14:$%04X does not begin with the translated stair choice'
                            % target)
        return target, problems
    return None, problems


def replay(rom_path, target, label, ram_path, direction, png=None, frames=3100):
    problems = []
    PyBoy = _import_pyboy()
    with tempfile.TemporaryDirectory(prefix='koppastairspill-') as tmp:
        work = os.path.join(tmp, 'stairs.gb')
        shutil.copyfile(rom_path, work)
        shutil.copyfile(ram_path, work + '.ram')
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        frame = [0]
        before, staged = [], []
        prompt = None

        def before_stager(_ctx=None):
            before.append((frame[0], pb.register_file.HL))

        def after_stager(_ctx=None):
            staged.append((frame[0], pb.register_file.HL))

        pb.hook_register(14, 0x4007, before_stager, None)
        pb.hook_register(14, 0x400D, after_stager, None)
        for value in range(frames):
            frame[0] = value
            button = BOOT.get(value)
            if value == 2610:
                button = direction
            if value == 2790:
                button = 'a'                    # choose the default Descend option
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if value == 2760:
                prompt = pb.screen.image.copy()
        final = pb.screen.image.copy()
        final_lcdc = pb.memory[0xFF40]
        pb.stop(save=False)

    post_before = [(f, hl) for f, hl in before if f >= 2600]
    post_staged = [(f, hl) for f, hl in staged if f >= 2600]
    tagged = target ^ 0xC000
    if not post_before or post_before[0][1] != tagged:
        problems.append('first tagged stair entry was %s, expected $%04X'
                        % (('$%04X' % post_before[0][1]) if post_before else '(none)',
                           tagged))
    if not post_staged or post_staged[0][1] != target:
        problems.append('first staged stair row was %s, expected $%04X'
                        % (('$%04X' % post_staged[0][1]) if post_staged else '(none)',
                           target))
    companion = [(f, hl) for f, hl in post_staged
                 if hl in (0x5AFD, 0x5B81, 0x7BC2)]
    if companion:
        problems.append('companion dialogue leaked into stair choice: %s'
                        % ' '.join('%d:$%04X' % pair for pair in companion))

    if prompt is None:
        problems.append('no stair-choice screenshot was captured')
    else:
        dark = sum(pixel < 96
                   for pixel in prompt.convert('L').crop((0, 104, 160, 144)).getdata())
        if dark < 20:
            problems.append('stair-choice area is blank (%d dark pixels)' % dark)
        if png:
            prompt.save(png)
            print('koppastairspill: wrote %s' % png)
    if not final_lcdc & 0x80:
        problems.append('route ended with LCD disabled (LCDC=$%02X)' % final_lcdc)
    if prompt is not None and prompt.tobytes() == final.tobytes():
        problems.append('default Descend selection did not advance beyond the choice')

    print('koppastairspill: %s tagged %s; staged %s; %d problem(s)'
          % (label,
             ' '.join('$%04X' % hl for _f, hl in post_before) or '(none)',
             ' '.join('$%04X' % hl for _f, hl in post_staged) or '(none)',
             len(problems)))
    for problem in problems:
        print('  ' + problem)
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', help='run one custom fixture instead of the suite')
    parser.add_argument('--direction', default='right')
    parser.add_argument('--png')
    parser.add_argument('--frames', type=int, default=3100)
    args = parser.parse_args()
    if not os.path.exists(args.rom):
        raise SystemExit('koppastairspill: missing %s' % args.rom)

    target, problems = verify_loads(args.rom)
    fixtures = (('custom', args.ram, args.direction),) if args.ram else FIXTURES
    if target is not None:
        for index, (label, save_name, direction) in enumerate(fixtures):
            ram_path = save_name if args.ram else os.path.join(ROOT, 'saves', save_name)
            if not os.path.exists(ram_path):
                problems.append('missing %s' % ram_path)
                continue
            shot = args.png if index == 0 else None
            problems.extend(replay(args.rom, target, label, ram_path, direction,
                                   shot, args.frames))
    for problem in problems:
        print('koppastairspill: ' + problem)
    print('koppastairspill: %d total problem(s)' % len(problems))
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
