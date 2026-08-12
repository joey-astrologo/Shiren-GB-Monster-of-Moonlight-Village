#!/usr/bin/env python3
"""Check the name-entry grid's cursor -> character lookup against the built ROM's layout.

31:$4186 picks a grid base ($4275 hiragana / $42F0 katakana in the original), then
31:$41A0 adds (row-1) * $13 + col to it. $13 = 19 is the ORIGINAL row stride: 18 bytes of
text plus a terminator. Once the rows are translated they are exactly 18 cells, so they
fill the box, `needs_term` drops their terminators and the built stride becomes 18 -- but
the constant is still 19, so every row below the first reads one byte further along.

Hooks 31:$41B0, where hl is the address the game decided to read, and compares it with
where that character actually is.
"""
import argparse, os, shutil, sys, tempfile

def _import_pyboy():
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path[:] = [p for p in sys.path if os.path.abspath(p or '.') != here]
    m = sys.modules.get('dis')
    if m is not None and not hasattr(m, 'COMPILER_FLAG_NAMES'):
        del sys.modules['dis']
    import pyboy
    return pyboy.PyBoy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from latinfont import EN_CODES
CH = {v: k for k, v in sorted(EN_CODES.items(), reverse=True)}
sys.path.pop(0)

ap = argparse.ArgumentParser()
ap.add_argument('rom')
ap.add_argument('--frames', type=int, default=1700)
ap.add_argument('--base', type=lambda s: int(s, 16),
                help='box 12 row-1 base in the built ROM; default: derive 31:$418D operand')
ap.add_argument('--row', type=int, default=1, help='grid row to walk (1-5)')
ap.add_argument('--toggle', action='store_true',
                help='select the aliased page-2 lookup directly')
ap.add_argument('--png')
ap.add_argument('--stride', type=int, default=18, help='expected built row stride')
args = ap.parse_args()

PyBoy = _import_pyboy()
tmp = tempfile.TemporaryDirectory(prefix='shiren-gridprobe-')
work = os.path.join(tmp.name, 'fresh.gb')
shutil.copyfile(args.rom, work)       # no adjacent .ram: deterministic blank-cart route
pb = PyBoy(work, window='null')
pb.set_emulation_speed(0)

rom = open(args.rom, 'rb').read()
BANK = 31
if args.base is None:
    ptr_at = BANK * 0x4000 + (0x418E - 0x4000)
    if rom[ptr_at - 1] != 0x21:       # 31:$418D `ld hl,nn`
        raise SystemExit('gridprobe: expected page-1 `ld hl,nn` at 31:$418D')
    args.base = rom[ptr_at] | (rom[ptr_at + 1] << 8)

def rom_at(addr):
    return rom[BANK * 0x4000 + (addr - 0x4000)]

seen = []
def on_lookup(ctx):
    hl = pb.register_file.HL
    col = pb.memory[0xC6F0]
    row = pb.memory[0xC6F5]
    page = bool(pb.memory[0xC6F3] & 0x80)
    seen.append((row, col, hl, page))

pb.hook_register(BANK, 0x41B0, on_lookup, None)

# Reach name entry on a private blank cartridge, then write the picker's cursor variables
# directly. Counting d-pad presses made the old test dependent on cartridge-save contents
# and silently left it in an Erase confirmation while reporting zero wrong lookups because
# it had observed no lookups at all. Three samples span the left/middle/right blocks; one
# row per run stays below the six-character field limit.
press = [('start', 700, 4), ('start', 760, 4), ('start', 820, 4), ('start', 880, 4),
         ('a', 1320, 4), ('a', 1450, 4), ('a', 1600, 4)]
toggle_at = 1680 if args.toggle else None
sample_cols = (0, 6, 13)
samples = {1725 + i * 70: (args.row, col) for i, col in enumerate(sample_cols)}
last_sample = max(samples)

sched = {}
for btn, at, hold in press:
    sched.setdefault(at, []).append((btn, hold))
for i in range(max(args.frames, last_sample + 150)):
    if i == toggle_at:
        pb.memory[0xC6F3] = pb.memory[0xC6F3] | 0x80
    if i in samples:
        row, col = samples[i]
        pb.memory[0xC6F5] = row
        pb.memory[0xC6F0] = col
        pb.button('a', 5)
    for btn, hold in sched.get(i, ()):
        pb.button(btn, hold)
    pb.tick()
if args.png:
    pb.screen.image.save(args.png)
pb.stop(save=False)
tmp.cleanup()

# The real layout: rows are 18 bytes with no terminator once translated.
print('%-10s %-8s %-8s %s' % ('cursor', 'read', 'correct', 'char read / char wanted'))
bad = 0
observed = set()
for row, col, hl, page in sorted(set(seen)):
    if not 0x4200 <= hl <= 0x4400 or row == 0:
        continue
    observed.add((row, col))
    want = args.base + (row - 1) * args.stride + col
    g = lambda a: CH.get(rom_at(a), '?')
    flag = '' if hl == want else '   <-- WRONG'
    if hl != want or page != args.toggle:
        bad += 1
        if page != args.toggle:
            flag += '   <-- WRONG PAGE'
    print('r%d c%-2d    $%04X    $%04X    %r / %r  page %d%s'
          % (row, col, hl, want, g(hl), g(want), 2 if page else 1, flag))
expected = {(args.row, col) for col in sample_cols}
missing = sorted(expected - observed)
if missing:
    bad += len(missing)
    print('missing lookup(s): %s' % ' '.join('r%d/c%d' % x for x in missing))
print('\n%d problem(s), %d of %d required lookup(s) observed'
      % (bad, len(observed & expected), len(expected)))
raise SystemExit(1 if bad else 0)
