#!/usr/bin/env python3
"""Guard the seven-row Floor action box: an identity-hidden Pot, and its Info return.

``saves/shiren_en_log3_unidentified_pot_crash.srm`` stands Log 3 on an unidentified Pot.
That single item produces the only seven-row action box in the game: a Pot contributes
``See`` and ``Push``, and a hidden identity inserts ``Name``, giving
``Take/See/Push/Toss/Swap/Name/Info``.

The renderer used to cap a box at SIX proportional rows (``shapeok``'s ``cp $06``), so
``Info`` fell out to the fixed-width fallback.  That was not a cosmetic loss.  A fallback
row never reaches the floor-info hook, so ``fiborder`` never observed ``D == [$C69C]-1``,
``fifinish``/``publishmap`` never ran, and ``publishmap`` is the ONLY site that re-enables
the LCD.  Dismissing the description therefore left ``$C1B3`` pinned at ``$04`` with LCDC
bit 7 clear: a permanent white screen with the CPU still running.  Joey found it in play.

Two independent assertions, because either alone would have missed the bug:

* every one of the seven rows is offered to the proportional allocator, ``Info`` included;
* the LCD is back on after the description closes, and ``$C1B3`` has returned to ``$00``.

The route is the player's: Adventure -> down -> down -> Log 3 -> Continue -> Menu ->
Floor -> action -> Info -> dismiss.
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


RAM = os.path.join(ROOT, 'saves', 'shiren_en_log3_unidentified_pot_crash.srm')
BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a',                                    # Adventure
    380: 'down', 460: 'down', 540: 'a',          # -> Log 3
    700: 'a',                                    # Continue
    2600: 'b', 2700: 'down', 2800: 'a',          # Menu -> Floor -> action box
    2880: 'down', 2940: 'down', 3000: 'down',
    3060: 'down', 3120: 'down', 3180: 'down',    # -> Info
    3300: 'a',                                   # Info -> description
    3700: 'a',                                   # dismiss -> return transaction
}
FRAMES = 4100
SETTLED = 3900               # by here the return redraw has published or it never will
ACTION_ROWS = 7
ROW_LABELS = ('Take', 'See', 'Push', 'Toss', 'Swap', 'Name', 'Info')
DECODE = {code: ch for ch, code in propvwf.EN_CODES.items()}


def staged(pb, source, limit=16):
    out = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            break
        out.append(value)
    return ''.join(DECODE.get(value, '?') for value in out).strip()


def run(rom_path, ram_path, png=None, frames=FRAMES):
    profile = menuspill.renderer_profile(rom_path)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('unidentifiedpotspill: requires the Dot proportional renderer')

    PyBoy = _import_pyboy()
    problems = []
    with tempfile.TemporaryDirectory(prefix='unidentifiedpotspill-') as tmp:
        run_rom = os.path.join(tmp, 'pot.gb')
        shutil.copyfile(rom_path, run_rom)
        shutil.copyfile(ram_path, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null')
        pb.set_emulation_speed(0)

        frame = [0]
        rows = {}
        offers = {}
        current = {'row': None}
        lcd_off_from = [None]

        # A row that clears the per-box row cap publishes its destination to $C0D9/$C0DA
        # before composing; a row that falls back never does.  Matching that against the
        # destination the drawer was called with identifies served rows without depending
        # on the gate's address, which moves whenever the emitted helper is re-laid out.
        def on_row(_ctx=None):
            shape = pb.memory[0xC69C]
            if shape == ACTION_ROWS:
                index = pb.register_file.D
                current['row'] = (index, pb.register_file.HL)
                rows.setdefault(frame[0] > 3400, set()).add(index)
            else:
                current['row'] = None

        def on_row_end(_ctx=None):
            # Sampled at the drawer's epilogue: once per row, so rows that share a frame
            # are still counted separately.
            if current['row'] is None:
                return
            index, destination = current['row']
            published = pb.memory[0xC0D9] | (pb.memory[0xC0DA] << 8)
            if published == destination:
                offers.setdefault(frame[0] > 3400, {})[index] = destination
            current['row'] = None

        pb.hook_register(31, menuvwf.ROW_DRAWER, on_row, None)
        pb.hook_register(31, menuvwf.ROW_EPILOG, on_row_end, None)

        for step in range(frames):
            frame[0] = step
            button = BOOT.get(step)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if step > 3700 and lcd_off_from[0] is None and not pb.memory[0xFF40] & 0x80:
                lcd_off_from[0] = step
            elif pb.memory[0xFF40] & 0x80:
                lcd_off_from[0] = None

        lcdc = pb.memory[0xFF40]
        transaction = pb.memory[0xC1B3]
        if png:
            pb.screen.image.save(png)
            print('unidentifiedpotspill: wrote %s' % png)
        pb.stop(save=False)

    # ---- the box must be seven rows, and every row must reach the allocator
    for after, label in ((False, 'initial draw'), (True, 'Info return')):
        drawn = rows.get(after, set())
        if drawn != set(range(ACTION_ROWS)):
            problems.append('%s drew rows %s, expected 0-%d'
                            % (label, sorted(drawn), ACTION_ROWS - 1))
        served = offers.get(after, {})
        missing = [index for index in range(ACTION_ROWS) if index not in served]
        if missing:
            problems.append(
                '%s: row(s) %s reached no proportional allocation, so %s fell back to '
                'fixed width -- the fallback row also skips the floor-info hook that '
                'closes the LCD transaction'
                % (label, ', '.join('%d (%s)' % (i, ROW_LABELS[i]) for i in missing),
                   'they' if len(missing) > 1 else ROW_LABELS[missing[0]]))

    # ---- and the description's return transaction must actually publish
    if not lcdc & 0x80:
        problems.append('LCDC=$%02X after the Info description closed: bit 7 is clear, so '
                        'publishmap never ran and the screen is dead' % lcdc)
    if transaction != 0x00:
        problems.append('$C1B3=$%02X after the return redraw, expected $00: the '
                        'Info->action transaction never completed' % transaction)

    for problem in problems:
        print('  ' + problem)
    print('unidentifiedpotspill: %d-row action box, rows offered %s/%s, LCDC=$%02X, '
          '$C1B3=$%02X; %d problem(s)'
          % (ACTION_ROWS, len(offers.get(True, {})), ACTION_ROWS, lcdc, transaction,
             len(problems)))
    if problems:
        raise SystemExit('unidentifiedpotspill: %d problem(s)' % len(problems))
    print('unidentifiedpotspill: seven-row identity-hidden Pot box is fully proportional '
          'and its Info return re-enables the LCD')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('unidentifiedpotspill: missing %s' % path)
    run(args.rom, args.ram, png=args.png)


if __name__ == '__main__':
    main()
