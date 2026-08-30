#!/usr/bin/env python3
"""Prove the exact screen-1 Item/Floor Action -> Info -> parent lifecycle.

Checkpoint 4's regional transaction admits exact screen-1 Item/Floor parents and the
screen-20 Floor picker, while Pot contents, shop, and unknown Info callers stay excluded.
This fixture drives the screen-1
screen-1 parents; ``floorinfospill.py`` separately audits the repaired legacy Floor
publisher:

* a carried Hyakki Shield opens Info on page 1 and leaves with B;
* a hidden Bracer reaches page 2, opens its five-row Action box, and leaves Info with B;
* a hidden Pot reaches page 4, opens its six-row Action box, and leaves Info with B;
* the standing Wood Arrow Floor page advances both Info pages and leaves the final page
  with A.

Both routes require complete empty Info chrome before text publication, retain the
completed outgoing page through the disposable Status replay, then commit complete empty
Item/Floor chrome before the replayed text. They must return to the originating page and
selection with a live hardware Window, prompt post-return input, and no LCD-off or
all-white frame.
"""

import argparse
import os
import shutil
import sys
import tempfile


TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

from gbrun import PRESS_FRAMES, _import_pyboy                    # noqa: E402
import gbasm                                                       # noqa: E402
import dotfont                                                      # noqa: E402
import menuspill                                                   # noqa: E402
import menuvwf                                                     # noqa: E402
import statusvwf                                                   # noqa: E402


HELD_RAM = os.path.join(ROOT, 'saves', 'shiren_en_log_1_shield_VWF.srm')
HELD_PAGE2_RAM = os.path.join(ROOT, 'saves', 'shiren_en_log_1_dragons_maw.srm')
FLOOR_RAM = os.path.join(ROOT, 'saves', 'shiren_en_item_menu_wood_arrow.srm')
REAL_SEALED_RAM = os.path.join(ROOT, 'saves',
                               'shiren_log3_unidentified_naming.srm')
REAL_DROP_RAM = os.path.join(ROOT, 'saves',
                             'shiren_en_log3_carried_unidentified_naming.srm')
FUSION_STATE = os.path.join(ROOT, 'saves', 'dungeon.state')
INVENTORY = 0xA3B0
OBJECTS = 0xA406
BOOT = {
    60: 'start', 120: 'start', 180: 'start', 240: 'start',
    300: 'a', 420: 'a', 480: 'a', 2620: 'b',
}
ITEM_SHAPE = (0, 3, 5, 18, 0x02)
ACTION_PREFIX = (13, 1)
ACTION_SUFFIX = (5, 0x02)
INFO_TOP = bytes((0xB8,)) + bytes((0xBC,)) * 18 + bytes((0xB9,))
INFO_SIDE = bytes((0xBE,)) + bytes(18) + bytes((0xBF,))
INFO_BOTTOM = bytes((0xBA,)) + bytes((0xBD,)) * 18 + bytes((0xBB,))


def visible_row(tilemap, row):
    return tilemap[row * 32:row * 32 + 20]


def snapshot(pb):
    return {
        'bg': bytes(pb.memory[0x9800:0x9C00]),
        'window': bytes(pb.memory[0x9C00:0xA000]),
        'tiles': bytes(pb.memory[0x8800:0x9800]),
        'shadow': bytes(pb.memory[0xC300:0xC700]),
        'lcdc': pb.memory[0xFF40],
        'ly': pb.memory[0xFF44],
    }


def resolved(state, layer, row, col):
    tile = state[layer][row * 32 + col]
    start = menuspill.tile_data_addr(tile) - 0x8800
    return tile, state['tiles'][start:start + 16]


def visible_equal(left, right, layer, rows):
    return all(resolved(left, layer, row, col) ==
               resolved(right, layer, row, col)
               for row in rows for col in range(20))


def visible_pixels_equal(left, right, layer, rows):
    return all(resolved(left, layer, row, col)[1] ==
               resolved(right, layer, row, col)[1]
               for row in rows for col in range(20))


def white_frame(image):
    return len(set(image.convert('RGB').getdata())) == 1


def info_blank_problems(state, label):
    problems = []
    expected = {3: INFO_TOP, 13: INFO_BOTTOM}
    expected.update((row, INFO_SIDE) for row in range(4, 13))
    for row, want in sorted(expected.items()):
        got = visible_row(state['bg'], row)
        if got != want:
            problems.append('%s empty Info row %d is %s, expected %s' %
                            (label, row, got.hex(' '), want.hex(' ')))
            break
    return problems


def target_blank_problems(state, floor, label):
    problems = []
    header_top = bytes((0xB8,)) + bytes((0xBC,)) * 4 + bytes((0xB9,)) + bytes(14)
    header_side = bytes((0xBE,)) + bytes(4) + bytes((0xBF,)) + bytes(14)
    header_bottom = bytes((0xBA,)) + bytes((0xBD,)) * 4 + bytes((0xBB,)) + bytes(14)
    expected = {0: header_top, 1: header_side, 2: header_bottom,
                3: INFO_TOP}
    if floor:
        expected.update({4: INFO_SIDE, 5: INFO_BOTTOM})
        expected.update((row, bytes(20)) for row in range(6, 16))
    else:
        expected.update((row, INFO_SIDE) for row in range(4, 13))
        expected[13] = INFO_BOTTOM
        expected.update((row, bytes(20)) for row in range(14, 16))
    for row, want in sorted(expected.items()):
        got = visible_row(state['bg'], row)
        if got != want:
            problems.append('%s empty parent row %d is %s, expected %s' %
                            (label, row, got.hex(' '), want.hex(' ')))
            break
    return problems


def runtime_labels():
    _code, labels = gbasm.assemble(menuvwf.INFO_LIFECYCLE_SRC,
                                   menuvwf.INFO_LIFECYCLE_AT)
    return labels


def pager_digit_pixels(digit):
    """Approved 1bpp digit duplicated into the Game Boy's two bitplanes."""
    return bytes(value for row in dotfont.load_approved().glyphs[str(digit)]
                 for value in (row, row))


def run_fusion_pager_case(PyBoy, rom, profile, labels, state_path, frames=1400):
    """Exercise Fusion Pot's five pages, footer ownership, and one-tap Down semantics."""
    problems = []
    pb = PyBoy(rom, window='null')
    pb.set_emulation_speed(0)
    with open(state_path, 'rb') as source:
        pb.load_state(source)

    frame = [0]
    schedule = {60: 'b', 120: 'a'}
    injected = [False]
    phase = [0]
    info_press = [None]
    publishes = []
    pending = []
    settled = []
    lcd_off = []
    down_press = [None]
    first_deliberate_after_down = [None]
    page_handlers = []
    legacy_blankers = []
    status_blankers = []

    def inject(_context=None):
        if injected[0]:
            return
        free = [index for index in range(128)
                if pb.memory[OBJECTS + 8 * index] == 0xFF]
        if len(free) < 2:
            return
        records = (
            (0x87, 2, 0, 0x04, 0, 0, 0xFF, 0xFF),  # Fusion Pot: five Info pages
            (0x06, 2, 0, 0xC4, 1, 0, 0xFF, 0xFF),
        )
        for ordinal, (object_index, record) in enumerate(zip(free[:2], records)):
            for offset, value in enumerate(record):
                pb.memory[OBJECTS + 8 * object_index + offset] = value
            pb.memory[INVENTORY + ordinal] = object_index
        pb.memory[INVENTORY + 2] = 0xFF
        injected[0] = True

    def render_entry(_context=None):
        shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
        row = pb.register_file.D
        if phase[0] == 0 and shape == ITEM_SHAPE and row == 4:
            schedule[frame[0] + 60] = 'a'
            phase[0] = 1
        elif (phase[0] == 1 and shape[:2] == ACTION_PREFIX and
              shape[3:] == ACTION_SUFFIX and row == shape[2] - 1):
            at = frame[0] + 50
            for _index in range(shape[2] - 1):
                schedule[at] = 'down'
                at += 50
            schedule[at] = 'a'
            info_press[0] = at
            phase[0] = 2

    def info_publish(_context=None):
        page = pb.memory[0xC6BC]
        total = pb.memory[0xC6BD]
        publishes.append((frame[0], page, total))
        pending.append((frame[0] + 20, page, total))
        if page == 0 and down_press[0] is None:
            down_press[0] = frame[0] + 60
            schedule[down_press[0]] = 'down'
        elif page == 1 and first_deliberate_after_down[0] is None:
            first_deliberate_after_down[0] = frame[0] + 80
            schedule[first_deliberate_after_down[0]] = 'a'
        else:
            schedule[frame[0] + 60] = 'a' if page + 1 < total else 'b'

    def page_handler(_context=None):
        page_handlers.append((frame[0], pb.memory[0xC6BC]))

    pb.hook_register(6, 0x4B29, inject, None)
    pb.hook_register(menuvwf.FAR_BANK, profile['entry'], render_entry, None)
    pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['infopublish'],
                     info_publish, None)
    pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['fidisable'],
                     lambda _context=None: legacy_blankers.append(frame[0]), None)
    status_labels = statusvwf.runtime_labels()
    pb.hook_register(statusvwf.FAR_BANK, status_labels['statusdisable'],
                     lambda _context=None: status_blankers.append(frame[0]), None)
    # mgbdis identifies 4:$5926 as the native screen-4 A/D-pad page handler.
    pb.hook_register(4, 0x5926, page_handler, None)

    for frame[0] in range(frames):
        button = schedule.get(frame[0])
        if button:
            pb.button(button, 1 if frame[0] == down_press[0] else PRESS_FRAMES)
        pb.tick()
        if info_press[0] is not None and frame[0] >= info_press[0] and \
                not pb.memory[0xFF40] & 0x80:
            lcd_off.append(frame[0])
        while pending and frame[0] >= pending[0][0]:
            _at, page, total = pending.pop(0)
            settled.append((page, total, snapshot(pb)))

    final_screen = pb.memory[0xC6A3]
    pb.stop(save=False)
    if legacy_blankers:
        problems.append('Fusion pager reached the explicit Info LCD blanker at %s' %
                        ' '.join('f%d' % at for at in legacy_blankers))
    if status_blankers:
        problems.append('Fusion pager return reached the explicit Status LCD blanker at %s' %
                        ' '.join('f%d' % at for at in status_blankers))

    if not injected[0]:
        problems.append('Fusion Pot pager fixture was not injected')
    expected_pages = tuple((page, 5) for page in range(5))
    if tuple(event[1:] for event in publishes) != expected_pages:
        problems.append('Fusion Pot publish sequence is %s, expected %s' %
                        (tuple(event[1:] for event in publishes), expected_pages))
    down_handlers = [event for event in page_handlers
                     if down_press[0] is not None and event[0] >= down_press[0] and
                     (first_deliberate_after_down[0] is None or
                      event[0] < first_deliberate_after_down[0])]
    if tuple(page for _at, page in down_handlers) != (0,):
        problems.append('one-frame Down invoked page handler as %s before the next '
                        'deliberate input, expected only page 0' %
                        (tuple(page for _at, page in down_handlers),))
    if tuple(event[:2] for event in settled) != expected_pages:
        problems.append('Fusion Pot settled sequence is %s, expected %s' %
                        (tuple(event[:2] for event in settled), expected_pages))
    for page, total, state in settled:
        footer = bytes(state['bg'][0x1B0:0x1B3])
        expected_footer = bytes((page + 2, 0xB0, total + 1))
        if footer != expected_footer:
            problems.append('Fusion Pot page %d footer map is %s, expected %s' %
                            (page + 1, footer.hex(' '),
                             expected_footer.hex(' ')))
            continue
        current_pixels = resolved(state, 'bg', 13, 16)[1]
        total_pixels = resolved(state, 'bg', 13, 18)[1]
        if current_pixels != pager_digit_pixels(page + 1):
            problems.append('Fusion Pot page %d current digit pixels differ' %
                            (page + 1))
        if total_pixels != pager_digit_pixels(total):
            problems.append('Fusion Pot page %d total digit pixels differ' %
                            (page + 1))
        for row in (4, 6, 8, 10, 12):
            start = row * 32 + 1
            if state['bg'][start:start + 18] != \
                    state['shadow'][start:start + 18]:
                problems.append('Fusion Pot page %d body row %d was not published '
                                'at its shadow position' % (page + 1, row))
                break
        leaked = next((row for row in (5, 7, 9, 11)
                       if visible_row(state['bg'], row) != INFO_SIDE), None)
        if leaked is not None:
            problems.append('Fusion Pot page %d leaked text/footer cells into '
                            'chrome row %d' % (page + 1, leaked))
    if lcd_off:
        problems.append('Fusion Pot pager disabled LCD at %s' %
                        ' '.join('f%d' % at for at in lcd_off[:16]))
    if final_screen == 4:
        problems.append('Fusion Pot pager did not return from Info')

    print('iteminfospill: fusion-pager pages %s; one-tap Down handlers %s; '
          'LCD-off %d; final screen %d' %
          (' '.join('%d/%d' % (page + 1, total)
                    for page, total, _state in settled),
           ' '.join('f%d:p%d' % event for event in down_handlers),
           len(lcd_off), final_screen))
    return problems


def run_real_sealed_short_page(PyBoy, rom, profile, labels, ram, frames=3900):
    """Use the manual-test SRAM for sealed final-A return, then expose short page 2."""
    problems = []
    with tempfile.TemporaryDirectory(prefix='iteminfospill-real-sealed-') as tmp:
        run_rom = os.path.join(tmp, 'real-sealed.gb')
        shutil.copyfile(rom, run_rom)
        shutil.copyfile(ram, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)
        frame = [0]
        schedule = {
            60: 'start', 120: 'start', 180: 'start', 240: 'start',
            300: 'a', 380: 'down', 460: 'down', 540: 'a', 700: 'a',
            2600: 'b', 2700: 'a',
        }
        phase = [0]
        info_publishes = []
        right_press = [None]
        dispatches = []
        explicit_blanks = []
        status_blanks = []
        lcd_off = []
        uniform = []

        def dispatch(_ctx=None):
            dispatches.append((frame[0], pb.register_file.A,
                               pb.memory[0xC6AC], pb.memory[0xC1B3]))

        def render(_ctx=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            row = pb.register_file.D
            screen = pb.memory[0xC6A3]
            if (phase[0] == 0 and screen == 1 and shape == ITEM_SHAPE and
                    row == 4 and pb.memory[0xC6AC] == 0):
                schedule[frame[0] + 90] = 'a'
                phase[0] = 1
            elif (phase[0] == 1 and screen == 2 and
                  shape[:2] == ACTION_PREFIX and shape[3:] == ACTION_SUFFIX and
                  row == shape[2] - 1):
                at = frame[0] + 70
                for _index in range(shape[2] - 1):
                    schedule[at] = 'down'
                    at += 60
                schedule[at] = 'a'
                phase[0] = 2

        def info_publish(_ctx=None):
            info_publishes.append((frame[0], pb.memory[0xC6BC],
                                   pb.memory[0xC6BD]))
            # This natural sealed item exits through screen 5's final-A handler.
            schedule[frame[0] + 90] = 'a'

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], render, None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['infopublish'],
                         info_publish, None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['fidisable'],
                         lambda _ctx=None: explicit_blanks.append(frame[0]), None)
        status_labels = statusvwf.runtime_labels()
        pb.hook_register(statusvwf.FAR_BANK, status_labels['statusdisable'],
                         lambda _ctx=None: status_blanks.append(frame[0]), None)

        for frame[0] in range(frames):
            button = schedule.get(frame[0])
            if button:
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if phase[0] >= 2:
                if not pb.memory[0xFF40] & 0x80:
                    lcd_off.append(frame[0])
                if white_frame(pb.screen.image):
                    uniform.append(frame[0])
            if (info_publishes and right_press[0] is None and
                    pb.memory[0xC6A3] == 1 and pb.memory[0xC1B3] == 0 and
                    frame[0] > info_publishes[-1][0] + 20):
                right_press[0] = frame[0] + 60
                schedule[right_press[0]] = 'right'

        selector = pb.memory[0xC6AC]
        item_count = pb.memory[0xC6AA]
        rows = []
        for row in range(5):
            bg_at = 0x9880 + row * 0x40
            shadow_at = 0xC380 + row * 0x40
            rows.append((bytes(pb.memory[bg_at:bg_at + 20]),
                         bytes(pb.memory[shadow_at:shadow_at + 20])))
        final_lcdc = pb.memory[0xFF40]
        pb.stop(save=False)

    screens = tuple(screen for _at, screen, _selector, _state in dispatches)
    if 5 not in screens or not any(screens[index:index + 3] == (0, 1, 1)
                                   for index in range(max(0, len(screens) - 2))):
        problems.append('real sealed final-A/right dispatches are %s' % (screens,))
    if len(info_publishes) != 1:
        problems.append('real sealed route published Info %d times' %
                        len(info_publishes))
    if explicit_blanks or status_blanks:
        problems.append('real sealed route reached explicit blankers %s/%s' %
                        (explicit_blanks, status_blanks))
    if lcd_off or uniform:
        problems.append('real sealed route produced LCD-off/uniform frames %s/%s' %
                        (lcd_off[:12], uniform[:12]))
    if (selector, item_count) != (5, 8):
        problems.append('real sealed short page settled selector/count %d/%d' %
                        (selector, item_count))
    # Eight carried items means page 2 owns rows 0-2. Every cell inside rows 3-4 must
    # be blank in both the visible map and shadow; this catches the old stray $88 at
    # row 4, column 18 even though the final screen otherwise looked settled.
    for row in (3, 4):
        bg, shadow = rows[row]
        expected = bytes((0xBE,)) + bytes(18) + bytes((0xBF,))
        if bg != expected or shadow != expected:
            problems.append('real sealed short-page row %d is %s/%s, expected %s' %
                            (row, bg.hex(' '), shadow.hex(' '), expected.hex(' ')))
    if not final_lcdc & 0x80:
        problems.append('real sealed short page ended with LCD disabled')
    print('iteminfospill: real-sealed-short final-A pages %s; selector/count %d/%d; '
          'blankers %d/%d; LCD-off %d, uniform %d' %
          (' '.join('%d/%d' % (page + 1, total)
                    for _at, page, total in info_publishes),
           selector, item_count, len(explicit_blanks), len(status_blanks),
           len(lcd_off), len(uniform)))
    return problems


def run_real_dropped_sealed_return(PyBoy, rom, profile, labels, ram, direct,
                                   frames=6200, png_dir=None):
    """Drop the fixture's sealed weapon normally, then finish its Floor Info pages.

    This deliberately does not inject or rewrite an object.  The ordinary Drop action
    crosses the intentional menu-to-gameplay boundary, after which the same object is
    reached through either Status -> Floor (screen 20) or Items' appended Floor page
    (screen 1).  The latter half reproduces the exact history which exposed the native
    2:$4621 display reconstruction after our regional return had already completed.
    """
    label = 'real-sealed-direct' if direct else 'real-sealed-appended'
    problems = []
    with tempfile.TemporaryDirectory(prefix='iteminfospill-%s-' % label) as tmp:
        run_rom = os.path.join(tmp, label + '.gb')
        shutil.copyfile(rom, run_rom)
        shutil.copyfile(ram, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        schedule = {
            60: 'start', 120: 'start', 180: 'start', 240: 'start',
            300: 'a', 380: 'down', 460: 'down', 540: 'a', 700: 'a',
            2600: 'b', 2700: 'a',
        }
        phase = [0]
        drop_press = [None]
        field_menu_press = [None]
        floor_action_press = [None]
        info_press = [None]
        final_press = [None]
        parent = [None]
        exact_return = [None]
        post_press = [None]
        post_accept = [None]
        reopen_press = [None]
        reopen_accept = [None]
        info_publishes = []
        dispatches = []
        native_reconfig = []
        explicit_blanks = []
        status_blanks = []
        lcd_off = []
        uniform = []
        applied = []
        info_attempts = []
        pop_attempts = []
        return_events = []
        def dispatch(_ctx=None):
            screen = pb.register_file.A
            dispatches.append((frame[0], screen, pb.memory[0xC6AC],
                               pb.memory[0xC1B3]))
            if phase[0] == 2 and screen == 0:
                # The Drop action has returned to the field and B has opened Status.
                at = frame[0] + 70
                if direct:
                    schedule[at] = 'down'
                    at += 70
                schedule[at] = 'a'
                phase[0] = 3
            elif phase[0] == 3 and direct and screen == 20:
                # Status -> Floor immediately constructs the standing item's Action
                # picker; there is no intermediate A press on a one-row Floor page.
                floor_action_press[0] = frame[0]
                phase[0] = 4
            if (direct and reopen_press[0] is not None and
                    frame[0] >= reopen_press[0] and screen == 0):
                reopen_accept[0] = frame[0]

        def render(_ctx=None):
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            row = pb.register_file.D
            screen = pb.memory[0xC6A3]
            selector = pb.memory[0xC6AC]
            if (phase[0] == 0 and screen == 1 and shape == ITEM_SHAPE and
                    row == 4 and selector == 0):
                schedule[frame[0] + 80] = 'a'
                phase[0] = 1
                return
            if (phase[0] == 1 and screen == 2 and shape == (13, 1, 4, 5, 2) and
                    row == 3):
                if png_dir:
                    os.makedirs(png_dir, exist_ok=True)
                    pb.screen.image.save(os.path.join(
                        png_dir, label + '-initial-action.png'))
                # Remove, Toss, Drop, Info: choose Drop without modifying the object.
                schedule[frame[0] + 70] = 'down'
                schedule[frame[0] + 140] = 'down'
                drop_press[0] = frame[0] + 210
                schedule[drop_press[0]] = 'a'
                phase[0] = 2
                return
            if phase[0] != 3:
                return
            if not direct and screen == 1 and shape == ITEM_SHAPE and row == 4:
                if selector != 0xFF:
                    schedule[frame[0] + 80] = 'right'
                    return
            if not direct and screen == 1 and selector == 0xFF:
                if (shape == ITEM_SHAPE and row == 4) or \
                        (shape == (0, 0, 1, 4, 0x50) and row == 0):
                    floor_action_press[0] = frame[0] + 90
                    parent[0] = snapshot(pb)
                    schedule[floor_action_press[0]] = 'a'
                    phase[0] = 4

        action_scheduled = [False]

        def action_render(_ctx=None):
            render()
            if phase[0] != 4 or action_scheduled[0]:
                return
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if (shape[0] != 13 or shape[2] < 3 or shape[2] > 7 or
                    shape[3:] != (5, 2)):
                return
            if pb.register_file.D != shape[2] - 1:
                return
            if png_dir:
                os.makedirs(png_dir, exist_ok=True)
                pb.screen.image.save(os.path.join(
                    png_dir, label + '-floor-action.png'))
            if parent[0] is None:
                # Direct Floor's parent includes the Action picker which remains
                # visible behind Info.  Capture it only after all six rows settle.
                parent[0] = snapshot(pb)
            at = frame[0] + 80
            for _index in range(shape[2] - 1):
                schedule[at] = 'down'
                at += 70
            info_press[0] = at
            schedule[at] = 'a'
            action_scheduled[0] = True
            phase[0] = 5

        def info_publish(_ctx=None):
            page = pb.memory[0xC6BC]
            total = pb.memory[0xC6BD]
            info_publishes.append((frame[0], page, total))
            at = frame[0] + 80
            schedule[at] = 'a'
            # Screen 5's seal-summary child reports the number of seal slots in C6BD;
            # it is still a single displayed page and this A is its automatic return.
            final_press[0] = at

        def native_display_reconfig(_ctx=None):
            if info_press[0] is not None and frame[0] >= info_press[0]:
                native_reconfig.append(frame[0])

        def info_try(_ctx=None):
            depth = pb.memory[0xC534]
            info_attempts.append((
                frame[0], pb.register_file.D, pb.register_file.HL,
                pb.memory[0xC6A3],
                tuple(pb.memory[0xC535 + index] for index in range(depth + 1)),
                pb.memory[0xC6A6], pb.memory[0xC6DE], pb.memory[0xC6AA],
                pb.memory[0xC6AC], pb.memory[0xC6BB], pb.memory[0xC6BC],
                pb.memory[0xC6BD], pb.memory[0xC1B3], pb.memory[0xC1B4],
                pb.memory[0xC1B5], pb.memory[0xC1B6], pb.memory[0xC1B7],
                tuple(pb.memory[0xC69A + i] for i in range(5))))

        def info_pop(_ctx=None):
            depth = pb.memory[0xC534]
            pop_attempts.append((
                frame[0], pb.register_file.HL, pb.memory[0xC6A3],
                tuple(pb.memory[0xC535 + index] for index in range(depth + 1)),
                pb.memory[0xC6DE], pb.memory[0xC6AC], pb.memory[0xC6BB],
                pb.memory[0xC6BC], pb.memory[0xC6BD], pb.memory[0xC1B3],
                pb.memory[0xC1B4], pb.memory[0xC1B5], pb.memory[0xC1B6]))

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], action_render, None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['infopublish'],
                         info_publish, None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['infotry'],
                         info_try, None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['infopop'],
                         info_pop, None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['inforeturn20owned'],
                         lambda _ctx=None: return_events.append(
                             (frame[0], '20-owned', pb.memory[0xC1B3])), None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['inforeturn20publish'],
                         lambda _ctx=None: return_events.append(
                             (frame[0], '20-publish', pb.memory[0xC1B3])), None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['inforeturnitemarmed'],
                         lambda _ctx=None: return_events.append(
                             (frame[0], 'item-armed', pb.memory[0xC1B3])), None)
        pb.hook_register(2, 0x463C, native_display_reconfig, None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['fidisable'],
                         lambda _ctx=None: explicit_blanks.append(frame[0]), None)
        status_labels = statusvwf.runtime_labels()
        pb.hook_register(statusvwf.FAR_BANK, status_labels['statusdisable'],
                         lambda _ctx=None: status_blanks.append(frame[0]), None)

        for frame[0] in range(frames):
            if direct and info_press[0] == frame[0]:
                # The direct parent retains its Action overlay and the selected Info
                # cursor. Capture after the five navigation presses, not while Take was
                # selected when the box first became complete.
                parent[0] = snapshot(pb)
            button = schedule.get(frame[0])
            if button:
                applied.append((frame[0], button, pb.memory[0xC6A3],
                                pb.memory[0xC6A6], pb.memory[0xC6AC],
                                tuple(pb.memory[0xC69A + i] for i in range(5))))
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if (png_dir and drop_press[0] is not None and
                    frame[0] == drop_press[0] - 180):
                pb.screen.image.save(os.path.join(
                    png_dir, label + '-initial-action-settled.png'))
            if (phase[0] == 2 and drop_press[0] is not None and
                    field_menu_press[0] is None and frame[0] > drop_press[0] + 500 and
                    pb.memory[0xC6A3] == 0xFF):
                field_menu_press[0] = frame[0] + 60
                schedule[field_menu_press[0]] = 'b'
            # The direct Floor B below deliberately crosses from the menu back to the
            # dungeon. Its native LCD-off font/terrain reload is required; scope the
            # no-blank contract to Info entry/return, before that boundary.
            in_menu_contract = (not direct or post_press[0] is None or
                                frame[0] < post_press[0])
            if (info_press[0] is not None and frame[0] >= info_press[0] and
                    in_menu_contract):
                if not pb.memory[0xFF40] & 0x80:
                    lcd_off.append(frame[0])
                if white_frame(pb.screen.image):
                    uniform.append(frame[0])
            if (final_press[0] is not None and frame[0] > final_press[0] + 20 and
                    exact_return[0] is None and parent[0] is not None and
                    pb.memory[0xC1B3] == 0 and pb.memory[0xC6AC] == 0xFF and
                    pb.memory[0xC11A] == 0):
                current = snapshot(pb)
                bg_equal = ((visible_pixels_equal if direct else visible_equal)(
                    parent[0], current, 'bg', range(16)))
                if (bg_equal and
                        visible_pixels_equal(parent[0], current, 'window', range(2))):
                    exact_return[0] = frame[0]
                    post_press[0] = frame[0] + 60
                    schedule[post_press[0]] = 'b' if direct else 'left'
            if post_press[0] is not None and frame[0] > post_press[0] and \
                    post_accept[0] is None:
                shape = tuple(pb.memory[0xC69A + i] for i in range(5))
                if ((direct and frame[0] >= post_press[0] + 60 and
                     pb.memory[0xC6A3] == 0xFF and pb.memory[0xFF40] & 0x80) or
                        (not direct and pb.memory[0xC6AC] != 0xFF)):
                    post_accept[0] = frame[0]
                    if direct:
                        reopen_press[0] = frame[0] + 60
                        schedule[reopen_press[0]] = 'b'

        final_screen = pb.memory[0xC6A3]
        final_state = (pb.memory[0xC1B3], pb.memory[0xC1B4],
                       pb.memory[0xC1B5], pb.memory[0xC1B6],
                       pb.memory[0xC1B7], pb.memory[0xC6AC],
                       tuple(pb.memory[0xC69A + i] for i in range(5)))
        final_lcdc = pb.memory[0xFF40]
        pb.stop(save=False)

    if drop_press[0] is None or field_menu_press[0] is None:
        problems.append('%s did not complete the natural Drop/field boundary' % label)
    if floor_action_press[0] is None or info_press[0] is None:
        problems.append('%s did not enter the real Floor Action/Info route' % label)
    if not info_publishes:
        problems.append('%s published no Info pages' % label)
    elif len(info_publishes) != 1 or info_publishes[0][1] != 0 or \
            info_publishes[0][2] < 2:
        problems.append('%s seal-summary publish is %s' %
                        (label, tuple(event[1:] for event in info_publishes)))
    if len(pop_attempts) != 1 or pop_attempts[0][9] != 3:
        problems.append('%s final-A regional pop attempts are %s' %
                        (label, pop_attempts))
    expected_return_event = '20-publish' if direct else 'item-armed'
    if not any(name == expected_return_event and state in (1, 9)
               for _at, name, state in return_events):
        problems.append('%s did not complete its %s lifecycle: %s' %
                        (label, expected_return_event, return_events))
    before_boundary = [at for at in native_reconfig
                       if post_press[0] is None or at < post_press[0]]
    after_boundary = [at for at in native_reconfig
                      if post_press[0] is not None and at >= post_press[0]]
    if before_boundary:
        problems.append('%s reached native LCD-off reconstruction inside the Info '
                        'transaction at %s' % (label, before_boundary))
    if direct and not after_boundary:
        problems.append('%s skipped the required native Floor-to-field reconstruction' %
                        label)
    if not direct and after_boundary:
        problems.append('%s reached native reconstruction on an appended-page input' %
                        label)
    if explicit_blanks or status_blanks:
        problems.append('%s reached explicit menu blankers %s/%s' %
                        (label, explicit_blanks, status_blanks))
    if lcd_off or uniform:
        problems.append('%s produced LCD-off/uniform frames %s/%s' %
                        (label, lcd_off[:12], uniform[:12]))
    if exact_return[0] is None or post_accept[0] is None:
        problems.append('%s did not restore the exact Floor parent/accept input' % label)
    if direct and reopen_accept[0] is None:
        problems.append('%s did not regain field input and reopen Status after Floor B' %
                        label)
    if not final_lcdc & 0x80:
        problems.append('%s ended with LCD disabled on screen %d' %
                        (label, final_screen))
    print('iteminfospill: %-20s pages %s; native menu/field %d/%d; exact/input/reopen '
          'f%s/f%s/f%s; LCD-off %d, uniform %d' %
          (label,
           ' '.join('%d/%d' % (page + 1, total)
                    for _at, page, total in info_publishes),
           len(before_boundary), len(after_boundary), exact_return[0], post_accept[0],
           reopen_accept[0], len(lcd_off), len(uniform)))
    if problems:
        print('iteminfospill: %s phase %d presses drop/field/floor/info/final %s; '
              'dispatches %s' %
              (label, phase[0],
               (drop_press[0], field_menu_press[0], floor_action_press[0],
                info_press[0], final_press[0]),
               dispatches))
        print('iteminfospill: %s applied tail %s' % (label, applied[-18:]))
        print('iteminfospill: %s Info attempts %s' % (label, info_attempts))
        print('iteminfospill: %s pop attempts %s' % (label, pop_attempts))
        print('iteminfospill: %s return events %s; final %s' %
              (label, return_events, final_state))
    return problems


def run_case(PyBoy, rom, profile, labels, label, ram, floor, png_dir=None,
             frames=5200, held_selector=0, action_rows=4,
             fusion_floor=False, fusion_inventory=False, sealed_floor=False,
             post_button=None, post_selector=None, final_button='b', info_pages=None):
    problems = []
    expected_pages = (info_pages if info_pages is not None else
                      (5 if fusion_floor else (2 if floor else 1)))
    expected_selector = 0xFF if floor else 0
    with tempfile.TemporaryDirectory(prefix='iteminfospill-') as tmp:
        run_rom = os.path.join(tmp, label + '.gb')
        shutil.copyfile(rom, run_rom)
        shutil.copyfile(ram, run_rom + '.ram')
        pb = PyBoy(run_rom, window='null', cgb=True)
        pb.set_emulation_speed(0)

        frame = [0]
        schedule = dict(BOOT)
        opened_items = [False]
        page_selectors = []
        action_started = [False]
        action_press = [None]
        info_press = [None]
        parent = [None]
        info_blank_commits = []
        info_box_commits = []
        info_attempts = []
        return_blank = []
        return_chrome = []
        return_attempts = []
        outgoing_info = [None]
        pop_calls = []
        pop_attempts = []
        dispatches = []
        post_press = [None]
        post_accept = [None]
        final_exact = [None]
        pot_action_press = [None]
        pot_see_press = [None]
        pot_back_press = [None]
        pot_parent = [None]
        pot_view = [None]
        pot_exact = [None]
        lcd_off = []
        white = []
        window_changes = []
        legacy_blankers = []
        status_blankers = []
        injected = [not (fusion_floor or fusion_inventory or sealed_floor)]

        def inject_fusion_floor(_ctx=None):
            if injected[0]:
                return
            carried = []
            for slot in range(20):
                index = pb.memory[INVENTORY + slot]
                if index == 0xFF:
                    break
                carried.append(index)
            ground = [index for index in range(128)
                      if index not in set(carried) and
                      pb.memory[OBJECTS + 8 * index] != 0xFF]
            if len(ground) != 1 or len(carried) < 5 or len(set(carried[:5])) != 5:
                return
            if sealed_floor:
                # Identified Manji Kabura+1 with one seal in the existing standing-item
                # slot. This retains the real saved route and changes only the object
                # class needed to exercise screen 5's final-A return from appended Floor.
                floor_record = (0x06, 1, 0, 0xC4, 1, 0, 0xFF, 0xFF)
                for offset, value in enumerate(floor_record):
                    pb.memory[OBJECTS + 8 * ground[0] + offset] = value
                injected[0] = True
                return
            records = (
                (0x3B, 0, 0, 0x04, 0, 0, 0xFF, 0xFF),  # Egg
                (0x3B, 0, 0, 0x04, 0, 0, 0xFF, 0xFF),  # Egg
                (0x2D, 3, 0, 0x84, 0, 0, 0xFF, 0xFF),  # Happy Bracer
                (0x87, 2, 0, 0x04, 0, 0, 0xFF, 0xFF),  # Fusion Pot[2]
                (0x06, 1, 0, 0xC4, 4, 0, 0xFF, 0xFF),  # Manji Kabura+1/seal
            )
            for index, record in zip(carried[:5], records):
                for offset, value in enumerate(record):
                    pb.memory[OBJECTS + 8 * index + offset] = value
            for index in carried[5:]:
                pb.memory[OBJECTS + 8 * index] = 0xFF
            pb.memory[INVENTORY + 5] = 0xFF
            # Identified Fusion Pot[2] in the standing-item record. This case reaches
            # it through the screen-1 paging carousel, not Status -> Floor screen 20.
            if fusion_floor:
                floor_record = (0x87, 2, 0, 0x80, 0, 0, 0xFF, 0xFF)
                for offset, value in enumerate(floor_record):
                    pb.memory[OBJECTS + 8 * ground[0] + offset] = value
            injected[0] = True

        def dispatch(_ctx=None):
            screen = pb.register_file.A
            dispatches.append((frame[0], screen))
            if screen == 0 and not opened_items[0]:
                schedule[frame[0] + 80] = 'a'
                opened_items[0] = True
            if fusion_floor and pot_action_press[0] is not None:
                if screen == 2 and pot_see_press[0] is None:
                    pot_see_press[0] = frame[0] + 80
                    schedule[pot_see_press[0]] = 'a'
                elif screen in (12, 13) and pot_back_press[0] is None:
                    pot_view[0] = screen
                    pot_back_press[0] = frame[0] + 80
                    schedule[pot_back_press[0]] = 'b'

        def item_row(_ctx=None):
            if action_started[0] or floor:
                return
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            selector = pb.memory[0xC6AC]
            if shape != ITEM_SHAPE or pb.register_file.D != 4 or selector % 5:
                return
            if page_selectors and page_selectors[-1][1] == selector:
                return
            page_selectors.append((frame[0], selector))
            target_page = held_selector // 5 * 5
            if selector < target_page:
                schedule[frame[0] + 90] = 'right'
                return
            if selector != target_page:
                return
            at = frame[0] + 90
            for _index in range(held_selector % 5):
                schedule[at] = 'down'
                at += 60
            action_press[0] = at
            schedule[action_press[0]] = 'a'
            action_started[0] = True

        def redraw_return(_ctx=None):
            if not floor or action_started[0] or not opened_items[0]:
                return
            selector = pb.memory[0xC6AC]
            latch = pb.memory[0xC1B7]
            if selector == 0xFF and latch == 1:
                action_press[0] = frame[0] + 90
                schedule[action_press[0]] = 'a'
                action_started[0] = True

        def page_complete(_ctx=None):
            if not floor or action_started[0]:
                return
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            selector = pb.memory[0xC6AC]
            if shape != ITEM_SHAPE or pb.register_file.D != 4:
                return
            if selector not in (0, 5, 10, 15):
                return
            if page_selectors and page_selectors[-1][1] == selector:
                return
            page_selectors.append((frame[0], selector))
            schedule[frame[0] + 90] = 'right'

        action_scheduled = [False]

        def action_row(_ctx=None):
            if not action_started[0] or action_scheduled[0]:
                return
            shape = tuple(pb.memory[address] for address in range(0xC69A, 0xC69F))
            if not (shape[:2] == ACTION_PREFIX and shape[3:] == ACTION_SUFFIX):
                return
            count = shape[2]
            if ((action_rows is not None and count != action_rows) or
                    pb.register_file.D != count - 1):
                return
            at = frame[0] + 60
            for _index in range(count - 1):
                schedule[at] = 'down'
                at += 60
            schedule[at] = 'a'
            info_press[0] = at
            action_scheduled[0] = True

        def render_entry(_ctx=None):
            item_row()
            page_complete()
            action_row()

        def info_publish(_ctx=None):
            state = snapshot(pb)
            info_blank_commits.append((frame[0], pb.memory[0xC6BC],
                                       pb.memory[0xC6BD], state))
            if len(info_blank_commits) < expected_pages:
                schedule[frame[0] + 60] = 'a'
            elif floor:
                schedule[frame[0] + 60] = 'a'
            else:
                schedule[frame[0] + 60] = final_button

        def info_box_done(_ctx=None):
            state = snapshot(pb)
            info_box_commits.append((frame[0], state))
            problems.extend(info_blank_problems(
                state, '%s page %d' % (label, len(info_box_commits))))

        def info_try(_ctx=None):
            info_attempts.append((
                frame[0], pb.register_file.D, pb.memory[0xC1B3], pb.memory[0xC1B6],
                pb.memory[0xC6A3], tuple(pb.memory[0xC534 + i] for i in range(5)),
                pb.memory[0xC6DE], pb.memory[0xC1B5], pb.memory[0xC6AC],
                pb.memory[0xC6AA], pb.memory[0xC1B7], pb.memory[0xFF40],
                pb.memory[0xFF42], pb.memory[0xFF43], pb.memory[0xFF4A],
                pb.memory[0xFF4B], pb.memory[0xC0D9], pb.memory[0xC0DA],
                tuple(pb.memory[0xC69A + i] for i in range(5)),
                pb.memory[0xC11A]))

        def info_pop(_ctx=None):
            pop_calls.append((frame[0], pb.memory[0xC1B3], pb.register_file.HL))

        def info_return(_ctx=None):
            mode = pb.register_file.A
            state = snapshot(pb)
            screen = pb.memory[0xC6A3]
            transaction = pb.memory[0xC1B3]
            admission = pb.memory[0xC1B6]
            row_mode = pb.memory[0xC1B1]
            shape = tuple(pb.memory[0xC69A + i] for i in range(5))
            return_attempts.append((frame[0], mode, pb.register_file.D,
                                    transaction, row_mode, screen,
                                    tuple(pb.memory[0xC534 + i] for i in range(3)),
                                    pb.memory[0xC0D9], pb.memory[0xC0DA],
                                    shape))
            if mode == 0:
                if not (transaction == 8 and admission == 1 and screen == 1 and
                        row_mode == 1 and
                        shape[:2] == (0, 3) and shape[2] in (1, 5) and
                        shape[3:] == (18, 2)):
                    return
                return_blank.append((frame[0], state))
                if outgoing_info[0] is not None and not visible_equal(
                        outgoing_info[0], state, 'bg', range(16)):
                    problems.append('%s changed the completed Info page before the '
                                    'screen-1 parent was ready' % label)

        def info_return_chrome(_ctx=None):
            state = snapshot(pb)
            return_chrome.append((frame[0], state))
            problems.extend(target_blank_problems(state, floor, label))

        def action_pop(_ctx=None):
            pop_attempts.append((frame[0], pb.register_file.A, pb.register_file.HL,
                                 pb.memory[0xC1B3], pb.memory[0xC6A3],
                                 tuple(pb.memory[0xC534 + i] for i in range(5))))

        pb.hook_register(4, 0x48AA, dispatch, None)
        pb.hook_register(6, 0x4B29, inject_fusion_floor, None)
        pb.hook_register(4, 0x4856, redraw_return, None)
        pb.hook_register(menuvwf.FAR_BANK, profile['entry'], render_entry, None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['infopublish'],
                         info_publish, None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['infoboxdone'],
                         info_box_done, None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['infotry'], info_try, None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['fidisable'],
                         lambda _ctx=None: legacy_blankers.append(frame[0]), None)
        status_labels = statusvwf.runtime_labels()
        pb.hook_register(statusvwf.FAR_BANK, status_labels['statusdisable'],
                         lambda _ctx=None: status_blankers.append(frame[0]), None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['infopop'], info_pop, None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['inforeturn'],
                         info_return, None)
        pb.hook_register(menuvwf.ACTION_BLANK_BANK, labels['inforeturnitemarmed'],
                         info_return_chrome, None)
        pb.hook_register(menuvwf.ACTION_POP_BANK, menuvwf.ACTION_POP_AT,
                         action_pop, None)

        for frame[0] in range(frames):
            if action_press[0] == frame[0]:
                parent[0] = snapshot(pb)
            if pot_action_press[0] == frame[0]:
                pot_parent[0] = snapshot(pb)
            button = schedule.get(frame[0])
            if button:
                if (button in ('a', 'b') and
                        pb.memory[0xC6A3] in (4, 5) and
                        pb.memory[0xC1B3] == 3):
                    outgoing_info[0] = snapshot(pb)
                pb.button(button, PRESS_FRAMES)
            pb.tick()
            if info_press[0] is not None and frame[0] >= info_press[0]:
                state = snapshot(pb)
                image = pb.screen.image.copy()
                # Entering Pot contents is an entirely new screen and retains its
                # native whole-screen transaction. Audit the regional Floor/Info
                # lifecycle before that entry and the See -> Items return after B.
                pot_entry = (fusion_floor and pot_action_press[0] is not None and
                             frame[0] >= pot_action_press[0] and
                             (pot_back_press[0] is None or
                              frame[0] < pot_back_press[0]))
                if not pot_entry:
                    if not state['lcdc'] & 0x80:
                        lcd_off.append(frame[0])
                    if white_frame(image):
                        white.append(frame[0])
                    if (parent[0] is not None and
                            state['window'] != parent[0]['window']):
                        window_changes.append(frame[0])
            if (return_chrome and final_exact[0] is None and parent[0] is not None and
                    pb.memory[0xC6A3] == 1 and pb.memory[0xC1B3] == 0 and
                    pb.memory[0xC11A] == 0):
                current = snapshot(pb)
                if (visible_equal(parent[0], current, 'bg', range(16)) and
                        visible_equal(parent[0], current, 'window', range(2))):
                    final_exact[0] = frame[0]
                    post_press[0] = frame[0] + 2
                    schedule[post_press[0]] = (post_button if post_button is not None else
                                               ('left' if floor else 'down'))
            if post_press[0] is not None and frame[0] >= post_press[0] and \
                    post_accept[0] is None:
                selector = pb.memory[0xC6AC]
                wanted = (post_selector if post_selector is not None else
                          ((0 if fusion_floor else 15) if floor else
                           held_selector + 1))
                if selector == wanted:
                    post_accept[0] = frame[0]
                    if fusion_floor:
                        at = frame[0] + 40
                        for _index in range(3):
                            schedule[at] = 'down'
                            at += 40
                        pot_action_press[0] = at + 40
                        schedule[pot_action_press[0]] = 'a'
            if (pot_back_press[0] is not None and frame[0] > pot_back_press[0] and
                    pot_exact[0] is None and pot_parent[0] is not None and
                    pb.memory[0xC6A3] == 1 and pb.memory[0xC1B3] == 0 and
                    pb.memory[0xC11A] == 0):
                current = snapshot(pb)
                if (visible_equal(pot_parent[0], current, 'bg', range(16)) and
                        visible_equal(pot_parent[0], current, 'window', range(2))):
                    pot_exact[0] = frame[0]
            if png_dir and info_press[0] is not None and \
                    info_press[0] <= frame[0] <= info_press[0] + 30:
                pb.screen.image.save(os.path.join(
                    png_dir, '%s_info_entry_f%04d.png' % (label, frame[0])))
            if png_dir and pop_calls and pop_calls[0][0] <= frame[0] <= pop_calls[0][0] + 40:
                pb.screen.image.save(os.path.join(
                    png_dir, '%s_info_return_f%04d.png' % (label, frame[0])))

        final = snapshot(pb)
        pb.stop(save=False)

    if parent[0] is None:
        problems.append('%s never captured its screen-1 parent' % label)
    if not injected[0]:
        problems.append('%s could not install the five-item Fusion inventory%s' %
                        (label, ' and standing Fusion Pot[2]' if fusion_floor else ''))
    expected_selectors = ((0,) if fusion_floor else
                          ((0, 5, 10, 15) if floor else
                           tuple(range(0, held_selector // 5 * 5 + 1, 5))))
    if tuple(selector for _at, selector in page_selectors) != expected_selectors:
        problems.append('%s carried page selectors are %s' %
                        (label, tuple(selector for _at, selector in page_selectors)))
    if len(info_blank_commits) != expected_pages:
        problems.append('%s published %d Info pages, expected %d' %
                        (label, len(info_blank_commits), expected_pages))
    elif tuple(total for _at, _page, total, _state in info_blank_commits) != \
            (expected_pages,) * expected_pages:
        problems.append('%s Info page totals are %s, expected %s' %
                        (label,
                         tuple(total for _at, _page, total, _state in info_blank_commits),
                         (expected_pages,) * expected_pages))
    if len(info_box_commits) != expected_pages:
        problems.append('%s committed %d complete empty Info boxes, expected %d' %
                        (label, len(info_box_commits), expected_pages))
    if len(pop_calls) != 1:
        problems.append('%s observed %d admitted Info pops, expected one' %
                        (label, len(pop_calls)))
    elif pop_calls[0][1] != 3:
        problems.append('%s Info pop began in transaction state %d, expected 3' %
                        (label, pop_calls[0][1]))
    if len(return_blank) != 1 or len(return_chrome) != 1:
        problems.append('%s return phases blank/chrome are %d/%d, expected 1/1' %
                        (label, len(return_blank), len(return_chrome)))
    if final_exact[0] is None:
        problems.append('%s never restored the exact originating page' % label)
    if post_accept[0] is None:
        problems.append('%s did not accept the post-return %s input' %
                        (label, post_button.title() if post_button else
                         ('Left' if floor else 'Down')))
    if lcd_off:
        problems.append('%s disabled the LCD at %s' %
                        (label, ' '.join('f%d' % at for at in lcd_off[:16])))
    if legacy_blankers:
        problems.append('%s reached the explicit Info LCD blanker at %s' %
                        (label, ' '.join('f%d' % at
                                         for at in legacy_blankers[:16])))
    if status_blankers:
        problems.append('%s reached the explicit Status LCD blanker at %s' %
                        (label, ' '.join('f%d' % at
                                         for at in status_blankers[:16])))
    if white:
        problems.append('%s produced all-white frame(s) at %s' %
                        (label, ' '.join('f%d' % at for at in white[:16])))
    if window_changes:
        problems.append('%s changed the hardware Window at %s' %
                        (label, ' '.join('f%d' % at for at in window_changes[:16])))
    if fusion_floor:
        if pot_view[0] not in (12, 13):
            problems.append('%s did not enter carried Fusion Pot See after Floor Info' %
                            label)
        if pot_exact[0] is None:
            problems.append('%s did not restore the exact five-row Items parent after '
                            'the chained Pot See' % label)
    if final['lcdc'] & 0x80 == 0:
        problems.append('%s ended with LCDC=$%02X' % (label, final['lcdc']))

    latency = (post_accept[0] - post_press[0]
               if post_accept[0] is not None and post_press[0] is not None else None)
    print('iteminfospill: %-13s pages %s; pop %s; return blank/chrome %d/%d; '
          'exact f%s; input +%s; Pot %s/f%s; LCD-off %d, white %d' %
          (label,
           ' '.join('f%d:%d/%d' % event[:3] for event in info_blank_commits),
           'f%d/$%04X' % (pop_calls[0][0], pop_calls[0][2]) if pop_calls else 'missing',
           len(return_blank), len(return_chrome), final_exact[0], latency,
           pot_view[0] if fusion_floor else '-',
           pot_exact[0] if fusion_floor else '-',
           len(lcd_off), len(white)))
    if problems:
        for attempt in info_attempts:
            print('iteminfospill: %s ownership attempt %r' % (label, attempt))
        for attempt in pop_attempts:
            print('iteminfospill: %s pop attempt %r' % (label, attempt))
        for attempt in return_attempts:
            print('iteminfospill: %s return attempt %r' % (label, attempt))
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rom')
    parser.add_argument('--held-ram', default=HELD_RAM)
    parser.add_argument('--held-page2-ram', default=HELD_PAGE2_RAM)
    parser.add_argument('--floor-ram', default=FLOOR_RAM)
    parser.add_argument('--real-sealed-ram', default=REAL_SEALED_RAM)
    parser.add_argument('--real-drop-ram', default=REAL_DROP_RAM)
    parser.add_argument('--fusion-state', default=FUSION_STATE)
    parser.add_argument('--png-dir')
    parser.add_argument('--frames', type=int, default=5200)
    args = parser.parse_args()
    for path in (args.held_ram, args.held_page2_ram, args.floor_ram,
                 args.real_sealed_ram, args.real_drop_ram):
        if not os.path.exists(path):
            raise SystemExit('iteminfospill: missing RAM fixture: ' + path)
    if args.png_dir:
        os.makedirs(args.png_dir, exist_ok=True)
    profile = menuspill.renderer_profile(args.rom)
    if profile['mode'] != 'dot-proportional':
        raise SystemExit('iteminfospill: requires the Dot proportional renderer')
    PyBoy = _import_pyboy()
    labels = runtime_labels()
    problems = []
    problems.extend(run_case(PyBoy, args.rom, profile, labels, 'held-b',
                             args.held_ram, False, args.png_dir, args.frames))
    problems.extend(run_case(PyBoy, args.rom, profile, labels, 'held-page2-b',
                             args.held_page2_ram, False, args.png_dir, args.frames,
                             held_selector=6, action_rows=5))
    problems.extend(run_case(PyBoy, args.rom, profile, labels, 'held-page4-pot-b',
                             args.held_page2_ram, False, args.png_dir, args.frames,
                             held_selector=15, action_rows=6))
    # Joey's reported screen-5 return: the fifth carried row is a fused Manji Kabura
    # with one seal. Enter its four-row Action picker, open seals, and back out with B.
    problems.extend(run_case(PyBoy, args.rom, profile, labels, 'held-seal-b',
                             args.floor_ram, False, args.png_dir, args.frames,
                             held_selector=4, action_rows=4, fusion_inventory=True,
                             post_button='up', post_selector=3))
    problems.extend(run_case(PyBoy, args.rom, profile, labels, 'held-seal-final-a',
                             args.floor_ram, False, args.png_dir, args.frames,
                             held_selector=4, action_rows=4, fusion_inventory=True,
                             post_button='up', post_selector=3, final_button='a'))
    problems.extend(run_case(PyBoy, args.rom, profile, labels, 'floor-final-a',
                             args.floor_ram, True, args.png_dir, args.frames))
    problems.extend(run_case(PyBoy, args.rom, profile, labels, 'floor-seal-final-a',
                             args.floor_ram, True, args.png_dir, args.frames,
                             action_rows=None, sealed_floor=True, info_pages=1))
    problems.extend(run_case(PyBoy, args.rom, profile, labels, 'floor-fusion-final-a',
                             args.floor_ram, True, args.png_dir, args.frames,
                             action_rows=6, fusion_floor=True))
    problems.extend(run_real_sealed_short_page(
        PyBoy, args.rom, profile, labels, args.real_sealed_ram,
        frames=max(3900, args.frames)))
    problems.extend(run_real_dropped_sealed_return(
        PyBoy, args.rom, profile, labels, args.real_drop_ram, True,
        frames=max(6200, args.frames)))
    problems.extend(run_real_dropped_sealed_return(
        PyBoy, args.rom, profile, labels, args.real_drop_ram, False,
        frames=max(6500, args.frames)))
    if os.path.exists(args.fusion_state):
        problems.extend(run_fusion_pager_case(
            PyBoy, args.rom, profile, labels, args.fusion_state,
            frames=max(1400, args.frames // 3)))
    else:
        print('iteminfospill: Fusion Pot five-page pager skipped; missing state: ' +
              args.fusion_state)
    for problem in problems:
        print('  ' + problem)
    if problems:
        raise SystemExit('iteminfospill: %d problem(s)' % len(problems))
    print('iteminfospill: exact screen-1 Item/Floor Info entry, paging, return, and '
          'post-return input stay regional and LCD-on')


if __name__ == '__main__':
    main()
