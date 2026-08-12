#!/usr/bin/env python3
"""Drive the name-entry screen deterministically and report every buffer the name lives in.

No walk seed reaches name entry, and counting d-pad presses to spell a name is how the
first three attempts at this typed `hire` instead of `Shiren` -- the header row does not
respond to `right` the way the letter rows do, and one miscounted press silently types the
wrong character. So the navigation is:

  title -> file menu -> New Log -> Log 1 -> Easy   (name entry is up by frame ~1610)

and the letters are chosen by WRITING the picker's cursor variables, which nothing else
touches while no direction is held:

  $C6F5  grid row, 0 = the retired toggle / Fwd / Bck / End header, 1-5 = character rows
  $C6F0  grid column, a 0-based cell index into the 18-cell row (read at 31:$4195)
  $C6F4  header cursor; 4:$652B maps it through the table at 4:$6543 to the action in
         $C6F3's low nibble -- 0 CAPS, 1 Fwd, 2 Bck, 3 End

What it prints, and why each one matters:

  $C6E2  packed: HIGH NIBBLE = field width, low nibble = cursor column. The 4-character
         limit is this byte -- `4:$5E91 ld a,$40`. 4:$6150 also uses the width to pick
         WHICH box to draw, so a wider field already has a wider box in the ROM.
  $C6E3  the entry line as drawn: 2x width cells of $88 blank, then $FF
  $CF81  display form, $FF-terminated, a dakuten kana following its base as $79/$7A
  $D0FD  packed form, one byte per character. It was $D100 and 4 bytes; tools/name6.py
         rehomes it BACKWARD because $D104 starts a live 120-byte block

`--end` confirms the name, which is the New Log save path (`4:$7618` -> `15:$5183`), and
`--sram` then writes the cartridge RAM out and reports the name as it landed in the save
record. That is the check the three-byte prototype could not pass: it typed six characters
and saved four. `--reload` boots the ROM again from that RAM and photographs file select,
which is the other half -- the name has to come back out through the summary.

Examples:
    python3 tools/namerun.py build/shiren_en.gb --name Shiren --end --png /tmp/n.png
    python3 tools/namerun.py build/shiren_en.gb --name ABCDEZ
    python3 tools/namerun.py build/shiren_en.gb --name Shiren --end --sram --reload
"""
import argparse, os, shutil, sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from latinfont import EN_CODES
sys.path.remove(TOOLS)
CH = {v: k for k, v in sorted(EN_CODES.items(), reverse=True)}
WANT = dict(EN_CODES)           # char -> the byte a correctly saved name holds
# pyboy's dependencies import the stdlib `dis`, which tools/dis.py shadows.
sys.path[:] = [p for p in sys.path if os.path.abspath(p or '.') != TOOLS]
import pyboy

# The built picker, straight off box 12's rows in script/en.tsv. Row 0 is the header and
# is addressed through $C6F4, not $C6F0, so it is excluded from the character map. The
# three visible blocks occupy columns 0-4, 6-10 and 13-17; every listed position is
# selectable, so the rows deliberately contain no accidental gaps inside those blocks.
ROWS = ['      Fwd Bck  End',
        'ABCDE Zabcd  yz.,\'',
        'FGHIJ efghi  -!?()',
        'KLMNO jklmn  :/[]+',
        'PQRST opqrs  01234',
        'UVWXY tuvwx  56789']
SELECTABLE_COLS = tuple(range(5)) + tuple(range(6, 11)) + tuple(range(13, 18))
assert all(len(row) == 18 for row in ROWS), 'every name-entry row must be exactly 18 cells'
assert all(row[5] == row[11] == row[12] == ' ' for row in ROWS[1:]), \
       'the three navigation-gap columns must remain blank'
selectable = [(r, c, ROWS[r][c]) for r in range(1, 6) for c in SELECTABLE_COLS]
assert all(ch != ' ' for _, _, ch in selectable), 'a selectable name cell is blank'
assert len({ch for _, _, ch in selectable}) == len(selectable), \
       'every selectable name character must occur exactly once'
WHERE = {ch: (r, c) for r, c, ch in selectable}

FIRST, STEP = 1700, 70          # first A press, and frames per character
NAV = {700: 'start', 760: 'start', 820: 'start', 880: 'start',
       1250: 'down',            # "New Log" sits under "Adventure" while a save exists
       1320: 'a', 1450: 'a', 1600: 'a'}     # New Log, Log 1, Easy
# On a cart with no save the menu is New Log / Rank+Pass / Fay's Puzzles, so there is nothing
# to move down past. `--fresh` is the run that exercises the NEW-GAME path end to end --
# 15:$4E03's template copy, which tools/name6.py turned into a far call.
NAV_FRESH = {k: v for k, v in NAV.items() if v != 'down'}
# Rename is the OTHER way into the entry field, and it is a different routine: New Log
# arrives through `4:$5E6E` with an empty $CF81, Rename arrives with the log already
# chosen. Main menu with saves: Adventure / New Log / Copy Log / Erase Log / Rename / ...
NAV_RENAME = {700: 'start', 760: 'start', 820: 'start', 880: 'start',
              1250: 'down', 1290: 'down', 1330: 'down', 1370: 'down',
              1420: 'a', 1600: 'a'}                 # Rename, then log 1
END_COL = 12                    # a header column 4:$6543 maps to the "End" action

# The save record, as tools/name6.py lays it out. Slot 0 is the log New Log overwrites,
# and the record's name field is at offset 2. SRAM banks are 8 KiB in the .ram file.
SRAM_BANK, SLOT0, NAME_AT, NAME_LEN = 2, 0xA700, 2, 6
BUF = 0xD0FD                    # the packed buffer, post-name6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('--name', default='Shiren')
    ap.add_argument('--end', action='store_true',
                    help='press End afterwards and run on into the game')
    ap.add_argument('--png')
    ap.add_argument('--frames', type=int, default=900, help='frames to run after End')
    ap.add_argument('--fresh', action='store_true',
                    help='the cart has no save: skip the `down` past Adventure')
    ap.add_argument('--rename', action='store_true',
                    help='reach the field through the main menu Rename entry instead')
    ap.add_argument('--ram',
                    help='cartridge RAM to boot from, copied to <rom>.ram first. The press '
                         'schedule below depends on what the cart already holds, so a run '
                         'that writes a save is NOT repeatable without this')
    ap.add_argument('--sram', action='store_true',
                    help='save cartridge RAM on exit and report the saved name record')
    ap.add_argument('--reload', action='store_true',
                    help='boot again from that RAM and photograph file select')
    args = ap.parse_args()
    if args.reload and not (args.sram and args.end):
        raise SystemExit('--reload needs --end --sram: there is nothing to reload without '
                         'a confirmed name and a written save')

    unknown = [c for c in args.name if c not in WHERE]
    if unknown:
        raise SystemExit('the picker has no key for %r' % ''.join(unknown))

    if args.ram:
        shutil.copyfile(args.ram, args.rom + '.ram')
    pb = pyboy.PyBoy(args.rom, window='null')
    pb.set_emulation_speed(0)

    def txt(b):
        return ''.join('_' if c == 0x88 else CH.get(c, '.') for c in b)

    def dump(tag):
        m = pb.memory
        print('%-14s C6E2=$%02X (width %d, cursor col %d)'
              % (tag, m[0xC6E2], m[0xC6E2] >> 4, m[0xC6E2] & 0xF))
        for label, lo, hi in (('C6E3', 0xC6E3, 0xC6F0), ('CF81', 0xCF81, 0xCF8B),
                              ('%04X' % BUF, BUF, BUF + 7), ('D104', 0xD104, 0xD110)):
            b = bytes(m[lo:hi])
            print('               %s %-40s %s' % (label, b.hex(' '), txt(b)))

    nav = NAV_RENAME if args.rename else NAV_FRESH if args.fresh else NAV
    steps = [WHERE[c] + (None,) for c in args.name]
    if args.end:
        steps.append((0, None, END_COL))
    end_at = FIRST + STEP * len(steps)
    stop = end_at + (args.frames if args.end else 200)

    for i in range(stop):
        if FIRST <= i < end_at:
            row, col, hdr = steps[(i - FIRST) // STEP]
            pb.memory[0xC6F5] = row
            if col is not None:
                pb.memory[0xC6F0] = col
            if hdr is not None:
                pb.memory[0xC6F4] = hdr
            if (i - FIRST) % STEP == 25:
                pb.button('a', 5)
        elif i in nav:
            pb.button(nav[i], 10 if nav[i] == 'down' else 4)
        if i == end_at - STEP - 10:
            dump('typed')
        pb.tick()

    dump('final')
    if args.png:
        pb.screen.image.save(args.png)
    pb.stop(save=bool(args.sram))

    if not args.sram:
        return
    ram = args.rom + '.ram'
    blob = open(ram, 'rb').read()
    at = SRAM_BANK * 0x2000 + (SLOT0 + NAME_AT - 0xA000)
    saved = blob[at:at + NAME_LEN]
    print('saved record   %s slot 0 name at SRAM $%04X: %s  %s'
          % (os.path.basename(ram), SLOT0 + NAME_AT, saved.hex(' '), txt(saved)))
    want = bytes(WANT[c] for c in args.name)
    ok = saved.startswith(want) and (len(want) == NAME_LEN or saved[len(want)] == 0xFF)
    print('               %s -- the save %s the typed name'
          % ('OK' if ok else 'MISMATCH', 'holds' if ok else 'does NOT hold'))

    if not args.reload:
        return
    pb = pyboy.PyBoy(args.rom, window='null')
    pb.set_emulation_speed(0)
    # start x4 to the main menu, then `a` on Adventure: the log list is where a saved
    # name is drawn, out of the summary buffer rather than out of the entry field.
    # `a` on Adventure regardless of --fresh: the run just wrote a log, so the menu now
    # has one whether or not the cart started with one.
    for i in range(1800):
        if i in (700, 760, 820, 880, 1300):
            pb.button('a' if i == 1300 else 'start', 4)
        pb.tick()
    out = args.png and args.png.replace('.png', '_reload.png') or '/tmp/name_reload.png'
    pb.screen.image.save(out)
    print('reloaded       file select photographed at %s' % out)
    pb.stop(save=False)


if __name__ == '__main__':
    main()
