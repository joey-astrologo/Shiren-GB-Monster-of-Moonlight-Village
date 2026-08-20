#!/usr/bin/env python3
"""Verify the proportional standing stair/trap command box.

The real dispatcher screen 3 supplies Proceed/Stay. A second run changes only its staged
row-0 payload to the translated Trigger source, exercising statusvwf's context gate and
requiring Trigger/Back. Both runs use the game's box producer, drawer, queue and map.
When Joey's Log-1 trap SRAM is present, a third run boots it normally and exercises the
actual Menu -> Trap route without injection.
"""

import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gbrun import _import_pyboy, PRESS_FRAMES
from latinfont import EN_CODES
import menuspill
import menuvwf


STATE = os.path.join(ROOT, 'saves', 'dungeon.state')
TRAP_RAM = os.path.join(ROOT, 'saves', 'shiren_en_log1_trap_menu.srm')
EXIT_RAM = os.path.join(ROOT, 'saves', 'shiren_en_log2_exit_menu.srm')
STAIRS_RAM = os.path.join(ROOT, 'saves', 'shiren_en_log2_stairs_menu.srm')
DISPATCH = (4, 0x48AA)
BGMAP = 0x9800
POPUP_SHAPE = bytes((3, 4, 2, 6, 0))


def encoded(text):
    return bytes(EN_CODES[ch] for ch in text)


def staged_row(pb, source, limit=24):
    out = []
    for address in range(source, source + limit):
        value = pb.memory[address]
        if value == 0xFF:
            break
        out.append(value)
    return bytes(out)


def run_case(PyBoy, rom, state, trap=False, png=None):
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(state, 'rb') as src:
        pb.load_state(src)
    profile = menuspill.renderer_profile(rom)
    forced = [False]
    injected = [False]
    calls = []
    frame = [0]

    def dispatch(_ctx=None):
        if not forced[0]:
            pb.register_file.A = 3
            forced[0] = True

    def entry(_ctx=None):
        if trap and pb.register_file.D == 0 and not injected[0]:
            data = b'\x00' + encoded('Trigger') + b'\xFF\x00' + encoded('Stay') + b'\xFF'
            for index, value in enumerate(data):
                pb.memory[0xC616 + index] = value
            injected[0] = True
        calls.append((frame[0], pb.register_file.D,
                      bytes(pb.memory[0xC69A:0xC69F])))

    pb.hook_register(*DISPATCH, dispatch, None)
    pb.hook_register(menuvwf.FAR_BANK, profile['entry'], entry, None)
    lcd = []
    for current in range(110):
        frame[0] = current
        if current == 60:
            pb.button('b', PRESS_FRAMES)
        pb.tick()
        if current >= 58:
            lcd.append((current, pb.memory[0xFF40]))
    image = pb.screen.image.copy()
    bg = bytes(pb.memory[BGMAP:BGMAP + 32 * 18])
    staged = bytes(pb.memory[0xC616:0xC630])
    tiles = {tile: bytes(pb.memory[menuspill.tile_data_addr(tile):
                                  menuspill.tile_data_addr(tile) + 16])
             for tile in range(0x43, 0x7C)}
    pb.stop(save=False)

    problems = []
    words = ('Trigger', 'Back') if trap else ('Proceed', 'Stay')
    if [row for _f, row, shape in calls if shape == POPUP_SHAPE] != [0, 1]:
        problems.append('%s popup did not draw exact widened rows 0/1: %s' %
                        (words[0], calls))
    if trap:
        want = b'\x00' + encoded('Trigger') + b'\xFF\x00' + encoded('Back') + b'\xFF'
        if staged[:len(want)] != want:
            problems.append('trap staging is %s, expected Trigger/Back %s' %
                            (staged[:len(want)].hex(' '), want.hex(' ')))
    if not lcd or not lcd[-1][1] & 0x80:
        problems.append('%s popup did not settle with the LCD enabled' % words[0])

    for row, word in enumerate(words):
        screen_row = 5 + row * 2
        cells = bg[screen_row * 32 + 4:screen_row * 32 + 10]
        if cells[0] not in (0, 0x81):
            problems.append('%s row lost its raw cursor cell ($%02X)' % (word, cells[0]))
        composed = menuspill.compose(list(encoded(word)), profile)
        cap = len(composed)
        bases = cells[1:1 + cap]
        if not bases or bases != bytes(range(bases[0], bases[0] + cap)):
            problems.append('%s map is not one contiguous %d-tile VWF record: %s' %
                            (word, cap, cells.hex(' ')))
            continue
        for index, want in enumerate(composed):
            if tiles[bases[0] + index] != bytes(want):
                problems.append('%s tile $%02X is not plane-exact' %
                                (word, bases[0] + index))
                break
        if any(cells[1 + cap:]):
            problems.append('%s leaves nonblank cells after its VWF extent: %s' %
                            (word, cells.hex(' ')))

    if png:
        image.save(png)
    return problems, words, calls


def real_route(log_downs):
    route = {
        60: 'start', 120: 'start', 180: 'start', 240: 'start',
        300: 'a', 420: 'a', 480: 'a',
        2620: 'b', 2700: 'down', 2780: 'a',
    }
    for step in range(log_downs):
        route[360 + step * 30] = 'down'
    return route


def run_real_ground(PyBoy, rom, ram, log_downs, menu_word, words, png=None):
    """Boot a supplied SRAM and exercise its real ground-object command route."""
    profile = menuspill.renderer_profile(rom)
    problems = []
    route = real_route(log_downs)
    with tempfile.TemporaryDirectory(prefix='groundpopup-real-') as tmp:
        work = os.path.join(tmp, 'ground.gb')
        shutil.copyfile(rom, work)
        shutil.copyfile(ram, work + '.ram')
        pb = PyBoy(work, window='null', cgb=True)
        pb.set_emulation_speed(0)
        frame = [0]
        dispatches = []
        calls = []
        menu_calls = []

        def dispatch(_ctx=None):
            dispatches.append((frame[0], pb.register_file.A))

        def entry(_ctx=None):
            shape = bytes(pb.memory[0xC69A:0xC69F])
            source = pb.memory[0xC69F] | (pb.memory[0xC6A0] << 8)
            data = staged_row(pb, source)
            if shape == POPUP_SHAPE:
                calls.append((frame[0], pb.register_file.D, pb.register_file.HL,
                              source, data))
            elif 2620 <= frame[0] < 2780 and encoded(menu_word) in data:
                menu_calls.append((frame[0], pb.register_file.D, pb.register_file.HL,
                                   source, data))

        pb.hook_register(*DISPATCH, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], entry, None)
        for current in range(3060):
            frame[0] = current
            button = route.get(current)
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()

        if png:
            pb.screen.image.save(png)
        if not any(screen == 3 for _at, screen in dispatches):
            problems.append('real %s route never dispatched screen 3' % menu_word)
        want_menu = bytes((0,)) + encoded(menu_word)
        exact_menu = [call for call in menu_calls if call[4] == want_menu]
        if len(exact_menu) != 1:
            problems.append('real menu staged %s for %s, expected one %s row' %
                            ([call[4].hex(' ') for call in menu_calls], menu_word,
                             want_menu.hex(' ')))
        elif not menuspill.visible_row_matches(
                pb, profile, exact_menu[0][2], encoded(menu_word), raw=1):
            problems.append('real %s menu label is not plane-exact VWF' % menu_word)
        if [row for _at, row, _key, _source, _data in calls] != [0, 1]:
            problems.append('real %s rows are %s, expected 0/1' %
                            (menu_word,
                             [row[1] for row in calls]))
        for expected_row, word in enumerate(words):
            matching = [call for call in calls if call[1] == expected_row]
            if len(matching) != 1:
                continue
            at, _row, key, source, data = matching[0]
            want = bytes((0,)) + encoded(word)
            directional_input = (expected_row == 0 and word == 'Proceed' and
                                 data in (bytes((0,)) + encoded('Up'),
                                          bytes((0,)) + encoded('Down')))
            if data != want and not directional_input:
                problems.append('real %s row at f%d/$%04X staged %s, expected %s' %
                                (word, at, source, data.hex(' '), want.hex(' ')))
            if not menuspill.visible_row_matches(
                    pb, profile, key, encoded(word), raw=1):
                problems.append('real %s row is not plane-exact VWF' % word)
        bad = menuspill.frame_invariant(pb, profile)
        if bad:
            problems.append('real %s popup leaves %d ownership problem(s): %s' %
                            (menu_word, len(bad), bad[:8]))
        pb.stop(save=False)
    return problems, dispatches, calls, menu_calls


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--state', default=STATE)
    parser.add_argument('--trap-ram', default=TRAP_RAM)
    parser.add_argument('--exit-ram', default=EXIT_RAM)
    parser.add_argument('--stairs-ram', default=STAIRS_RAM)
    parser.add_argument('--png-dir')
    args = parser.parse_args()
    if args.png_dir:
        os.makedirs(args.png_dir, exist_ok=True)
    PyBoy = _import_pyboy()
    problems = []
    for trap in (False, True):
        png = (os.path.join(args.png_dir, 'trap.png' if trap else 'stairs.png')
               if args.png_dir else None)
        found, words, calls = run_case(PyBoy, args.rom, args.state, trap, png)
        problems.extend(found)
        print('groundpopupspill: %s/%s rows=%d; %d problem(s)' %
              (words[0], words[1], len(calls), len(found)))
    real_cases = (
        ('Trap', args.trap_ram, 0, ('Trigger', 'Back'), 'trap-real.png'),
        ('Exit', args.exit_ram, 1, ('Proceed', 'Stay'), 'exit-real.png'),
        ('Stairs', args.stairs_ram, 1, ('Proceed', 'Stay'), 'stairs-real.png'),
    )
    for menu_word, ram, log_downs, words, png_name in real_cases:
        if not ram or not os.path.exists(ram):
            continue
        png = os.path.join(args.png_dir, png_name) if args.png_dir else None
        found, dispatches, calls, menu_calls = run_real_ground(
            PyBoy, args.rom, ram, log_downs, menu_word, words, png)
        problems.extend(found)
        print('groundpopupspill: real %s %s/%s dispatches=%s menu=%d rows=%d; '
              '%d problem(s)' %
              (menu_word, words[0], words[1],
               ' '.join('f%d:%d' % event for event in dispatches), len(menu_calls),
               len(calls), len(found)))
    for problem in problems:
        print('  ' + problem)
    raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    main()
