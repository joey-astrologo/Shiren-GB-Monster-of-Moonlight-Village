#!/usr/bin/env python3
"""Guard Koppa's shared ``Brrr... That was scary`` message in town and dungeon.

The Japanese record at 14:$7BC2 ends naturally at $FF.  Appending ``<end><brk>`` to the
English produced ``message -> empty box -> closed`` when talking to Koppa in town.  The
same record is also consumed by a dungeon rescue context, so this test covers both:

* the supplied town SRAM talks to the adjacent Koppa and requires one A press to close;
* a diagnostic copy of the first Koppa dungeon fixture points the two ordinary-stair text
  loads at 14:$7BC2.  This is NOT production behavior (the real build keeps the shared
  ``Go down / Stay here`` choice); it exercises the same dungeon caller and requires one A
  press to reach the next-floor card without an empty intermediate box.

``koppastairspill.py`` separately proves those production stair loads still target the
normal choice on both Koppa floors, Nagi and Fumi.
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile


TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import build                                                    # noqa: E402
import pool as textpool                                         # noqa: E402
from gbrun import _import_pyboy, PRESS_FRAMES                   # noqa: E402


LOC = '14:$7BC2'
ADDR = 0x7BC2
TOWN_SAVE = 'shiren_en_log_1_talk_to_koppa.srm'
DUNGEON_SAVE = 'shiren_en_log_1_koppa_exit_pee.srm'
STAIR_LOADS = (0x549F, 0x54B5)
BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a',
}


def translation(loc, path):
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        if line.startswith(loc + '\t'):
            return line.split('\t', 1)[1]
    raise SystemExit('koppatalkspill: %s has no translation in %s' % (loc, path))


def offset(bank, addr):
    return bank * 0x4000 + addr - (0x4000 if bank else 0)


def verify_record(rom_path):
    rom = open(rom_path, 'rb').read()
    manifest = json.load(open(os.path.join(ROOT, 'script', 'script.json'), encoding='utf-8'))
    source = next((row for row in manifest['strings'] if row['loc'] == LOC), None)
    text = translation(LOC, os.path.join(ROOT, 'script', 'en.tsv'))
    problems = []
    if source is None:
        problems.append('%s is absent from script.json' % LOC)
    elif '<end>' in source['jp'] or '<brk>' in source['jp']:
        problems.append('%s Japanese source unexpectedly contains end/page controls' % LOC)
    if re.search(r'<end>(?:<brk>)*$', text):
        problems.append('%s retains a terminal <end>; it will redraw/empty the last box' % LOC)
    if text.count('<br>') != 1:
        problems.append('%s should render as exactly two English lines' % LOC)

    record = rom[offset(14, ADDR):offset(14, ADDR) + textpool.RECORD_LEN]
    if record[:1] != bytes([textpool.MARK]):
        problems.append('%s is not a pool redirect record' % LOC)
    else:
        got = textpool.record_text(record, rom)
        want = build.encode_en(text, 14) + b'\xFF'
        if got != want:
            problems.append('%s pool text differs from script/en.tsv' % LOC)
    return problems


def _run(rom_path, ram_path, actions, frames, capture_frames, patch_stairs=False):
    PyBoy = _import_pyboy()
    with tempfile.TemporaryDirectory(prefix='koppatalkspill-') as tmp:
        work = os.path.join(tmp, 'koppa.gb')
        data = bytearray(open(rom_path, 'rb').read())
        if patch_stairs:
            # Diagnostic only: select the shared Koppa record through the dungeon caller.
            # Assert the instruction shape and patch both matching loads exactly.
            for addr in STAIR_LOADS:
                at = offset(13, addr)
                if data[at] != 0x21:
                    raise SystemExit('koppatalkspill: 13:$%04X is not ld hl,nn' % addr)
                data[at + 1:at + 3] = bytes((ADDR & 0xFF, ADDR >> 8))
        with open(work, 'wb') as out:
            out.write(data)
        shutil.copyfile(ram_path, work + '.ram')
        pb = PyBoy(work, window='null')
        pb.set_emulation_speed(0)
        frame = [0]
        staged = []
        captures = {}

        def at_stager(_ctx=None):
            staged.append((frame[0], pb.register_file.HL))

        pb.hook_register(14, 0x400D, at_stager, None)
        for value in range(frames):
            frame[0] = value
            button = BOOT.get(value) or actions.get(value)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if value in capture_frames:
                captures[value] = pb.screen.image.copy()
        lcdc = pb.memory[0xFF40]
        pb.stop(save=False)
    return staged, captures, lcdc


def _counts(image, crop=None):
    grey = image.convert('L')
    if crop:
        grey = grey.crop(crop)
    pixels = list(grey.getdata())
    return (sum(pixel < 96 for pixel in pixels),
            sum(pixel > 224 for pixel in pixels))


def town(rom_path, ram_path, png=None):
    staged, shots, lcdc = _run(
        rom_path, ram_path, {2610: 'a', 2850: 'a'}, 3100,
        {2849, 2900}, patch_stairs=False)
    problems = []
    post = [hl for frame, hl in staged if frame >= 2500]
    if ADDR not in post:
        problems.append('town talk never staged %s' % LOC)
    before, after = shots.get(2849), shots.get(2900)
    if before is None or after is None:
        problems.append('town screenshots were not captured')
    else:
        dark_before, white_before = _counts(before, (0, 104, 160, 144))
        dark_after, white_after = _counts(after, (0, 104, 160, 144))
        if white_before < 5000 or dark_before < 50:
            problems.append('town message was not visibly complete')
        if dark_after < 3000 or white_after > 2000:
            problems.append('one A left an empty dialogue box open')
        if png:
            root, ext = os.path.splitext(png)
            before.save(root + '_town_message' + (ext or '.png'))
            after.save(root + '_town_closed' + (ext or '.png'))
    if not lcdc & 0x80:
        problems.append('town route ended with LCD disabled')
    print('koppatalkspill: town staged %s; one-press close; %d problem(s)'
          % (' '.join('$%04X' % value for value in post) or '(none)', len(problems)))
    return problems


def dungeon(rom_path, ram_path, png=None):
    staged, shots, lcdc = _run(
        rom_path, ram_path, {2610: 'right', 2850: 'a'}, 3070,
        {2849, 3049}, patch_stairs=True)
    problems = []
    post = [hl for frame, hl in staged if frame >= 2500]
    if ADDR not in post:
        problems.append('diagnostic dungeon caller never staged %s' % LOC)
    message, floor_card = shots.get(2849), shots.get(3049)
    if message is None or floor_card is None:
        problems.append('dungeon screenshots were not captured')
    else:
        dark_message, white_message = _counts(message, (0, 104, 160, 144))
        dark_card, white_card = _counts(floor_card)
        if white_message < 5000 or dark_message < 50:
            problems.append('dungeon message was not visibly complete')
        if white_card < 20000 or dark_card < 25:
            problems.append('one A did not reach the next-floor card')
        if png:
            root, ext = os.path.splitext(png)
            message.save(root + '_dungeon_message' + (ext or '.png'))
            floor_card.save(root + '_dungeon_floor' + (ext or '.png'))
    if not lcdc & 0x80:
        problems.append('dungeon route ended with LCD disabled')
    print('koppatalkspill: dungeon probe staged %s; one-press floor advance; %d problem(s)'
          % (' '.join('$%04X' % value for value in post) or '(none)', len(problems)))
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--town-ram', default=os.path.join(ROOT, 'saves', TOWN_SAVE))
    parser.add_argument('--dungeon-ram', default=os.path.join(ROOT, 'saves', DUNGEON_SAVE))
    parser.add_argument('--png')
    args = parser.parse_args()
    for path in (args.rom, args.town_ram, args.dungeon_ram):
        if not os.path.exists(path):
            raise SystemExit('koppatalkspill: missing %s' % path)
    problems = verify_record(args.rom)
    problems.extend(town(args.rom, args.town_ram, args.png))
    problems.extend(dungeon(args.rom, args.dungeon_ram, args.png))
    for problem in problems:
        print('koppatalkspill: ' + problem)
    print('koppatalkspill: %d total problem(s)' % len(problems))
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
