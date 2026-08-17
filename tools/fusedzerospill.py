#!/usr/bin/env python3
"""Guard the zero-seal fusion mark ``$8B`` on a real fused item row.

A fused item appends ``$8B + seal_count`` to its name, arithmetically: ``$8B`` is zero
seals and ``$94`` is nine.  The renderer admitted only ``$8C-$94``, because the nine
ability bits in the canonical weapon/shield masks were read as the number of reachable
values rather than the maximum.  Fusing two items that carry no seals produces exactly the
unconsidered case, and because ``$8B`` was not an admitted code the proportional scanner
rejected the WHOLE row: ``saves/shiren_en_log2_weapon_VWF_break.srm`` drew its equipped
``Nagamaki`` in fixed width with ``$8B`` painted through the English font as a stray latin
glyph.  Joey found it in play; ``fusioncountspill.py`` did not, because it exercises the
counts ``$8C-$94`` and never the mark that zero produces.

The row is asserted two ways, since the visible fallback and the cause are different
things:

* ``$8B`` is present in the staged row and the row passes the proportional eligibility
  model, so the scanner cannot silently drop it again;
* the row composes to VWF tiles rather than raw source codes, which is what the player
  actually sees.

Route: Adventure -> down -> Log 2 -> Continue -> Menu -> Items.
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
import propvwf                                                    # noqa: E402


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log2_weapon_VWF_break.srm')
BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a',                       # Adventure
    380: 'down', 540: 'a',          # -> Log 2
    700: 'a',                       # Continue
    3000: 'b', 3150: 'a',           # Menu -> Items
}
FRAMES = 3600
ZERO_SEAL = 0x8B
ITEM_NAME = 'Nagamaki'
DECODE = {code: ch for ch, code in propvwf.EN_CODES.items()}


def run(rom_path, ram_path, png=None, frames=FRAMES):
    profile = menuspill.renderer_profile(rom_path)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('fusedzerospill: requires the Dot proportional renderer')

    PyBoy = _import_pyboy()
    with tempfile.TemporaryDirectory(prefix='fusedzerospill-') as tmp:
        run_rom = os.path.join(tmp, 'fused.gb')
        shutil.copyfile(rom_path, run_rom)
        shutil.copyfile(ram_path, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null')
        pb.set_emulation_speed(0)
        for step in range(frames):
            button = BOOT.get(step)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()

        row = []
        for address in range(menuspill.STAGING, menuspill.STAGING + 24):
            value = pb.memory[address]
            if value == 0xFF:
                break
            row.append(value)
        # Row 0 is two raw cells (equipped marker, cursor) followed by the scanned source.
        scanned = row[2:]
        # The shadow tilemap holds raw source codes where a row fell back, and composed
        # VWF tile ids where it did not.
        painted = bytes(pb.memory[0xC38C:0xC39C])
        if png:
            pb.screen.image.save(png)
            print('fusedzerospill: wrote %s' % png)
        pb.stop(save=False)

    problems = []
    text = ''.join(DECODE.get(code, '?') for code in scanned)
    if ITEM_NAME not in text:
        problems.append('staged row %r does not contain %s -- the route did not reach the '
                        'fused item' % (text, ITEM_NAME))
    if ZERO_SEAL not in scanned:
        problems.append('staged row carries no $%02X, so this save no longer exercises a '
                        'zero-seal fusion' % ZERO_SEAL)
    if ZERO_SEAL not in menuvwf.FUSED_CODES:
        problems.append('$%02X is not in FUSED_CODES %s -- zero seals is a reachable count'
                        % (ZERO_SEAL, ' '.join('$%02X' % c for c in menuvwf.FUSED_CODES)))
    if not menuspill.eligible(scanned):
        bad = [code for code in scanned
               if not (code < 0x43 or code in menuspill.ELIGIBLE_EXTRA)]
        problems.append('the proportional scanner rejects the row (%d glyphs, ineligible '
                        '%s), so the whole item name falls back to fixed width'
                        % (len(scanned), ' '.join('$%02X' % c for c in bad) or 'none'))
    if any(code in painted for code in scanned if code >= 0x43):
        problems.append('the shadow tilemap still holds raw source codes, so the row was '
                        'drawn by the fixed-width fallback rather than composed')

    for problem in problems:
        print('  ' + problem)
    print('fusedzerospill: staged %r (%d glyphs), $%02X present=%s, eligible=%s; '
          '%d problem(s)'
          % (text, len(scanned), ZERO_SEAL, ZERO_SEAL in scanned,
             menuspill.eligible(scanned), len(problems)))
    if problems:
        raise SystemExit('fusedzerospill: %d problem(s)' % len(problems))
    print('fusedzerospill: a fusion carrying zero seals composes proportionally')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('fusedzerospill: missing %s' % path)
    run(args.rom, args.ram, png=args.png)


if __name__ == '__main__':
    main()
