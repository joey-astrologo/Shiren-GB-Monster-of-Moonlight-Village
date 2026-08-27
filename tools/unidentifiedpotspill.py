#!/usr/bin/env python3
"""Guard the seven-row Floor action box: an identity-hidden Pot, and its Info return.

``saves/shiren_en_log3_unidentified_pot_crash.srm`` stands Log 3 on an unidentified Pot.
That single item produces the only seven-row action box in the game: a Pot contributes
``See`` and ``Push``, and a hidden identity inserts ``Name``, giving
``Take/See/Push/Toss/Swap/Name/Info``.

The renderer used to cap a box at SIX proportional rows (``shapeok``'s ``cp $06``), so
``Info`` fell out to the fixed-width fallback.  That was not a cosmetic loss.  A fallback
row never reached the floor-info hook, so dismissing the description could leave the LCD
off permanently.  The screen-7 lifecycle also used to enter and return through two
explicit whole-LCD blanks.  It now restores the covered Floor header, draws Info chrome
before publishing its text, carries a private transaction through the disposable screen
0 replay, and reconstructs box 5 plus box 6 before revealing the seven Action rows.

Two independent assertions, because either alone would have missed the bug:

* every one of the seven rows is offered to the proportional allocator, ``Info`` included;
* neither transition reaches the explicit LCD blanker or leaves LCDC bit 7 clear;
* the replay dispatches screen 0 and screen 7 with the private transaction still armed;
* the settled return reproduces the exact outgoing BG and Window tilemaps and pixels.

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
FULL_TOP = bytes((0xB8,)) + bytes((0xBC,)) * 18 + bytes((0xB9,))
FULL_BOTTOM = bytes((0xBA,)) + bytes((0xBD,)) * 18 + bytes((0xBB,))
# The genuine hidden-Pot route is the proven screen-7 alternate Floor parent, not
# screen 20.  Both formerly catalogued whole-LCD blanks are now regional transactions.
EXPECTED_INFO_BLANKS = ()


def staged(pb, source, limit=16):
    out = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            break
        out.append(value)
    return ''.join(DECODE.get(value, '?') for value in out).strip()


def run(rom_path, ram_path, png=None, frames=FRAMES, trace=False):
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
        lcd_off_frames = []
        explicit_blanks = []
        dispatches = []
        lifecycle = []
        checkpoints = {}

        def stack():
            depth = pb.memory[0xC534]
            return tuple(pb.memory[0xC535 + index] for index in range(depth + 1))

        def dispatch(_ctx=None):
            dispatches.append((frame[0], pb.register_file.A, pb.memory[0xC1B3],
                               pb.memory[0xC1B6], stack()))

        def life(label):
            def capture(_ctx=None):
                lifecycle.append((
                    frame[0], label, pb.register_file.A, pb.register_file.D,
                    pb.register_file.HL, pb.memory[0xFF40], pb.memory[0xC1B1],
                    pb.memory[0xC1B3], pb.memory[0xC1B4], pb.memory[0xC1B5],
                    pb.memory[0xC1B6], pb.memory[0xC6A3], pb.memory[0xC6BB],
                    stack(), tuple(pb.memory[address]
                                   for address in range(0xC69A, 0xC69F))))
            return capture

        def resolved(refs):
            return tuple(b''.join(bytes(pb.memory[menuspill.tile_data_addr(tile):
                                                 menuspill.tile_data_addr(tile) + 16])
                                  for tile in row)
                         for row in refs)

        def bg_refs():
            return tuple(bytes(pb.memory[0x9800 + row * 0x20:
                                         0x9814 + row * 0x20])
                         for row in range(16))

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
        pb.hook_register(4, 0x48AA, dispatch, None)
        info_labels = menuvwf.info_lifecycle_labels()
        pb.hook_register(
            menuvwf.ACTION_BLANK_BANK, info_labels['fidisable'],
            lambda _ctx=None: explicit_blanks.append((
                frame[0], pb.memory[0xC6A3], pb.memory[0xC1B1],
                pb.memory[0xC1B3], pb.memory[0xC1B6], pb.memory[0xC6DE],
                pb.memory[0xC6AC], pb.memory[0xC6BB],
                tuple(pb.memory[0xC535 + index]
                      for index in range(pb.memory[0xC534] + 1)),
                tuple(pb.memory[address] for address in range(0xC69A, 0xC69F)))), None)
        for label in ('infotry', 'infoboxdone', 'infopublishrowdone',
                      'infopublish', 'infopop', 'inforeturn',
                      'inforeturn20publish', 'inforeturn7start',
                      'inforeturn7publish', 'inforeturn7ready',
                      'info7header', 'info7chrome', 'info7chromedone',
                      'info20chrome'):
            pb.hook_register(menuvwf.ACTION_BLANK_BANK, info_labels[label],
                             life(label), None)

        for step in range(frames):
            frame[0] = step
            if step in (3299, 3500, 3699, 3900):
                bg = bg_refs()
                window = tuple(bytes(pb.memory[0x9C00 + row * 0x20:
                                               0x9C14 + row * 0x20])
                               for row in range(2))
                checkpoints[step] = (
                    pb.memory[0xC6A3], pb.memory[0xFF40], stack(),
                    bg, resolved(bg), window, resolved(window))
            button = BOOT.get(step)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if 3299 <= step <= SETTLED and not pb.memory[0xFF40] & 0x80:
                lcd_off_frames.append(step)

        lcdc = pb.memory[0xFF40]
        transaction = pb.memory[0xC1B3]
        if png:
            pb.screen.image.save(png)
            print('unidentifiedpotspill: wrote %s' % png)
        pb.stop(save=False)

    if trace:
        print('unidentifiedpotspill: dispatches %s' % (dispatches,))
        for event in lifecycle:
            print('unidentifiedpotspill: lifecycle %r' % (event,))
        parent_pixels = checkpoints.get(3299, (None, None, None, None, (), (), ()))[4]
        for at, state in sorted(checkpoints.items()):
            screen, state_lcdc, state_stack, bg, pixels, _window, _window_pixels = state
            changed = tuple(index for index, pair in enumerate(zip(parent_pixels, pixels))
                            if pair[0] != pair[1])
            right = tuple(row[13:20] for row in bg)
            print('unidentifiedpotspill: checkpoint f%d screen=%d LCDC=$%02X stack=%s '
                  'right=%s changed-pixel-rows=%s' %
                  (at, screen, state_lcdc, state_stack,
                   '/'.join(row.hex() for row in right), changed))

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

    # ---- freeze the exact regional lifecycle, including the otherwise easy-to-miss
    # disposable screen 0.  A generic failure there used to clear state $0B one screen
    # too soon and let screen 7 redraw outside the regional publisher.
    replay = tuple((screen, state, phase, call_stack)
                   for _at, screen, state, phase, call_stack in dispatches
                   if _at >= 3700)
    expected_replay = ((0, 0x0B, 0, (0, 7)), (7, 0x0B, 0, (0, 7)))
    if replay[:2] != expected_replay:
        problems.append('Info return dispatch replay is %s, expected exact armed '
                        'screen 0 -> screen 7 sequence %s' % (replay[:2], expected_replay))

    def event_index(label, screen=None, after=-1):
        for index, event in enumerate(lifecycle):
            if index <= after or event[1] != label:
                continue
            if screen is None or event[11] == screen:
                return index
        return None

    entry_header = event_index('info7header', 4)
    entry_box = event_index('infoboxdone', 4)
    entry_publish = event_index('infopublish', 4)
    if None in (entry_header, entry_box, entry_publish) or not (
            entry_header < entry_box < entry_publish):
        problems.append('screen-7 Info entry lifecycle is header=%s, box=%s, publish=%s; '
                        'the covered header and complete box must precede text publication'
                        % (entry_header, entry_box, entry_publish))

    return_start = event_index('inforeturn7start', 7)
    return_chrome = event_index('info7chrome', 7)
    return_chrome_done = event_index('info7chromedone', 7)
    return_publish = event_index('inforeturn7publish', 7)
    return_order = (return_start, return_chrome, return_chrome_done, return_publish)
    if None in return_order or tuple(sorted(return_order)) != return_order:
        problems.append('screen-7 Info return lifecycle order is %s; expected start, '
                        'complete empty chrome, then final publication' % (return_order,))
    if event_index('inforeturn7publish', 0) is not None:
        problems.append('disposable screen 0 attempted the screen-7 final publisher')

    info = checkpoints.get(3500)
    if info is not None:
        bg = info[3]
        expected_info_chrome = {
            0: FULL_TOP, 2: FULL_BOTTOM,
            3: FULL_TOP, 13: FULL_BOTTOM,
        }
        bad_chrome = [row for row, expected in expected_info_chrome.items()
                      if bg[row] != expected]
        bad_chrome.extend(row for row in (1,) + tuple(range(4, 13))
                          if bg[row][0] != 0xBE or bg[row][19] != 0xBF)
        if bad_chrome:
            problems.append('settled screen-7 Info has incomplete full-width chrome on '
                            'row(s) %s' % bad_chrome)

    # ---- and the description's return transaction must actually publish
    if not lcdc & 0x80:
        problems.append('LCDC=$%02X after the Info description closed: bit 7 is clear, so '
                        'publishmap never ran and the screen is dead' % lcdc)
    if transaction != 0x00:
        problems.append('$C1B3=$%02X after the return redraw, expected $00: the '
                        'Info->action transaction never completed' % transaction)
    if lcd_off_frames:
        problems.append('LCDC bit 7 was clear after frame(s) %s during the regional '
                        'Info entry/return interval' % lcd_off_frames)
    blank_states = tuple(event[1:] for event in explicit_blanks)
    if blank_states != EXPECTED_INFO_BLANKS:
        problems.append('explicit Info LCD blank states are %s, expected catalogued '
                        'screen-7 entry/return %s' %
                        (blank_states, EXPECTED_INFO_BLANKS))

    parent = checkpoints.get(3299)
    returned = checkpoints.get(3900)
    if parent is None or returned is None:
        problems.append('missing outgoing or returned visual checkpoint')
    else:
        for index, label in ((3, 'BG tilemap'), (4, 'BG resolved pixels'),
                             (5, 'Window tilemap'), (6, 'Window resolved pixels')):
            if parent[index] != returned[index]:
                problems.append('settled Info return does not reproduce the outgoing %s'
                                % label)

    for problem in problems:
        print('  ' + problem)
    print('unidentifiedpotspill: %d-row action box, rows offered %s/%s, LCDC=$%02X, '
          '$C1B3=$%02X, explicit blanks=%d; %d problem(s)'
          % (ACTION_ROWS, len(offers.get(True, {})), ACTION_ROWS, lcdc, transaction,
             len(explicit_blanks), len(problems)))
    if problems:
        raise SystemExit('unidentifiedpotspill: %d problem(s)' % len(problems))
    print('unidentifiedpotspill: seven-row identity-hidden Pot box is fully proportional; '
          'screen-7 Info entry/return is regional and reproduces its exact parent')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--ram', default=RAM)
    parser.add_argument('--png')
    parser.add_argument('--trace', action='store_true')
    args = parser.parse_args()
    for path in (args.rom, args.ram):
        if not os.path.exists(path):
            raise SystemExit('unidentifiedpotspill: missing %s' % path)
    run(args.rom, args.ram, png=args.png, trace=args.trace)


if __name__ == '__main__':
    main()
